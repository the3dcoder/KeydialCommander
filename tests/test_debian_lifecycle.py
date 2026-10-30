"""Exercise maintscripts without contacting any host service manager."""
import importlib.util
import subprocess
from pathlib import Path

import pytest

MODULE = Path(__file__).parents[1] / 'packaging/debian/lifecycle.py'


def load():
    assert MODULE.exists(), 'Package lifecycle safety helper is missing'
    spec = importlib.util.spec_from_file_location('debian_lifecycle', MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Managers:
    def __init__(self, marker, *, fail_stop=False, fail_query=False, dropins=''):
        self.marker = marker
        self.fail_stop = fail_stop
        self.fail_query = fail_query
        self.dropins = dropins
        self.calls = []
        self.states = {'1000': 'active', '1001': 'active', '1002': 'inactive'}

    def __call__(self, args):
        self.calls.append(args)
        assert self.marker.exists(), 'Maintenance barrier must precede service operations'
        if 'list-units' in args:
            out = '\n'.join('user@%s.service loaded active running User Manager' % uid for uid in self.states)
        elif 'show' in args:
            uid = args[args.index('--machine') + 1].rstrip('@')
            if self.fail_query:
                raise RuntimeError('manager unavailable')
            fragment = ('/home/test/.config/systemd/user/' if uid == '1001' else '/usr/lib/systemd/user/') + 'huion-keydial-mini-user.service'
            out = 'LoadState=loaded\nActiveState=%s\nFragmentPath=%s\nDropInPaths=%s\n' % (self.states[uid], fragment, self.dropins)
        elif 'stop' in args:
            uid = args[args.index('--machine') + 1].rstrip('@')
            assert uid != '1001', 'User-local preview must be preserved'
            if not self.fail_stop:
                self.states[uid] = 'inactive'
            out = ''
        else:
            raise AssertionError('Unexpected command: %r' % args)
        return subprocess.CompletedProcess(args, 0, out, '')


def host(module, tmp_path, monkeypatch):
    marker = tmp_path / 'run/keydial-commander/maintenance'
    monkeypatch.setattr(module, 'MARKER', marker)
    monkeypatch.setattr(module, 'running_host', lambda: True)
    return marker


def test_upgrade_stops_only_active_vendor_units_before_unpack(tmp_path, monkeypatch):
    module = load()
    marker = host(module, tmp_path, monkeypatch)
    managers = Managers(marker)
    module.maintain('preinst', 'upgrade', Path('/'), managers)
    assert managers.states == {'1000': 'inactive', '1001': 'active', '1002': 'inactive'}
    assert marker.exists()
    assert sum('stop' in call for call in managers.calls) == 1
    assert not any(set(call) & {'start', 'enable', 'preset', 'restart'} for call in managers.calls)


@pytest.mark.parametrize('failure', ['fail_stop', 'fail_query'])
def test_failure_blocks_file_replacement_and_keeps_barrier(tmp_path, monkeypatch, failure):
    module = load()
    marker = host(module, tmp_path, monkeypatch)
    with pytest.raises(RuntimeError):
        module.maintain('preinst', 'upgrade', Path('/'), Managers(marker, **{failure: True}))
    assert marker.exists()


def test_upgrade_preserves_vendor_unit_with_user_dropin(tmp_path, monkeypatch):
    module = load()
    marker = host(module, tmp_path, monkeypatch)
    managers = Managers(marker, dropins='/home/test/.config/systemd/user/' + module.UNIT + '.d/override.conf')
    with pytest.raises(RuntimeError, match='custom|override|drop-in'):
        module.maintain('preinst', 'upgrade', Path('/'), managers)
    assert managers.states['1000'] == 'active'
    assert not any('stop' in call for call in managers.calls)


def test_foreign_root_never_contacts_host_and_preserves_profiles(tmp_path):
    module = load()
    profile = tmp_path / 'home/test/.config/huion-keydial-mini/profiles/test.json'
    profile.parent.mkdir(parents=True)
    profile.write_bytes(b'USER PROFILE')
    def forbidden(args):
        pytest.fail('Foreign-root maintscript contacted host: %r' % args)
    for script, action in [('preinst', 'install'), ('postinst', 'configure'), ('prerm', 'remove'), ('postrm', 'remove'), ('postrm', 'purge')]:
        module.maintain(script, action, tmp_path, forbidden)
    assert profile.read_bytes() == b'USER PROFILE'
    assert not (tmp_path / 'run/keydial-commander/maintenance').exists()


@pytest.mark.parametrize(('script', 'action'), [('postinst', 'abort-upgrade'), ('postinst', 'abort-remove'), ('postrm', 'abort-install'), ('postrm', 'abort-upgrade')])
def test_abort_clears_barrier_without_starting_service(tmp_path, monkeypatch, script, action):
    module = load()
    marker = host(module, tmp_path, monkeypatch)
    marker.parent.mkdir(parents=True)
    marker.touch()
    def forbidden(args):
        pytest.fail('Abort must not start remapping: %r' % args)
    module.maintain(script, action, Path('/'), forbidden)
    assert not marker.exists()
