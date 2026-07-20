"""Pytest configuration and common fixtures for huion-keydial-mini-driver tests."""

import pytest
import tempfile
import yaml
from pathlib import Path

from huion_keydial_mini.config import Config


@pytest.fixture
def sample_config_data():
    """Sample configuration data for testing."""
    return {
        'device': {
            'name': 'Huion Keydial Mini',
        },
        'bluetooth': {
            'connection_timeout': 30.0,
        },
        'uinput': {
            'device_name': 'Huion Keydial Mini',
        },
        'key_mappings': {
            'BUTTON_1': 'KEY_F1',
            'BUTTON_2': 'KEY_F2',
        },
        'dial_settings': {
            'sensitivity': 1.0,
            'DIAL_CW': 'KEY_VOLUMEUP',
            'DIAL_CCW': 'KEY_VOLUMEDOWN',
            'DIAL_CLICK': 'KEY_ENTER',
        },
        'debug_mode': True,
    }


@pytest.fixture
def temp_config_file(sample_config_data):
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(sample_config_data, f)
        temp_path = f.name
    yield temp_path
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def config(sample_config_data):
    """Create a Config instance for testing."""
    return Config(sample_config_data)
