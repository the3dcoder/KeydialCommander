"""README examples must actually work (audit M2)."""
from pathlib import Path
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
    readme = Path(__file__).resolve().parent.parent / "README.md"
    assert "bind BUTTON_1 keyboard KEY_F1" not in readme.read_text()
