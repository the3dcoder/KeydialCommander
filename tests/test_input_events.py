from huion_keydial_mini.input_events import InputEvent, EventType


def test_types_importable_and_basic():
    ev = InputEvent(EventType.KEY_PRESS, "BUTTON_1")
    assert ev.key_code == "BUTTON_1"
    assert ev.event_type == EventType.KEY_PRESS


def test_uinput_handler_reexports_same_types():
    import huion_keydial_mini.uinput_handler as u
    assert u.EventType is EventType
    assert u.InputEvent is InputEvent
