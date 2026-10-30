import asyncio

import pytest
from evdev import ecodes

from huion_keydial_mini.config import Config
from huion_keydial_mini.device import HuionKeydialMini
from huion_keydial_mini.keybind_manager import KeybindAction
from huion_keydial_mini.profile_store import ProfileStore
from tests.test_input_recovery import Node, key, REPORT, tick
from tests.test_output_ownership import Output


def driver(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmp_path / 'runtime'))
    store = ProfileStore(tmp_path / 'profiles')
    store.ensure_initialized()
    store.save_binding('BUTTON_13', KeybindAction(keys=['KEY_LEFTCTRL'], sticky=True))
    store.save_binding('BUTTON_1', KeybindAction(type='macro', steps=[
        {'delay_ms': 5000}, {'keys': ['KEY_B']}]))
    monkeypatch.setattr('huion_keydial_mini.device.ProfileStore', lambda: store)
    dev = HuionKeydialMini(Config({}))
    output = Output()
    dev.uinput_handler.device = output
    nodes = {'keyboard': Node('keyboard', True), 'wheel': Node('wheel')}
    monkeypatch.setattr('huion_keydial_mini.evdev_source.evdev.InputDevice', nodes.__getitem__)
    wanted = set(nodes)
    dev.evdev_source.discover = lambda: sorted(wanted)
    return dev, nodes, wanted, output


def test_active_profile_edit_releases_original_hold_and_waits_for_neutral(tmp_path, monkeypatch):
    async def run():
        dev, nodes, _, output = driver(tmp_path, monkeypatch)
        await dev.evdev_source.start()
        keyboard = nodes['keyboard']
        keyboard.push(key(ecodes.KEY_LEFTCTRL, 1), REPORT)
        await tick()
        assert output.down == {ecodes.KEY_LEFTCTRL}
        dev.profile_store.save_binding('BUTTON_13', KeybindAction(keys=['KEY_LEFTSHIFT'], sticky=True))
        dev.keybind_manager.reload_bindings()
        assert output.down == set() and not dev.evdev_source.ready
        keyboard.push(key(ecodes.KEY_LEFTCTRL, 0), REPORT)
        await tick()
        assert output.down == set() and dev.evdev_source.ready
        keyboard.push(key(ecodes.KEY_LEFTCTRL, 1), REPORT)
        await tick()
        assert output.down == {ecodes.KEY_LEFTSHIFT}
        await dev.stop()
    asyncio.run(run())


def test_macro_cancelled_on_partial_disconnect_and_preview_recovers_after_full_removal(tmp_path, monkeypatch):
    async def run():
        dev, nodes, wanted, output = driver(tmp_path, monkeypatch)
        entered = asyncio.Event()
        async def sleep(_):
            entered.set()
            await asyncio.Event().wait()
        dev.action_engine._sleep = sleep
        await dev.evdev_source.start()
        nodes['keyboard'].push(key(ecodes.KEY_K, 1), REPORT, key(ecodes.KEY_K, 0), REPORT)
        await entered.wait()
        wanted.remove('keyboard')
        await dev.evdev_source._sync_devices()
        await dev.action_engine.drain()
        with pytest.raises(RuntimeError, match='unavailable'):
            await dev.action_engine.fire(KeybindAction(keys=['KEY_A']))
        wanted.clear()
        await dev.evdev_source._sync_devices()
        await dev.action_engine.fire(KeybindAction(keys=['KEY_A']))
        assert output.writes == [(ecodes.KEY_A, 1), (ecodes.KEY_A, 0)]
        await dev.stop()
    asyncio.run(run())


def test_output_fault_suspends_input_and_does_not_publish_successful_key_event(tmp_path, monkeypatch):
    async def run():
        dev, nodes, _, _ = driver(tmp_path, monkeypatch)
        dev.uinput_handler.device = Output(fail=lambda code, value: value == 1)
        published = []
        dev.event_bus.publish = published.append
        await dev.evdev_source.start()
        nodes['keyboard'].push(key(ecodes.KEY_LEFTCTRL, 1), REPORT)
        await tick()
        assert not dev.evdev_source.ready
        assert dev.evdev_source.state == 'output_unavailable'
        assert not any(item['type'] == 'key_event' for item in published)
        await dev.stop()
    asyncio.run(run())


def test_shutdown_releases_before_slow_http_cleanup(tmp_path, monkeypatch):
    async def run():
        dev, nodes, _, output = driver(tmp_path, monkeypatch)
        await dev.evdev_source.start()
        nodes['keyboard'].push(key(ecodes.KEY_LEFTCTRL, 1), REPORT)
        await tick()
        entered, resume = asyncio.Event(), asyncio.Event()
        async def slow_stop():
            entered.set()
            assert output.down == set()
            await resume.wait()
        dev.api_server.stop = slow_stop
        stop = asyncio.create_task(dev.stop())
        await entered.wait()
        resume.set()
        await stop
        assert output.closed
    asyncio.run(run())


def test_routine_scan_and_preview_completion_do_not_quarantine_healthy_hold(tmp_path, monkeypatch):
    async def run():
        dev, nodes, _, output = driver(tmp_path, monkeypatch)
        await dev.evdev_source.start()
        nodes['keyboard'].push(key(ecodes.KEY_LEFTCTRL, 1), REPORT)
        await tick()
        await dev.evdev_source._sync_devices()
        assert dev.evdev_source.ready
        await dev.action_engine.fire(KeybindAction(keys=['KEY_A']))
        await tick()
        assert dev.evdev_source.ready and output.down == {ecodes.KEY_LEFTCTRL}
        nodes['keyboard'].push(key(ecodes.KEY_LEFTCTRL, 0), REPORT)
        await tick()
        assert output.down == set()
        await dev.stop()
    asyncio.run(run())
