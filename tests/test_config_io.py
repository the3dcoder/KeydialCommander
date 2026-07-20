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


def test_save_to_fresh_path(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("device: {address: null}\n")
    cfg = Config.load(str(p))
    cfg.save()
    assert Config.load(str(p)).device_address is None
