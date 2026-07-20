import asyncio

from aiohttp.test_utils import TestServer, TestClient

from huion_keydial_mini.api_server import ApiServer
from huion_keydial_mini.action_engine import ActionEngine
from huion_keydial_mini.event_bus import EventBus
from huion_keydial_mini.profile_store import ProfileStore


class FakeUinput:
    def __init__(self):
        self.emitted = []

    async def emit_keys(self, keys):
        self.emitted.append(list(keys))


class FakeMgr:
    def get_action(self, aid):
        return None


def make(tmp_path):
    store = ProfileStore(config_dir=tmp_path)
    store.ensure_initialized()
    uinput = FakeUinput()
    engine = ActionEngine(FakeMgr(), uinput)
    bus = EventBus()
    api = ApiServer(keybind_manager=FakeMgr(), profile_store=store, event_bus=bus,
                    action_engine=engine, version="9.9.9")
    return api, uinput, bus


def test_test_fire_keystroke(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "rt"))
    api, uinput, bus = make(tmp_path)

    async def run():
        async with TestClient(TestServer(api.app)) as c:
            r = await c.post("/api/test-fire",
                             json={"action": {"type": "keystroke", "keys": ["KEY_F9"]}})
            assert r.status == 200
        assert uinput.emitted == [["KEY_F9"]]

    asyncio.run(run())


def test_test_fire_rejects_invalid(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "rt"))
    api, uinput, bus = make(tmp_path)

    async def run():
        async with TestClient(TestServer(api.app)) as c:
            r = await c.post("/api/test-fire",
                             json={"action": {"type": "keystroke", "keys": ["KEY_BOGUS"]}})
            assert r.status == 400

    asyncio.run(run())


def test_websocket_relays_events_and_unsubscribes(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "rt"))
    api, uinput, bus = make(tmp_path)

    async def run():
        async with TestClient(TestServer(api.app)) as c:
            ws = await c.ws_connect("/api/events")
            await asyncio.sleep(0.05)                 # let the server subscribe
            bus.publish({"type": "key_event", "action_id": "BUTTON_1", "pressed": True})
            msg = await asyncio.wait_for(ws.receive_json(), timeout=2)
            assert msg == {"type": "key_event", "action_id": "BUTTON_1", "pressed": True}
            await ws.close()
            await asyncio.sleep(0.05)                 # let the server unsubscribe
        assert bus._queues == []

    asyncio.run(run())
