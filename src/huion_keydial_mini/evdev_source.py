"""evdev input source: discover, grab, and read the Keydial's kernel nodes.

Opens the K20's evdev event nodes (keyboard + mouse), EVIOCGRABs them so the
original fixed keystrokes are suppressed, converts events to action IDs via
input_map, runs them through the combo/sticky translator, and forwards the
resulting InputEvents to a callback. A periodic rescan handles hotplug
(device power-cycle / connect / disconnect) without extra dependencies.
"""
import asyncio
import logging
from typing import List

import evdev
from evdev import ecodes

from .input_events import InputEvent
from .input_map import action_for_key, dial_for_wheel, is_keydial, KEY_TO_ACTION
from .input_translator import InputTranslator

logger = logging.getLogger(__name__)


def default_discover(exclude_names=frozenset()) -> List[str]:
    """Return evdev paths for all connected Keydial nodes.

    `exclude_names` skips devices by exact name — used to avoid grabbing our own
    uinput OUTPUT device (whose name also contains "keydial").
    """
    paths = []
    for path in evdev.list_devices():
        try:
            d = evdev.InputDevice(path)
            name = d.name or ""
            info = d.info  # (bustype, vendor, product, version)
            if name not in exclude_names and is_keydial(name, info.vendor, info.product):
                paths.append(path)
            d.close()
        except Exception:
            continue
    return paths


class EvdevSource:
    """One conservative K20 capture session with explicit synchronization."""

    def __init__(self, on_event, translator, on_state=None, discover=None,
                 exclude_names=frozenset(), rescan_interval=2.0,
                 on_reset=None, on_readiness=None):
        self.on_event = on_event
        self.translator = translator
        self.on_state = on_state
        self.on_reset = on_reset
        self.on_readiness = on_readiness
        self.exclude_names = set(exclude_names)
        self.discover = discover or (lambda: default_discover(self.exclude_names))
        self.rescan_interval = rescan_interval
        self._devices = {}
        self._tasks = {}
        self._caps = {}
        self._raw_down = {}
        self._drop_until_report = set()
        self._query_failed = set()
        self._rescan_task = None
        self._connected = False
        self._running = False
        self._capture_failed = False
        self._suspended = None
        self._epoch = 0
        self._rearming = True
        self.ready = False
        self.state = 'disconnected'
        self.recovery_complete = lambda: True

    @property
    def preview_allowed(self):
        return self.ready or (not self._devices and not self._capture_failed
                              and self._suspended is None)

    async def start(self):
        self._running = True
        self._suspended = None
        await self._sync_devices()
        self._rescan_task = asyncio.create_task(self._rescan_loop())

    async def stop(self):
        self._running = False
        self.suspend('stopped')
        tasks = tuple(self._tasks.values())
        if self._rescan_task:
            self._rescan_task.cancel()
            tasks += (self._rescan_task,)
            self._rescan_task = None
        for path in list(self._devices):
            self._drop_device(path, reset=False)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._update_state()

    def _begin_reset(self, reason):
        self._epoch += 1
        self.ready = False
        self._rearming = True
        self.translator.reset()
        if self.on_reset:
            self.on_reset(reason)

    def suspend(self, reason):
        self._suspended = reason
        self._begin_reset(reason)
        self._update_state()

    def resynchronize(self, reason='input_changed'):
        self._begin_reset(reason)
        self._synchronize_nodes()

    def _drain_node(self, path, device):
        while True:
            try:
                batch = list(device.read())
            except BlockingIOError:
                return
            if not batch:
                return
            for event in batch:
                self._discard_event(path, event)

    def _discard_event(self, path, event):
        if event.type == ecodes.EV_SYN:
            if event.code == ecodes.SYN_DROPPED:
                self._drop_until_report.add(path)
            elif event.code == ecodes.SYN_REPORT:
                self._drop_until_report.discard(path)

    def _query_node(self, path, device):
        keys = self._caps[path].get(ecodes.EV_KEY, [])
        self._raw_down[path] = (set(device.active_keys()) & KEY_TO_ACTION.keys()
                                if keys else set())
        self._query_failed.discard(path)

    def _synchronize_nodes(self):
        for path, device in list(self._devices.items()):
            try:
                self._drain_node(path, device)
                if path not in self._drop_until_report:
                    self._query_node(path, device)
            except OSError:
                self._query_failed.add(path)
        self._update_state()

    def _update_state(self):
        connected = bool(self._devices)
        if self._suspended:
            state = self._suspended
        elif self._capture_failed or self._query_failed:
            state = 'capture_failed'
        elif not self.recovery_complete():
            state = 'recovering'
        elif not connected:
            state = 'disconnected'
        else:
            keys, relative = set(), set()
            for caps in self._caps.values():
                keys.update(caps.get(ecodes.EV_KEY, []))
                relative.update(caps.get(ecodes.EV_REL, []))
            if (not (keys & (KEY_TO_ACTION.keys() - {ecodes.KEY_PLAYPAUSE}))
                    or ecodes.KEY_PLAYPAUSE not in keys or ecodes.REL_WHEEL not in relative):
                state = 'missing_input'
            elif self._drop_until_report:
                state = 'recovering'
            elif self._rearming and any(self._raw_down.values()):
                state = 'release_controls'
            else:
                state = 'ready'
        changed = state != self.state or connected != self._connected
        self.state, self.ready = state, state == 'ready'
        if self.ready:
            self._rearming = False
        if connected != self._connected:
            self._connected = connected
            if self.on_state:
                self.on_state(connected)
        if changed and self.on_readiness:
            self.on_readiness()

    async def _rescan_loop(self):
        try:
            while self._running:
                await asyncio.sleep(self.rescan_interval)
                await self._sync_devices()
        except asyncio.CancelledError:
            pass

    async def _sync_devices(self):
        try:
            wanted = set(self.discover())
        except Exception as error:
            logger.warning('Device discovery failed: %s', error)
            self._capture_failed = True
            self.resynchronize('discovery_failed')
            return
        dead = {path for path, task in self._tasks.items() if task.done()}
        topology_changed = wanted != set(self._devices) or bool(dead)
        if topology_changed:
            self._begin_reset('input_changed')
        for path in (set(self._devices) - wanted) | dead:
            self._drop_device(path, reset=False)
        for path in wanted - set(self._devices):
            self._add_device(path)
        self._capture_failed = bool(wanted - set(self._devices))
        if topology_changed or self._query_failed:
            self._synchronize_nodes()
        else:
            self._update_state()

    def _add_device(self, path):
        device = None
        try:
            device = evdev.InputDevice(path)
            device.grab()
            caps = device.capabilities()
            self._devices[path] = device
            self._caps[path] = caps
            self._raw_down[path] = set()
            self._tasks[path] = asyncio.create_task(self._read_loop(device))
        except Exception as error:
            if device is not None:
                device.close()
            logger.warning('Could not capture %s: %s', path, error)

    def _drop_device(self, path, reset=True):
        if reset:
            self._begin_reset('input_lost')
        task = self._tasks.pop(path, None)
        if task and task is not asyncio.current_task():
            task.cancel()
        device = self._devices.pop(path, None)
        self._caps.pop(path, None)
        self._raw_down.pop(path, None)
        self._drop_until_report.discard(path)
        self._query_failed.discard(path)
        if device:
            try:
                device.ungrab()
            except OSError:
                pass
            device.close()
        if reset:
            self._synchronize_nodes()

    async def _read_loop(self, device):
        path = device.path
        try:
            while self._running and self._devices.get(path) is device:
                try:
                    # Own the batch explicitly so reset cannot admit its stale tail.
                    batch = list(await device.async_read())
                except BlockingIOError:
                    continue
                if not batch:
                    break
                epoch = self._epoch
                for event in batch:
                    if epoch != self._epoch:
                        self._discard_event(path, event)
                        continue
                    await self._handle_event(path, event)
                if epoch != self._epoch:
                    self._synchronize_nodes()
        except asyncio.CancelledError:
            pass
        except Exception as error:
            logger.warning('Input reader failed for %s: %s', path, error)
        finally:
            # A stale task must never remove a replacement at the same path.
            if self._running and self._devices.get(path) is device:
                self._drop_device(path)

    async def _handle_event(self, path, event):
        if event.type == ecodes.EV_SYN and event.code == ecodes.SYN_DROPPED:
            self._drop_until_report.add(path)
            self.resynchronize('input_lost')
            return
        if path in self._drop_until_report:
            self._discard_event(path, event)
            if path not in self._drop_until_report:
                # The report ends loss recovery, but this already-read batch
                # can still contain pre-snapshot gestures. Retire its tail.
                self._epoch += 1
                self._synchronize_nodes()
            return
        if event.type == ecodes.EV_KEY and event.code in KEY_TO_ACTION:
            if event.value == 1:
                self._raw_down[path].add(event.code)
            elif event.value == 0:
                self._raw_down[path].discard(event.code)
        if not self.ready:
            if event.type == ecodes.EV_SYN and event.code == ecodes.SYN_REPORT:
                self._update_state()
            return
        epoch = self._epoch
        for output in self._translate(event):
            if epoch != self._epoch or not self.ready:
                break
            await self.on_event(output)

    def _translate(self, ev) -> List[InputEvent]:
        if ev.type == ecodes.EV_KEY:
            if ev.value == 2:                       # key repeat -> ignore
                return []
            action = action_for_key(ev.code)
            if action is None:
                return []
            pressed = ev.value == 1
            if action == "DIAL_CLICK":
                return self.translator.feed_dial_click(pressed)
            return self.translator.feed_button(action, pressed)
        if ev.type == ecodes.EV_REL and ev.code == ecodes.REL_WHEEL:
            action = dial_for_wheel(ev.value)
            if action:
                return self.translator.feed_dial(action)
        return []
