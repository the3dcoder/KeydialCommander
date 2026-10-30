"""Output invariants, with only the kernel output endpoint replaced."""
import asyncio

import pytest
from evdev import ecodes

from huion_keydial_mini.config import Config
from huion_keydial_mini.input_events import InputEvent, EventType
from huion_keydial_mini.keybind_manager import KeybindManager, KeybindAction
from huion_keydial_mini.uinput_handler import UInputHandler


class Output:
    def __init__(self, fail=None):
        self.down = set()
        self.writes = []
        self.closed = False
        self.fail = fail

    def write(self, kind, code, value):
        assert kind == ecodes.EV_KEY
        self.writes.append((code, value))
        if value:
            self.down.add(code)
        else:
            self.down.discard(code)
        if self.fail and self.fail(code, value):
            raise OSError('simulated output failure')

    def syn(self):
        pass

    def close(self):
        self.closed = True


def rig():
    config = Config({})
    manager = KeybindManager(config, socket_path='/tmp/unused-ownership-test.sock')
    writer = UInputHandler(config, manager)
    writer.device = Output()
    return manager, writer


@pytest.mark.parametrize('replacement', [None, KeybindAction(keys=['KEY_LEFTSHIFT']),
                                      KeybindAction(type='macro', steps=[])])
def test_release_uses_original_keys_after_binding_changes(replacement):
    manager, writer = rig()
    output = writer.device
    manager.keybind_map['BUTTON_13'] = KeybindAction(keys=['KEY_LEFTCTRL'])

    async def run():
        await writer.send_event(InputEvent(EventType.KEY_PRESS, 'BUTTON_13'))
        if replacement is None:
            manager.keybind_map.clear()
        else:
            manager.keybind_map['BUTTON_13'] = replacement
        await writer.send_event(InputEvent(EventType.KEY_RELEASE, 'BUTTON_13'))

    asyncio.run(run())
    assert output.down == set()
    assert output.writes == [(ecodes.KEY_LEFTCTRL, 1), (ecodes.KEY_LEFTCTRL, 0)]


def test_chord_tap_preserves_another_owners_modifier():
    manager, writer = rig()
    manager.keybind_map['BUTTON_13'] = KeybindAction(keys=['KEY_LEFTCTRL'])

    async def run():
        await writer.send_event(InputEvent(EventType.KEY_PRESS, 'BUTTON_13'))
        await writer.emit_keys(['KEY_LEFTCTRL', 'KEY_C'])
        assert writer.device.down == {ecodes.KEY_LEFTCTRL}
        await writer.send_event(InputEvent(EventType.KEY_RELEASE, 'BUTTON_13'))

    asyncio.run(run())
    assert writer.device.writes == [(ecodes.KEY_LEFTCTRL, 1), (ecodes.KEY_C, 1),
                                    (ecodes.KEY_C, 0), (ecodes.KEY_LEFTCTRL, 0)]


def test_shared_owners_and_duplicate_codes_release_only_on_last_owner():
    _, writer = rig()
    writer.acquire('one', ['KEY_LEFTCTRL', 'KEY_LEFTCTRL'])
    writer.acquire('two', ['KEY_LEFTCTRL'])
    writer.release('one')
    assert writer.device.down == {ecodes.KEY_LEFTCTRL}
    writer.release('one')
    writer.release('two')
    writer.release_all()
    assert writer.device.writes == [(ecodes.KEY_LEFTCTRL, 1), (ecodes.KEY_LEFTCTRL, 0)]


def test_partial_acquisition_fault_releases_possibly_pressed_keys_and_closes():
    _, writer = rig()
    output = Output(fail=lambda code, value: code == ecodes.KEY_C and value == 1)
    writer.device = output
    faults = []
    writer.on_fault = faults.append
    with pytest.raises(RuntimeError):
        writer.acquire('tap', ['KEY_LEFTCTRL', 'KEY_C'])
    assert output.down == set()
    assert output.closed and writer.failed
    assert len(faults) == 1
    before = list(output.writes)
    with pytest.raises(RuntimeError):
        writer.acquire('later', ['KEY_A'])
    assert output.writes == before


def test_release_failure_is_uncertain_and_cleanup_is_idempotent():
    _, writer = rig()
    output = Output(fail=lambda code, value: value == 0)
    writer.device = output
    writer.acquire('held', ['KEY_LEFTCTRL'])
    with pytest.raises(RuntimeError):
        writer.release('held')
    assert writer.failed and not writer.cleanup_confirmed
    assert output.closed
    writer.release_all()
    writer.close()


def test_close_releases_owned_keys_before_closing_endpoint():
    _, writer = rig()
    output = writer.device
    writer.acquire('held', ['KEY_LEFTCTRL'])
    writer.close()
    writer.close()
    assert output.down == set() and output.closed
