"""Configuration management for the Huion Keydial Mini driver."""

import io
import os
from typing import Optional, Dict, Any
from pathlib import Path

from ruamel.yaml import YAML

from .validation import validate_mac

_yaml = YAML(typ="rt")  # round-trip mode: preserves comments and ordering
_yaml.preserve_quotes = True


class Config:
    """Configuration class for the driver."""

    def __init__(self, data: Dict[str, Any], doc=None, source_path: Optional[Path] = None):
        self.data = self._validate_config_data(data)
        # Preserve all top-level keys for global options
        self._global = {k: v for k, v in data.items() if k not in self.data}
        # The original parsed document (ruamel CommentedMap) — the save target
        self._doc = doc if doc is not None else {}
        self.source_path = source_path

    def _validate_config_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize configuration data."""
        # Ensure all required sections exist
        validated: Dict[str, Dict[str, Any]] = {
            'device': {},
            'bluetooth': {},
            'uinput': {},
            'key_mappings': {},
            'sticky_key_mappings': {},
            'dial_settings': {},
            'api': {},
        }

        # Copy and validate each section
        for section in validated.keys():
            if section in data and isinstance(data[section], dict):
                validated[section] = data[section].copy()
            elif section in data:
                # Convert non-dict values to empty dict for safety
                validated[section] = {}

        return validated

    @property
    def device_address(self) -> Optional[str]:
        """Get the Bluetooth device address."""
        address = self.data.get('device', {}).get('address')
        return str(address) if address is not None else None

    @property
    def device_name(self) -> str:
        """Get the expected device name."""
        name = self.data.get('device', {}).get('name', 'Huion Keydial Mini')
        return str(name)

    @property
    def connection_timeout(self) -> float:
        """Get the connection timeout in seconds."""
        timeout = self.data.get('bluetooth', {}).get('connection_timeout', 30.0)
        try:
            return float(timeout)
        except (TypeError, ValueError):
            return 30.0

    @property
    def uinput_device_name(self) -> str:
        """Get the uinput device name."""
        name = self.data.get('uinput', {}).get('device_name', 'keydial-commander-uinput')
        return str(name)

    @property
    def api_port(self) -> int:
        """Get the Commander API port (default 8137)."""
        port = self.data.get('api', {}).get('port', 8137)
        try:
            return int(port)
        except (TypeError, ValueError):
            return 8137

    @property
    def key_mappings(self) -> Dict[str, str]:
        """Get the key mappings configuration."""
        mappings = self.data.get('key_mappings', {})
        if not isinstance(mappings, dict):
            return {}
        # Ensure all keys and values are strings with proper type checking
        result: Dict[str, str] = {}
        for k, v in mappings.items():
            if isinstance(k, str) and isinstance(v, str) and v:
                result[k] = v
        return result

    @property
    def sticky_key_mappings(self) -> Dict[str, str]:
        """Get the sticky key mappings configuration."""
        mappings = self.data.get('sticky_key_mappings', {})
        if not isinstance(mappings, dict):
            return {}
        result: Dict[str, str] = {}
        for k, v in mappings.items():
            if isinstance(k, str) and isinstance(v, str) and v:
                result[k] = v
        return result

    @property
    def dial_settings(self) -> Dict[str, Any]:
        """Get the dial settings configuration."""
        settings = self.data.get('dial_settings', {})
        if not isinstance(settings, dict):
            return {}

        # Cast specific dial settings to appropriate types
        result: Dict[str, Any] = {}
        for key, value in settings.items():
            if not isinstance(key, str):
                continue

            if key == 'sensitivity':
                try:
                    result[key] = float(value) if value is not None else 1.0
                except (TypeError, ValueError):
                    result[key] = 1.0
            elif key in ['DIAL_CW', 'DIAL_CCW', 'DIAL_CLICK']:
                result[key] = str(value) if value is not None else None
            else:
                result[key] = value

        return result

    @property
    def debug_mode(self) -> bool:
        # Prefer top-level debug_mode, fallback to False
        return bool(self._global.get('debug_mode', False))

    @classmethod
    def load(cls, config_path: Optional[str] = None, device_address: Optional[str] = None) -> 'Config':
        """Load configuration from file or create default."""

        # Try to find config file
        if config_path:
            config_file = Path(config_path)
        else:
            # Look for config in standard locations
            config_locations = [
                Path.home() / '.config' / 'huion-keydial-mini' / 'config.yaml',
                Path('/etc/huion-keydial-mini/config.yaml'),
            ]

            config_file = None
            for location in config_locations:
                if location.exists():
                    config_file = location
                    break

        # Load config data (round-trip parse keeps comments for later save)
        doc = {}
        raw_data: Dict[str, Any] = {}
        if config_file and config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    loaded_data = _yaml.load(f)
                if loaded_data is not None and isinstance(loaded_data, dict):
                    doc = loaded_data
                    raw_data = dict(loaded_data)
            except Exception as e:
                # If config file is malformed, use defaults
                print(f"Warning: Error loading config file {config_file}: {e}")

        # Handle flat config structure mapping to nested structure
        if 'device_address' in raw_data:
            if 'device' not in raw_data:
                raw_data['device'] = {}
            raw_data['device']['address'] = raw_data.pop('device_address')

        if 'connection_timeout' in raw_data:
            if 'bluetooth' not in raw_data:
                raw_data['bluetooth'] = {}
            raw_data['bluetooth']['connection_timeout'] = raw_data.pop('connection_timeout')

        if 'uinput_device_name' in raw_data:
            if 'uinput' not in raw_data:
                raw_data['uinput'] = {}
            raw_data['uinput']['device_name'] = raw_data.pop('uinput_device_name')

        # Start with defaults and merge user data
        config_data = cls._get_default_config()
        config_data = cls._merge_config_data(config_data, raw_data)

        cfg = cls(config_data, doc=doc, source_path=config_file)
        # Apply command line override (validated)
        if device_address:
            cfg.set_device_address(device_address)
        return cfg

    @staticmethod
    def _merge_config_data(defaults: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Merge user configuration with defaults, ensuring proper types."""
        result = defaults.copy()

        for section, section_data in user_data.items():
            if section in result and isinstance(section_data, dict) and isinstance(result[section], dict):
                # Merge section data
                result[section].update(section_data)
            elif section_data is not None:
                # Replace entire section
                result[section] = section_data

        return result

    @staticmethod
    def _get_default_config() -> Dict[str, Any]:
        """Get the default configuration."""
        return {
            'device': {
                'name': 'Huion Keydial Mini',
                'address': None,
            },
            'bluetooth': {
                'scan_timeout': 10.0,
                'connection_timeout': 30.0,
                'reconnect_attempts': 3,
            },
            'uinput': {
                'device_name': 'keydial-commander-uinput',
            },
            'key_mappings': {},
            'sticky_key_mappings': {},
            'dial_settings': {},
        }

    def set_device_address(self, mac: Optional[str]) -> None:
        """Set (validated) or clear (None) the device address in view AND document."""
        value = validate_mac(mac) if mac is not None else None
        self.data.setdefault('device', {})['address'] = value
        if not isinstance(self._doc, dict):
            self._doc = {}
        self._doc.pop('device_address', None)  # legacy flat key
        device = self._doc.setdefault('device', {})
        device['address'] = value

    def save(self, config_path: Optional[str] = None):
        """Save configuration atomically, preserving comments and unknown keys."""
        target = Path(config_path) if config_path else self.source_path
        if target is None:
            target = Path.home() / '.config' / 'huion-keydial-mini' / 'config.yaml'
        target.parent.mkdir(parents=True, exist_ok=True)

        buf = io.StringIO()
        _yaml.dump(self._doc if self._doc else self.data, buf)
        tmp = target.with_name(target.name + '.tmp')
        tmp.write_text(buf.getvalue())
        os.replace(str(tmp), str(target))
        self.source_path = target

    def validate(self) -> bool:
        """Validate the current configuration."""
        try:
            # Test all property accessors to ensure they work
            _ = self.device_address
            _ = self.device_name
            _ = self.connection_timeout
            _ = self.uinput_device_name
            _ = self.key_mappings
            _ = self.sticky_key_mappings
            _ = self.dial_settings
            return True
        except Exception:
            return False

    def get_effective_config(self) -> Dict[str, Any]:
        """Get the effective configuration with all type casting applied."""
        return {
            'device': {
                'address': self.device_address,
                'name': self.device_name,
            },
            'bluetooth': {
                'connection_timeout': self.connection_timeout,
            },
            'uinput': {
                'device_name': self.uinput_device_name,
            },
            'key_mappings': self.key_mappings,
            'sticky_key_mappings': self.sticky_key_mappings,
            'dial_settings': self.dial_settings,
        }
