import asyncio
import json
import os
import stat
import pytest
from huion_keydial_mini import ipc
from huion_keydial_mini.keybind_manager import KeybindManager, send_command
from huion_keydial_mini.config import Config


@pytest.fixture()
def manager(tmp_path):
    cfg = Config.load(None)
    return KeybindManager(cfg, socket_path=str(tmp_path / "test.sock"))


def test_runtime_dir_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    d = ipc.runtime_dir()
    assert d == tmp_path / "huion-keydial-mini"
    assert (d.stat().st_mode & 0o777) == 0o700
    assert ipc.socket_path() == str(d / "control.sock")


async def _roundtrip(manager, payloads):
    await manager.start_socket_server()
    try:
        results = []
        for p in payloads:
            results.append(await send_command(manager.socket_path, p))
        return results
    finally:
        await manager.stop_socket_server()


def test_v2_envelope_and_multiple_commands(manager):
    r1, r2 = asyncio.run(_roundtrip(manager, [
        {"command": "list_actions"},
        {"command": "get_bindings"},
    ]))
    assert r1["v"] == 2 and r1["status"] == "success"
    assert r2["v"] == 2 and "bindings" in r2


def test_large_command_not_truncated(manager):  # audit L1
    big_desc = "x" * 5000
    resp = asyncio.run(_roundtrip(manager, [{
        "command": "set_binding", "action_id": "BUTTON_1",
        "action": {"type": "keyboard", "keys": ["KEY_F1"], "description": big_desc},
    }]))[0]
    assert resp["status"] == "success"


def test_client_timeout(tmp_path):  # audit M8
    async def run():
        writers = []

        async def dead_handler(reader, writer):
            writers.append(writer)          # hold the connection open, never reply

        server = await asyncio.start_unix_server(
            dead_handler, path=str(tmp_path / "dead.sock"))
        try:
            return await send_command(str(tmp_path / "dead.sock"),
                                      {"command": "list_actions"}, timeout=0.3)
        finally:
            for w in writers:               # close server-side transports so
                w.close()                   # Server.wait_closed() can finish (3.12)
            server.close()
            await server.wait_closed()
    resp = asyncio.run(run())
    assert resp["status"] == "error"
    assert "timeout" in resp["message"].lower()


def test_socket_file_mode(manager):
    async def run():
        await manager.start_socket_server()
        mode = os.stat(manager.socket_path).st_mode
        await manager.stop_socket_server()
        return stat.S_IMODE(mode)
    assert asyncio.run(run()) == 0o600
