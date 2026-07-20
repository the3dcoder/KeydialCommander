import pytest
from huion_keydial_mini.keybind_manager import KeybindAction, EventType
from huion_keydial_mini.validation import validate_action, ValidationError


def test_keystroke_roundtrip():
    a = KeybindAction.from_dict({"type": "keystroke", "keys": ["KEY_LEFTCTRL", "KEY_C"]})
    assert a.type == "keystroke" and a.keys == ["KEY_LEFTCTRL", "KEY_C"]
    assert a.to_dict()["type"] == "keystroke"


def test_legacy_keyboard_alias():
    assert KeybindAction.from_dict({"type": "keyboard", "keys": ["KEY_A"]}).type == "keystroke"


def test_enum_type_still_accepted():
    # Old construction style (enum) normalizes to the string value.
    a = KeybindAction(type=EventType.KEYBOARD, keys=["KEY_A"])
    assert a.type == "keystroke"


def test_macro_roundtrip():
    a = KeybindAction.from_dict({"type": "macro", "steps": [
        {"keys": ["KEY_LEFTCTRL", "KEY_S"]}, {"delay_ms": 100}, {"keys": ["KEY_ENTER"]}]})
    assert a.type == "macro" and len(a.steps) == 3
    assert a.to_dict()["steps"] == a.steps


def test_command_and_profile_switch_roundtrip():
    c = KeybindAction.from_dict({"type": "command", "argv": ["xdg-open", "https://x"]})
    assert c.type == "command" and c.argv == ["xdg-open", "https://x"]
    p = KeybindAction.from_dict({"type": "profile_switch", "profile": "next"})
    assert p.type == "profile_switch" and p.profile == "next"


def test_validate_action_ok():
    validate_action({"type": "keystroke", "keys": ["KEY_A"]})
    validate_action({"type": "command", "argv": ["xdg-open", "https://x"]})
    validate_action({"type": "profile_switch", "profile": "next"})
    validate_action({"type": "macro", "steps": [{"keys": ["KEY_A"]}, {"delay_ms": 50}]})


@pytest.mark.parametrize("bad", [
    {"type": "keystroke", "keys": ["KEY_BOGUS"]},
    {"type": "keystroke", "keys": []},
    {"type": "command", "argv": []},
    {"type": "command"},
    {"type": "profile_switch", "profile": ""},
    {"type": "macro", "steps": [{"delay_ms": 99999}]},          # > 10s
    {"type": "macro", "steps": [{"keys": ["KEY_A"]}] * 40},      # > 32 steps
    {"type": "macro", "steps": [{"keys": ["KEY_BOGUS"]}]},       # bad key
    {"type": "nope"},
])
def test_validate_action_rejects(bad):
    with pytest.raises(ValidationError):
        validate_action(bad)
