"""Build and extract real Debian archives; never install into the host."""
import email
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).parents[1]
VERSION = '1.3.0a2'
DIST = 'huion_keydial_mini_driver-' + VERSION + '.dist-info'


def builder():
    path = ROOT / 'packaging/debian/build_deb.py'
    assert path.exists(), 'Native wheel-fed Debian builder is missing'
    spec = importlib.util.spec_from_file_location('build_deb', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def wheel(tmp_path):
    path = tmp_path / ('huion_keydial_mini_driver-' + VERSION + '-py3-none-any.whl')
    with ZipFile(path, 'w') as z:
        package = ROOT / 'src/huion_keydial_mini'
        for file in package.rglob('*'):
            if file.is_file() and '__pycache__' not in file.parts and not file.is_relative_to(package / 'web/dist'):
                z.write(file, str(Path('huion_keydial_mini') / file.relative_to(package)))
        z.writestr('huion_keydial_mini/web/dist/index.html', '<!doctype html><script src="/assets/app.js"></script>')
        z.writestr('huion_keydial_mini/web/dist/assets/app.js', 'console.log("fixture")')
        z.writestr(DIST + '/METADATA', 'Metadata-Version: 2.1\nName: huion-keydial-mini-driver\nVersion: ' + VERSION + '\n')
        z.writestr(DIST + '/WHEEL', 'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n')
        z.writestr(DIST + '/entry_points.txt', '[console_scripts]\nhuion-keydial-mini = huion_keydial_mini.main:main\nkeydialctl = huion_keydial_mini.keydialctl:cli\n')
    return path


def test_build_native_archive_with_system_python_and_desktop_payload(wheel, tmp_path):
    deb = builder().build(wheel, tmp_path / 'output')
    # GitHub normalizes '~' to '.', so public filenames use the Python version.
    assert deb.name == 'huion-keydial-mini-driver_1.3.0a2-1_all.deb'
    control = email.message_from_string(subprocess.check_output(['dpkg-deb', '-f', str(deb)], text=True))
    assert control['Version'] == '1.3.0~a2-1'
    assert control['Maintainer'] == 'Earl <earl@bigbwain.com>'
    assert control['Architecture'] == 'all'
    for dependency in ['python3-evdev', 'python3-aiohttp', 'python3-ruamel.yaml', 'gir1.2-webkit2-4.1']:
        assert dependency in control['Depends']
    root = tmp_path / 'extract'
    subprocess.run(['dpkg-deb', '-x', str(deb), str(root)], check=True)
    library = root / 'usr/lib/python3/dist-packages'
    assert (library / DIST / 'METADATA').is_file()
    assert (library / 'huion_keydial_mini/web/dist/index.html').is_file()
    assert not (root / 'usr/lib/python3/site-packages').exists()
    for script in ['keydialctl', 'huion-keydial-mini']:
        command = root / 'usr/bin' / script
        assert command.read_text().startswith('#!/usr/bin/python3\n')
        assert command.stat().st_mode & 0o111
        env = dict(os.environ, PYTHONPATH=str(library))
        result = subprocess.run([sys.executable, str(command), '--help'], env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    assert (root / 'usr/share/keydial-commander/service_startup.py').is_file()
    assert (root / 'usr/lib/udev/rules.d/70-huion-keydial-mini.rules').is_file()
    desktop = (root / 'usr/share/applications/keydial-commander.desktop').read_text()
    assert 'Exec=/usr/bin/keydial-commander --start-service' in desktop
    assert 'Exec=/usr/bin/keydial-commander --stop-service' in desktop
    # Execute all generated lifecycle scripts in a foreign root: no host systemd.
    scripts = tmp_path / 'control'
    subprocess.run(['dpkg-deb', '-e', str(deb), str(scripts)], check=True)
    env = dict(os.environ, DPKG_ROOT=str(root))
    for script, action in [('preinst', 'install'), ('postinst', 'configure'), ('prerm', 'remove'), ('postrm', 'purge')]:
        subprocess.run([str(scripts / script), action], env=env, check=True)
    assert not (root / 'run/keydial-commander/maintenance').exists()


@pytest.mark.parametrize('bad', ['traversal', 'metadata', 'tag', 'entry', 'missing_ui', 'data'])
def test_rejects_invalid_wheel_before_producing_package(wheel, tmp_path, bad):
    with ZipFile(wheel) as z:
        files = {n: z.read(n) for n in z.namelist()}
    if bad == 'traversal':
        files['../escaped'] = b'bad'
    elif bad == 'metadata':
        files[DIST + '/METADATA'] = b'Name: another-project\nVersion: 1.3.0a2\n'
    elif bad == 'tag':
        files[DIST + '/WHEEL'] = b'Root-Is-Purelib: false\nTag: cp314-cp314-linux_x86_64\n'
    elif bad == 'entry':
        files[DIST + '/entry_points.txt'] = b'[console_scripts]\nother = os:system\n'
    elif bad == 'data':
        files['huion_keydial_mini_driver.data/scripts/surprise'] = b'bad'
    else:
        files = {n: data for n, data in files.items() if '/web/dist/' not in n}
    with ZipFile(wheel, 'w') as z:
        for name, data in files.items():
            z.writestr(name, data)
    output = tmp_path / 'output'
    with pytest.raises(ValueError):
        builder().build(wheel, output)
    assert not list(output.glob('*.deb'))
    assert not (tmp_path / 'escaped').exists()
