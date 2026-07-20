import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import aiohttp
import pytest

from huion_keydial_mini.config import Config


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "rt"))
    return tmp_path


def test_daemon_starts_and_serves_api(isolated):
    with patch("huion_keydial_mini.evdev_source.EvdevSource.start", new=AsyncMock()), \
         patch("huion_keydial_mini.evdev_source.EvdevSource.stop", new=AsyncMock()), \
         patch("huion_keydial_mini.uinput_handler.UInputHandler.start", new=AsyncMock()), \
         patch("huion_keydial_mini.keybind_manager.KeybindManager.start_socket_server", new=AsyncMock()), \
         patch("huion_keydial_mini.keybind_manager.KeybindManager.stop_socket_server", new=AsyncMock()):
        from huion_keydial_mini.device import HuionKeydialMini
        dev = HuionKeydialMini(Config.load(None))
        dev.uinput_handler.close = MagicMock()
        dev.api_server.port = 8231          # fixed test port

        async def run():
            await dev.start()
            from huion_keydial_mini import ipc
            assert (ipc.runtime_dir() / "port").read_text().strip() == "8231"
            async with aiohttp.ClientSession() as s:
                async with s.get("http://127.0.0.1:8231/api/status") as r:
                    body = await r.json()
                    assert body["service"]["version"]
                    assert body["active_profile"] == "Default"
            await dev.stop()
            assert not (ipc.runtime_dir() / "port").exists()

        asyncio.run(run())
