"""Pure evdev -> Keydial action-ID mapping.

Derived from the live-verified fixed firmware (docs/DEVICE-K20.md sec G):
each K20 button emits a fixed KEY_* on the keyboard node; the dial emits
REL_WHEEL on the mouse node; the dial click emits KEY_PLAYPAUSE.
No state here — see input_translator for combo/sticky handling.
"""
from typing import Dict, Optional

from evdev import ecodes

# K20 vendor/product (PnP / Modalias v256Cp8251)
KEYDIAL_VENDOR = 0x256C
KEYDIAL_PRODUCT = 0x8251

# Fixed firmware key -> action ID (physical reading order = BUTTON_1..18)
KEY_TO_ACTION: Dict[int, str] = {
    ecodes.KEY_K: "BUTTON_1",
    ecodes.KEY_G: "BUTTON_2",
    ecodes.KEY_L: "BUTTON_3",
    ecodes.KEY_DELETE: "BUTTON_4",
    ecodes.KEY_I: "BUTTON_5",
    ecodes.KEY_D: "BUTTON_6",
    ecodes.KEY_B: "BUTTON_7",
    ecodes.KEY_E: "BUTTON_8",
    ecodes.KEY_S: "BUTTON_9",
    ecodes.KEY_Z: "BUTTON_10",
    ecodes.KEY_C: "BUTTON_11",
    ecodes.KEY_V: "BUTTON_12",
    ecodes.KEY_LEFTCTRL: "BUTTON_13",
    ecodes.KEY_LEFTALT: "BUTTON_14",
    ecodes.KEY_LEFTSHIFT: "BUTTON_15",
    ecodes.KEY_ENTER: "BUTTON_16",
    ecodes.KEY_SPACE: "BUTTON_17",
    ecodes.KEY_N: "BUTTON_18",
    ecodes.KEY_PLAYPAUSE: "DIAL_CLICK",
}

# Live capture: turning one way gives REL_WHEEL -1, the other +1. Flip here if
# a given unit reports the opposite sense.
INVERT_WHEEL = False


def action_for_key(code: int) -> Optional[str]:
    """Return the action ID for an evdev key code, or None if unmapped."""
    return KEY_TO_ACTION.get(code)


def dial_for_wheel(value: int) -> Optional[str]:
    """Map a REL_WHEEL delta to a dial-rotation action ID."""
    if value == 0:
        return None
    clockwise = value < 0
    if INVERT_WHEEL:
        clockwise = not clockwise
    return "DIAL_CW" if clockwise else "DIAL_CCW"


def is_keydial(name: str, vendor: int, product: int) -> bool:
    """True if an input device is a Huion Keydial (by name or VID:PID)."""
    if name and "keydial" in name.lower():
        return True
    return vendor == KEYDIAL_VENDOR and product == KEYDIAL_PRODUCT
