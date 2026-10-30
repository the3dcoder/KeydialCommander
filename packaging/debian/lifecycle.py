"""Self-contained Debian maintscript support; never import the application here.

Embedded into each maintscript by build_deb.py. Python is a Pre-Dependency.
Foreign-root dpkg operations must not address the host's running managers.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

PACKAGE = 'huion-keydial-mini-driver'
UNIT = 'huion-keydial-mini-user.service'
MARKER = Path('/run/keydial-commander/maintenance')
VENDOR_UNITS = {'/usr/lib/systemd/user/' + UNIT, '/lib/systemd/user/' + UNIT}


def run_command(args):
    result = subprocess.run(args, text=True, capture_output=True, timeout=20)
    if result.returncode:
        raise RuntimeError('%s failed: %s' % (' '.join(args), result.stderr.strip()))
    return result


def running_host():
    return Path('/run/systemd/system').is_dir()


def stop_managed(run):
    result = run(['systemctl', 'list-units', '--state=running', '--type=service',
                  '--no-legend', '--plain', '--no-pager', 'user@*.service'])
    for line in result.stdout.splitlines():
        match = re.match(r'user@(\d+)\.service\s', line.strip())
        if not match:
            continue
        uid = match.group(1)
        prefix = ['systemctl', '--user', '--machine', uid + '@']

        def properties():
            shown = run(prefix + ['show', UNIT, '--no-pager',
                                  '--property=FragmentPath,ActiveState,LoadState,DropInPaths'])
            values = dict(line.split('=', 1) for line in shown.stdout.splitlines() if '=' in line)
            if not {'LoadState', 'ActiveState', 'FragmentPath', 'DropInPaths'} <= values.keys():
                raise RuntimeError('Cannot inspect Commander for user %s; retry after checking that user manager.' % uid)
            return values

        values = properties()
        if values['LoadState'] == 'not-found' or values['FragmentPath'] not in VENDOR_UNITS:
            continue
        if values['ActiveState'] in {'inactive', 'failed'}:
            continue
        if values['DropInPaths']:
            raise RuntimeError('Commander for user %s has custom service drop-ins. Stop that customized unit manually, then retry; no files were replaced.' % uid)
        run(prefix + ['stop', UNIT])
        if properties()['ActiveState'] not in {'inactive', 'failed'}:
            raise RuntimeError('Commander for user %s did not stop. Files were not replaced; stop it and retry the package operation.' % uid)


def maintain(script, action, root=Path('/'), run=run_command):
    root = Path(root)
    foreign = root.resolve() != Path('/')
    marker = root / str(MARKER).lstrip('/') if foreign else MARKER
    entering = (script == 'preinst' and action in {'install', 'upgrade'}) or (
        script == 'prerm' and action in {'remove', 'upgrade', 'deconfigure'})
    finishing = (script == 'postinst' and action in {'configure', 'abort-upgrade', 'abort-remove', 'abort-deconfigure'}) or (
        script == 'postrm' and action in {'remove', 'purge', 'abort-install', 'abort-upgrade', 'disappear'})
    if entering:
        marker.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        marker.touch(mode=0o644)
        if not foreign and running_host():
            stop_managed(run)
        if script == 'prerm' and not foreign:
            run(['/usr/bin/py3clean', '-p', PACKAGE])
    if script == 'postinst' and action == 'configure' and not foreign:
        run(['/usr/bin/py3compile', '-p', PACKAGE])
        if Path('/run/udev/control').exists():
            run(['udevadm', 'control', '--reload-rules'])
        if Path('/sys/module').is_dir():
            # A failed optional module request must not leave apt half-configured.
            try:
                run(['modprobe', 'uinput'])
            except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
                print('Commander: uinput was not loaded; reconnect/reboot before starting: %s' % error, file=sys.stderr)
    if finishing:
        marker.unlink(missing_ok=True)
        try:
            marker.parent.rmdir()
        except OSError:
            pass
