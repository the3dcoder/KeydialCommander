import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from huion_keydial_mini.config import Config
from huion_keydial_mini.input_events import InputEvent, EventType


@pytest.fixture()
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    return tmp_path


def test_device_dispatches_through_action_engine_and_bus(isolated_home):
    from huion_keydial_mini.device import HuionKeydialMini

    dev = HuionKeydialMini(Config.load(None))
    dev.action_engine.execute = AsyncMock()
    published = []
    dev.event_bus.publish = published.append

    ev = InputEvent(EventType.KEY_PRESS, "BUTTON_1")
    asyncio.run(dev._dispatch(ev))

    dev.action_engine.execute.assert_awaited_once_with(ev)
    assert {"type": "key_event", "action_id": "BUTTON_1", "pressed": True} in published


def test_start_stop_wires_evdev_source(isolated_home):
    with patch("huion_keydial_mini.evdev_source.EvdevSource.start", new=AsyncMock()) as m_start, \
         patch("huion_keydial_mini.evdev_source.EvdevSource.stop", new=AsyncMock()) as m_stop, \
         patch("huion_keydial_mini.uinput_handler.UInputHandler.start", new=AsyncMock()), \
         patch("huion_keydial_mini.api_server.ApiServer.start", new=AsyncMock()), \
         patch("huion_keydial_mini.api_server.ApiServer.stop", new=AsyncMock()), \
         patch("huion_keydial_mini.keybind_manager.KeybindManager.start_socket_server", new=AsyncMock()), \
         patch("huion_keydial_mini.keybind_manager.KeybindManager.stop_socket_server", new=AsyncMock()):
        from huion_keydial_mini.device import HuionKeydialMini
        dev = HuionKeydialMini(Config.load(None))
        dev.uinput_handler.close = MagicMock()

        asyncio.run(dev.start())
        assert dev.running is True
        m_start.assert_awaited_once()

        asyncio.run(dev.stop())
        assert dev.running is False
        m_stop.assert_awaited_once()


def test_on_state_publishes(isolated_home):
    from huion_keydial_mini.device import HuionKeydialMini
    dev = HuionKeydialMini(Config.load(None))
    published = []
    dev.event_bus.publish = published.append
    dev._on_state(True)
    dev._on_state(False)
    assert {"type": "device_state", "connected": True, "battery": None} in published
    assert {"type": "device_state", "connected": False, "battery": None} in published
