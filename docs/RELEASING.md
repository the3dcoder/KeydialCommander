# Release checklist

GitHub Releases is the public download page. Keep README download links, version
metadata and release notes aligned. Commits and annotated tags use Earl's Git
identity without assistant credits or coauthor trailers.

## Prepare

1. Start a work branch from current `main`. Verify the existing remote release
   and tag before selecting a new version; do not replace published artifacts.
2. Update `pyproject.toml` using a Python-compatible version. The package reads
   its installed version from distribution metadata.
3. Write versioned notes under `docs/releases/`, with a short download table,
   installation path, changes, measured checks and unqualified platforms.
4. Build the web UI from the lockfile **before** building the wheel. Source
   archives alone do not contain the ignored built assets.

```bash
npm --prefix web ci
npm --prefix web run build
python3 -m build
```

Use a temporary build environment with `build`, `setuptools` and `wheel`, rather
than modifying system Python. Use Node 24 or newer for browser checks.

## Preview artifacts

Publish these files for a wheel-based preview:

- `huion_keydial_mini_driver-<version>-py3-none-any.whl` containing the built
  `web/dist/index.html` and JavaScript/CSS assets.
- `keydial-commander-<version>-linux.tar.gz`, containing one versioned directory
  with that wheel, `INSTALL.md`, `LICENSE`, `RELEASE_NOTES.md`, `system/`,
  `desktop/` and `examples/`.
- `SHA256SUMS` containing the wheel and bundle hashes.

Copy the current udev rule into `system/`. The bundled user-service template
must use `ExecStart=%h/.local/share/keydial-commander/venv/bin/huion-keydial-mini`
to match the installation guide; the repository's system-package template uses
`/usr/bin` and must not be copied unchanged into the user-local preview.
Copy the shell Python file, launcher, icon and optional game profile unchanged.
Set `Icon=keydial-commander` in the bundled desktop entry, matching the installed
icon filename and the source checkout's `install-shell` behavior.

Build archives with a fixed file order, normalized owner/group and a recorded
source timestamp. Record the exact source commit separately in release notes.
List only published artifacts in `SHA256SUMS`.

## Verify before publishing

- Install the wheel into a fresh temporary virtual environment outside the
  checkout, using its declared dependencies. Verify imports and both CLI help
  commands there.
- Confirm the installed wheel serves its built UI using an isolated fixture
  API. Do not start `HuionKeydialMini` or capture a device for release smoke
  checks.
- Run the hardware-excluded Python suite and isolated browser regressions;
  record counts, exclusions, warnings, build and lint results.
- Inspect every archive member and service/desktop path. Recompute checksums.
- Perform a bounded independent review of README instructions, release notes,
  support claims and artifacts. Preserve older published releases.

A temporary virtual environment proves package installation, not a clean
Ubuntu `.deb` installation, user login/service behavior or Bluetooth/USB input.
Keep those evidence categories separate.

## Publish

Commit the reviewed files with Earl's identity and open a PR against `main`.
Create an annotated version tag on the exact reviewed release commit.
Append that full commit SHA and the versioned artifact-evidence link to the
published release body once the final commit exists.
Use a draft GitHub release while uploading and inspecting assets, then publish
with a prerelease flag until qualification justifies a stable release.
For an initial preview, publish the verified release before integrating the
documentation PR so new README download links work as soon as they appear on
`main`. Verify afterward that the tagged commit is included in `main`.

Use the explicit release URL in the README when only a prerelease exists;
GitHub's `/releases/latest` route selects stable releases. Link the release list
as well so people can find history and future versions.

After publication, fetch the GitHub README and release metadata, verify the
asset names and download links, and compare published checksums. The next
installation milestone is an Ubuntu package with clean-environment evidence.

## Native Ubuntu preview (1.3.0a3 onward)

Build the locked UI and wheel first, then explicitly select that wheel:

```bash
python3 packaging/debian/build_deb.py dist/huion_keydial_mini_driver-1.3.0a3-py3-none-any.whl --output-dir dist
# Equivalent: make package-debian WHEEL=dist/huion_keydial_mini_driver-1.3.0a3-py3-none-any.whl
```

`dpkg-deb` stages the runtime into `/usr/lib/python3/dist-packages`, including
version metadata. The native package includes shell/startup helpers, the vendor
user unit, access rule, module-load request, desktop launcher and icon. Debian
prerelease `1.3.0~a3-1` corresponds to Python `1.3.0a3`. The older debhelper
source-package rules are retired; this is a binary-package builder.

Publish the `.deb`, wheel and `SHA256SUMS` in a new prerelease. The earlier
manual bundle remains an explicitly versioned fallback; do not overwrite it
or assume its service path matches the native package. Native installer tests
must cover install, upgrade fixture, remove/purge and unchanged user profiles.
A fixture built from an earlier wheel is not a previously published native
package. Record clean-rootfs/runtime limitations separately from real systemd,
GUI, permissions and hardware qualification.

GitHub replaces `~` in release asset filenames. The binary builder therefore
uses `huion-keydial-mini-driver_1.3.0a3-1_all.deb` as its public filename while
retaining `Version: 1.3.0~a3-1` inside the package. Verify downloaded filenames
as well as bytes/checksums before publishing; never rewrite an existing tag
to fix a failed draft.
