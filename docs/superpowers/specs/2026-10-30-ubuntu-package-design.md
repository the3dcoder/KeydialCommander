# Ubuntu package and explicit startup

## Authorization and scope

Earl said, "Please continue with your recommended updates and improvements,"
after the recommendation for Ubuntu 26.04 first, explicit first start and
optional login auto-start. Those are now the selected milestone direction.
The implementation details below are engineering decisions within that scope;
they are not answers about physical equipment or permission to capture it.

Build a native Ubuntu 26.04 amd64-qualified `.deb` containing the existing
Commander runtime and built UI. No Node, pip, compiler or checkout is needed by
the installed application. Preserve Earl's Git/package identity, the existing
Python architecture and the separate KeyCommand project. Keep installation,
upgrade and removal tests away from the host's service, profiles and devices.

The next preview is Python `1.3.0a3` / Debian `1.3.0~a3-1`. Do not replace the
published `v1.3.0a1` artifacts.

## Approaches and selection

| Approach | Assessment |
| --- | --- |
| Wheel-fed binary package using `dpkg-deb` | Selected. Reuses the tested pure-Python wheel and explicitly stages Debian paths. Small build surface with inspectable payload and lifecycle scripts. |
| Repair full Debian source/debhelper pipeline | Useful for a future distribution submission. Current files reference deleted BLE components, an enabling preset and the wrong build layout; not needed for this first binary artifact. |
| AppImage/Flatpak | Deferred. Bundling another runtime does not eliminate host device-access integration. |

Retain binary package name `huion-keydial-mini-driver` so normal APT upgrades
replace the package's own files. Market it as Keydial Commander. Preserve the
older changelog's historical credits; new metadata/entries identify Earl.

## Payload and dependencies

Install wheel package files and `.dist-info` into
`/usr/lib/python3/dist-packages`, preserving installed version metadata. Generate
the two declared console entry points with `/usr/bin/python3` shebangs. Validate
wheel name/version, pure-Python tags, safe member paths, required UI assets and
declared entry points before staging. Reject unexpected wheel layouts rather
than copying arbitrary files outside the staging root.

| System path | Payload |
| --- | --- |
| `/usr/bin/huion-keydial-mini`, `/usr/bin/keydialctl` | Backend and CLI entry points |
| `/usr/bin/keydial-commander` | Desktop wrapper, system shell path with user-local fallback |
| `/usr/share/keydial-commander/` | GTK/browser shell and startup helper |
| `/usr/lib/systemd/user/huion-keydial-mini-user.service` | Vendor user unit |
| `/usr/lib/udev/rules.d/70-huion-keydial-mini.rules` | Current session-access rule |
| `/usr/lib/modules-load.d/keydial-commander.conf` | Boot-time `uinput` module request |
| `/usr/share/applications/keydial-commander.desktop` | Explicit-start launcher and stop action |
| `/usr/share/icons/hicolor/scalable/apps/keydial-commander.svg` | Existing icon |
| `/usr/share/doc/huion-keydial-mini-driver/` | License, installed-package guide and release notes |

Use `Pre-Depends: python3 (>= 3.8)` for self-contained Python maintscripts that
must run before unpack. Runtime dependencies are distro packages for evdev,
Click, ruamel.yaml, aiohttp, systemd, udev, PyGObject, GTK3 and WebKit2 4.1.
The desktop dependencies are installed by APT so the window/error dialog has
its normal runtime. Do not vendor those libraries or retain retired BLE deps.

Build web assets from the lockfile before building the wheel. The binary build
tool uses Python 3.11+ and `dpkg-deb`; it does not install tools or mutate system
paths. Accept a wheel and output directory as explicit arguments. Derive the
Python/Debian versions from that wheel; this also permits an old-wheel upgrade
fixture. Default output goes to ignored `dist/`, never the host installation.

## Explicit first start

The package's desktop entry invokes the shell with `--start-service`. This is
the user's explicit start action. A plain shell invocation keeps the existing
open-UI behavior. `--stop-service` stops only the named user service and exits.

Before starting, reload the user's unit catalog and query the unit's
`FragmentPath`. Accept vendor paths under `/usr/lib/systemd/user` or its `/lib`
alias. A user-local unit override or a legacy unbind rule produces a migration
message rather than silently starting the preview environment or deleting
unowned files. User configuration and venvs are preserved.

Start the user unit with an argument array, then poll the local status endpoint
for at most ten seconds using short bounded requests. Require the installed
package's expected API version. Do not open a broken shell or an unrelated
listener as though startup succeeded. Fail with fixed, useful service/log
instructions in a GTK error dialog; stderr is the fallback without a display.
Keep the API loopback-only and validate an advertised port before using it.

Closing the window leaves remapping active. Document `--stop-service` and the
desktop stop action. Login startup is a separate opt-in using
`systemctl --user enable`; disabling it does not silently stop a running session.
No new settings page, pause API or automatic capture-on-install is introduced.

## Upgrade and removal safety

Installing files never enables, presets, starts or restarts remapping.
Preserve existing user login choices and all user profiles/configuration.

APT may need to stop an already active **package-managed** unit before replacing
or removing its files. Root `systemctl --user` targets the wrong user; enumerate
running `user@UID.service` managers and address each with
`systemctl --user --machine UID@`. Query only the exact Commander unit, its
active state and fragment path. Stop only vendor-owned instances; preserve
user-local preview units and explain their migration at launch.

The existing `deb-systemd-invoke --user stop` confirms this supported addressing
scheme but masks individual stop failures. The package helper must verify each
managed instance is inactive after stopping. If a running manager cannot be
queried or a managed unit cannot be stopped, fail the operation before files are
replaced/removed and provide retry instructions. Do not kill launched programs.

Use a root-owned `/run/keydial-commander/maintenance` marker during lifecycle
operations, with a negative `ConditionPathExists` on the vendor unit, to prevent
new managed starts while files change. Remove the marker after configuration or
completed/aborted removal. Failure leaves the marker in place until a safe
retry/abort path; instructions explain the maintenance state. No unrelated unit
or user-owned service file is changed.

Self-contained preinst/prerm scripts can run before/after payload replacement;
they cannot depend on importing the installed application. Postinst compiles
only package-owned Python files, reloads available udev rules and may request
`uinput` only on a real running host with `/sys/module` available. It never
captures input or starts the service. Do not trigger all input devices. Postrm
cleans application bytecode/owned maintenance state while leaving shared kernel
modules, user profiles, user overrides and manual installations alone.

Foreign-root operation through standard `DPKG_ROOT` must never contact the host
service manager. Unit tests inject command runners and temporary roots; no test
needs real host service control.

## Qualification

The experiment fails if installation starts/enables remapping, if missing UI
assets are accepted, if a lifecycle failure deletes application files, or if
upgrade/removal changes profile contents.

1. Test the binary builder against a real generated wheel and inspect/extract
   the resulting `.deb`: paths, metadata, executable modes, no build tools,
   system Python import scheme, service and desktop resources.
2. Test first-start success/failure/version mismatch, stale port files,
   user-local overrides and explicit stop with fake managers/HTTP responders.
3. Test lifecycle behavior with multiple fake user managers: owned/unowned,
   active/inactive, failed queries/stops, no starts/enables, maintenance marker
   ordering and profile preservation.
4. Use signed official Ubuntu Base 26.04.1 amd64 under `/tmp`. User namespaces
   are unavailable here; explicit PRoot path translation is the fallback. It is
   not a security boundary. Use sanitized environment and no host home, checkout,
   `/run`, `/proc`, `/sys`, or device-tree bindings; only individual null/entropy
   devices if required. Download/extract tools privately; install nothing on host.
5. In that rootfs, resolve dependencies with public Ubuntu APT sources, install
   a native fixture built from the published `1.3.0a1` wheel, then upgrade to the
   new package. Verify installed version/CLI/UI with no Node/checkout, remove and
   purge, and compare guest profile hashes throughout. Clearly call the old
   native package an upgrade fixture, not a formerly published `.deb`.
6. Run the full hardware-excluded Python and isolated browser suites, build/lint,
   and an independent final review. Preserve dated evidence and exact exclusions.

Clean-rootfs checks qualify dependency resolution and file/package behavior.
Real systemd user-manager execution, graphical window/login behavior, udev
permissions and Bluetooth/USB input remain unqualified unless separately
measured. Do not start the host service or capture devices to fill those rows.

## Delivery

Use Earl-authored commits/tags. Publish a new prerelease with the Ubuntu `.deb`,
wheel and checksums after verification; preserve the earlier preview. Update
README/install/release guides to make the `.deb` the Ubuntu 26.04 path while
keeping qualification boundaries and the earlier generic bundle available.
Integrate through a reviewed PR, with a local Earl-authored merge as before.

## Draft publication correction

GitHub normalized the a2 draft's tilde-containing filename. Verification stopped
publication. Keep that source tag immutable and draft unpublished; deliver a3
with Python-version filenames and Debian-version control metadata. This is a
release engineering correction within the authorized milestone.
