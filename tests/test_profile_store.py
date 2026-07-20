import pytest
from huion_keydial_mini.profile_store import ProfileStore, ProfileError
from huion_keydial_mini.keybind_manager import KeybindAction, EventType
from huion_keydial_mini.config import Config


def make_store(tmp_path):
    store = ProfileStore(config_dir=tmp_path)
    store.ensure_initialized()
    return store


def act(keys, sticky=False):
    return KeybindAction(type=EventType.KEYBOARD, keys=keys, sticky=sticky)


def test_initialization_creates_default(tmp_path):
    store = make_store(tmp_path)
    assert store.list_profiles() == ["Default"]
    assert store.get_active() == "Default"
    assert (tmp_path / "profiles" / "Default.yaml").exists()


def test_binding_round_trip_and_keystroke_type(tmp_path):
    store = make_store(tmp_path)
    store.save_binding("BUTTON_1", act(["KEY_LEFTCTRL", "KEY_Z"]))
    text = (tmp_path / "profiles" / "Default.yaml").read_text()
    assert "keystroke" in text            # spec: writes keystroke, not keyboard
    loaded = store.load_bindings()
    assert loaded["BUTTON_1"].keys == ["KEY_LEFTCTRL", "KEY_Z"]


def test_remove_and_clear(tmp_path):
    store = make_store(tmp_path)
    store.save_binding("BUTTON_1", act(["KEY_F1"]))
    store.remove_binding("BUTTON_1")
    assert store.load_bindings() == {}
    store.save_binding("BUTTON_2", act(["KEY_F2"]))
    store.clear_bindings()
    assert store.load_bindings() == {}


def test_profiles_create_switch_delete(tmp_path):
    store = make_store(tmp_path)
    store.save_binding("BUTTON_1", act(["KEY_F1"]))
    store.create_profile("Krita", clone_from="Default")
    assert sorted(store.list_profiles()) == ["Default", "Krita"]
    store.set_active("Krita")
    assert store.load_bindings()["BUTTON_1"].keys == ["KEY_F1"]   # cloned
    with pytest.raises(ProfileError):
        store.delete_profile("Krita")                              # active
    store.set_active("Default")
    store.delete_profile("Krita")
    with pytest.raises(ProfileError):
        store.delete_profile("Default")                            # last one


def test_migration_from_legacy_config(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "key_mappings:\n  BUTTON_1: \"KEY_F1\"\n"
        "sticky_key_mappings:\n  BUTTON_2: \"KEY_LEFTCTRL\"\n"
        "dial_settings:\n  DIAL_CW: \"KEY_VOLUMEUP\"\n  sensitivity: 2.0\n"
    )
    cfg = Config.load(str(cfg_file))
    store = ProfileStore(config_dir=tmp_path)
    store.ensure_initialized(legacy_config=cfg)
    b = store.load_bindings("Default")
    assert b["BUTTON_1"].keys == ["KEY_F1"]
    assert b["BUTTON_2"].sticky is True
    assert b["DIAL_CW"].keys == ["KEY_VOLUMEUP"]
    assert store.get_dial_sensitivity("Default") == 2.0
    # idempotent: second init must not duplicate/overwrite
    store.ensure_initialized(legacy_config=cfg)
    assert store.load_bindings("Default")["BUTTON_1"].keys == ["KEY_F1"]


def test_dial_chord_values_split_on_plus(tmp_path):  # audit L2
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text('dial_settings:\n  DIAL_CW: "KEY_LEFTCTRL+KEY_EQUAL"\n')
    cfg = Config.load(str(cfg_file))
    store = ProfileStore(config_dir=tmp_path)
    store.ensure_initialized(legacy_config=cfg)
    assert store.load_bindings("Default")["DIAL_CW"].keys == ["KEY_LEFTCTRL", "KEY_EQUAL"]


def test_unknown_profile_raises(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(ProfileError):
        store.set_active("Nope")
    with pytest.raises(ProfileError):
        store.load_bindings("Nope")
