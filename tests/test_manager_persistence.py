import asyncio
import pytest
from huion_keydial_mini.config import Config
from huion_keydial_mini.keybind_manager import KeybindManager, send_command
from huion_keydial_mini.profile_store import ProfileStore


@pytest.fixture()
def rig(tmp_path):
    cfg = Config.load(None)
    store = ProfileStore(config_dir=tmp_path / "cfg")
    store.ensure_initialized()
    mgr = KeybindManager(cfg, socket_path=str(tmp_path / "s.sock"), profile_store=store)
    return cfg, store, mgr


def run_cmds(mgr, *cmds):
    async def go():
        await mgr.start_socket_server()
        try:
            return [await send_command(mgr.socket_path, c) for c in cmds]
        finally:
            await mgr.stop_socket_server()
    return asyncio.run(go())


def test_set_binding_persists_across_restart(rig, tmp_path):  # audit H5
    cfg, store, mgr = rig
    (resp,) = run_cmds(mgr, {"command": "set_binding", "action_id": "BUTTON_1",
                             "action": {"type": "keyboard", "keys": ["KEY_F5"]}})
    assert resp["status"] == "success"
    mgr2 = KeybindManager(cfg, socket_path=str(tmp_path / "s2.sock"), profile_store=store)
    assert mgr2.get_action("BUTTON_1").keys == ["KEY_F5"]


def test_server_rejects_garbage(rig):  # audit L3
    _, _, mgr = rig
    bad_id, bad_key = run_cmds(
        mgr,
        {"command": "set_binding", "action_id": "bogus_id",
         "action": {"type": "keyboard", "keys": ["KEY_F1"]}},
        {"command": "set_binding", "action_id": "BUTTON_1",
         "action": {"type": "keyboard", "keys": ["KEY_BOGUS"]}},
    )
    assert bad_id["status"] == "error"
    assert bad_key["status"] == "error"


def test_profile_commands(rig):
    _, store, mgr = rig
    r_create, r_list, r_switch = run_cmds(
        mgr,
        {"command": "create_profile", "name": "Krita"},
        {"command": "list_profiles"},
        {"command": "switch_profile", "name": "Krita"},
    )
    assert r_create["status"] == "success"
    assert set(r_list["profiles"]) == {"Default", "Krita"}
    assert r_switch["status"] == "success"
    assert store.get_active() == "Krita"


def test_switch_profile_swaps_bindings(rig):
    _, store, mgr = rig
    run_cmds(mgr, {"command": "set_binding", "action_id": "BUTTON_1",
                   "action": {"type": "keyboard", "keys": ["KEY_A"]}})
    store.create_profile("Empty")
    mgr.switch_profile("Empty")
    assert mgr.get_action("BUTTON_1") is None
    mgr.switch_profile("Default")
    assert mgr.get_action("BUTTON_1").keys == ["KEY_A"]


def test_remove_and_clear_persist(rig, tmp_path):
    cfg, store, mgr = rig
    run_cmds(mgr,
             {"command": "set_binding", "action_id": "BUTTON_1",
              "action": {"type": "keyboard", "keys": ["KEY_A"]}},
             {"command": "remove_binding", "action_id": "BUTTON_1"})
    assert store.load_bindings() == {}
    run_cmds(mgr,
             {"command": "set_binding", "action_id": "BUTTON_2",
              "action": {"type": "keyboard", "keys": ["KEY_B"]}},
             {"command": "clear_all"})
    assert store.load_bindings() == {}
