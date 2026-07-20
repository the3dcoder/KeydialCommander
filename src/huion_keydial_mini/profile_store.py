"""On-disk profile storage: one YAML per profile + an `active` pointer file.

Single writer for everything under <config_dir>/profiles/. Auto-persists
every mutation atomically (spec: no Save button anywhere).
"""
import io
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
    """Invalid profile operation (unknown name, last-profile delete, ...)."""


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
        self._path(name).unlink()

    def rename_profile(self, old: str, new: str) -> None:
        self._require(old)
        if not _PROFILE_NAME_RE.match(new or ""):
            raise ProfileError("Invalid profile name: %r" % new)
        if new in self.list_profiles():
            raise ProfileError("Profile already exists: %r" % new)
        was_active = self.get_active() == old
        self._path(old).rename(self._path(new))
        if was_active:
            self.set_active(new)

    def set_dial_sensitivity(self, value: float, profile: Optional[str] = None) -> None:
        name = profile or self.get_active()
        doc = self._read_profile(name)
        doc["dial_sensitivity"] = float(value)
        self._dump_profile(name, doc)

    def export_profile(self, name: str) -> str:
        """Return the raw profile YAML text."""
        self._require(name)
        return self._path(name).read_text()

    def import_profile(self, yaml_text: str, name: str) -> None:
        """Create a new profile from exported YAML (invalid bindings are skipped)."""
        from .validation import validate_action, normalize_action_id, ValidationError
        if not _PROFILE_NAME_RE.match(name or ""):
            raise ProfileError("Invalid profile name: %r" % name)
        if name in self.list_profiles():
            raise ProfileError("Profile already exists: %r" % name)
        try:
            doc = _yaml.load(yaml_text) or {}
        except Exception as e:
            raise ProfileError("Could not parse profile YAML: %s" % e)
        try:
            sensitivity = float(doc.get("dial_sensitivity", 1.0))
        except (TypeError, ValueError):
            sensitivity = 1.0
        self._write_profile(name, {}, sensitivity)
        for aid, raw in (doc.get("bindings") or {}).items():
            try:
                canonical = normalize_action_id(str(aid))
                validate_action(dict(raw))
            except (ValidationError, Exception) as e:
                logger.warning("Import: skipping binding %r: %s", aid, e)
                continue
            self.save_binding(canonical, KeybindAction.from_dict(dict(raw)), profile=name)

    # -- bindings -----------------------------------------------------------
    def load_bindings(self, profile: Optional[str] = None) -> Dict[str, KeybindAction]:
        name = profile or self.get_active()
        doc = self._read_profile(name)
        out: Dict[str, KeybindAction] = {}
        for action_id, raw in (doc.get("bindings") or {}).items():
            if not isinstance(raw, dict):
                continue
            out[str(action_id)] = KeybindAction.from_dict(dict(raw))
        return out

    def save_binding(self, action_id: str, action: KeybindAction,
                     profile: Optional[str] = None) -> None:
        name = profile or self.get_active()
        doc = self._read_profile(name)
        bindings = doc.setdefault("bindings", {})
        # Serialize by type, dropping empty/irrelevant fields for clean YAML.
        entry = action.to_dict()
        for k in ("description", "sticky", "keys", "steps", "argv", "profile"):
            if entry.get(k) in (None, False, [], ""):
                entry.pop(k, None)
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
        buf = io.StringIO()
        _yaml.dump(doc, buf)
        self._atomic_write(self._path(name), buf.getvalue())

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text)
        os.replace(str(tmp), str(path))
