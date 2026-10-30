import asyncio
from types import SimpleNamespace

from evdev import ecodes

from huion_keydial_mini.evdev_source import EvdevSource
from huion_keydial_mini.input_translator import InputTranslator


def event(kind, code, value=0):
    return SimpleNamespace(type=kind, code=code, value=value)


def key(code, value):
    return event(ecodes.EV_KEY, code, value)


REPORT = event(ecodes.EV_SYN, ecodes.SYN_REPORT)
DROPPED = event(ecodes.EV_SYN, ecodes.SYN_DROPPED)


class Node:
    def __init__(self, path, keyboard=False):
        self.path, self.name = path, 'Fake K20'
        self.keyboard = keyboard
        self.down = set()
        self.queue = asyncio.Queue()
        self.closed = False
        self.queries = 0
        self.grab_error = False
        self.query_error = False

    def capabilities(self):
        return ({ecodes.EV_KEY: [ecodes.KEY_K, ecodes.KEY_G, ecodes.KEY_LEFTCTRL,
                                ecodes.KEY_PLAYPAUSE]} if self.keyboard else
                {ecodes.EV_REL: [ecodes.REL_WHEEL]})

    def grab(self):
        if self.grab_error:
            raise OSError('simulated grab failure')

    def ungrab(self):
        pass

    def close(self):
        self.closed = True

    def active_keys(self):
        self.queries += 1
        if self.query_error:
            raise OSError('simulated state query failure')
        return sorted(self.down)

    def read(self):
        try:
            batch = self.queue.get_nowait()
        except asyncio.QueueEmpty:
            raise BlockingIOError from None
        if isinstance(batch, Exception):
            raise batch
        return iter(batch)

    async def async_read(self):
        batch = await self.queue.get()
        if isinstance(batch, Exception):
            raise batch
        return iter(batch)

    async def async_read_loop(self):
        while True:
            for ev in await self.async_read():
                yield ev

    def push(self, *events):
        for ev in events:
            if ev.type == ecodes.EV_KEY and ev.value != 2:
                if ev.value:
                    self.down.add(ev.code)
                else:
                    self.down.discard(ev.code)
        self.queue.put_nowait(events)


async def tick():
    for _ in range(4):
        await asyncio.sleep(0)


def setup(monkeypatch, keyboard=None):
    keyboard = keyboard or Node('keyboard', True)
    nodes = {'keyboard': keyboard, 'wheel': Node('wheel')}
    wanted = set(nodes)
    monkeypatch.setattr('huion_keydial_mini.evdev_source.evdev.InputDevice', nodes.__getitem__)
    output, resets = [], []
    async def receive(ev):
        output.append(ev.key_code)
    source = EvdevSource(receive, InputTranslator(), discover=lambda: sorted(wanted))
    source.on_reset = resets.append
    return source, nodes, wanted, output, resets


def test_silent_neutral_nodes_are_ready_without_extra_gesture(monkeypatch):
    async def run():
        source, nodes, _, output, _ = setup(monkeypatch)
        await source.start()
        assert source.ready and source.state == 'ready'
        assert nodes['keyboard'].queries and output == []
        await source.stop()
    asyncio.run(run())


def test_held_startup_and_dial_click_release_only_rearm(monkeypatch):
    async def run():
        keyboard = Node('keyboard', True)
        keyboard.down = {ecodes.KEY_K, ecodes.KEY_PLAYPAUSE}
        source, nodes, _, output, _ = setup(monkeypatch, keyboard)
        await source.start()
        assert not source.ready and not source.preview_allowed
        keyboard.push(key(ecodes.KEY_K, 0), key(ecodes.KEY_PLAYPAUSE, 0), REPORT)
        await tick()
        assert source.ready and output == []
        keyboard.push(key(ecodes.KEY_K, 1), REPORT, key(ecodes.KEY_K, 0), REPORT)
        await tick()
        assert output == ['BUTTON_1', 'BUTTON_1']
        await source.stop()
    asyncio.run(run())


def test_partial_node_loss_and_complete_removal_have_distinct_preview_admission(monkeypatch):
    async def run():
        source, nodes, wanted, _, resets = setup(monkeypatch)
        await source.start()
        wanted.remove('keyboard')
        await source._sync_devices()
        assert not source.ready and not source.preview_allowed and resets
        wanted.clear()
        await source._sync_devices()
        assert source.preview_allowed and source.state == 'disconnected'
        await source.stop()
    asyncio.run(run())


def test_lost_frame_is_discarded_and_held_snapshot_requires_release(monkeypatch):
    async def run():
        source, nodes, _, output, resets = setup(monkeypatch)
        await source.start()
        keyboard = nodes['keyboard']
        queries = keyboard.queries
        keyboard.push(key(ecodes.KEY_K, 1), DROPPED, key(ecodes.KEY_G, 1), REPORT)
        await tick()
        assert output == [] and resets and keyboard.queries > queries
        assert not source.ready
        keyboard.push(key(ecodes.KEY_K, 0), key(ecodes.KEY_G, 0), REPORT)
        await tick()
        assert source.ready and output == []
        keyboard.push(key(ecodes.KEY_G, 1), REPORT, key(ecodes.KEY_G, 0), REPORT)
        await tick()
        assert output == ['BUTTON_2', 'BUTTON_2']
        await source.stop()
    asyncio.run(run())


def test_profile_reset_discards_buffered_gestures_and_trailing_pair(monkeypatch):
    async def run():
        source, nodes, _, output, _ = setup(monkeypatch)
        await source.start()
        keyboard = nodes['keyboard']
        keyboard.push(key(ecodes.KEY_K, 1), REPORT, key(ecodes.KEY_K, 0), REPORT)
        source.resynchronize('profile_changed')
        await tick()
        assert output == [] and source.ready
        async def receive(ev):
            output.append(ev.key_code)
            source.resynchronize('profile_changed')
        source.on_event = receive
        keyboard.push(key(ecodes.KEY_K, 1), REPORT, key(ecodes.KEY_K, 0), REPORT)
        await tick()
        assert output == ['BUTTON_1']
        await source.stop()
    asyncio.run(run())


def test_reader_failure_is_evicted_even_while_discovery_retains_path(monkeypatch):
    async def run():
        source, nodes, _, _, _ = setup(monkeypatch)
        await source.start()
        old = nodes['keyboard']
        old.queue.put_nowait(OSError('simulated reader failure'))
        await tick()
        assert old.closed and not source.ready
        replacement = Node('keyboard', True)
        nodes['keyboard'] = replacement
        await source._sync_devices()
        await tick()
        assert source.ready and not replacement.closed
        assert source._devices['keyboard'] is replacement
        await source.stop()
    asyncio.run(run())


def test_failed_grab_or_state_query_never_advertises_ready(monkeypatch):
    async def run():
        source, nodes, _, _, _ = setup(monkeypatch)
        nodes['keyboard'].grab_error = True
        await source.start()
        assert not source.ready and not source.preview_allowed
        assert nodes['keyboard'].closed
        nodes['keyboard'] = Node('keyboard', True)
        nodes['keyboard'].query_error = True
        await source._sync_devices()
        assert not source.ready
        nodes['keyboard'].query_error = False
        await source._sync_devices()
        assert source.ready
        await source.stop()
    asyncio.run(run())


def test_unexpected_reader_eof_invalidates_session(monkeypatch):
    async def run():
        source, nodes, _, _, resets = setup(monkeypatch)
        await source.start()
        before = len(resets)
        nodes['keyboard'].queue.put_nowait(())
        await tick()
        assert not source.ready and nodes['keyboard'].closed
        assert len(resets) > before
        await source.stop()
    asyncio.run(run())


def test_split_dropped_frame_discards_already_buffered_tail_before_rearming(monkeypatch):
    async def run():
        source, nodes, _, output, _ = setup(monkeypatch)
        await source.start()
        keyboard = nodes['keyboard']
        keyboard.push(DROPPED)
        await tick()
        assert source.state == 'recovering'
        keyboard.push(REPORT, key(ecodes.KEY_K, 1), REPORT, key(ecodes.KEY_K, 0), REPORT)
        await tick()
        assert output == [] and source.ready
        keyboard.push(key(ecodes.KEY_G, 1), REPORT, key(ecodes.KEY_G, 0), REPORT)
        await tick()
        assert output == ['BUTTON_2', 'BUTTON_2']
        await source.stop()
    asyncio.run(run())
