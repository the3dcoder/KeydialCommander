import asyncio

import pytest
from aiohttp.test_utils import TestServer, TestClient

from huion_keydial_mini.api_server import ApiServer, group_keys
from huion_keydial_mini.profile_store import ProfileStore


class FakeMgr:
    def get_action(self, aid):
        return None


def make_api(tmp_path):
    store = ProfileStore(config_dir=tmp_path)
    store.ensure_initialized()
    return ApiServer(keybind_manager=FakeMgr(), profile_store=store,
                     event_bus=None, action_engine=None, version="9.9.9")


def test_group_keys_categorizes():
    g = group_keys(["KEY_F1", "KEY_A", "KEY_1", "KEY_LEFTCTRL", "BTN_LEFT"])
    assert "KEY_F1" in g["Function"]
    assert "KEY_A" in g["Letters"]
    assert "BTN_LEFT" in g["Mouse"]


def test_status_keys_and_spa(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "rt"))
    api = make_api(tmp_path)

    async def run():
        async with TestClient(TestServer(api.app)) as client:
            r = await client.get("/api/status")
            body = await r.json()
            assert body["service"]["version"] == "9.9.9"
            assert body["active_profile"] == "Default"
            assert body["device"]["connected"] is False

            r = await client.get("/api/keys")
            assert "KEY_F1" in (await r.text())

            r = await client.get("/")
            text = await r.text()
            # Serves either the placeholder or the built SPA shell.
            assert r.status == 200 and ('id="root"' in text or "Keydial Commander" in text)

            r = await client.get("/some/spa/route")
            assert r.status == 200          # SPA fallback serves index

            r = await client.get("/api/nonexistent")
            assert r.status == 404          # unknown API path 404s

    asyncio.run(run())


def test_start_writes_port_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "rt"))
    api = make_api(tmp_path)
    api.port = 0  # let OS pick? TCPSite needs a real port; use a high test port instead
    api.port = 8231

    async def run():
        await api.start()
        from huion_keydial_mini import ipc
        assert (ipc.runtime_dir() / "port").read_text().strip() == "8231"
        await api.stop()
        assert not (ipc.runtime_dir() / "port").exists()

    asyncio.run(run())
