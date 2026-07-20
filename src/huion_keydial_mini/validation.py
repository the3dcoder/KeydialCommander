"""Single source of truth for action-ID, key-name, and MAC validation (audit L3)."""
import re
from typing import List

from .keymap import KEY_MAPPING


class ValidationError(ValueError):
    """Raised for any invalid user-supplied identifier."""


VALID_BUTTONS = frozenset("BUTTON_%d" % i for i in range(1, 19))
VALID_DIAL_ACTIONS = frozenset({"DIAL_CW", "DIAL_CCW", "DIAL_CLICK"})

_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def normalize_action_id(action_id: str) -> str:
    """Return the canonical action ID (chords sorted) or raise ValidationError."""
    if not action_id or not action_id.strip():
        raise ValidationError("Empty action ID")
    action_id = action_id.strip()

    if action_id in VALID_DIAL_ACTIONS or action_id in VALID_BUTTONS:
        return action_id

    if "+" in action_id:
        parts = [p.strip() for p in action_id.split("+")]
        if any(not p for p in parts) or len(parts) < 2:
            raise ValidationError("Chords need at least 2 buttons: %r" % action_id)
        if len(parts) != len(set(parts)):
            raise ValidationError("Duplicate button in chord: %r" % action_id)
        for part in parts:
            if part not in VALID_BUTTONS:
                raise ValidationError("Invalid button %r in chord %r" % (part, action_id))
        return "+".join(sorted(parts))

    raise ValidationError("Invalid action ID: %r" % action_id)


def validate_keys(keys: List[str]) -> List[str]:
    """Return stripped key names, all present in KEY_MAPPING, or raise."""
    if not keys:
        raise ValidationError("At least one key required")
    cleaned = []
    for key in keys:
        name = key.strip()
        if name not in KEY_MAPPING:
            raise ValidationError("Unknown key name: %r (see keydialctl list-keys)" % name)
        cleaned.append(name)
    return cleaned


def validate_mac(mac: str) -> str:
    """Return the MAC uppercased, or raise."""
    if not mac or not _MAC_RE.match(mac.strip()):
        raise ValidationError("Invalid MAC address: %r (expected AA:BB:CC:DD:EE:FF)" % mac)
    return mac.strip().upper()


MACRO_MAX_STEPS = 32
MACRO_MAX_TOTAL_MS = 10000
_ACTION_ALIASES = {"keyboard": "keystroke"}


def validate_action(data):
    """Validate a binding action dict and return it normalized, or raise."""
    if not isinstance(data, dict):
        raise ValidationError("Action must be an object")
    atype = _ACTION_ALIASES.get(str(data.get("type", "keystroke")),
                                str(data.get("type", "keystroke")))

    if atype == "keystroke":
        keys = validate_keys(data.get("keys") or [])
        out = {"type": "keystroke", "keys": keys}
        if data.get("sticky"):
            out["sticky"] = True
        return out

    if atype == "macro":
        steps = data.get("steps")
        if not isinstance(steps, list) or not steps:
            raise ValidationError("Macro requires a non-empty 'steps' list")
        if len(steps) > MACRO_MAX_STEPS:
            raise ValidationError("Macro exceeds %d steps" % MACRO_MAX_STEPS)
        total_ms = 0
        norm_steps = []
        for step in steps:
            if not isinstance(step, dict):
                raise ValidationError("Macro step must be an object")
            if "delay_ms" in step:
                try:
                    ms = int(step["delay_ms"])
                except (TypeError, ValueError):
                    raise ValidationError("delay_ms must be an integer")
                if ms < 0:
                    raise ValidationError("delay_ms must be >= 0")
                total_ms += ms
                norm_steps.append({"delay_ms": ms})
            elif "keys" in step:
                norm_steps.append({"keys": validate_keys(step.get("keys") or [])})
            else:
                raise ValidationError("Macro step needs 'keys' or 'delay_ms'")
        if total_ms > MACRO_MAX_TOTAL_MS:
            raise ValidationError("Macro total delay exceeds %d ms" % MACRO_MAX_TOTAL_MS)
        return {"type": "macro", "steps": norm_steps}

    if atype == "command":
        argv = data.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
            raise ValidationError("Command requires a non-empty 'argv' list of strings")
        return {"type": "command", "argv": list(argv)}

    if atype == "profile_switch":
        profile = data.get("profile")
        if not isinstance(profile, str) or not profile.strip():
            raise ValidationError("profile_switch requires a non-empty 'profile'")
        return {"type": "profile_switch", "profile": profile.strip()}

    raise ValidationError("Unknown action type: %r" % atype)
