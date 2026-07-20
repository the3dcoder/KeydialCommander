import asyncio
import os
from collections import namedtuple

import pytest
from evdev import ecodes

from huion_keydial_mini.evdev_source import EvdevSource
from huion_keydial_mini.input_translator import InputTranslator
from huion_keydial_mini.input_events import EventType

FakeEv = namedtuple("FakeEv", "type code value")


class FakeMgr:
    def get_action(self, action_id):
        return None


def make_source(collected):
    async def on_event(ev):
        collected.append((ev.event_type, ev.key_code))
    return EvdevSource(on_event=on_event, translator=InputTranslator(FakeMgr()),
                       discover=lambda: [])


def test_translate_button_key():
    src = make_source([])
    # key down for KEY_K (BUTTON_1): translator emits nothing until release
    assert src._translate(FakeEv(ecodes.EV_KEY, ecodes.KEY_K, 1)) == []
    ev = src._translate(FakeEv(ecodes.EV_KEY, ecodes.KEY_K, 0))
    assert [(e.event_type, e.key_code) for e in ev] == [
        (EventType.KEY_PRESS, "BUTTON_1"), (EventType.KEY_RELEASE, "BUTTON_1")]


def test_translate_dial_wheel():
    src = make_source([])
    ev = src._translate(FakeEv(ecodes.EV_REL, ecodes.REL_WHEEL, -1))
    assert [(e.event_type, e.key_code) for e in ev] == [
        (EventType.KEY_PRESS, "DIAL_CW"), (EventType.KEY_RELEASE, "DIAL_CW")]


def test_translate_dial_click():
    src = make_source([])
    down = src._translate(FakeEv(ecodes.EV_KEY, ecodes.KEY_PLAYPAUSE, 1))
    assert [(e.event_type, e.key_code) for e in down] == [(EventType.KEY_PRESS, "DIAL_CLICK")]


def test_translate_ignores_repeat_and_unmapped():
    src = make_source([])
    assert src._translate(FakeEv(ecodes.EV_KEY, ecodes.KEY_K, 2)) == []      # repeat
    assert src._translate(FakeEv(ecodes.EV_KEY, ecodes.KEY_A, 1)) == []      # unmapped
    assert src._translate(FakeEv(ecodes.EV_REL, ecodes.REL_X, 5)) == []      # not wheel


@pytest.mark.skipif(not os.access("/dev/uinput", os.W_OK),
                    reason="needs writable /dev/uinput")
def test_end_to_end_grab_and_read():
    """Create a synthetic Keydial-named uinput device, write KEY_K, and assert
    EvdevSource grabs it and yields BUTTON_1 through the real read loop."""
    from evdev import UInput

    caps = {ecodes.EV_KEY: [ecodes.KEY_K]}
    ui = UInput(caps, name="Keydial mini-504 Test Synthetic")

    async def run():
        collected = []

        async def on_event(ev):
            collected.append((ev.event_type, ev.key_code))

        src = EvdevSource(on_event=on_event, translator=InputTranslator(FakeMgr()),
                          rescan_interval=0.2)
        await src.start()
        await asyncio.sleep(0.3)                # let grab + reader attach
        ui.write(ecodes.EV_KEY, ecodes.KEY_K, 1); ui.syn()
        ui.write(ecodes.EV_KEY, ecodes.KEY_K, 0); ui.syn()
        await asyncio.sleep(0.4)
        await src.stop()
        return collected

    try:
        collected = asyncio.run(run())
    finally:
        ui.close()

    assert (EventType.KEY_PRESS, "BUTTON_1") in collected
    assert (EventType.KEY_RELEASE, "BUTTON_1") in collected


def test_default_discover_excludes_uinput_output_name():
    # The uinput output device name contains "keydial" and must be excluded.
    import huion_keydial_mini.evdev_source as es

    class FakeInfo:
        vendor = 0
        product = 0

    class FakeDev:
        def __init__(self, name):
            self.name = name
            self.info = FakeInfo()
        def close(self):
            pass

    devs = {"/dev/input/event0": FakeDev("keydial-commander-uinput"),
            "/dev/input/event1": FakeDev("Keydial mini-504 Keyboard")}
    import unittest.mock as m
    with m.patch.object(es.evdev, "list_devices", return_value=list(devs)), \
         m.patch.object(es.evdev, "InputDevice", side_effect=lambda p: devs[p]):
        # real Keydial matches by name; but both contain "keydial", so only the
        # exclusion keeps us from grabbing our own output.
        found = es.default_discover(exclude_names={"keydial-commander-uinput"})
    assert found == ["/dev/input/event1"]
