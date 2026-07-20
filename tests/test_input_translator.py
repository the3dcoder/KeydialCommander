from huion_keydial_mini.input_translator import InputTranslator
from huion_keydial_mini.input_events import EventType
from huion_keydial_mini.keybind_manager import KeybindAction, EventType as BindType


class FakeManager:
    """Minimal keybind manager: only these action_ids are sticky."""
    def __init__(self, sticky_ids=()):
        self.sticky_ids = set(sticky_ids)

    def get_action(self, action_id):
        if action_id in self.sticky_ids:
            return KeybindAction(type=BindType.KEYBOARD, keys=["KEY_LEFTCTRL"], sticky=True)
        return None


def ids(events):
    return [(e.event_type, e.key_code) for e in events]


def test_single_button_fires_on_release():
    t = InputTranslator(FakeManager())
    assert t.feed_button("BUTTON_1", True) == []            # nothing on press
    ev = t.feed_button("BUTTON_1", False)
    assert ids(ev) == [(EventType.KEY_PRESS, "BUTTON_1"),
                       (EventType.KEY_RELEASE, "BUTTON_1")]


def test_two_button_combo_via_peak_set():
    t = InputTranslator(FakeManager())
    t.feed_button("BUTTON_1", True)
    t.feed_button("BUTTON_2", True)                          # peak = {1,2}
    ev = t.feed_button("BUTTON_2", False)                    # first release fires combo
    assert ids(ev) == [(EventType.KEY_PRESS, "BUTTON_1+BUTTON_2"),
                       (EventType.KEY_RELEASE, "BUTTON_1+BUTTON_2")]
    # releasing the second button produces nothing new (already triggered)
    assert t.feed_button("BUTTON_1", False) == []
    assert t.current_buttons == set()


def test_three_button_combo_sorted():
    t = InputTranslator(FakeManager())
    t.feed_button("BUTTON_3", True)
    t.feed_button("BUTTON_1", True)
    t.feed_button("BUTTON_2", True)
    ev = t.feed_button("BUTTON_2", False)
    assert ids(ev)[0] == (EventType.KEY_PRESS, "BUTTON_1+BUTTON_2+BUTTON_3")


def test_sticky_press_and_hold():
    t = InputTranslator(FakeManager(sticky_ids={"BUTTON_13"}))
    ev_down = t.feed_button("BUTTON_13", True)
    assert ids(ev_down) == [(EventType.KEY_PRESS, "BUTTON_13")]     # press on down
    ev_up = t.feed_button("BUTTON_13", False)
    assert ids(ev_up) == [(EventType.KEY_RELEASE, "BUTTON_13")]     # release on up


def test_dial_rotation_pulse():
    t = InputTranslator(FakeManager())
    assert ids(t.feed_dial("DIAL_CW")) == [(EventType.KEY_PRESS, "DIAL_CW"),
                                           (EventType.KEY_RELEASE, "DIAL_CW")]


def test_dial_click_direct():
    t = InputTranslator(FakeManager())
    assert ids(t.feed_dial_click(True)) == [(EventType.KEY_PRESS, "DIAL_CLICK")]
    assert ids(t.feed_dial_click(False)) == [(EventType.KEY_RELEASE, "DIAL_CLICK")]


def test_reset_clears_state():
    t = InputTranslator(FakeManager())
    t.feed_button("BUTTON_1", True)
    t.reset()
    assert t.current_buttons == set()
    assert t.peak_buttons == set()
    assert t.active_sticky_actions == {}
