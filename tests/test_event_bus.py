import asyncio
import json
from huion_keydial_mini.event_bus import EventBus
from huion_keydial_mini.keybind_manager import KeybindManager
from huion_keydial_mini.config import Config


def test_pub_sub_and_drop_oldest():
    async def go():
        bus = EventBus()
        q = bus.subscribe(maxsize=2)
        for i in range(4):
            bus.publish({"n": i})
        got = [q.get_nowait()["n"], q.get_nowait()["n"]]
        assert got == [2, 3]              # oldest dropped
        bus.unsubscribe(q)
        bus.publish({"n": 99})            # no crash after unsubscribe
    asyncio.run(go())


def test_subscribe_events_streams(tmp_path):
    async def go():
        bus = EventBus()
        mgr = KeybindManager(Config.load(None),
                             socket_path=str(tmp_path / "s.sock"), event_bus=bus)
        await mgr.start_socket_server()
        try:
            reader, writer = await asyncio.open_unix_connection(mgr.socket_path)
            writer.write(b'{"command": "subscribe_events"}\n')
            await writer.drain()
            ack = json.loads(await reader.readline())
            assert ack["status"] == "success"
            bus.publish({"type": "key_event", "action_id": "BUTTON_1", "pressed": True})
            event = json.loads(await asyncio.wait_for(reader.readline(), timeout=2))
            assert event == {"type": "key_event", "action_id": "BUTTON_1", "pressed": True}
            writer.close()
            await writer.wait_closed()
        finally:
            await mgr.stop_socket_server()
    asyncio.run(go())
