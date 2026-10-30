import asyncio

import pytest

from huion_keydial_mini.config import Config
from huion_keydial_mini.keybind_manager import KeybindManager, KeybindAction
from huion_keydial_mini.profile_store import ProfileStore, ProfileError


def rig(tmp_path):
    store = ProfileStore(tmp_path)
    store.ensure_initialized()
    store.save_binding('BUTTON_13', KeybindAction(keys=['KEY_LEFTCTRL']))
    manager = KeybindManager(Config({}), socket_path=str(tmp_path / 'unused'), profile_store=store)
    observed = []
    manager.on_bindings_changing = lambda: observed.append(manager.get_action('BUTTON_13').keys)
    return store, manager, observed


def test_effective_reload_invalidates_before_original_map_is_replaced(tmp_path):
    store, manager, observed = rig(tmp_path)
    store.save_binding('BUTTON_13', KeybindAction(keys=['KEY_LEFTSHIFT']))
    manager.reload_bindings()
    assert observed == [['KEY_LEFTCTRL']]
    assert manager.get_action('BUTTON_13').keys == ['KEY_LEFTSHIFT']


def test_description_only_and_identical_reload_preserve_interaction(tmp_path):
    store, manager, observed = rig(tmp_path)
    manager.reload_bindings()
    store.save_binding('BUTTON_13', KeybindAction(keys=['KEY_LEFTCTRL'], description='New label'))
    manager.reload_bindings()
    assert observed == []
    store.rename_profile('Default', 'Renamed')
    manager.reload_bindings()
    assert observed == []


def test_distinct_profile_switch_invalidates_even_matching_bindings(tmp_path):
    store, manager, observed = rig(tmp_path)
    store.create_profile('Copy', clone_from='Default')
    manager.switch_profile('Copy')
    manager.switch_profile('Copy')
    assert observed == [['KEY_LEFTCTRL']]


def test_invalid_switch_does_not_invalidate_or_change_active_profile(tmp_path):
    store, manager, observed = rig(tmp_path)
    with pytest.raises(ProfileError):
        manager.switch_profile('Missing')
    assert store.get_active() == 'Default' and observed == []


def test_ipc_persistence_failure_preserves_original_live_map(tmp_path, monkeypatch):
    store, manager, observed = rig(tmp_path)
    def fail(*args, **kwargs):
        raise OSError('simulated storage failure')
    monkeypatch.setattr(store, 'save_binding', fail)
    result = asyncio.run(manager._process_command({'command': 'set_binding',
        'action_id': 'BUTTON_13', 'action': {'keys': ['KEY_LEFTSHIFT']}}))
    assert result['status'] == 'error'
    assert manager.get_action('BUTTON_13').keys == ['KEY_LEFTCTRL']
    assert observed == []


@pytest.mark.parametrize('operation', ['set', 'remove', 'clear'])
def test_ipc_mutations_share_publication_boundary(tmp_path, operation):
    store, manager, observed = rig(tmp_path)
    command = {'command': {'set': 'set_binding', 'remove': 'remove_binding', 'clear': 'clear_all'}[operation],
               'action_id': 'BUTTON_13', 'action': {'keys': ['KEY_LEFTSHIFT']}}
    result = asyncio.run(manager._process_command(command))
    assert result['status'] == 'success'
    assert observed == [['KEY_LEFTCTRL']]


def test_public_mutation_helpers_share_boundary(tmp_path):
    _, manager, observed = rig(tmp_path)
    manager.set_action('BUTTON_13', KeybindAction(keys=['KEY_LEFTSHIFT']))
    manager.remove_action('BUTTON_13')
    assert observed == [['KEY_LEFTCTRL'], ['KEY_LEFTSHIFT']]


def test_invalid_ipc_action_is_rejected_before_persistence_or_cleanup(tmp_path):
    store, manager, observed = rig(tmp_path)
    result = asyncio.run(manager._process_command({'command': 'set_binding',
        'action_id': 'BUTTON_13',
        'action': {'type': 'command', 'keys': ['KEY_A'], 'argv': None}}))
    assert result['status'] == 'error'
    assert store.load_bindings()['BUTTON_13'].keys == ['KEY_LEFTCTRL']
    assert manager.get_action('BUTTON_13').keys == ['KEY_LEFTCTRL']
    assert observed == []


@pytest.mark.parametrize('action', [KeybindAction(type='unknown'),
    KeybindAction(type='macro', steps=[{'delay_ms': 'bad'}])])
def test_invalid_public_candidate_preserves_live_hold(tmp_path, action):
    _, manager, observed = rig(tmp_path)
    with pytest.raises(ValueError):
        manager.set_action('BUTTON_13', action)
    assert manager.get_action('BUTTON_13').keys == ['KEY_LEFTCTRL'] and observed == []


def test_invalid_profile_candidate_does_not_persist_active_name(tmp_path):
    store, manager, observed = rig(tmp_path)
    store.create_profile('Broken')
    # Storage accepts legacy action objects; switching must validate the candidate.
    store.save_binding('BUTTON_13', KeybindAction(type='unknown'), profile='Broken')
    with pytest.raises(ValueError):
        manager.switch_profile('Broken')
    assert store.get_active() == 'Default'
    assert manager.get_action('BUTTON_13').keys == ['KEY_LEFTCTRL'] and observed == []


def test_invalid_action_id_never_reaches_publication(tmp_path):
    _, manager, observed = rig(tmp_path)
    with pytest.raises(ValueError):
        manager.set_action('not-a-control', KeybindAction(keys=['KEY_A']))
    assert observed == [] and not manager.get_action('not-a-control')


def test_ipc_valid_macro_preserves_description_and_ignores_unused_fields(tmp_path):
    store, manager, observed = rig(tmp_path)
    result = asyncio.run(manager._process_command({'command': 'set_binding',
        'action_id': 'BUTTON_13', 'action': {'type': 'macro',
        'steps': [{'keys': ['KEY_A']}], 'description': 'Save'}}))
    assert result['status'] == 'success'
    assert store.load_bindings()['BUTTON_13'].description == 'Save'
    observed.clear()
    manager.set_action('BUTTON_13', KeybindAction(type='macro', keys=[],
        steps=[{'keys': ['KEY_A']}], description='Renamed'))
    assert observed == []


def test_invalid_initial_profile_is_rejected_before_device_start(tmp_path):
    store = ProfileStore(tmp_path)
    store.ensure_initialized()
    store.save_binding('BUTTON_1', KeybindAction(type='unknown'))
    with pytest.raises(ValueError):
        KeybindManager(Config({}), socket_path=str(tmp_path / 'unused'), profile_store=store)


def test_invalid_reload_retains_original_live_map(tmp_path):
    store, manager, observed = rig(tmp_path)
    store.save_binding('BUTTON_13', KeybindAction(type='macro', steps=[{'delay_ms': 'bad'}]))
    with pytest.raises(ValueError):
        manager.reload_bindings()
    assert manager.get_action('BUTTON_13').keys == ['KEY_LEFTCTRL'] and observed == []


def test_public_combo_replacement_and_removal_share_canonical_id(tmp_path):
    _, manager, _ = rig(tmp_path)
    manager.set_action('BUTTON_2+BUTTON_1', KeybindAction(keys=['KEY_A']))
    manager.set_action('BUTTON_2+BUTTON_1', KeybindAction(keys=['KEY_B']))
    assert manager.get_action('BUTTON_1+BUTTON_2').keys == ['KEY_B']
    assert manager.remove_action('BUTTON_2+BUTTON_1')
    assert not manager.get_action('BUTTON_1+BUTTON_2')
