# Preview artifact verification

Version: `1.3.0a1`. Source will be identified by annotated tag `v1.3.0a1` and
the full commit SHA in the published GitHub release body. Runtime behavior is
the merged recovery baseline (`f4fa9ef`, integrated by `92ff585`); this delivery
changes documentation and distribution version metadata.

## Checks

| Check | Measured result |
| --- | --- |
| Frontend lockfile build | `npm ci` and production build passed with Node 24.18.0. |
| Wheel/source build | `1.3.0a1` wheel and source distribution built in a temporary build environment. The wheel contains built HTML, JavaScript and CSS. |
| Fresh wheel installation | Declared runtime dependencies installed into a new virtual environment outside the checkout. No application was installed into system Python or Earl's existing environment. |
| Installed CLI/UI/API | Both CLI help commands, installed package identity/version, built UI and isolated fixture API passed with Node absent from `PATH`. No device driver or virtual output was started. |
| Python regressions against installed wheel | 192 passed; one hardware capture test excluded; 36 existing-style aiohttp/legacy mock warnings. |
| Browser regressions | 15 passed using isolated fixture APIs and Chromium. |
| Frontend lint | Passed. |
| Bundle inspection | 16 safe archive entries; embedded wheel matches the separate wheel; user-service venv path and desktop icon match the instructions. |

The wheel and bundle use source timestamp `1793335893` for normalized archive
timestamps. Python build tooling reports the pre-existing deprecation warning
for table-style project license metadata; it did not fail the build.

Published filenames and SHA-256 values:

```text
1e62f90e4c7055f2ddc66dfd41ae447a14dea8219edf71355a96eb8bee3307d1  huion_keydial_mini_driver-1.3.0a1-py3-none-any.whl
9ca52e02198755602a514a5a85b470a30bad79623c8d8a3e146552d53d308bf2  keydial-commander-1.3.0a1-linux.tar.gz
```

These values are also provided in `SHA256SUMS`. Publication verifies draft
uploads by downloading the actual assets and checking those hashes before
making the release public.

## Review

A bounded independent documentation/architecture review checked filenames,
version, CLI entry points, service paths, identity and qualification claims.
The source/evidence links, initial pairing guidance and bundled desktop icon
selection were clarified before publication.

## Limits

No device is captured and no installed service, profile or system rule is
changed by this verification. Fresh virtual-environment installation is not a
clean Ubuntu package installation. Bluetooth, USB, actual login/service
behavior and desktop delivery after an output failure remain unqualified.
The next native-package design is recorded in the
[release interview](2026-10-30-release-direction.md).
