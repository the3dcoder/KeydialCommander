# Release and installation interview

## Explicit direction

Earl requested an improved GitHub README, an easy-to-use releases page,
continued roadmap work/interviews and the same Earl-only commit/code identity.
The current recovery implementation is merged through PR #1 into `main` at
`92ff585`. GitHub had no releases when this work began.

The immediate delivery uses GitHub's native releases page with a clearly marked
`1.3.0a1` preview: a prebuilt Linux bundle, wheel, installation instructions and
checksums. It corrects README build order and hardware claims. It does not imply
a qualified Ubuntu package or physical transport result.

## Next installation milestone

Recommended direction: a native Ubuntu `.deb` that includes built web assets,
the desktop launcher, user service and device rule, with no Node/checkout at
runtime. Keep one clean installation/upgrade/uninstall matrix before expanding
distribution claims.

| Approach | Tradeoff |
| --- | --- |
| Ubuntu `.deb` first (recommended) | Familiar installation and dependency management; needs Debian metadata, user-service and upgrade/uninstall testing. |
| Wheel/preview bundle | Available immediately and useful for testing; manual environment and permission setup remain. |
| AppImage/Flatpak first | More bundled runtime work; device capture and uinput permissions still need host integration. Does not remove the current qualification work. |

Question asked: qualify Ubuntu 26.04 first, or Ubuntu 24.04 and 26.04 together?
Ubuntu 26.04 first is a **provisional planning recommendation**, not an answer
from Earl. Physical equipment, transport availability and capture permission
remain unknown; elapsed time supplies none of those facts.

Second question asked: explicit first start with optional login auto-start, or
automatic remapping at login after installation? Explicit first start is the
provisional recommendation. No response has been recorded yet; this is a
product-behavior preference question, not permission to capture a device now.

After that choice, discuss the install/first-launch experience and whether
service start should be an explicit first-run action. Then write a concrete
packaging design, review it and get the design decision before implementing
the new installer. Hardware diagnostics and a second curated adapter follow the
reliability/installation work; game development stays in the KeyCommand session.

## Accepted recommendation and next interview

Earl subsequently said, “Please continue with your recommended updates and
improvements.” This selects Ubuntu 26.04 first, explicit first start and
optional login startup for the next implementation milestone. The earlier
provisional wording above records the interview at that point in time; it is
superseded by this acceptance and the
[native-package design](../superpowers/specs/2026-10-30-ubuntu-package-design.md).
It supplies no facts or permission about physical devices.

The next question asks which matters most after packaging:

1. Local diagnostics and guided Bluetooth/USB checks (recommended): reduce
   installation troubleshooting before adding more hardware abstractions.
2. Apply saved dial sensitivity: fix a currently ineffective setting, after
   agreeing units and direction/reset behavior.
3. Begin a second maintained device adapter: requires identifying a physical
   device and obtaining real descriptors/input evidence.

No answer is recorded yet. Diagnostics is a provisional planning default;
implementation, hardware availability and capture permission are not inferred
from silence. Commander and the separate KeyCommand game retain their boundary.
