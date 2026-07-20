"""Core input-event types shared across the device layer.

Kept dependency-free so both the evdev source and the uinput handler can
import it without pulling in the (retired) HID parser.
"""
from typing import NamedTuple, Optional
from enum import Enum


class EventType(Enum):
    """Types of input events."""
    KEY_PRESS = "key_press"
    KEY_RELEASE = "key_release"
    DIAL_ROTATE = "dial_rotate"
    DIAL_CLICK = "dial_click"


class InputEvent(NamedTuple):
    """Represents an input event (key_code carries the action ID)."""
    event_type: EventType
    key_code: Optional[str] = None
    direction: Optional[int] = None  # dial rotation: 1 = clockwise, -1 = counterclockwise
    value: Optional[int] = None
    raw_data: Optional[bytearray] = None  # optional debug payload
