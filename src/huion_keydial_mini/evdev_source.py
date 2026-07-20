"""evdev input source: discover, grab, and read the Keydial's kernel nodes.

Opens the K20's evdev event nodes (keyboard + mouse), EVIOCGRABs them so the
original fixed keystrokes are suppressed, converts events to action IDs via
input_map, runs them through the combo/sticky translator, and forwards the
resulting InputEvents to a callback. A periodic rescan handles hotplug
(device power-cycle / connect / disconnect) without extra dependencies.
"""
import asyncio
import logging
from typing import Awaitable, Callable, Dict, List, Optional

import evdev
from evdev import ecodes

from .input_events import InputEvent
from .input_map import action_for_key, dial_for_wheel, is_keydial
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
    def __init__(self,
                 on_event: Callable[[InputEvent], Awaitable],
                 translator: InputTranslator,
                 on_state: Optional[Callable[[bool], None]] = None,
                 discover: Optional[Callable[[], List[str]]] = None,
                 exclude_names=frozenset(),
                 rescan_interval: float = 2.0):
        self.on_event = on_event
        self.translator = translator
        self.on_state = on_state
        self.exclude_names = set(exclude_names)
        # Default discovery excludes our own uinput output device by name
        self.discover = discover or (lambda: default_discover(self.exclude_names))
        self.rescan_interval = rescan_interval
        self._devices: Dict[str, evdev.InputDevice] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._rescan_task: Optional[asyncio.Task] = None
        self._connected = False
        self._running = False

    # -- lifecycle ----------------------------------------------------------
    async def start(self) -> None:
        self._running = True
        await self._sync_devices()
        self._rescan_task = asyncio.ensure_future(self._rescan_loop())
        logger.info("evdev source started (%d device node(s))", len(self._devices))

    async def stop(self) -> None:
        self._running = False
        if self._rescan_task:
            self._rescan_task.cancel()
            try:
                await self._rescan_task
            except asyncio.CancelledError:
                pass
            self._rescan_task = None
        for path in list(self._devices):
            self._drop_device(path)
        self.translator.reset()

    # -- discovery / hotplug ------------------------------------------------
    async def _rescan_loop(self) -> None:
        try:
            while self._running:
                await asyncio.sleep(self.rescan_interval)
                await self._sync_devices()
        except asyncio.CancelledError:
            pass

    async def _sync_devices(self) -> None:
        try:
            wanted = set(self.discover())
        except Exception as e:
            logger.warning("Device discovery failed: %s", e)
            return
        for path in wanted - set(self._devices):
            self._add_device(path)
        for path in set(self._devices) - wanted:
            self._drop_device(path)
        self._update_state()

    def _add_device(self, path: str) -> None:
        try:
            dev = evdev.InputDevice(path)
            dev.grab()
            self._devices[path] = dev
            self._tasks[path] = asyncio.ensure_future(self._read_loop(dev))
            logger.info("Grabbed %s (%s)", path, dev.name)
        except Exception as e:
            logger.warning("Could not grab %s: %s", path, e)

    def _drop_device(self, path: str) -> None:
        task = self._tasks.pop(path, None)
        if task:
            task.cancel()
        dev = self._devices.pop(path, None)
        if dev:
            try:
                dev.ungrab()
            except Exception:
                pass
            try:
                dev.close()
            except Exception:
                pass
            logger.info("Released %s", path)

    def _update_state(self) -> None:
        now = bool(self._devices)
        if now != self._connected:
            self._connected = now
            if self.on_state:
                self.on_state(now)

    # -- read loop ----------------------------------------------------------
    async def _read_loop(self, dev: evdev.InputDevice) -> None:
        try:
            async for ev in dev.async_read_loop():
                for out in self._translate(ev):
                    await self.on_event(out)
        except asyncio.CancelledError:
            pass
        except OSError:
            # device went away between rescans; let the next rescan clean up
            logger.debug("Read loop ended for %s", dev.path)

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
