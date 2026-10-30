#!/usr/bin/env python3
"""Build a native binary deb from a trusted, validated Commander wheel.

No root, pip installation, service access or checkout at runtime is required.
"""
import argparse
import configparser
import email
import gzip
import re
import stat
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'huion-keydial-mini-driver'
SCRIPTS = {'huion-keydial-mini': 'huion_keydial_mini.main:main',
           'keydialctl': 'huion_keydial_mini.keydialctl:cli'}


def inspect_wheel(wheel):
    match = re.fullmatch(r'huion_keydial_mini_driver-(\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?)-py3-none-any\.whl', wheel.name)
    if not match:
        raise ValueError('Expected a versioned Commander py3-none-any wheel')
    version = match.group(1)
    dist = 'huion_keydial_mini_driver-' + version + '.dist-info'
    with ZipFile(wheel) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate wheel member')
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if (path.is_absolute() or '..' in path.parts or '\\' in info.filename
                    or not path.parts or path.parts[0] not in {'huion_keydial_mini', dist}
                    or stat.S_ISLNK(info.external_attr >> 16)):
                raise ValueError('Unexpected wheel path: ' + info.filename)
        try:
            metadata = email.message_from_bytes(archive.read(dist + '/METADATA'))
            layout = email.message_from_bytes(archive.read(dist + '/WHEEL'))
            entries = configparser.ConfigParser()
            entries.read_string(archive.read(dist + '/entry_points.txt').decode())
        except (KeyError, ValueError, configparser.Error) as error:
            raise ValueError('Missing or invalid wheel metadata') from error
        if metadata['Name'] != PACKAGE or metadata['Version'] != version:
            raise ValueError('Wheel metadata does not match its filename')
        if layout['Root-Is-Purelib'] != 'true' or layout.get_all('Tag') != ['py3-none-any']:
            raise ValueError('Only pure Python wheels are supported')
        if entries.sections() != ['console_scripts'] or dict(entries['console_scripts']) != SCRIPTS:
            raise ValueError('Unexpected wheel entry points')
        index = 'huion_keydial_mini/web/dist/index.html'
        if index not in names or not any(n.startswith('huion_keydial_mini/web/dist/assets/') and n.endswith('.js') for n in names):
            raise ValueError('Wheel is missing its built web UI')
    deb_version = re.sub(r'(a|b|rc)(\d+)$', r'~\1\2', version) + '-1'
    return version, deb_version


def build(wheel, output):
    wheel, output = Path(wheel), Path(output)
    version, deb_version = inspect_wheel(wheel)
    output.mkdir(parents=True, exist_ok=True)
    # GitHub changes '~' in asset names; keep Debian ordering in control metadata.
    result = output.resolve() / ('%s_%s-1_all.deb' % (PACKAGE, version))
    with tempfile.TemporaryDirectory(prefix='commander-deb-') as temporary:
        stage = Path(temporary)
        stage.chmod(0o755)

        def write(path, data, executable=False):
            target = stage / path.lstrip('/')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data.encode() if isinstance(data, str) else data)
            target.chmod(0o755 if executable else 0o644)

        def copy(source, destination, executable=False):
            write(destination, (ROOT / source).read_bytes(), executable)

        with ZipFile(wheel) as archive:
            for info in archive.infolist():
                if not info.is_dir():
                    write('/usr/lib/python3/dist-packages/' + info.filename, archive.read(info))
        for name, entry in SCRIPTS.items():
            module, function = entry.split(':')
            write('/usr/bin/' + name, '#!/usr/bin/python3\nfrom %s import %s\nif __name__ == "__main__":\n    raise SystemExit(%s())\n' % (module, function, function), True)
        copy('packaging/shell/keydial-commander', '/usr/bin/keydial-commander', True)
        for name in ['commander_shell.py', 'service_startup.py']:
            copy('packaging/shell/' + name, '/usr/share/keydial-commander/' + name)
        copy('packaging/systemd/huion-keydial-mini-user.service', '/usr/lib/systemd/user/huion-keydial-mini-user.service')
        copy('packaging/udev/70-huion-keydial-mini.rules', '/usr/lib/udev/rules.d/70-huion-keydial-mini.rules')
        write('/usr/lib/modules-load.d/keydial-commander.conf', 'uinput\n')
        copy('packaging/shell/icon.svg', '/usr/share/icons/hicolor/scalable/apps/keydial-commander.svg')
        desktop = (ROOT / 'packaging/shell/keydial-commander.desktop').read_text().replace('Exec=keydial-commander', 'Exec=/usr/bin/keydial-commander --start-service').replace('Icon=input-keyboard', 'Icon=keydial-commander')
        desktop += 'Actions=Stop;\n\n[Desktop Action Stop]\nName=Stop remapping\nExec=/usr/bin/keydial-commander --stop-service\n'
        write('/usr/share/applications/keydial-commander.desktop', desktop)
        docs = '/usr/share/doc/' + PACKAGE + '/'
        copy('LICENSE', docs + 'copyright')
        copy('docs/INSTALL.md', docs + 'INSTALL.md')
        notes = ROOT / ('docs/releases/' + version + '.md')
        if notes.exists():
            write(docs + 'RELEASE_NOTES.md', notes.read_bytes())
        write(docs + 'changelog.Debian.gz', gzip.compress((ROOT / 'packaging/debian/changelog').read_bytes(), mtime=0))
        size = sum(p.stat().st_size for p in stage.rglob('*') if p.is_file())
        control = (ROOT / 'packaging/debian/control').read_text().format(version=deb_version, installed_size=(size + 1023) // 1024)
        write('/DEBIAN/control', control)
        lifecycle = (ROOT / 'packaging/debian/lifecycle.py').read_text()
        for name in ['preinst', 'postinst', 'prerm', 'postrm']:
            entry = ('\nif __name__ == "__main__":\n'
                     '    try:\n'
                     '        maintain(%r, sys.argv[1], Path(os.environ.get("DPKG_ROOT") or "/"))\n'
                     '    except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:\n'
                     '        print("Commander package operation stopped: %%s" %% error, file=sys.stderr)\n'
                     '        sys.exit(1)\n') % name
            write('/DEBIAN/' + name, '#!/usr/bin/python3\n' + lifecycle + entry, True)
        subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(stage), str(result)], check=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheel', type=Path)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    print(build(args.wheel, args.output_dir))
