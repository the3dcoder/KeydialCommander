"""Explicit desktop startup for the native package; no capture during install."""
import http.client
import json
import os
import subprocess
import time
from pathlib import Path

UNIT = 'huion-keydial-mini-user.service'
VENDOR_UNITS = {'/usr/lib/systemd/user/' + UNIT, '/lib/systemd/user/' + UNIT}
LEGACY_RULE = Path('/etc/udev/rules.d/99-huion-keydial-mini.rules')
HELP = ('Check: systemctl --user status ' + UNIT + '\n'
        'Logs: journalctl --user -u ' + UNIT + ' -n 50\n'
        'Installation/migration: https://github.com/the3dcoder/KeydialCommander/blob/main/docs/INSTALL.md')


class StartupError(RuntimeError):
    pass


def run_command(args):
    result = subprocess.run(args, text=True, capture_output=True, timeout=10)
    if result.returncode:
        raise StartupError('The user service command failed.\n' + HELP)
    return result


def service_url(port_file=None):
    if port_file is None:
        runtime = os.environ.get('XDG_RUNTIME_DIR')
        port_file = Path(runtime) / 'huion-keydial-mini/port' if runtime else None
    port = 8137
    if port_file is not None and Path(port_file).exists():
        try:
            port = int(Path(port_file).read_text().strip())
            if not 1 <= port <= 65535:
                raise ValueError('out of range')
        except (OSError, ValueError) as error:
            raise StartupError('Invalid Commander runtime port file.\n' + HELP) from error
    return 'http://127.0.0.1:%d/' % port


def read_status(url, timeout):
    # HTTPConnection does not use environment proxies or follow redirects.
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    connection = http.client.HTTPConnection('127.0.0.1', parsed.port, timeout=timeout)
    try:
        connection.request('GET', '/api/status')
        response = connection.getresponse()
        if response.status != 200:
            raise ConnectionError('Status endpoint returned %s' % response.status)
        body = response.read(65537)
        if len(body) > 65536:
            raise ValueError('Oversized status response')
        return json.loads(body)
    finally:
        connection.close()


def verify_vendor(run):
    run(['systemctl', '--user', 'daemon-reload'])
    shown = run(['systemctl', '--user', 'show', UNIT, '--property=FragmentPath,DropInPaths', '--no-pager'])
    values = dict(line.split('=', 1) for line in shown.stdout.splitlines() if '=' in line)
    if (values.get('FragmentPath') not in VENDOR_UNITS
            or 'DropInPaths' not in values or values['DropInPaths']):
        raise StartupError('Commander needs migration: a user-local service override or missing vendor unit prevents native startup. Preserve your profiles and follow the migration guide.\n' + HELP)


def start_service(expected_version, *, port_file=None, run=run_command,
                  read_status=read_status, legacy_rule=LEGACY_RULE,
                  clock=time.monotonic, sleep=time.sleep, deadline=10):
    try:
        if legacy_rule.exists():
            raise StartupError('A legacy unbind rule needs migration before Commander can start.\n' + HELP)
        verify_vendor(run)
        run(['systemctl', '--user', 'start', UNIT])
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        if isinstance(error, StartupError):
            raise
        raise StartupError('Could not start the Commander user service.\n' + HELP) from error
    end = clock() + deadline
    reason = 'service is not ready'
    while clock() < end:
        url = service_url(port_file)
        try:
            status = read_status(url + 'api/status', min(.5, max(.001, end - clock())))
            if status.get('service', {}).get('version') == expected_version:
                return url
            reason = 'API version does not match the installed package'
        except (OSError, ValueError, http.client.HTTPException, AttributeError):
            reason = 'service is not ready'
        sleep(min(.1, max(0, end - clock())))
    raise StartupError('Commander %s.\n%s' % (reason, HELP))


def stop_service(*, run=run_command):
    try:
        verify_vendor(run)
        run(['systemctl', '--user', 'stop', UNIT])
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        if isinstance(error, StartupError):
            raise
        raise StartupError('Could not stop the Commander user service.\n' + HELP) from error
