# Ubuntu package preview evidence — 2026-10-30

Version: Python `1.3.0a3`, Debian `1.3.0~a3-1`, tag `v1.3.0a3`.
The release body identifies the exact source commit. This preview delivers a
native archive and explicit-start launcher. **Clean Ubuntu installation remains
unqualified** because the available rootfs harness cannot finish configuring
Ubuntu's own systemd package. No installer scripts were bypassed to claim a
successful APT install.

## Measured checks

| Check | Result |
| --- | --- |
| Python regression suite | 221 passed, one physical/synthetic uinput capture case deselected; 36 existing aiohttp/legacy mock warnings. Uses installed a3 runtime and current package helpers. |
| Isolated browser regressions | 15 passed with temporary Chromium and fixture API state, Node 24.18.0. |
| Frontend build/lint | Passed. Locked frontend dependencies unchanged from the verified a1 build; rebuilt production UI before the wheel. |
| Wheel build | Passed using temporary build tooling; built HTML/JS/CSS included. Existing table-style license metadata deprecation warning remains. |
| Native archive | Real dpkg-deb build/extract passed. Distro Python paths, dist-info version, console help, GTK shell helper, desktop start/stop actions and system resources verified. |
| Startup/lifecycle/builder tests | 29 passed, including failed stop/query, customized units, invalid ports, mismatched API version, foreign roots, unsafe wheel layouts and absent UI assets. |
| Unit syntax | systemd-analyze --user verify passed; restricted sandbox emitted two ignored socket-option warnings. This does not exercise a running user manager. |
| Foreign-root real dpkg transactions | a1 native fixture install → a3 upgrade → remove → purge passed. Self-contained maintscripts ran with DPKG_ROOT; profiles preserved and owned application files removed. Dependency checks were explicitly forced; see limits below. |
| Ubuntu extracted runtime | Both CLI help commands, Earl identity/version, fixture status API, built index and JS/CSS assets passed under Ubuntu Base with Node/checkout absent. No driver or output was constructed. |
| Clean Ubuntu APT installation | **Blocked/unqualified.** Dependency bootstrap failed in Ubuntu systemd's postinst before a native app installation could complete. |
| Actual graphical session/login, permissions, Bluetooth/USB | **Unqualified.** No host service, user profile, access rule, or physical device was changed. |

The Python command excludes `test_end_to_end_grab_and_read` explicitly. It must
not capture even a synthetic device during release checks. The browser suite
uses its own temporary profile/server. Existing backend runtime semantics are
unchanged; new code concerns packaging and explicit desktop service actions.

## Native package behavior

The package never enables, presets, starts or restarts remapping during its
lifecycle. Before upgrade/removal it places a maintenance barrier and inspects
running user managers. It stops only the exact active vendor-managed unit,
checks the result, and preserves user-local services. An active vendor unit
with drop-ins blocks replacement until manually stopped. User profiles,
overrides and manual environments are preserved.

The launcher rejects a non-vendor fragment or any drop-ins, checks for the
legacy unbind rule, explicitly starts the user unit and waits for a matching
local API version. Closing the window leaves remapping active. The vendor unit
uses `KillMode=process` because command actions launch independent user
programs. Real manager/cgroup behavior still requires a graphical-session test.

The published a1 wheel was used to build an **internal native upgrade fixture**
with the new package layout. There was no previously published a1 `.deb`.
Foreign-root tests used `fakeroot` with `FAKEROOTDONTTRYCHOWN=1`,
`dpkg --root=... --force-script-chrootless --force-depends`, and a log inside
`/tmp`. They exercise real package file replacement and maintscript dispatch,
using host Python and skipping live-manager actions/bytecode compilation under
DPKG_ROOT. They do not prove dependency installation, real-user shutdown,
bytecode handling on a live install, or native login behavior.

The preserved fixture profile SHA-256 after every transaction was:
`3a28b8f5b8da0b9a2fbdeb419dae2c75c2f9d78c7fcaa21936fad34b9a40b013`.

## Ubuntu rootfs method and failure

Downloaded the official [Ubuntu Base 26.04.1 amd64 image](https://cdimage.ubuntu.com/ubuntu-base/releases/26.04/release/).
Its checksum list's detached signature verified with the Ubuntu archive keyring.
The rootfs SHA-256 was
`a496a960472ce474a59590b8987d3a1135d3cbef1991f3b1abe8cacfea8bf85a`.
The privately extracted Ubuntu PRoot 5.4.0-3 package SHA-256 was
`8520a33632dc721ec9404eb8bb0079834dcced02f6e861510238bf636cc629e7`.

User namespaces were unavailable. PRoot path translation was the fallback,
with `-r`, sanitized environment, and only individual null/zero/entropy device
bindings. No host home, checkout, `/proc`, `/sys`, `/run`, input tree, uinput or
service socket was bound. PRoot shares the host kernel/network and is not a
security boundary. A guest-only sentinel and translated filesystem writes
verified the guest view before continuing APT. `PROOT_NO_SECCOMP=1` was needed
because the default acceleration did not translate post-exec operations here.

Public `resolute`, `resolute-updates` and `resolute-security`, `main`/`universe`
repositories supplied signed indexes and downloaded dependencies. A guest
policy-rc.d returning 101 blocked service starts. Ubuntu's GNU coreutils
provider replaced its uutils provider only inside the guest to avoid PRoot's
executable-name incompatibility. No host package was installed or changed.

Ubuntu systemd 259.9's postinst reported that `/proc` was not mounted and failed:
`Cannot open '/etc/machine-id' in neither writable nor read-only mode: Function not implemented`.
The APT dependency bootstrap exited 100. We retained that failure rather than
patching distro maintscripts or exposing host kernel/service trees.

For the narrower runtime check, 267 downloaded dependency archives and the
native a3 archive were **extracted**, without claiming they were configured by
APT. Guest Python imported Commander from `/usr/lib/python3/dist-packages` and
served a fixture API/UI at an ephemeral loopback port. This establishes runtime
payload/dependency closure in that filesystem, not an installed-package result.

## Review and remaining gate

A fresh whole-branch reviewer found three Important issues: service stops could
terminate launched programs, drop-ins could mask manual service ownership, and
the earlier user-local launcher could intercept new flags. The fixes add the
process-only stop policy, override checks with failing-then-passing regression
tests, and explicit launcher migration/absolute native commands. No further
blocking code findings were reported.

Before calling the Ubuntu package qualified or stable, run unmodified APT
install/upgrade/remove/purge in a real Ubuntu 26.04 VM or isolated supported
container, then test a logged-in user's explicit start/stop and opt-in login,
error dialogs, permissions and Bluetooth/USB separately. Preserve profiles and
launched programs across those real service operations. The next optional
feature interview recommends diagnostics/guided device checks.

## Release naming correction

Draft a2 verification caught GitHub normalizing `~` to `.` in an uploaded
filename. Publication stopped because the downloaded name did not match the
manifest. The a2 draft stays unpublished and its Git tag is preserved.
A regression test now verifies the public filename uses the Python version
(`1.3.0a3`), while internal Debian Version keeps prerelease ordering
(`1.3.0~a3-1`). The corrected preview receives a new immutable `v1.3.0a3` tag.

## Release artifacts

Source timestamp `1793335893`; source commit appears in the release body.
Draft downloads must match these names and hashes before publication:

```text
b75d44f5f8b69b9fd7a03d9c1ad5d3d53cc30a5444d1c1a3ab705689a70a3d14  huion-keydial-mini-driver_1.3.0a3-1_all.deb
45fd5a661dbd7e2a1d60b425930eccc4637fbf4aedd6d05ca67869ab2d2878a6  huion_keydial_mini_driver-1.3.0a3-py3-none-any.whl
```
