import pytest
from huion_keydial_mini.validation import (
    ValidationError, normalize_action_id, validate_keys, validate_mac,
    VALID_BUTTONS, VALID_DIAL_ACTIONS,
)


def test_sets():
    assert "BUTTON_1" in VALID_BUTTONS and "BUTTON_18" in VALID_BUTTONS
    assert "BUTTON_19" not in VALID_BUTTONS
    assert VALID_DIAL_ACTIONS == frozenset({"DIAL_CW", "DIAL_CCW", "DIAL_CLICK"})


@pytest.mark.parametrize("raw,expected", [
    ("BUTTON_1", "BUTTON_1"),
    ("DIAL_CW", "DIAL_CW"),
    ("BUTTON_2+BUTTON_1", "BUTTON_1+BUTTON_2"),          # sorted
    (" BUTTON_3 + BUTTON_2 ", "BUTTON_2+BUTTON_3"),      # stripped
])
def test_normalize_ok(raw, expected):
    assert normalize_action_id(raw) == expected


@pytest.mark.parametrize("bad", [
    "", "bogus", "BUTTON_19", "BUTTON_1+BUTTON_1",       # dup
    "BUTTON_1+DIAL_CW",                                   # dial can't chord
    "BUTTON_1+", "+",
])
def test_normalize_rejects(bad):
    with pytest.raises(ValidationError):
        normalize_action_id(bad)


def test_validate_keys():
    assert validate_keys([" KEY_F1", "KEY_LEFTCTRL "]) == ["KEY_F1", "KEY_LEFTCTRL"]
    with pytest.raises(ValidationError):
        validate_keys(["KEY_BOGUS"])
    with pytest.raises(ValidationError):
        validate_keys([])


def test_validate_mac():
    assert validate_mac("20:23:06:01:8a:b0") == "20:23:06:01:8A:B0"
    for bad in ["not-a-mac-addr-17", "20:23:06:01:8a", "GG:23:06:01:8A:B0"]:
        with pytest.raises(ValidationError):
            validate_mac(bad)
