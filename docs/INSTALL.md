# Install on Ubuntu 26.04

Download the **Ubuntu package** from [GitHub Releases](https://github.com/the3dcoder/KeydialCommander/releases/tag/v1.3.0a3).
The preview contains the application, built UI, desktop window, service and
access rules. APT supplies its runtime libraries. No Node, pip, compiler or
source checkout is needed on the installed machine.

This is a prerelease. Clean-rootfs checks and automated startup tests are
recorded in the [package evidence](development/2026-10-30-ubuntu-package.md).
Clean Ubuntu installation remains unqualified because the rootfs test could
not finish Ubuntu's systemd setup. Actual desktop/login, device permissions
and Bluetooth/USB qualification also remain open. Other distributions can use
the earlier [manual Linux preview](INSTALL-PREVIEW.md).

## Download and install

Download `huion-keydial-mini-driver_1.3.0a3-1_all.deb` and `SHA256SUMS`.
In the download directory, verify the package and install it:

```bash
sha256sum --check --ignore-missing SHA256SUMS
sudo apt update
sudo apt install './huion-keydial-mini-driver_1.3.0a3-1_all.deb'
```

Use Ubuntu's public `main` and `universe` repositories. APT resolves Python,
GTK/WebKit and device-access dependencies. The package name remains
`huion-keydial-mini-driver` for compatibility; its application name is
**Keydial Commander**. The package is architecture-independent Python; the
initial clean installation checks target Ubuntu 26.04 amd64.

**Installation does not start remapping or enable login startup.** Pair the K20
in Ubuntu's Bluetooth settings, or connect it with a USB data cable. Reconnect
it after installation so the new access rules apply. If device access fails,
reboot once to apply the uinput/session rules, then check the service logs below.
Physical USB operation still needs qualification.

## Start and stop

Open **Keydial Commander** from the application menu. This explicitly starts
remapping and opens the window after the local service reports the installed
version. You can also run:

```bash
/usr/bin/keydial-commander --start-service
```

Select a control, choose an action and press **Save**. Profiles remain under
`~/.config/huion-keydial-mini/profiles/`.

**Closing the window leaves remapping active.** To stop it, use the launcher's
**Stop remapping** action or run:

```bash
/usr/bin/keydial-commander --stop-service
```

A plain `keydial-commander` opens the existing UI without starting remapping.
The browser UI is normally at http://127.0.0.1:8137; an explicitly configured
port is advertised in `$XDG_RUNTIME_DIR/huion-keydial-mini/port`.

## Optional login startup

After a successful manual start, opt in with:

```bash
systemctl --user enable huion-keydial-mini-user.service
```

To turn login startup off:

```bash
systemctl --user disable huion-keydial-mini-user.service
```

Disabling login startup leaves an already-running service active. Use the stop
command above when you also want remapping to stop now. Never run these user
commands with `sudo`.

## Upgrade and remove

Install a newer downloaded `.deb` with `sudo apt install ./filename.deb`.
The package stops active package-managed instances before replacing files;
launch Commander again afterward. It preserves your login-start choice and
profiles. If a manager cannot be inspected or stopped, the operation fails
before replacing/removing the application. Resolve the reported manager issue
and retry the same APT operation. Do not delete the maintenance marker to force
an incomplete upgrade to run.
An active vendor unit with custom drop-ins requires you to stop it manually
before retrying; the installer cannot safely infer which runtime it uses.

```bash
sudo apt remove huion-keydial-mini-driver
# Optional: remove package configuration bookkeeping as well.
sudo apt purge huion-keydial-mini-driver
```

Removal stops package-managed remapping. Your profiles, manual environments
and user-local service overrides remain. The shared uinput kernel module is
not unloaded.

## Migrate from the manual preview

The native launcher refuses to start a user-local preview unit or a legacy
`99-huion-keydial-mini.rules` unbind setup. It does not delete those files.

1. Back up your profiles and note whether login startup was enabled.
2. Stop and disable the old user service:
   `systemctl --user disable --now huion-keydial-mini-user.service`.
3. Move your old `~/.config/systemd/user/huion-keydial-mini-user.service` and any
   matching override directory to a backup outside the systemd user directory.
   Remove or back up an old user-local Commander desktop entry if it masks the
   new application-menu entry. Also move the old
   `~/.local/bin/keydial-commander` launcher to a backup outside `PATH`, then run
   `hash -r` in Bash (or open a fresh terminal). Otherwise that published preview
   launcher can intercept the new start/stop flags. Use the absolute
   `/usr/bin/keydial-commander` command for the native package.
   Keep your profiles and preview venv.
4. If a legacy `/etc/udev/rules.d/99-huion-keydial-mini.rules` unbind rule exists,
   back it up outside the rules directory with administrator help. Also check
   for old `/etc/systemd/user` overrides. Reboot after changing legacy rules.
5. Run `systemctl --user daemon-reload`, then verify
   `systemctl --user show huion-keydial-mini-user.service --property=FragmentPath`.
   It should report `/usr/lib/systemd/user/huion-keydial-mini-user.service`
   (or Ubuntu's `/lib` alias). Start the native launcher; opt into login startup
   again if wanted.

An older `/etc/udev/rules.d/70-huion-keydial-mini.rules` takes precedence over
the vendor file. Compare/back up stale manual rules when migrating. Package
installation deliberately preserves files it does not own.

## Troubleshooting

```bash
systemctl --user status huion-keydial-mini-user.service
journalctl --user -u huion-keydial-mini-user.service -n 50
curl http://127.0.0.1:8137/api/status
```

Run the app in a logged-in graphical user session. A startup error includes
these log commands and a link to this guide. If another preview listener or a
stale port file reports the wrong version, stop that old service and retry.
Keep the HTTP/WebSocket API on loopback.
