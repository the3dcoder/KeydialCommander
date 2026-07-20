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
