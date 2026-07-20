"""keymap must be importable without touching /dev/uinput."""
from huion_keydial_mini.keymap import KEY_MAPPING, SUPPORTED_KEYS


def test_key_mapping_spot_checks():
    from evdev import ecodes
    assert KEY_MAPPING["KEY_F1"] == ecodes.KEY_F1
    assert KEY_MAPPING["BTN_LEFT"] == ecodes.BTN_LEFT
    assert KEY_MAPPING["KEY_LEFTCTRL"] == ecodes.KEY_LEFTCTRL
    assert len(KEY_MAPPING) >= 167  # README's documented "167+ keys"


def test_supported_keys_sorted_and_complete():
    assert SUPPORTED_KEYS == sorted(KEY_MAPPING.keys())


def test_uinput_handler_alias_still_exists():
    from huion_keydial_mini.uinput_handler import UInputHandler
    assert UInputHandler.KEY_MAPPING is KEY_MAPPING
