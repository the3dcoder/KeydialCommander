"""Desktop startup uses fake systemd and HTTP boundaries, never real capture."""
import importlib.util
import subprocess
from pathlib import Path

import pytest

MODULE = Path(__file__).parents[1] / 'packaging/shell/service_startup.py'
UNIT = 'huion-keydial-mini-user.service'


def load():
    assert MODULE.exists(), 'Explicit desktop service startup is missing'
    spec = importlib.util.spec_from_file_location('service_startup', MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UserManager:
    def __init__(self, fragment='/usr/lib/systemd/user/' + UNIT, fail=None, dropins=''):
        self.fragment, self.fail, self.calls = fragment, fail, []
        self.dropins = dropins
    def __call__(self, args):
        self.calls.append(args)
        if self.fail in args:
            raise RuntimeError('systemd command failed')
        out = ''
        if 'show' in args:
            out = self.fragment + '\n' if '--value' in args else ('FragmentPath=%s\nDropInPaths=%s\n' % (self.fragment, self.dropins))
        return subprocess.CompletedProcess(args, 0, out, '')


def test_start_verifies_vendor_unit_and_api_before_opening(tmp_path):
    module, manager = load(), UserManager()
    port = tmp_path / 'port'
    port.write_text('9123')
    seen = []
    def status(url, timeout):
        seen.append((url, timeout))
        return {'service': {'version': '1.3.0a2'}}
    url = module.start_service('1.3.0a2', port_file=port, run=manager, read_status=status, legacy_rule=tmp_path / 'absent')
    assert url == 'http://127.0.0.1:9123/'
    assert seen[0][0] == url + 'api/status'
    assert 0 < seen[0][1] <= .5
    assert ['systemctl', '--user', 'start', UNIT] in manager.calls
    assert not any(set(call) & {'enable', 'preset', 'restart'} for call in manager.calls)


def test_local_preview_unit_is_not_started_or_deleted(tmp_path):
    module, manager = load(), UserManager('/home/test/.config/systemd/user/' + UNIT)
    with pytest.raises(module.StartupError, match='migration|user-local'):
        module.start_service('1.3.0a2', run=manager, legacy_rule=tmp_path / 'absent')
    assert not any('start' in args for args in manager.calls)


def test_local_execstart_dropin_requires_migration_before_start(tmp_path):
    module = load()
    manager = UserManager(dropins='/home/test/.config/systemd/user/' + UNIT + '.d/override.conf')
    with pytest.raises(module.StartupError, match='migration|override'):
        module.start_service('1.3.0a2', run=manager, legacy_rule=tmp_path / 'absent', read_status=lambda url, timeout: {'service': {'version': '1.3.0a2'}})
    assert not any('start' in args for args in manager.calls)


def test_legacy_unbind_rule_requires_migration(tmp_path):
    module, manager = load(), UserManager()
    rule = tmp_path / '99-huion-keydial-mini.rules'
    rule.write_text('legacy')
    with pytest.raises(module.StartupError, match='legacy|migration'):
        module.start_service('1.3.0a2', run=manager, legacy_rule=rule)
    assert rule.read_text() == 'legacy'
    assert not any('start' in args for args in manager.calls)


@pytest.mark.parametrize('text', ['0', '-1', '65536', 'http://other', 'no port'])
def test_invalid_advertised_port_is_rejected(tmp_path, text):
    module = load()
    port = tmp_path / 'port'
    port.write_text(text)
    with pytest.raises(module.StartupError, match='port'):
        module.service_url(port)


def test_version_mismatch_and_dead_listener_obey_deadline(tmp_path):
    module = load()
    for reply in [None, {'service': {'version': 'older'}}]:
        now = [0.0]
        def sleep(seconds):
            now[0] += seconds
        def status(url, timeout):
            if reply is None:
                raise ConnectionError('no listener')
            return reply
        with pytest.raises(module.StartupError, match='ready|version'):
            module.start_service('1.3.0a2', run=UserManager(), read_status=status, port_file=tmp_path / 'absent', legacy_rule=tmp_path / 'absent', clock=lambda: now[0], sleep=sleep, deadline=.3)
        assert now[0] <= .4


@pytest.mark.parametrize('operation', ['start', 'stop'])
def test_failed_systemd_action_is_reported(tmp_path, operation):
    module, manager = load(), UserManager(fail=operation)
    with pytest.raises(module.StartupError, match='systemd|service'):
        if operation == 'start':
            module.start_service('1.3.0a2', run=manager, legacy_rule=tmp_path / 'absent')
        else:
            module.stop_service(run=manager)


def test_stop_only_addresses_named_vendor_user_unit():
    module, manager = load(), UserManager()
    module.stop_service(run=manager)
    assert ['systemctl', '--user', 'stop', UNIT] in manager.calls
    assert not any('start' in args for args in manager.calls)
