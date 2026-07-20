# Phase 1 — Driver Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix every foundation defect from `docs/AUDIT-2026-07-19.md` and add the persistence/profile/event primitives the Keydial Commander GUI (Phase 2) will build on.

**Architecture:** The daemon keeps its pipeline (BluetoothWatcher → device → hid_parser → keybind_manager → uinput) but gains: a shared validation module, comment-preserving config IO (ruamel.yaml), a ProfileStore owning on-disk binding sets, a framed v2 Unix-socket protocol with profile/event commands, an EventBus, FFE1-specific BLE subscription with battery, and clean async lifecycles. Packaging (systemd/udev/pyproject) is repaired.

**Tech Stack:** Python ≥3.8, asyncio, bleak, dbus-next, evdev, click, **ruamel.yaml (new runtime dep)**, pytest + pytest-asyncio.

## Global Constraints

- Python floor is 3.8 (`pyproject.toml requires-python = ">=3.8"`): use `typing.Optional/List/Dict`, no `X | Y` unions, no `match`.
- Never block the event loop: no `time.sleep` anywhere under `src/` (audit H6).
- Runtime sockets/artifacts live in `$XDG_RUNTIME_DIR/huion-keydial-mini/` (fallback `~/.local/share/huion-keydial-mini/`), dir mode `0o700`, socket `0o600`.
- `src/huion_keydial_mini/validation.py` is the ONLY place button/dial/key validity is defined (audit L3).
- Profile YAML writes `type: keystroke`; readers accept legacy `"keyboard"` as an alias.
- Spec deviation (recorded): active-profile pointer lives in `profiles/active` (single-writer ProfileStore), not `config.yaml`; spec §4 gets amended in Task 12.
- Device facts from `docs/DEVICE-K20.md`: event source = vendor char `0000ffe1-…`, battery = `2a19`, adapter may be **hci1** — never hardcode `hci0`.
- All work on branch `feat/phase1-driver-hardening`; venv at `.venv/` (already gitignored); run tests with `.venv/bin/pytest tests/ -v`.
- Every commit: short imperative subject, end body with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 0: Branch + environment + green baseline

**Files:** none created (branch + venv only)

**Interfaces:**
- Produces: merged `main`, branch `feat/phase1-driver-hardening`, working `.venv` used by all later tasks.

- [ ] **Step 1: Confirm tooling** — Run: `python3 -m venv --help >/dev/null && echo OK`. If this fails, STOP and ask the user to run: `sudo apt install python3-venv python3-pip` (decision already approved: user runs the apt line).

- [ ] **Step 2: Merge approved docs branch and cut the feature branch**

```bash
git checkout main
git merge --no-ff docs/audit-and-design -m "merge audit, design docs, and device reference"
git checkout -b feat/phase1-driver-hardening
```

- [ ] **Step 3: Create venv and install**

Run: `python3 -m venv .venv && .venv/bin/pip install -e ".[test]"`
Expected: ends with `Successfully installed … huion-keydial-mini-driver-1.2.1 …`

- [ ] **Step 4: Baseline test run**

Run: `.venv/bin/pytest tests/ -q`
Expected: all tests PASS (audit §5 predicts green). If any fail, record the failure verbatim in `docs/WORKLOG.md` before continuing — do not fix unrelated tests silently.

---

### Task 1: Extract `keymap.py` (breaks the import cycle; enables device-free key listing)

**Files:**
- Create: `src/huion_keydial_mini/keymap.py`
- Modify: `src/huion_keydial_mini/uinput_handler.py` (delete class-attribute dict, import instead)
- Test: `tests/test_keymap.py`

**Interfaces:**
- Produces: `keymap.KEY_MAPPING: Dict[str, int]` (exact same 225 entries), `keymap.SUPPORTED_KEYS: List[str]` (sorted names). `UInputHandler.KEY_MAPPING` remains available as a class attribute alias.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_keymap.py
"""keymap must be importable without touching /dev/uinput."""
from huion_keydial_mini.keymap import KEY_MAPPING, SUPPORTED_KEYS


def test_key_mapping_spot_checks():
    from evdev import ecodes
    assert KEY_MAPPING["KEY_F1"] == ecodes.KEY_F1
    assert KEY_MAPPING["BTN_LEFT"] == ecodes.BTN_LEFT
    assert KEY_MAPPING["KEY_LEFTCTRL"] == ecodes.KEY_LEFTCTRL
    assert len(KEY_MAPPING) > 200


def test_supported_keys_sorted_and_complete():
    assert SUPPORTED_KEYS == sorted(KEY_MAPPING.keys())


def test_uinput_handler_alias_still_exists():
    from huion_keydial_mini.uinput_handler import UInputHandler
    assert UInputHandler.KEY_MAPPING is KEY_MAPPING
```

- [ ] **Step 2: Run test to verify it fails** — Run: `.venv/bin/pytest tests/test_keymap.py -v` — Expected: FAIL `ModuleNotFoundError: No module named 'huion_keydial_mini.keymap'`

- [ ] **Step 3: Implement** — Create `keymap.py` with header below, then **move the dict body verbatim** from `uinput_handler.py` (the `KEY_MAPPING = { … }` class attribute, currently lines 22–215) into it at module level; in `uinput_handler.py` delete the class-attribute dict and add the import + alias:

```python
# src/huion_keydial_mini/keymap.py
"""Static key-name → evdev keycode table. Import must never touch /dev/uinput."""
from typing import Dict, List
from evdev import ecodes

KEY_MAPPING: Dict[str, int] = {
    # … moved verbatim from UInputHandler.KEY_MAPPING …
}

SUPPORTED_KEYS: List[str] = sorted(KEY_MAPPING.keys())
```

```python
# uinput_handler.py — top of file
from .keymap import KEY_MAPPING


class UInputHandler:
    """Handles creation of virtual input device and event generation."""

    KEY_MAPPING = KEY_MAPPING  # compatibility alias
```

- [ ] **Step 4: Run** — `.venv/bin/pytest tests/test_keymap.py tests/ -q` — Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/huion_keydial_mini/keymap.py src/huion_keydial_mini/uinput_handler.py tests/test_keymap.py
git commit -m "extract static keymap module

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Shared validation module (audit L3, L4)

**Files:**
- Create: `src/huion_keydial_mini/validation.py`
- Test: `tests/test_validation.py`

**Interfaces:**
- Consumes: `keymap.KEY_MAPPING` (Task 1)
- Produces (used by Tasks 3, 5, 6):
  - `class ValidationError(ValueError)`
  - `VALID_BUTTONS: frozenset` (`BUTTON_1..BUTTON_18`), `VALID_DIAL_ACTIONS: frozenset`
  - `normalize_action_id(action_id: str) -> str` — returns canonical ID (chords sorted) or raises `ValidationError`
  - `validate_keys(keys: List[str]) -> List[str]` — returns stripped names or raises
  - `validate_mac(mac: str) -> str` — returns uppercase `AA:BB:…` or raises

- [ ] **Step 1: Write the failing test**

```python
# tests/test_validation.py
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
```

- [ ] **Step 2: Run to fail** — `.venv/bin/pytest tests/test_validation.py -v` — Expected: FAIL (module missing)

- [ ] **Step 3: Implement**

```python
# src/huion_keydial_mini/validation.py
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
```

- [ ] **Step 4: Run** — `.venv/bin/pytest tests/test_validation.py -v` — Expected: ALL PASS

- [ ] **Step 5: Commit** — `git add src/huion_keydial_mini/validation.py tests/test_validation.py && git commit -m "add shared validation module

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 3: Comment-preserving config IO + fixed set/clear-device (audit H3, H4, L4)

**Files:**
- Modify: `src/huion_keydial_mini/config.py` (replace pyyaml with ruamel round-trip; add setters), `src/huion_keydial_mini/keydialctl.py` (`set_device`, `clear_device` commands), `pyproject.toml` (add `ruamel.yaml>=0.17.21` to `dependencies`)
- Test: `tests/test_config_io.py`

**Interfaces:**
- Consumes: `validation.validate_mac`
- Produces (used by Tasks 4, 6):
  - `Config.load(path: Optional[str], device_address: Optional[str]) -> Config` (unchanged signature)
  - `Config.save(config_path: Optional[str] = None) -> None` — writes the ORIGINAL parsed document (comments + unknown keys intact) to the loaded path or given path, atomically (`tmp` + `os.replace`)
  - `Config.set_device_address(mac: Optional[str]) -> None` — `None` clears; updates both the read view and the document (nested `device.address`; removes any flat `device_address` key)
  - `Config.source_path: Optional[Path]` — where the config was loaded from

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config_io.py
from pathlib import Path
import pytest
from huion_keydial_mini.config import Config
from huion_keydial_mini.validation import ValidationError

SAMPLE = """\
# my precious comment
debug_mode: true            # keep me too
device_address: "20:23:06:01:8A:B0"
key_mappings:
  BUTTON_1: "KEY_F1"        # binding comment
"""


@pytest.fixture()
def cfg_file(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(SAMPLE)
    return p


def test_round_trip_preserves_comments_and_unknown_keys(cfg_file):
    cfg = Config.load(str(cfg_file))
    cfg.save()
    text = cfg_file.read_text()
    assert "# my precious comment" in text
    assert "debug_mode: true" in text
    assert "# binding comment" in text


def test_set_device_address_updates_and_persists(cfg_file):
    cfg = Config.load(str(cfg_file))
    cfg.set_device_address("aa:bb:cc:dd:ee:ff")
    assert cfg.device_address == "AA:BB:CC:DD:EE:FF"
    cfg.save()
    cfg2 = Config.load(str(cfg_file))
    assert cfg2.device_address == "AA:BB:CC:DD:EE:FF"
    assert "# my precious comment" in cfg_file.read_text()


def test_clear_device_address_actually_clears(cfg_file):  # audit H4
    cfg = Config.load(str(cfg_file))
    assert cfg.device_address == "20:23:06:01:8A:B0"
    cfg.set_device_address(None)
    cfg.save()
    assert Config.load(str(cfg_file)).device_address is None


def test_invalid_mac_rejected(cfg_file):  # audit L4
    cfg = Config.load(str(cfg_file))
    with pytest.raises(ValidationError):
        cfg.set_device_address("not-a-mac-addr-17")


def test_save_is_atomic_no_partial_on_error(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("device: {address: null}\n")
    cfg = Config.load(str(p))
    cfg.save()                      # simply must not corrupt
    assert Config.load(str(p)).validate() if hasattr(cfg, "validate") else True
```

- [ ] **Step 2: Run to fail** — `.venv/bin/pytest tests/test_config_io.py -v` — Expected: FAIL (comments destroyed / clear no-op / no `set_device_address`)

- [ ] **Step 3: Implement.** In `pyproject.toml` `dependencies`, add `"ruamel.yaml>=0.17.21",`. Then rework `config.py`:

```python
# config.py — replace `import yaml` and rework load/save; KEEP the existing
# property accessors and _validate_config_data exactly as they are.
import io
import os
from pathlib import Path
from typing import Optional, Dict, Any

from ruamel.yaml import YAML

from .validation import validate_mac

_yaml = YAML(typ="rt")          # round-trip: preserves comments/order
_yaml.preserve_quotes = True


class Config:
    def __init__(self, data: Dict[str, Any], doc=None, source_path: Optional[Path] = None):
        self.data = self._validate_config_data(data)
        self._global = {k: v for k, v in data.items() if k not in self.data}
        self._doc = doc if doc is not None else {}   # ruamel CommentedMap or plain dict
        self.source_path = source_path
```

`Config.load` changes (same flat→nested migration logic, but parse with ruamel and keep the doc):

```python
    @classmethod
    def load(cls, config_path: Optional[str] = None, device_address: Optional[str] = None) -> "Config":
        if config_path:
            config_file = Path(config_path)
        else:
            config_file = None
            for location in [Path.home() / ".config" / "huion-keydial-mini" / "config.yaml",
                             Path("/etc/huion-keydial-mini/config.yaml")]:
                if location.exists():
                    config_file = location
                    break

        doc = {}
        if config_file and config_file.exists():
            try:
                with open(config_file, "r") as f:
                    loaded = _yaml.load(f)
                if loaded is not None:
                    doc = loaded
            except Exception as e:
                print("Warning: Error loading config file %s: %s" % (config_file, e))

        raw_data: Dict[str, Any] = dict(doc) if isinstance(doc, dict) else {}
        # (existing flat→nested migration of device_address / connection_timeout /
        #  uinput_device_name over raw_data stays IDENTICAL here)
        # (existing defaults merge stays IDENTICAL here)
        config_data = cls._merge_config_data(cls._get_default_config(), raw_data)
        cfg = cls(config_data, doc=doc, source_path=config_file)
        if device_address:
            cfg.set_device_address(device_address)
        return cfg
```

New setter + atomic save (replaces old `save`):

```python
    def set_device_address(self, mac: Optional[str]) -> None:
        """Set (validated) or clear (None) the device address in view AND document."""
        value = validate_mac(mac) if mac is not None else None
        self.data.setdefault("device", {})["address"] = value
        if not isinstance(self._doc, dict):
            self._doc = {}
        self._doc.pop("device_address", None)          # legacy flat key
        device = self._doc.setdefault("device", {})
        device["address"] = value

    def save(self, config_path: Optional[str] = None) -> None:
        target = Path(config_path) if config_path else self.source_path
        if target is None:
            target = Path.home() / ".config" / "huion-keydial-mini" / "config.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        buf = io.StringIO()
        _yaml.dump(self._doc if self._doc else self.data, buf)
        tmp = target.with_suffix(".yaml.tmp")
        tmp.write_text(buf.getvalue())
        os.replace(str(tmp), str(target))
        self.source_path = target
```

In `keydialctl.py` replace the bodies of `set_device` and `clear_device`:

```python
@cli.command()
@click.argument('device_address')
@click.pass_context
def set_device(ctx, device_address: str):
    """Set the device address in configuration."""
    from .validation import ValidationError
    config = _load_config(ctx.obj.get('config_path'))
    try:
        config.set_device_address(device_address)
    except ValidationError as e:
        click.echo("Error: %s" % e, err=True)
        sys.exit(1)
    config.save(str(_get_config_file(ctx.obj.get('config_path'))))
    click.echo("Device address set to: %s" % config.device_address)


@cli.command()
@click.pass_context
def clear_device(ctx):
    """Clear the device address from configuration (return to auto-discover)."""
    config = _load_config(ctx.obj.get('config_path'))
    old = config.device_address
    if old is None:
        click.echo("No device address configured")
        return
    config.set_device_address(None)
    config.save(str(_get_config_file(ctx.obj.get('config_path'))))
    click.echo("Cleared device address (was: %s)" % old)
```

Also delete the now-unused `import yaml` from `keydialctl.py`.

- [ ] **Step 4: Reinstall (new dep) and run** — `.venv/bin/pip install -e ".[test]" -q && .venv/bin/pytest tests/test_config_io.py tests/ -q` — Expected: ALL PASS

- [ ] **Step 5: Commit** — `git add -A && git commit -m "preserve config comments and fix set/clear-device

Config IO now uses ruamel.yaml round-trip (audit H3); clear-device works
again (H4); MAC addresses validated (L4).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 4: ProfileStore with legacy migration (audit H5 groundwork; spec §4)

**Files:**
- Create: `src/huion_keydial_mini/profile_store.py`
- Test: `tests/test_profile_store.py`

**Interfaces:**
- Consumes: `KeybindAction`, `EventType` from `keybind_manager` (import at module level is safe — keybind_manager must NOT import profile_store at module level; Task 5 wires them via constructor injection), `validation.normalize_action_id/validate_keys`
- Produces (used by Tasks 5, 6 and Phase 2):
  - `class ProfileStore:`
    - `__init__(self, config_dir: Optional[Path] = None)` — default `~/.config/huion-keydial-mini`
    - `ensure_initialized(self, legacy_config: Optional["Config"] = None) -> None` — mkdir, migrate legacy sections into `profiles/Default.yaml` once, guarantee ≥1 profile + `profiles/active`
    - `list_profiles(self) -> List[str]`
    - `get_active(self) -> str` / `set_active(self, name: str) -> None`
    - `load_bindings(self, profile: Optional[str] = None) -> Dict[str, KeybindAction]`
    - `save_binding(self, action_id: str, action: KeybindAction, profile: Optional[str] = None) -> None`
    - `remove_binding(self, action_id: str, profile: Optional[str] = None) -> None`
    - `clear_bindings(self, profile: Optional[str] = None) -> None`
    - `create_profile(self, name: str, clone_from: Optional[str] = None) -> None`
    - `delete_profile(self, name: str) -> None` — refuses to delete the last profile or the active one
    - `get_dial_sensitivity(self, profile: Optional[str] = None) -> float`
  - Profile file format (spec §4): `schema: 1`, `dial_sensitivity: <float>`, `bindings: {<action_id>: {type: keystroke, keys: […], sticky: bool}}`
  - `ProfileError(Exception)` for invalid profile operations

- [ ] **Step 1: Write the failing test**

```python
# tests/test_profile_store.py
import pytest
from huion_keydial_mini.profile_store import ProfileStore, ProfileError
from huion_keydial_mini.keybind_manager import KeybindAction, EventType
from huion_keydial_mini.config import Config


def make_store(tmp_path):
    store = ProfileStore(config_dir=tmp_path)
    store.ensure_initialized()
    return store


def act(keys, sticky=False):
    return KeybindAction(type=EventType.KEYBOARD, keys=keys, sticky=sticky)


def test_initialization_creates_default(tmp_path):
    store = make_store(tmp_path)
    assert store.list_profiles() == ["Default"]
    assert store.get_active() == "Default"
    assert (tmp_path / "profiles" / "Default.yaml").exists()


def test_binding_round_trip_and_keystroke_type(tmp_path):
    store = make_store(tmp_path)
    store.save_binding("BUTTON_1", act(["KEY_LEFTCTRL", "KEY_Z"]))
    text = (tmp_path / "profiles" / "Default.yaml").read_text()
    assert "keystroke" in text            # spec: writes keystroke, not keyboard
    loaded = store.load_bindings()
    assert loaded["BUTTON_1"].keys == ["KEY_LEFTCTRL", "KEY_Z"]


def test_remove_and_clear(tmp_path):
    store = make_store(tmp_path)
    store.save_binding("BUTTON_1", act(["KEY_F1"]))
    store.remove_binding("BUTTON_1")
    assert store.load_bindings() == {}
    store.save_binding("BUTTON_2", act(["KEY_F2"]))
    store.clear_bindings()
    assert store.load_bindings() == {}


def test_profiles_create_switch_delete(tmp_path):
    store = make_store(tmp_path)
    store.save_binding("BUTTON_1", act(["KEY_F1"]))
    store.create_profile("Krita", clone_from="Default")
    assert sorted(store.list_profiles()) == ["Default", "Krita"]
    store.set_active("Krita")
    assert store.load_bindings()["BUTTON_1"].keys == ["KEY_F1"]   # cloned
    with pytest.raises(ProfileError):
        store.delete_profile("Krita")                              # active
    store.set_active("Default")
    store.delete_profile("Krita")
    with pytest.raises(ProfileError):
        store.delete_profile("Default")                            # last one


def test_migration_from_legacy_config(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "key_mappings:\n  BUTTON_1: \"KEY_F1\"\n"
        "sticky_key_mappings:\n  BUTTON_2: \"KEY_LEFTCTRL\"\n"
        "dial_settings:\n  DIAL_CW: \"KEY_VOLUMEUP\"\n  sensitivity: 2.0\n"
    )
    cfg = Config.load(str(cfg_file))
    store = ProfileStore(config_dir=tmp_path)
    store.ensure_initialized(legacy_config=cfg)
    b = store.load_bindings("Default")
    assert b["BUTTON_1"].keys == ["KEY_F1"]
    assert b["BUTTON_2"].sticky is True
    assert b["DIAL_CW"].keys == ["KEY_VOLUMEUP"]
    assert store.get_dial_sensitivity("Default") == 2.0
    # idempotent: second init must not duplicate/overwrite
    store.ensure_initialized(legacy_config=cfg)
    assert store.load_bindings("Default")["BUTTON_1"].keys == ["KEY_F1"]


def test_unknown_profile_raises(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(ProfileError):
        store.set_active("Nope")
    with pytest.raises(ProfileError):
        store.load_bindings("Nope")
```

- [ ] **Step 2: Run to fail** — `.venv/bin/pytest tests/test_profile_store.py -v` — Expected: FAIL (module missing)

- [ ] **Step 3: Implement**

```python
# src/huion_keydial_mini/profile_store.py
"""On-disk profile storage: one YAML per profile + an `active` pointer file.

Single writer for everything under <config_dir>/profiles/. Auto-persists
every mutation atomically (spec: no Save button anywhere).
"""
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from ruamel.yaml import YAML

from .keybind_manager import KeybindAction, EventType
from .validation import normalize_action_id, validate_keys, ValidationError

logger = logging.getLogger(__name__)

_yaml = YAML(typ="rt")
_PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}$")
_TYPE_ALIASES = {"keyboard": "keystroke"}  # legacy value accepted on read


class ProfileError(Exception):
    """Invalid profile operation (unknown name, last-profile delete, …)."""


class ProfileStore:
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = Path(config_dir) if config_dir else (
            Path.home() / ".config" / "huion-keydial-mini")
        self.profiles_dir = self.config_dir / "profiles"
        self._active_file = self.profiles_dir / "active"

    # -- init / migration ---------------------------------------------------
    def ensure_initialized(self, legacy_config=None) -> None:
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        if not self.list_profiles():
            bindings: Dict[str, KeybindAction] = {}
            sensitivity = 1.0
            if legacy_config is not None:
                bindings, sensitivity = self._bindings_from_legacy(legacy_config)
            self._write_profile("Default", bindings, sensitivity)
            logger.info("Created Default profile (%d migrated bindings)", len(bindings))
        if not self._active_file.exists():
            self.set_active(self.list_profiles()[0])

    def _bindings_from_legacy(self, config):
        result: Dict[str, KeybindAction] = {}
        for mapping, sticky in ((config.key_mappings, False),
                                (config.sticky_key_mappings, True)):
            for action_id, keydata in mapping.items():
                try:
                    aid = normalize_action_id(action_id)
                    keys = validate_keys([k.strip() for k in keydata.split("+")])
                except ValidationError as e:
                    logger.warning("Skipping legacy binding %r: %s", action_id, e)
                    continue
                result[aid] = KeybindAction(type=EventType.KEYBOARD, keys=keys, sticky=sticky)
        dial = config.dial_settings
        for dial_id in ("DIAL_CW", "DIAL_CCW", "DIAL_CLICK"):
            value = dial.get(dial_id)
            if value:
                try:
                    keys = validate_keys([k.strip() for k in str(value).split("+")])
                except ValidationError as e:
                    logger.warning("Skipping legacy dial binding %r: %s", dial_id, e)
                    continue
                result[dial_id] = KeybindAction(type=EventType.KEYBOARD, keys=keys)
        try:
            sensitivity = float(dial.get("sensitivity", 1.0))
        except (TypeError, ValueError):
            sensitivity = 1.0
        return result, sensitivity

    # -- profile management -------------------------------------------------
    def list_profiles(self) -> List[str]:
        if not self.profiles_dir.exists():
            return []
        return sorted(p.stem for p in self.profiles_dir.glob("*.yaml"))

    def get_active(self) -> str:
        if self._active_file.exists():
            name = self._active_file.read_text().strip()
            if name in self.list_profiles():
                return name
        profiles = self.list_profiles()
        if not profiles:
            raise ProfileError("No profiles exist; call ensure_initialized() first")
        return profiles[0]

    def set_active(self, name: str) -> None:
        self._require(name)
        self._atomic_write(self._active_file, name + "\n")

    def create_profile(self, name: str, clone_from: Optional[str] = None) -> None:
        if not _PROFILE_NAME_RE.match(name or ""):
            raise ProfileError("Invalid profile name: %r" % name)
        if name in self.list_profiles():
            raise ProfileError("Profile already exists: %r" % name)
        if clone_from is not None:
            self._require(clone_from)
            bindings = self.load_bindings(clone_from)
            sensitivity = self.get_dial_sensitivity(clone_from)
        else:
            bindings, sensitivity = {}, 1.0
        self._write_profile(name, bindings, sensitivity)

    def delete_profile(self, name: str) -> None:
        self._require(name)
        if len(self.list_profiles()) == 1:
            raise ProfileError("Cannot delete the last profile")
        if name == self.get_active():
            raise ProfileError("Cannot delete the active profile")
        (self.profiles_dir / (name + ".yaml")).unlink()

    # -- bindings -----------------------------------------------------------
    def load_bindings(self, profile: Optional[str] = None) -> Dict[str, KeybindAction]:
        name = profile or self.get_active()
        doc = self._read_profile(name)
        out: Dict[str, KeybindAction] = {}
        for action_id, raw in (doc.get("bindings") or {}).items():
            if not isinstance(raw, dict):
                continue
            rtype = _TYPE_ALIASES.get(str(raw.get("type", "keystroke")),
                                      str(raw.get("type", "keystroke")))
            if rtype != "keystroke":
                logger.warning("Profile %s: unsupported action type %r on %s (Phase 2)",
                               name, rtype, action_id)
                continue
            out[str(action_id)] = KeybindAction(
                type=EventType.KEYBOARD,
                keys=list(raw.get("keys") or []),
                sticky=bool(raw.get("sticky", False)),
                description=raw.get("description"),
            )
        return out

    def save_binding(self, action_id: str, action: KeybindAction,
                     profile: Optional[str] = None) -> None:
        name = profile or self.get_active()
        doc = self._read_profile(name)
        bindings = doc.setdefault("bindings", {})
        entry = {"type": "keystroke", "keys": list(action.keys or [])}
        if action.sticky:
            entry["sticky"] = True
        bindings[action_id] = entry
        self._dump_profile(name, doc)

    def remove_binding(self, action_id: str, profile: Optional[str] = None) -> None:
        name = profile or self.get_active()
        doc = self._read_profile(name)
        (doc.get("bindings") or {}).pop(action_id, None)
        self._dump_profile(name, doc)

    def clear_bindings(self, profile: Optional[str] = None) -> None:
        name = profile or self.get_active()
        doc = self._read_profile(name)
        doc["bindings"] = {}
        self._dump_profile(name, doc)

    def get_dial_sensitivity(self, profile: Optional[str] = None) -> float:
        doc = self._read_profile(profile or self.get_active())
        try:
            return float(doc.get("dial_sensitivity", 1.0))
        except (TypeError, ValueError):
            return 1.0

    # -- plumbing -----------------------------------------------------------
    def _require(self, name: str) -> None:
        if name not in self.list_profiles():
            raise ProfileError("Unknown profile: %r" % name)

    def _path(self, name: str) -> Path:
        return self.profiles_dir / (name + ".yaml")

    def _read_profile(self, name: str):
        self._require(name)
        with open(self._path(name)) as f:
            return _yaml.load(f) or {}

    def _write_profile(self, name, bindings, sensitivity) -> None:
        doc = {"schema": 1, "dial_sensitivity": sensitivity, "bindings": {}}
        self._dump_profile(name, doc, create=True)
        for action_id, action in bindings.items():
            self.save_binding(action_id, action, profile=name)

    def _dump_profile(self, name, doc, create=False) -> None:
        if not create:
            self._require(name)
        import io
        buf = io.StringIO()
        _yaml.dump(doc, buf)
        self._atomic_write(self._path(name), buf.getvalue())

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text)
        os.replace(str(tmp), str(path))
```

- [ ] **Step 4: Run** — `.venv/bin/pytest tests/test_profile_store.py tests/ -q` — Expected: ALL PASS

- [ ] **Step 5: Commit** — `git add src/huion_keydial_mini/profile_store.py tests/test_profile_store.py && git commit -m "add ProfileStore with legacy config migration

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 5: IPC v2 — framed protocol, runtime-dir socket, client timeout (audit L1, M8)

**Files:**
- Create: `src/huion_keydial_mini/ipc.py`
- Modify: `src/huion_keydial_mini/keybind_manager.py` (server: `_handle_client` loop + socket path/permissions; client: `send_command`), `src/huion_keydial_mini/keydialctl.py` (`get_socket_path` delegates to ipc)
- Test: `tests/test_ipc.py`

**Interfaces:**
- Produces (used by Task 6, 7 and Phase 2):
  - `ipc.runtime_dir() -> Path` — `$XDG_RUNTIME_DIR/huion-keydial-mini` or `~/.local/share/huion-keydial-mini`; created `0o700`
  - `ipc.socket_path() -> str` — `<runtime_dir>/control.sock`
  - `ipc.MAX_LINE = 65536`
  - Wire protocol v2: one JSON object per `\n`-terminated line, both directions; multiple requests per connection; every response carries `"v": 2`
  - `keybind_manager.send_command(socket_path: str, command: Dict[str, Any], timeout: float = 5.0) -> Dict[str, Any]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ipc.py
import asyncio
import json
import pytest
from huion_keydial_mini import ipc
from huion_keydial_mini.keybind_manager import KeybindManager, send_command
from huion_keydial_mini.config import Config


@pytest.fixture()
def manager(tmp_path):
    cfg = Config.load(None)
    m = KeybindManager(cfg, socket_path=str(tmp_path / "test.sock"))
    return m


def test_runtime_dir_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    d = ipc.runtime_dir()
    assert d == tmp_path / "huion-keydial-mini"
    assert (d.stat().st_mode & 0o777) == 0o700
    assert ipc.socket_path() == str(d / "control.sock")


async def _roundtrip(manager, payloads):
    await manager.start_socket_server()
    try:
        results = []
        for p in payloads:
            results.append(await send_command(manager.socket_path, p))
        return results
    finally:
        await manager.stop_socket_server()


def test_v2_envelope_and_multiple_commands(manager):
    r1, r2 = asyncio.run(_roundtrip(manager, [
        {"command": "list_actions"},
        {"command": "get_bindings"},
    ]))
    assert r1["v"] == 2 and r1["status"] == "success"
    assert r2["v"] == 2 and "bindings" in r2


def test_large_command_not_truncated(manager):  # audit L1
    big_desc = "x" * 5000
    resp = asyncio.run(_roundtrip(manager, [{
        "command": "set_binding", "action_id": "BUTTON_1",
        "action": {"type": "keyboard", "keys": ["KEY_F1"], "description": big_desc},
    }]))[0]
    assert resp["status"] == "success"


def test_client_timeout(tmp_path):  # audit M8
    async def run():
        server = await asyncio.start_unix_server(
            lambda r, w: None, path=str(tmp_path / "dead.sock"))  # never answers
        try:
            return await send_command(str(tmp_path / "dead.sock"),
                                      {"command": "list_actions"}, timeout=0.3)
        finally:
            server.close()
            await server.wait_closed()
    resp = asyncio.run(run())
    assert resp["status"] == "error"
    assert "timeout" in resp["message"].lower()


def test_socket_file_mode(manager):
    async def run():
        await manager.start_socket_server()
        import os, stat
        mode = os.stat(manager.socket_path).st_mode
        await manager.stop_socket_server()
        return stat.S_IMODE(mode)
    assert asyncio.run(run()) == 0o600
```

- [ ] **Step 2: Run to fail** — `.venv/bin/pytest tests/test_ipc.py -v` — Expected: FAIL (no `ipc` module; no `v` field; no timeout param)

- [ ] **Step 3: Implement**

```python
# src/huion_keydial_mini/ipc.py
"""IPC v2 helpers: runtime paths + framing constants.

Wire format: one JSON object per newline-terminated line, both directions.
A connection may carry many requests. Responses always include {"v": 2}.
"""
import os
from pathlib import Path

PROTOCOL_VERSION = 2
MAX_LINE = 65536


def runtime_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR")
    if base:
        d = Path(base) / "huion-keydial-mini"
    else:
        d = Path.home() / ".local" / "share" / "huion-keydial-mini"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(str(d), 0o700)
    return d


def socket_path() -> str:
    return str(runtime_dir() / "control.sock")
```

In `keybind_manager.py`: `_get_default_socket_path` returns `ipc.socket_path()`; after `asyncio.start_unix_server` succeeds add `os.chmod(self.socket_path, 0o600)`. Replace `_handle_client` with a line-framed loop:

```python
    async def _handle_client(self, reader, writer):
        from . import ipc
        try:
            while True:
                try:
                    line = await reader.readline()
                except (ConnectionResetError, asyncio.IncompleteReadError):
                    break
                if not line:
                    break                     # client closed
                if len(line) > ipc.MAX_LINE:
                    await self._reply(writer, {"status": "error",
                                               "message": "Command too large"})
                    break
                try:
                    command = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    await self._reply(writer, {"status": "error",
                                               "message": "Invalid JSON"})
                    continue
                response = await self._process_command(command)
                streamed = await self._maybe_stream(command, response, writer)
                if streamed:
                    break                     # subscribe_events owns the connection
                await self._reply(writer, response)
        except Exception as e:
            logger.error("Error handling client: %s", e)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _reply(self, writer, response):
        from . import ipc
        response.setdefault("v", ipc.PROTOCOL_VERSION)
        writer.write((json.dumps(response) + "\n").encode("utf-8"))
        await writer.drain()

    async def _maybe_stream(self, command, response, writer):
        """Hook for subscribe_events (implemented in Task 7). Returns False here."""
        return False
```

Replace client `send_command`:

```python
async def send_command(socket_path: str, command: Dict[str, Any],
                       timeout: float = 5.0) -> Dict[str, Any]:
    """Send one framed command; always returns a response dict, never raises."""
    try:
        async def _do():
            reader, writer = await asyncio.open_unix_connection(socket_path)
            try:
                writer.write((json.dumps(command) + "\n").encode("utf-8"))
                await writer.drain()
                line = await reader.readline()
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
            if not line:
                return {"status": "error", "message": "No response from service"}
            return json.loads(line.decode("utf-8"))
        return await asyncio.wait_for(_do(), timeout=timeout)
    except asyncio.TimeoutError:
        return {"status": "error", "message": "Timeout waiting for service (%.1fs)" % timeout}
    except FileNotFoundError:
        return {"status": "error", "message": "Service not running (socket not found)"}
    except ConnectionRefusedError:
        return {"status": "error", "message": "Service not running (connection refused)"}
    except json.JSONDecodeError as e:
        return {"status": "error", "message": "Invalid response from service: %s" % e}
    except Exception as e:
        return {"status": "error", "message": "Communication error: %s" % e}
```

In `keydialctl.py`, replace `get_socket_path` body with `from .ipc import socket_path; return socket_path()`.

- [ ] **Step 4: Run** — `.venv/bin/pytest tests/test_ipc.py tests/ -q` — Expected: ALL PASS (old keybind tests still green — `_handle_client` behavior for single commands is compatible)

- [ ] **Step 5: Commit** — `git add -A && git commit -m "frame the control socket protocol (v2) with timeouts

Newline-delimited JSON both directions, 64K line cap, XDG_RUNTIME_DIR
socket at 0600, client timeout (audit L1, M8).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 6: KeybindManager on ProfileStore — auto-persist + profile commands + server-side validation (audit H5, L3)

**Files:**
- Modify: `src/huion_keydial_mini/keybind_manager.py` (constructor, `_load_initial_bindings` → store-backed, `_cmd_*`), `src/huion_keydial_mini/device.py` (construct ProfileStore and pass it in), `src/huion_keydial_mini/keydialctl.py` (replace duplicated validation with `validation` module; add `profile` command group)
- Test: `tests/test_manager_persistence.py`

**Interfaces:**
- Consumes: `ProfileStore` (Task 4), `validation` (Task 2), IPC v2 (Task 5)
- Produces:
  - `KeybindManager.__init__(self, config: Config, socket_path: Optional[str] = None, profile_store: Optional[ProfileStore] = None, event_bus: Optional[object] = None)` — when `profile_store` is None, behavior falls back to legacy in-memory mode (keeps old tests valid)
  - New socket commands: `list_profiles` → `{profiles: […], active: str}`; `switch_profile {name}`; `create_profile {name, clone_from?}`; `delete_profile {name}`
  - `set_binding`/`remove_binding`/`clear_all` now validate via `validation` and persist through the store when present
  - `KeybindManager.switch_profile(name: str) -> None` (also used by Task 7 events and Phase 2)
  - CLI: `keydialctl profile list|switch|create|delete`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_manager_persistence.py
import asyncio
import pytest
from huion_keydial_mini.config import Config
from huion_keydial_mini.keybind_manager import KeybindManager, send_command
from huion_keydial_mini.profile_store import ProfileStore


@pytest.fixture()
def rig(tmp_path):
    cfg = Config.load(None)
    store = ProfileStore(config_dir=tmp_path / "cfg")
    store.ensure_initialized()
    mgr = KeybindManager(cfg, socket_path=str(tmp_path / "s.sock"), profile_store=store)
    return cfg, store, mgr


def run_cmds(mgr, *cmds):
    async def go():
        await mgr.start_socket_server()
        try:
            return [await send_command(mgr.socket_path, c) for c in cmds]
        finally:
            await mgr.stop_socket_server()
    return asyncio.run(go())


def test_set_binding_persists_across_restart(rig, tmp_path):  # audit H5
    cfg, store, mgr = rig
    (resp,) = run_cmds(mgr, {"command": "set_binding", "action_id": "BUTTON_1",
                             "action": {"type": "keyboard", "keys": ["KEY_F5"]}})
    assert resp["status"] == "success"
    mgr2 = KeybindManager(cfg, socket_path=str(tmp_path / "s2.sock"), profile_store=store)
    assert mgr2.get_action("BUTTON_1").keys == ["KEY_F5"]


def test_server_rejects_garbage(rig):  # audit L3
    _, _, mgr = rig
    bad_id, bad_key = run_cmds(
        mgr,
        {"command": "set_binding", "action_id": "bogus_id",
         "action": {"type": "keyboard", "keys": ["KEY_F1"]}},
        {"command": "set_binding", "action_id": "BUTTON_1",
         "action": {"type": "keyboard", "keys": ["KEY_BOGUS"]}},
    )
    assert bad_id["status"] == "error"
    assert bad_key["status"] == "error"


def test_profile_commands(rig):
    _, store, mgr = rig
    r_create, r_list, r_switch = run_cmds(
        mgr,
        {"command": "create_profile", "name": "Krita"},
        {"command": "list_profiles"},
        {"command": "switch_profile", "name": "Krita"},
    )
    assert r_create["status"] == "success"
    assert set(r_list["profiles"]) == {"Default", "Krita"}
    assert r_switch["status"] == "success"
    assert store.get_active() == "Krita"


def test_switch_profile_swaps_bindings(rig):
    _, store, mgr = rig
    run_cmds(mgr, {"command": "set_binding", "action_id": "BUTTON_1",
                   "action": {"type": "keyboard", "keys": ["KEY_A"]}})
    store.create_profile("Empty")
    mgr.switch_profile("Empty")
    assert mgr.get_action("BUTTON_1") is None
    mgr.switch_profile("Default")
    assert mgr.get_action("BUTTON_1").keys == ["KEY_A"]
```

- [ ] **Step 2: Run to fail** — `.venv/bin/pytest tests/test_manager_persistence.py -v` — Expected: FAIL (`__init__` has no `profile_store`)

- [ ] **Step 3: Implement.** In `keybind_manager.py`:

```python
    def __init__(self, config: Config, socket_path: Optional[str] = None,
                 profile_store=None, event_bus=None):
        self.config = config
        self.socket_path = socket_path or self._get_default_socket_path()
        self.profile_store = profile_store
        self.event_bus = event_bus
        self.keybind_map: Dict[str, KeybindAction] = {}
        self.server: Optional[asyncio.AbstractServer] = None
        if self.profile_store is not None:
            self.keybind_map = self.profile_store.load_bindings()
            logger.info("Loaded %d bindings from profile %r",
                        len(self.keybind_map), self.profile_store.get_active())
        else:
            self._load_initial_bindings()      # legacy in-memory mode

    def switch_profile(self, name: str) -> None:
        if self.profile_store is None:
            raise RuntimeError("No profile store attached")
        self.profile_store.set_active(name)
        self.keybind_map = self.profile_store.load_bindings()
        if self.event_bus is not None:
            self.event_bus.publish({"type": "profile_changed", "name": name})
        logger.info("Switched to profile %r (%d bindings)", name, len(self.keybind_map))
```

`_cmd_set_binding` gains validation + persistence (same pattern for remove/clear):

```python
    async def _cmd_set_binding(self, command):
        from .validation import normalize_action_id, validate_keys, ValidationError
        action_id = command.get("action_id")
        action_data = command.get("action")
        if not action_id or not action_data:
            return {"status": "error", "message": "Missing action_id or action"}
        try:
            action_id = normalize_action_id(str(action_id))
            action = KeybindAction.from_dict(action_data)
            action.keys = validate_keys(action.keys or [])
        except (ValidationError, KeyError, ValueError) as e:
            return {"status": "error", "message": "Invalid binding: %s" % e}
        self.keybind_map[action_id] = action
        if self.profile_store is not None:
            self.profile_store.save_binding(action_id, action)
        self._publish_bindings_changed()
        return {"status": "success", "message": "Binding %s updated" % action_id}

    def _publish_bindings_changed(self):
        if self.event_bus is not None and self.profile_store is not None:
            self.event_bus.publish({"type": "bindings_changed",
                                    "profile": self.profile_store.get_active()})
```

`_process_command` dispatch gains:

```python
            elif cmd_type == 'list_profiles':
                if self.profile_store is None:
                    return {'status': 'error', 'message': 'Profiles unavailable'}
                return {'status': 'success',
                        'profiles': self.profile_store.list_profiles(),
                        'active': self.profile_store.get_active()}
            elif cmd_type == 'switch_profile':
                self.switch_profile(str(command.get('name')))
                return {'status': 'success', 'message': 'Switched profile'}
            elif cmd_type == 'create_profile':
                self.profile_store.create_profile(str(command.get('name')),
                                                  command.get('clone_from'))
                return {'status': 'success', 'message': 'Profile created'}
            elif cmd_type == 'delete_profile':
                self.profile_store.delete_profile(str(command.get('name')))
                return {'status': 'success', 'message': 'Profile deleted'}
```

(wrap the dispatch in `except (ProfileError, ValidationError, RuntimeError) as e: return {'status': 'error', 'message': str(e)}` — import `ProfileError` lazily inside the method to avoid the module cycle).

In `device.py.__init__`, build the store and pass it (constructor injection avoids the import cycle — `profile_store` imports `keybind_manager`, never the reverse at module level):

```python
        from .profile_store import ProfileStore
        self.profile_store = ProfileStore()
        self.profile_store.ensure_initialized(legacy_config=config)
        self.keybind_manager = KeybindManager(config, profile_store=self.profile_store)
```

In `keydialctl.py`: delete BOTH copies of the inline `valid_buttons`/combo-validation blocks in `bind`/`unbind` and call `validation.normalize_action_id` (echo `ValidationError` message + exit 1 on failure); add the profile group:

```python
@cli.group()
def profile():
    """Manage binding profiles."""


@profile.command("list")
def profile_list():
    resp = asyncio.run(send_command(get_socket_path(), {"command": "list_profiles"}))
    if resp["status"] != "success":
        click.echo("Error: %s" % resp["message"], err=True); sys.exit(1)
    for name in resp["profiles"]:
        marker = "*" if name == resp["active"] else " "
        click.echo(" %s %s" % (marker, name))


@profile.command("switch")
@click.argument("name")
def profile_switch(name):
    resp = asyncio.run(send_command(get_socket_path(),
                                    {"command": "switch_profile", "name": name}))
    click.echo(resp.get("message", resp["status"]))
    if resp["status"] != "success":
        sys.exit(1)


@profile.command("create")
@click.argument("name")
@click.option("--clone-from", default=None)
def profile_create(name, clone_from):
    resp = asyncio.run(send_command(get_socket_path(),
                                    {"command": "create_profile", "name": name,
                                     "clone_from": clone_from}))
    click.echo(resp.get("message", resp["status"]))
    if resp["status"] != "success":
        sys.exit(1)


@profile.command("delete")
@click.argument("name")
def profile_delete(name):
    resp = asyncio.run(send_command(get_socket_path(),
                                    {"command": "delete_profile", "name": name}))
    click.echo(resp.get("message", resp["status"]))
    if resp["status"] != "success":
        sys.exit(1)
```

- [ ] **Step 4: Run** — `.venv/bin/pytest tests/ -q` — Expected: ALL PASS (legacy KeybindManager tests keep passing via the no-store fallback)

- [ ] **Step 5: Commit** — `git add -A && git commit -m "persist bindings through ProfileStore and add profile commands

Runtime binds survive restarts (audit H5); socket validates action ids
and key names server-side (L3); keydialctl gains a profile group.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 7: EventBus + `subscribe_events` stream

**Files:**
- Create: `src/huion_keydial_mini/event_bus.py`
- Modify: `src/huion_keydial_mini/keybind_manager.py` (`_maybe_stream` real implementation), `src/huion_keydial_mini/device.py` (create bus; publish key events + device state)
- Test: `tests/test_event_bus.py`

**Interfaces:**
- Produces (Phase 2's WS bridge consumes the same bus):
  - `class EventBus:` `subscribe(self, maxsize: int = 64) -> asyncio.Queue` · `unsubscribe(self, queue) -> None` · `publish(self, event: Dict[str, Any]) -> None` (non-blocking; on a full queue drops the OLDEST item)
  - Socket: `{"command": "subscribe_events"}` → response line `{"v":2,"status":"success","message":"subscribed"}` then one JSON event per line until the client disconnects
  - Event shapes: `{"type":"key_event","action_id":str,"pressed":bool}` · `{"type":"device_state","connected":bool,"battery":Optional[int]}` · `{"type":"profile_changed","name":str}` · `{"type":"bindings_changed","profile":str}`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_event_bus.py
import asyncio
import json
import pytest
from huion_keydial_mini.event_bus import EventBus
from huion_keydial_mini.keybind_manager import KeybindManager
from huion_keydial_mini.config import Config


def test_pub_sub_and_drop_oldest():
    async def go():
        bus = EventBus()
        q = bus.subscribe(maxsize=2)
        for i in range(4):
            bus.publish({"n": i})
        got = [q.get_nowait()["n"], q.get_nowait()["n"]]
        assert got == [2, 3]              # oldest dropped
        bus.unsubscribe(q)
        bus.publish({"n": 99})            # no crash after unsubscribe
    asyncio.run(go())


def test_subscribe_events_streams(tmp_path):
    async def go():
        bus = EventBus()
        mgr = KeybindManager(Config.load(None),
                             socket_path=str(tmp_path / "s.sock"), event_bus=bus)
        await mgr.start_socket_server()
        try:
            reader, writer = await asyncio.open_unix_connection(mgr.socket_path)
            writer.write(b'{"command": "subscribe_events"}\n')
            await writer.drain()
            ack = json.loads(await reader.readline())
            assert ack["status"] == "success"
            bus.publish({"type": "key_event", "action_id": "BUTTON_1", "pressed": True})
            event = json.loads(await asyncio.wait_for(reader.readline(), timeout=2))
            assert event == {"type": "key_event", "action_id": "BUTTON_1", "pressed": True}
            writer.close()
            await writer.wait_closed()
        finally:
            await mgr.stop_socket_server()
    asyncio.run(go())
```

- [ ] **Step 2: Run to fail** — `.venv/bin/pytest tests/test_event_bus.py -v` — Expected: FAIL (module missing)

- [ ] **Step 3: Implement**

```python
# src/huion_keydial_mini/event_bus.py
"""In-process pub/sub for driver events (socket stream now, WebSocket in Phase 2)."""
import asyncio
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self):
        self._queues: List[asyncio.Queue] = []

    def subscribe(self, maxsize: int = 64) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._queues.append(q)
        return q

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        try:
            self._queues.remove(queue)
        except ValueError:
            pass

    def publish(self, event: Dict[str, Any]) -> None:
        for q in list(self._queues):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()            # drop oldest
                    q.put_nowait(event)
                except Exception:
                    pass
```

`keybind_manager._maybe_stream` becomes:

```python
    async def _maybe_stream(self, command, response, writer):
        if command.get("command") != "subscribe_events":
            return False
        if self.event_bus is None:
            await self._reply(writer, {"status": "error",
                                       "message": "Events unavailable"})
            return True
        await self._reply(writer, {"status": "success", "message": "subscribed"})
        queue = self.event_bus.subscribe()
        try:
            while True:
                event = await queue.get()
                writer.write((json.dumps(event) + "\n").encode("utf-8"))
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            self.event_bus.unsubscribe(queue)
        return True
```

`device.py` wiring: create `self.event_bus = EventBus()` in `__init__`, pass it to `KeybindManager(…, event_bus=self.event_bus)`; in `_handle_notification` publish after parsing:

```python
                for event in events:
                    await self.uinput_handler.send_event(event)
                    self.event_bus.publish({
                        "type": "key_event",
                        "action_id": event.key_code,
                        "pressed": event.event_type == ParserEventType.KEY_PRESS,
                    })
```

(import the parser's enum as `from .hid_parser import EventType as ParserEventType`), and publish `{"type": "device_state", "connected": True/False, "battery": None}` from `_on_device_connected_via_dbus` success / `_detach_from_device` (battery wired in Task 8).

- [ ] **Step 4: Run** — `.venv/bin/pytest tests/test_event_bus.py tests/ -q` — Expected: ALL PASS

- [ ] **Step 5: Commit** — `git add -A && git commit -m "add event bus with socket event streaming

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 8: Device identity filter, FFE1-targeted subscription, battery, any-adapter (audit H2, M9; DEVICE-K20 §F)

**Files:**
- Modify: `src/huion_keydial_mini/bluetooth_watcher.py`, `src/huion_keydial_mini/device.py`
- Test: `tests/test_device_identity.py`

**Interfaces:**
- Produces:
  - `BluetoothWatcher` callbacks now receive `(mac: str, name: Optional[str])`; watcher accepts any `/org/bluez/*/dev_*` path (hci0/hci1/…); keeps a reference set for created tasks
  - `bluetooth_watcher.get_device_name(bus, device_path: str) -> Optional[str]` — D-Bus `Get org.bluez.Device1 Alias`
  - `device.HuionKeydialMini._should_attach(mac: str, name: Optional[str]) -> bool` — pure function: config address match wins; else case-insensitive `keydial`/`huion` in name; unknown name → False
  - `device.VENDOR_EVENT_CHAR = "0000ffe1-0000-1000-8000-00805f9b34fb"`, `device.BATTERY_CHAR = "00002a19-0000-1000-8000-00805f9b34fb"` — `_start_notifications` subscribes ONLY to these (falls back to all-notify with a warning if FFE1 absent)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_device_identity.py
import pytest
from huion_keydial_mini.config import Config
from huion_keydial_mini.device import HuionKeydialMini
from huion_keydial_mini.bluetooth_watcher import BluetoothWatcher


def make_device(address=None):
    cfg = Config.load(None)
    if address:
        cfg.set_device_address(address)
    return HuionKeydialMini(cfg)


def test_attach_by_configured_mac_only():
    dev = make_device("20:23:06:01:8A:B0")
    assert dev._should_attach("20:23:06:01:8a:b0", "Anything") is True
    assert dev._should_attach("AA:AA:AA:AA:AA:AA", "Keydial mini-504") is False


def test_auto_discover_requires_huion_name():  # audit H2
    dev = make_device()
    assert dev._should_attach("20:23:06:01:8A:B0", "Keydial mini-504") is True
    assert dev._should_attach("20:23:06:01:8A:B0", "HUION something") is True
    assert dev._should_attach("EA:A8:9A:EA:9D:DE", "BT5.0 KB") is False
    assert dev._should_attach("E8:EE:CC:D9:D6:77", None) is False


def test_watcher_accepts_any_adapter():  # audit M9
    w = BluetoothWatcher()
    assert w._is_device_path("/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF")
    assert w._is_device_path("/org/bluez/hci1/dev_20_23_06_01_8A_B0")
    assert not w._is_device_path("/org/bluez/hci1")
    assert not w._is_device_path("/other/path/dev_AA_BB_CC_DD_EE_FF")
```

- [ ] **Step 2: Run to fail** — `.venv/bin/pytest tests/test_device_identity.py -v` — Expected: FAIL (no `_should_attach` / `_is_device_path`)

- [ ] **Step 3: Implement.** `bluetooth_watcher.py`:

```python
import re
_DEVICE_PATH_RE = re.compile(r"^/org/bluez/[^/]+/dev_[A-F0-9_]+$")


async def get_device_name(bus, device_path):
    """Fetch org.bluez.Device1 Alias for a device path; None on any failure."""
    from dbus_next.message import Message
    try:
        reply = await bus.call(Message(
            destination="org.bluez", path=device_path,
            interface="org.freedesktop.DBus.Properties", member="Get",
            signature="ss", body=["org.bluez.Device1", "Alias"]))
        if reply and reply.body:
            variant = reply.body[0]
            return variant.value if hasattr(variant, "value") else str(variant)
    except Exception as e:
        logger.debug("Could not fetch device name for %s: %s", device_path, e)
    return None


class BluetoothWatcher:
    def _is_device_path(self, path):
        return bool(path and _DEVICE_PATH_RE.match(path))
```

In `_handle_message` replace the `startswith("/org/bluez/hci0/dev_")` check with `self._is_device_path(object_path)`; keep created tasks alive:

```python
        self._tasks = getattr(self, "_tasks", set())
        task = asyncio.create_task(
            self._handle_device_property_change(object_path, mac_address, changed_properties))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
```

`_handle_device_property_change(self, device_path, mac_address, changed_properties)` fetches the name before invoking callbacks: `name = await get_device_name(self.bus, device_path)` and calls `self.on_connect_callback(mac_address, name)` / disconnect likewise. `device.py`:

```python
    VENDOR_EVENT_CHAR = "0000ffe1-0000-1000-8000-00805f9b34fb"
    BATTERY_CHAR = "00002a19-0000-1000-8000-00805f9b34fb"

    def _should_attach(self, mac_address: str, name: Optional[str]) -> bool:
        configured = self.config.device_address
        if configured:
            return mac_address.upper() == configured.upper()
        if not name:
            return False
        lowered = name.lower()
        return "keydial" in lowered or "huion" in lowered

    async def _on_device_connected_via_dbus(self, mac_address: str, name=None):
        if not self._should_attach(mac_address, name):
            logger.debug("Ignoring non-Huion device %s (%r)", mac_address, name)
            return
        # …existing connect flow unchanged, plus on success:
        # self.event_bus.publish({"type": "device_state", "connected": True,
        #                         "battery": await self._read_battery()})
```

`_start_notifications` targeted subscription:

```python
        wanted = {self.VENDOR_EVENT_CHAR: self._handle_notification,
                  self.BATTERY_CHAR: self._handle_battery}
        found = []
        for service in self.client.services:
            for char in service.characteristics:
                handler = wanted.get(char.uuid.lower())
                if handler and "notify" in char.properties:
                    try:
                        await self.client.start_notify(char, handler)
                        found.append(char.uuid)
                    except Exception as e:
                        logger.warning("Notify failed for %s: %s", char.uuid, e)
        if self.VENDOR_EVENT_CHAR not in [u.lower() for u in found]:
            logger.warning("Vendor event characteristic FFE1 not found — "
                           "falling back to all notify characteristics")
            # keep the old subscribe-everything loop here as fallback

    async def _handle_battery(self, sender, data: bytearray):
        if data:
            self.event_bus.publish({"type": "device_state", "connected": True,
                                    "battery": int(data[0])})

    async def _read_battery(self) -> Optional[int]:
        try:
            value = await self.client.read_gatt_char(self.BATTERY_CHAR)
            return int(value[0]) if value else None
        except Exception:
            return None
```

`_on_device_disconnected_via_dbus(self, mac_address: str, name=None)` gains the name param (unused) and publishes `{"type": "device_state", "connected": False, "battery": None}` after detach.

- [ ] **Step 4: Run** — `.venv/bin/pytest tests/test_device_identity.py tests/ -q` — Expected: ALL PASS

- [ ] **Step 5: Commit** — `git add -A && git commit -m "attach only to Huion devices and target FFE1 notifications

Name/MAC identity filter (audit H2), any-adapter D-Bus paths (M9),
FFE1+battery targeted subscription per DEVICE-K20.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 9: uinput lifecycle — async open, close on stop, device-free list-keys (audit H6, M10)

**Files:**
- Modify: `src/huion_keydial_mini/uinput_handler.py`, `src/huion_keydial_mini/device.py`, `src/huion_keydial_mini/keydialctl.py` (`list_keys`)
- Test: `tests/test_uinput_lifecycle.py`

**Interfaces:**
- Produces:
  - `UInputHandler.__init__` no longer opens the device (no retry loop, returns instantly)
  - `async UInputHandler.start(self, retries: int = 10, delay: float = 0.5) -> None` — creates the UInput via `loop.run_in_executor`, `asyncio.sleep` between attempts, raises `RuntimeError` after exhaustion
  - `UInputHandler.close(self) -> None` — idempotent
  - `keydialctl list-keys` reads `keymap.SUPPORTED_KEYS` only (no UInputHandler instantiation)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_uinput_lifecycle.py
import asyncio
import pytest
from unittest.mock import patch, MagicMock
from huion_keydial_mini.config import Config
from huion_keydial_mini.uinput_handler import UInputHandler


def test_constructor_does_not_open_device():
    with patch("huion_keydial_mini.uinput_handler.UInput") as mock_uinput:
        UInputHandler(Config.load(None))
        mock_uinput.assert_not_called()


def test_start_retries_then_succeeds():
    handler = UInputHandler(Config.load(None))
    attempts = {"n": 0}

    def flaky(*a, **k):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise PermissionError("uinput busy")
        return MagicMock()

    with patch("huion_keydial_mini.uinput_handler.UInput", side_effect=flaky):
        asyncio.run(handler.start(retries=5, delay=0.01))
    assert attempts["n"] == 3
    assert handler.device is not None


def test_start_raises_after_exhaustion():
    handler = UInputHandler(Config.load(None))
    with patch("huion_keydial_mini.uinput_handler.UInput",
               side_effect=PermissionError("no access")):
        with pytest.raises(RuntimeError):
            asyncio.run(handler.start(retries=2, delay=0.01))


def test_close_is_idempotent():
    handler = UInputHandler(Config.load(None))
    handler.device = MagicMock()
    handler.close()
    handler.close()
    assert handler.device is None


def test_list_keys_never_touches_uinput():
    from click.testing import CliRunner
    from huion_keydial_mini.keydialctl import cli
    with patch("huion_keydial_mini.uinput_handler.UInput") as mock_uinput:
        result = CliRunner().invoke(cli, ["list-keys"])
        assert result.exit_code == 0
        assert "KEY_F1" in result.output
        mock_uinput.assert_not_called()
```

- [ ] **Step 2: Run to fail** — `.venv/bin/pytest tests/test_uinput_lifecycle.py -v` — Expected: FAIL (constructor opens device / no `start`/`close`)

- [ ] **Step 3: Implement.** `uinput_handler.py` — delete `_try_open_device` and the `time` import; constructor ends with `self.device = None`; add:

```python
    async def start(self, retries: int = 10, delay: float = 0.5) -> None:
        """Create the virtual device without blocking the event loop (audit H6)."""
        loop = asyncio.get_event_loop()
        last_error = None
        for attempt in range(retries):
            try:
                self.device = await loop.run_in_executor(
                    None, lambda: UInput(events=self.capabilities,
                                         name=self.config.uinput_device_name))
                logger.info("Opened uinput device %r", self.config.uinput_device_name)
                return
            except Exception as e:
                last_error = e
                logger.info("uinput not ready (attempt %d/%d): %s",
                            attempt + 1, retries, e)
                await asyncio.sleep(delay)
        raise RuntimeError("Could not open uinput device after %d attempts: %s"
                           % (retries, last_error))

    def close(self) -> None:
        if self.device is not None:
            try:
                self.device.close()
            except Exception as e:
                logger.warning("Error closing uinput device: %s", e)
            self.device = None
```

(reinstate `import asyncio` at the top — it was flagged unused before, now it's used). `device.py`: in `start()` add `await self.uinput_handler.start()` right after the socket server starts; in `stop()` replace the dead `if self.uinput_handler: pass` with `self.uinput_handler.close()`. `keydialctl.list_keys`: delete `config`/`UInputHandler` usage; `from .keymap import SUPPORTED_KEYS` and iterate `SUPPORTED_KEYS` with the existing grouping logic (the group filters take the same list; keep output format identical).

- [ ] **Step 4: Run** — `.venv/bin/pytest tests/test_uinput_lifecycle.py tests/ -q` — Expected: ALL PASS

- [ ] **Step 5: Commit** — `git add -A && git commit -m "make uinput lifecycle async and closeable

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 10: Dial detent accumulator + parser fixes (audit M5, M6, L6, L9)

**Files:**
- Modify: `src/huion_keydial_mini/hid_parser.py`, `src/huion_keydial_mini/device.py` (`_detach_from_device` calls full reset)
- Test: `tests/test_parser_fixes.py`

**Interfaces:**
- Produces:
  - Sensitivity semantics: an accumulator emits `int(accumulated × sensitivity)` press/release pairs — `0.5` skips every other detent, `2.0` doubles, `1.0` unchanged
  - `_get_button_names_from_data` scans type-1 bytes **2–7**
  - `HIDParser.reset_state()` clears ALL state: `previous_state`, `peak_buttons_this_session`, `key_event_triggered`, `active_sticky_buttons`, `active_sticky_actions`, dial accumulator
  - Line `from ast import Continue` removed

- [ ] **Step 1: Write the failing test**

```python
# tests/test_parser_fixes.py
import pytest
from huion_keydial_mini.config import Config
from huion_keydial_mini.hid_parser import HIDParser


def make_parser(sensitivity=1.0):
    cfg = Config.load(None)
    cfg.data["dial_settings"]["sensitivity"] = sensitivity
    return HIDParser(cfg)


def dial_cw(count=1):
    return bytearray([0xF1, 0x00, count, 0x00, 0, 0, 0, 0, 0])


def press(*scancodes):
    data = bytearray(8)
    for i, code in enumerate(scancodes):
        data[2 + i] = code
    return data


def release_all():
    return bytearray(8)


def count_presses(events):
    from huion_keydial_mini.hid_parser import EventType
    return sum(1 for e in events if e.event_type == EventType.KEY_PRESS)


def test_sensitivity_half_skips_alternate_detents():  # audit M5
    parser = make_parser(0.5)
    total = sum(count_presses(parser.parse(dial_cw(1))) for _ in range(4))
    assert total == 2


def test_sensitivity_double():
    parser = make_parser(2.0)
    assert count_presses(parser.parse(dial_cw(1))) == 2


def test_full_byte_window_sees_first_key_slot():  # audit M6
    parser = make_parser()
    parser.parse(press(0x0E))            # scancode in byte 2 (first array slot)
    events = parser.parse(release_all())
    assert any(e.key_code == "BUTTON_1" for e in events)


def test_four_key_chord_all_detected():
    parser = make_parser()
    parser.parse(press(0x0E, 0x0A, 0x0F, 0x0C))     # bytes 2..5
    events = parser.parse(release_all())
    combo = [e.key_code for e in events if e.key_code and "+" in e.key_code]
    assert combo and set(combo[0].split("+")) == {
        "BUTTON_1", "BUTTON_2", "BUTTON_3", "BUTTON_5"}


def test_reset_state_clears_everything():  # audit L9
    parser = make_parser()
    parser.parse(press(0x0E))
    parser.reset_state()
    assert parser.previous_state == {}
    assert parser.peak_buttons_this_session == set()
    assert parser.active_sticky_buttons == set()
    assert parser.active_sticky_actions == {}
    assert parser.key_event_triggered is False


def test_no_ast_import():
    import huion_keydial_mini.hid_parser as m
    assert not hasattr(m, "Continue")
```

- [ ] **Step 2: Run to fail** — `.venv/bin/pytest tests/test_parser_fixes.py -v` — Expected: FAIL on sensitivity/byte-window/reset assertions

- [ ] **Step 3: Implement.** In `hid_parser.py`: delete line 3 (`from ast import Continue`); add `self._dial_accum = 0.0` in `__init__`; change the type-1 scan `for i in range(3, 6):` to `for i in range(2, 8):`; replace the steps computation in `_parse_dial_events`:

```python
                sensitivity = self.config.dial_settings.get('sensitivity', 1.0)
                try:
                    sensitivity = float(sensitivity)
                except (TypeError, ValueError):
                    sensitivity = 1.0
                self._dial_accum += movement * sensitivity
                steps = int(self._dial_accum)
                self._dial_accum -= steps
```

and extend `reset_state`:

```python
    def reset_state(self):
        """Reset ALL parser state (called on device disconnect)."""
        self.previous_state = {}
        self.peak_buttons_this_session = set()
        self.key_event_triggered = False
        self.active_sticky_buttons = set()
        self.active_sticky_actions = {}
        self._dial_accum = 0.0
        logger.debug("Parser state reset")
```

In `device.py._detach_from_device` add `self.hid_parser.reset_state()`.

**Compatibility check:** `tests/test_hid_parser.py` and `tests/test_combo_hid_parser.py` place scancodes at bytes 3–5, which remain inside the 2–7 window — they must still pass unchanged. If any existing test placed a *non-scancode* marker byte at 2, 6, or 7, it will now be looked up in the scancode table; the table has no entries below 0x05, so `0x00–0x04` markers stay inert. Run the full suite to confirm.

- [ ] **Step 4: Run** — `.venv/bin/pytest tests/test_parser_fixes.py tests/ -q` — Expected: ALL PASS

- [ ] **Step 5: Commit** — `git add -A && git commit -m "fix dial sensitivity semantics and widen parser key window

Detent accumulator makes sensitivity <1.0 meaningful (audit M5); type-1
scan covers bytes 2-7 (M6); reset_state clears all state and runs on
disconnect (L9); drop stray ast import (L6).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 11: Packaging repair — systemd, udev, pyproject, version (audit H1, M1, M4, L7)

**Files:**
- Modify: `packaging/systemd/huion-keydial-mini-user.service`, `packaging/udev/99-huion-keydial-mini.rules`, `pyproject.toml`, `src/huion_keydial_mini/__init__.py`, `Makefile` (drop phantom uninstall line)
- Test: `tests/test_packaging_meta.py`

**Interfaces:**
- Produces: a unit that starts out of the box; udev rules matching real hardware names; `huion_keydial_mini.__version__` derived from installed metadata.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_packaging_meta.py
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_no_phantom_entry_point():
    text = (ROOT / "pyproject.toml").read_text()
    assert "create_uinput_device" not in text          # audit M1


def test_version_single_source():
    import huion_keydial_mini
    text = (ROOT / "pyproject.toml").read_text()
    pyproject_version = re.search(r'^version = "([^"]+)"', text, re.M).group(1)
    assert huion_keydial_mini.__version__ == pyproject_version   # audit L7


def test_systemd_unit_sane():                          # audit H1
    unit = (ROOT / "packaging/systemd/huion-keydial-mini-user.service").read_text()
    assert "%i" not in unit
    assert "ProtectSystem" not in unit
    assert "Restart=on-failure" in unit


def test_udev_rules_match_real_device_names():         # audit M4
    rules = (ROOT / "packaging/udev/99-huion-keydial-mini.rules").read_text()
    assert '"Huion Keydial Mini"' not in rules
    assert "*Keydial*" in rules
```

- [ ] **Step 2: Run to fail** — `.venv/bin/pytest tests/test_packaging_meta.py -v` — Expected: FAIL on all four

- [ ] **Step 3: Implement.** Replace the systemd unit body entirely:

```ini
[Unit]
Description=Huion Keydial Mini Driver
After=bluetooth.target

[Service]
Type=simple
ExecStart=/usr/bin/huion-keydial-mini
Restart=on-failure
RestartSec=2
NoNewPrivileges=true

[Install]
WantedBy=default.target
```

udev rules — change the two exact-name lines to wildcard and fix the missing comma:

```
# Allow user access to huion keydial mini input devices
KERNEL=="event*", SUBSYSTEM=="input", ATTRS{name}=="*Keydial*", TAG+="uaccess"
# Ensure the keydial is not treated as a tablet
KERNEL=="event*", SUBSYSTEM=="input", ATTRS{name}=="*Keydial*", ENV{ID_INPUT_TABLET}="0"
```

`pyproject.toml`: delete the `create-huion-keydial-uinput-device = …` script line; author placeholder cleanup is Task 12. `Makefile`: delete the `rm -f /usr/bin/create-huion-keydial-uinput-device` line. `src/huion_keydial_mini/__init__.py`:

```python
"""Huion Keydial Mini user-space driver."""
try:
    from importlib.metadata import version, PackageNotFoundError
except ImportError:                                   # Python 3.7 fallback path
    from importlib_metadata import version, PackageNotFoundError

try:
    __version__ = version("huion-keydial-mini-driver")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"
```

- [ ] **Step 4: Run** — `.venv/bin/pytest tests/test_packaging_meta.py tests/ -q` — Expected: ALL PASS

- [ ] **Step 5: Commit** — `git add -A && git commit -m "repair systemd unit, udev rules, and version sourcing

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"`

---

### Task 12: Truth pass — docs, spec amendment, test hygiene, dead code (audit M2, M3, L5, L8 partials, §4, §5)

**Files:**
- Modify: `README.md`, `CONTRIBUTING.md`, `tests/README.md`, `tests/conftest.py`, `docs/superpowers/specs/2026-07-19-keydial-commander-design.md`, `docs/ROADMAP.md`, `docs/WORKLOG.md`, `src/huion_keydial_mini/event_logger.py`, `src/huion_keydial_mini/main.py`, misc dead-code removals
- Test: existing suite + `tests/test_cli.py`

**Interfaces:** none new — this task closes the phase.

- [ ] **Step 1: Write the failing CLI test**

```python
# tests/test_cli.py
"""README examples must actually work (audit M2)."""
from click.testing import CliRunner
from huion_keydial_mini.keydialctl import cli


def test_bind_takes_two_args_and_fails_cleanly_without_service(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))   # no socket there
    result = CliRunner().invoke(cli, ["bind", "BUTTON_1", "KEY_F1"])
    assert "Error" in result.output
    assert result.exit_code == 1          # clean error, not usage crash


def test_bind_rejects_invalid_button():
    result = CliRunner().invoke(cli, ["bind", "BUTTON_99", "KEY_F1"])
    assert result.exit_code == 1
    assert "Invalid" in result.output


def test_readme_uses_correct_bind_syntax():
    from pathlib import Path
    readme = Path(__file__).resolve().parent.parent / "README.md"
    assert "bind BUTTON_1 keyboard KEY_F1" not in readme.read_text()
```

- [ ] **Step 2: Run to fail** — `.venv/bin/pytest tests/test_cli.py -v` — Expected: `test_readme_uses_correct_bind_syntax` FAILS (and possibly the first if bind validation drifted)

- [ ] **Step 3: Apply the sweep**

1. **README.md**: fix every `keydialctl bind` example to two-argument form (`keydialctl bind BUTTON_1 KEY_F1`, `keydialctl bind --sticky BUTTON_1 KEY_LEFTCTRL`, `keydialctl bind DIAL_CW KEY_VOLUMEUP`); delete the "Mouse movement: X/Y relative movement support" and "Mouse scroll" bullets and the "Combo Actions (future enhancement)" claim, replacing with: "Mouse buttons (`BTN_LEFT`, …) can be bound like keys. Mouse movement/scroll and mixed-type actions arrive with Keydial Commander Phase 2."; document `keydialctl profile list|switch|create|delete`; document that bindings persist per-profile automatically.
2. **CONTRIBUTING.md**: replace `pip install -r requirements.txt` with `pip install -e ".[test]"`; delete references to `debug_parser.py`, `tests/run_tests.py`, `make test-simple`, and the "run with sudo" testing advice.
3. **tests/README.md**: delete the obsolete report-format tables; point to `docs/DEVICE-K20.md`.
4. **conftest.py**: dial fixture keys become real ones (`DIAL_CW`/`DIAL_CCW`/`DIAL_CLICK`); `KeybindManager` fixtures pass `socket_path=str(tmp_path / "test.sock")`; add a comment on `INVALID_DATA` explaining 0xFF bytes decode as modifier bits 13/14/15.
5. **event_logger.py**: replace the stale `--test` sample data with current formats (`dial_cw(1)`-style frames and 8-byte key frames as in `tests/test_parser_fixes.py`); delete the duplicated `_extract_handle_from_uuid`.
6. **main.py**: remove the unused `--user` flag; replace the `while self.running: await asyncio.sleep(1)` poll with an `asyncio.Event` awaited until the signal handler sets it.
7. **Dead code removals** (audit §4, all verified call-free): `hid_parser._extract_handle_from_uuid`, `_should_check_combo_mapping` (inline `True` at its one call site), `bluetooth_watcher._mac_to_dbus_path`, `device.py` unused HID constants + `ALTERNATIVE_HID_SERVICES` + `reconnect_attempts`/`max_reconnect_attempts`, `config.scan_timeout`/`reconnect_attempts` properties, unused imports across all modules (keep `Config.validate`/`get_effective_config` — Phase 2 API uses them).
8. **pyproject.toml**: move `pyyaml` from `dependencies` to the `test` extra (runtime no longer imports it; tests' conftest does); fix author placeholder to `Earl` + repo URLs to `the3dcoder/KeydialCommander`.
9. **Spec amendment** (`docs/superpowers/specs/2026-07-19-keydial-commander-design.md` §4): change "`active_profile` pointer in `config.yaml`" to "`profiles/active` pointer file (single-writer ProfileStore; deviation recorded in Phase 1 plan)".
10. **docs/ROADMAP.md**: tick every completed Phase 1 checkbox; move the `scan_devices` socket-command bullet from Phase 1 to Phase 2 with the note "(deferred: consumed by the GUI pairing screen; BLE scanning has no CLI consumer)"; **docs/WORKLOG.md**: add a dated Phase 1 completion entry listing audit IDs closed — include L2, which is closed structurally: ProfileStore migration splits dial values on `+` (Task 4), and profile-backed loading replaces the legacy non-splitting path.

- [ ] **Step 4: Full suite** — `.venv/bin/pytest tests/ -q` — Expected: ALL PASS. Then run the daemon smoke test manually: `.venv/bin/python -m huion_keydial_mini --log-level DEBUG` for ~10 s — expect "Driver started successfully", socket created under `$XDG_RUNTIME_DIR/huion-keydial-mini/` with mode 0600, no tracebacks; Ctrl+C exits within 1 s.

- [ ] **Step 5: Commit + merge**

```bash
git add -A
git commit -m "docs truth pass, test hygiene, and dead code sweep

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
git checkout main
git merge --no-ff feat/phase1-driver-hardening -m "merge Phase 1 driver hardening"
```

(Present the merged result to the user before pushing anywhere.)

---

## Verification checklist (whole phase)

- [ ] `.venv/bin/pytest tests/ -q` fully green
- [ ] `keydialctl bind BUTTON_1 KEY_F1` → restart daemon → `keydialctl list-bindings` still shows it (H5 closed)
- [ ] `keydialctl clear-device` on a config with an address actually clears it (H4 closed)
- [ ] Config comments survive `set-device` (H3 closed)
- [ ] Daemon attaches to "Keydial mini-504" on **hci1** with no address configured, ignores other BLE devices (H2, M9 closed)
- [ ] `keydialctl list-keys` runs instantly with no uinput device created (M10 closed)
- [ ] With the real device: live `subscribe_events` stream shows key_event lines when pressing keys (foundation for GUI identify mode)
