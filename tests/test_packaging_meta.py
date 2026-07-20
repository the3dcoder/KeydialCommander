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
    rules = (ROOT / "packaging/udev/70-huion-keydial-mini.rules").read_text()
    assert '"Huion Keydial Mini"' not in rules
    assert "*Keydial*" in rules


def test_uaccess_rule_numbered_below_seat_late():
    """uaccess tags must be applied before systemd's 73-seat-late.rules (so the
    rule file must sort < 73). The evdev architecture uses a single 70- rule and
    no unbind (99-) rule."""
    seventy = (ROOT / "packaging/udev/70-huion-keydial-mini.rules").read_text()
    assert 'TAG+="uaccess"' in seventy
    assert 'KERNEL=="uinput"' in seventy
    # the old hid-generic unbind rule is retired in the evdev architecture
    assert not (ROOT / "packaging/udev/99-huion-keydial-mini.rules").exists()
