# Install the Linux preview

The preview bundle contains a built browser UI and Python package. It does not
need Node or a source checkout. These instructions use Ubuntu's package manager
for Python prerequisites; clean distribution-package qualification is the next
milestone. Bluetooth and USB hardware qualification remain separate open checks.

## 1. Download and unpack

From [GitHub Releases](https://github.com/the3dcoder/KeydialCommander/releases),
download **`keydial-commander-1.3.0a1-linux.tar.gz`** and unpack it:

```bash
tar -xzf keydial-commander-1.3.0a1-linux.tar.gz
cd keydial-commander-1.3.0a1
```

The bundle contains `INSTALL.md`, the `.whl`, `system/`, `desktop/`, `examples/`
and the license. GitHub's automatic source archives are for development and do
not contain the prebuilt web assets.

If you also downloaded `SHA256SUMS` and the wheel beside the bundle, check both
published files with `sha256sum --check SHA256SUMS` before unpacking.

## 2. Install Python and the application

Install the Python environment and compiler prerequisites used when a runtime
dependency needs building:

```bash
sudo apt update
sudo apt install python3-venv python3-dev build-essential
python3 -m venv "$HOME/.local/share/keydial-commander/venv"
"$HOME/.local/share/keydial-commander/venv/bin/python" -m pip install ./huion_keydial_mini_driver-1.3.0a1-py3-none-any.whl
```

The application and its dependencies live in that user-owned environment.
The wheel includes the web UI; no frontend build is required. Its technical
package name is `huion-keydial-mini-driver`, retained for compatibility.

## 3. Allow your desktop session to use the K20

This initial system setup requires administrator access:

```bash
sudo install -Dm644 system/70-huion-keydial-mini.rules /etc/udev/rules.d/70-huion-keydial-mini.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=misc --subsystem-match=input
```

Pair the K20 through your desktop's Bluetooth settings before starting the
service. If testing USB, connect it with a known data cable; USB qualification
is still open. Reconnect the device if access has not taken effect. The rule grants your active
desktop session access to the matching input nodes and `/dev/uinput`. It does
not require adding your account to the blanket `input` group.

## 4. Start the user service

The bundle's service template uses the virtual environment from step 2. Copy it
into your user-service directory:

```bash
install -Dm644 system/huion-keydial-mini-user.service "$HOME/.config/systemd/user/huion-keydial-mini-user.service"
systemctl --user daemon-reload
systemctl --user enable --now huion-keydial-mini-user.service
```

Starting the service captures the K20's input nodes and applies the active
profile. Open **http://127.0.0.1:8137**, choose a control, configure its action
and press **Save**. The service starts again at login.

To return the device to its factory behavior, stop Commander:

```bash
systemctl --user stop huion-keydial-mini-user.service
```

## Optional desktop window

The browser UI needs no GTK packages. For a desktop launcher/window, install:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1
install -Dm644 desktop/commander_shell.py "$HOME/.local/share/keydial-commander/commander_shell.py"
install -Dm755 desktop/keydial-commander "$HOME/.local/bin/keydial-commander"
install -Dm644 desktop/icon.svg "$HOME/.local/share/icons/hicolor/scalable/apps/keydial-commander.svg"
install -Dm644 desktop/keydial-commander.desktop "$HOME/.local/share/applications/keydial-commander.desktop"
```

Ensure `~/.local/bin` is on your desktop session's `PATH` (a new login may be
needed), then open **Keydial Commander** from the applications menu. The shell
opens the browser if GTK/WebKit is unavailable. There is currently no tray icon.
The bundle's desktop entry selects the included Keydial Commander icon.

## Status and recovery

```bash
systemctl --user status huion-keydial-mini-user.service
journalctl --user -u huion-keydial-mini-user.service -f
```

- **Release controls to resume:** let go of the K20 buttons/dial click, then use
  a fresh press or turn. Recovery-time gestures do not run actions.
- **Waiting for all K20 controls / cannot access input:** check pairing,
  connection and the device-access setup above.
- **Output unavailable:** inspect the service log, resolve the output access
  problem, then restart the user service. Commander does not automatically
  recreate a failed output backend.

Bluetooth has historical physical evidence. The current recovery changes and
USB path still need dated hardware qualification; an absent USB device can also
mean a charge-only cable. Windows/macOS and other peripherals are outside the
current release scope.

## Upgrade and remove

For a later preview using the same environment, stop the service, install the
new wheel with the environment's Python using `-m pip install --upgrade`, then
start the service again. Follow that release's notes for service-template
updates. User profiles remain in `~/.config/huion-keydial-mini/profiles/`.

To remove this preview's backend and user service:

```bash
systemctl --user disable --now huion-keydial-mini-user.service
rm -f "$HOME/.config/systemd/user/huion-keydial-mini-user.service"
systemctl --user daemon-reload
rm -rf "$HOME/.local/share/keydial-commander/venv"
```

This preserves profiles. Optional desktop files use the exact destinations above
and can be removed individually. Remove the device rule only when it is no
longer used by another Commander installation, then reload udev rules.
