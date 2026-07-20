import asyncio

from aiohttp.test_utils import TestServer, TestClient

from huion_keydial_mini.api_server import ApiServer
from huion_keydial_mini.profile_store import ProfileStore
from huion_keydial_mini.keybind_manager import KeybindManager
from huion_keydial_mini.config import Config


def make_api(tmp_path):
    store = ProfileStore(config_dir=tmp_path)
    store.ensure_initialized()
    mgr = KeybindManager(Config.load(None), socket_path=str(tmp_path / "s.sock"),
                         profile_store=store)
    return ApiServer(keybind_manager=mgr, profile_store=store, event_bus=None,
                     action_engine=None, version="9.9.9"), store, mgr


def test_profiles_and_bindings_crud(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "rt"))
    api, store, mgr = make_api(tmp_path)

    async def run():
        async with TestClient(TestServer(api.app)) as c:
            # create + list
            assert (await c.post("/api/profiles", json={"name": "Krita"})).status == 200
            names = [p["name"] for p in await (await c.get("/api/profiles")).json()]
            assert set(names) == {"Default", "Krita"}

            # activate Krita
            assert (await c.post("/api/profiles/Krita/activate")).status == 200
            assert store.get_active() == "Krita"

            # put a keystroke binding on the active profile -> live map updates
            r = await c.put("/api/profiles/Krita/bindings/BUTTON_1",
                            json={"type": "keystroke", "keys": ["KEY_F9"]})
            assert r.status == 200
            assert mgr.get_action("BUTTON_1").keys == ["KEY_F9"]

            # get bindings back
            body = await (await c.get("/api/profiles/Krita/bindings")).json()
            assert body["bindings"]["BUTTON_1"]["keys"] == ["KEY_F9"]

            # a macro binding
            r = await c.put("/api/profiles/Krita/bindings/BUTTON_2", json={
                "type": "macro",
                "steps": [{"keys": ["KEY_LEFTCTRL", "KEY_S"]}, {"delay_ms": 100}]})
            assert r.status == 200

            # invalid action -> 400
            r = await c.put("/api/profiles/Krita/bindings/BUTTON_3",
                            json={"type": "keystroke", "keys": ["KEY_BOGUS"]})
            assert r.status == 400

            # settings
            assert (await c.put("/api/profiles/Krita/settings",
                                json={"dial_sensitivity": 2.0})).status == 200
            assert store.get_dial_sensitivity("Krita") == 2.0

            # delete a binding
            assert (await c.delete("/api/profiles/Krita/bindings/BUTTON_1")).status == 200
            assert mgr.get_action("BUTTON_1") is None

            # export contains the macro; import round-trips into a new profile
            text = await (await c.get("/api/profiles/Krita/export")).text()
            assert "macro" in text
            assert (await c.post("/api/profiles/import",
                                 json={"name": "KritaCopy", "yaml": text})).status == 200
            copy = await (await c.get("/api/profiles/KritaCopy/bindings")).json()
            assert copy["bindings"]["BUTTON_2"]["type"] == "macro"
            assert copy["dial_sensitivity"] == 2.0

            # rename + delete
            assert (await c.put("/api/profiles/KritaCopy",
                                json={"new_name": "KritaCopy2"})).status == 200
            assert (await c.delete("/api/profiles/KritaCopy2")).status == 200

            # cannot delete active
            assert (await c.delete("/api/profiles/Krita")).status == 400

    asyncio.run(run())
