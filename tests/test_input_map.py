from evdev import ecodes
from huion_keydial_mini.input_map import (
    action_for_key, dial_for_wheel, is_keydial, KEY_TO_ACTION,
)


def test_button_keys():
    assert action_for_key(ecodes.KEY_K) == "BUTTON_1"
    assert action_for_key(ecodes.KEY_G) == "BUTTON_2"
    assert action_for_key(ecodes.KEY_DELETE) == "BUTTON_4"
    assert action_for_key(ecodes.KEY_LEFTCTRL) == "BUTTON_13"
    assert action_for_key(ecodes.KEY_LEFTSHIFT) == "BUTTON_15"
    assert action_for_key(ecodes.KEY_N) == "BUTTON_18"
    assert action_for_key(ecodes.KEY_PLAYPAUSE) == "DIAL_CLICK"
    assert action_for_key(ecodes.KEY_A) is None


def test_all_18_buttons_plus_click_present():
    buttons = {v for v in KEY_TO_ACTION.values() if v.startswith("BUTTON_")}
    assert buttons == {"BUTTON_%d" % i for i in range(1, 19)}
    assert "DIAL_CLICK" in KEY_TO_ACTION.values()


def test_dial_wheel():
    assert dial_for_wheel(-1) == "DIAL_CW"
    assert dial_for_wheel(1) == "DIAL_CCW"
    assert dial_for_wheel(-3) == "DIAL_CW"
    assert dial_for_wheel(0) is None


def test_is_keydial():
    assert is_keydial("Keydial mini-504 Keyboard", 0, 0)
    assert is_keydial("keydial mini-504 mouse", 0, 0)
    assert is_keydial("whatever", 0x256C, 0x8251)
    assert not is_keydial("Some Keyboard", 0x1234, 0x5678)
    assert not is_keydial("", 0x256C, 0x0000)
