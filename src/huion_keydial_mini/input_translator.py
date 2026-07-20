"""Combo + sticky state machine for the evdev device layer.

Ports the peak-button-set combo detection and sticky press-and-hold logic
from the retired HID parser, but driven by discrete button/dial events from
the grabbed evdev stream instead of raw HID frames.

- BUTTON_* events go through `feed_button` (combo + sticky).
- DIAL_CW / DIAL_CCW go through `feed_dial` (one press+release pulse each).
- DIAL_CLICK goes through `feed_dial_click` (direct press/release, no combo).
"""
import logging
from typing import List, Optional

from .input_events import InputEvent, EventType

logger = logging.getLogger(__name__)


class InputTranslator:
    def __init__(self, keybind_manager=None):
        self.keybind_manager = keybind_manager
        self.current_buttons = set()          # buttons currently held
        self.peak_buttons = set()             # peak set this press session
        self.key_event_triggered = False      # one action per session
        self.active_sticky_buttons = set()
        self.active_sticky_actions = {}       # action_id -> button set

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _combo_id(buttons) -> str:
        if not buttons:
            return ""
        return "+".join(sorted(buttons))

    def _is_sticky(self, action_id: str) -> bool:
        if not self.keybind_manager:
            return False
        action = self.keybind_manager.get_action(action_id)
        return bool(action and getattr(action, "sticky", False))

    # -- buttons ------------------------------------------------------------
    def feed_button(self, action_id: str, pressed: bool) -> List[InputEvent]:
        events: List[InputEvent] = []
        current = self.current_buttons

        if pressed:
            if action_id in current:
                return events                 # already down (repeat guard)
            current.add(action_id)
            pressed_set = {action_id}
            released_set = set()
        else:
            if action_id not in current:
                return events
            current.discard(action_id)
            pressed_set = set()
            released_set = {action_id}

        # Press: reset trigger + grow the peak set
        if pressed_set:
            self.key_event_triggered = False
            if current != self.peak_buttons:
                self.peak_buttons = set(current)

        # Release: fire sticky releases, else the peak-set action
        if released_set and not self.key_event_triggered:
            sticky_released = False
            for aid, abtns in list(self.active_sticky_actions.items()):
                if released_set & abtns:
                    events.append(InputEvent(EventType.KEY_RELEASE, aid))
                    logger.debug("Sticky action released: %s", aid)
                    remaining = abtns - released_set
                    if remaining:
                        self.active_sticky_actions[aid] = remaining
                        for b in released_set:
                            self.active_sticky_buttons.discard(b)
                    else:
                        del self.active_sticky_actions[aid]
                        for b in abtns:
                            self.active_sticky_buttons.discard(b)
                    sticky_released = True
                    self.key_event_triggered = True

            if not sticky_released:
                aid = self._combo_id(self.peak_buttons)
                if aid and not self._is_sticky(aid):
                    if not self.active_sticky_buttons:
                        events.append(InputEvent(EventType.KEY_PRESS, aid))
                        events.append(InputEvent(EventType.KEY_RELEASE, aid))
                        logger.debug("Action triggered: %s", aid)
                        self.key_event_triggered = True
                    else:
                        logger.debug("Blocking %s due to active sticky bindings", aid)

        # Press: activate a sticky action for the current set
        if pressed_set:
            cur_aid = self._combo_id(current)
            if cur_aid and self._is_sticky(cur_aid) and not self.active_sticky_actions:
                events.append(InputEvent(EventType.KEY_PRESS, cur_aid))
                self.active_sticky_actions[cur_aid] = set(current)
                for b in current:
                    self.active_sticky_buttons.add(b)
                logger.debug("Sticky action pressed: %s", cur_aid)

        # Session end
        if not current:
            self.peak_buttons = set()
            self.active_sticky_buttons = set()
            self.active_sticky_actions = {}
            if not events:
                self.key_event_triggered = False

        return events

    # -- dial ---------------------------------------------------------------
    def feed_dial(self, action_id: str) -> List[InputEvent]:
        """One rotation detent -> a press+release pulse of DIAL_CW/DIAL_CCW."""
        return [
            InputEvent(EventType.KEY_PRESS, action_id),
            InputEvent(EventType.KEY_RELEASE, action_id),
        ]

    def feed_dial_click(self, pressed: bool) -> List[InputEvent]:
        """Dial center press -> direct DIAL_CLICK press/release (no combo)."""
        etype = EventType.KEY_PRESS if pressed else EventType.KEY_RELEASE
        return [InputEvent(etype, "DIAL_CLICK")]

    # -- lifecycle ----------------------------------------------------------
    def reset(self) -> None:
        self.current_buttons = set()
        self.peak_buttons = set()
        self.key_event_triggered = False
        self.active_sticky_buttons = set()
        self.active_sticky_actions = {}
