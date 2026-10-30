# Keydial Commander next development session

This is the handoff for continuing Commander independently from KeyCommand. The direction below is agreed; the next release design and individual feature designs still need the ongoing interview.

## Recovery milestone update, 2026-10-30

Earl approved `docs/superpowers/specs/2026-10-30-k20-recovery-design.md` and
instructed implementation. The software milestone now includes original output
ownership, bounded cancellable macros, validated active-map publication,
node/lost-frame recovery, neutral rearm, client-abort cancellation and truthful
local status. Normal remapping semantics and the separate game boundary remain.

Final verification: **192 Python tests passed** with the hardware capture case
excluded, **15 browser regressions passed**, frontend build/lint and whitespace
checks passed. A principal architecture/code review found three Important gaps;
all were reproduced and fixed in one pass, then the full checks passed.
See [dated qualification](2026-10-30-k20-qualification.md) and the
[implementation plan](../superpowers/plans/2026-10-30-k20-recovery.md).

Current physical K20 availability, disruptive symptoms and USB data-cable facts
remain unanswered. No device was captured and no installed service/profile or
deployment was changed. Bluetooth and USB need separate physical qualification;
packaging remains the next software milestone. The architecture findings below
record the **pre-recovery baseline**, not a list of still-unfixed software bugs.

## Agreed direction

Earl wants a dependable Linux K20 release first, followed by maintained device adapters. Commander remains the original local control center. KeyCommand is a separate browser game with its own repository, deployment and development session.

The game is also pursuing player growth, competition, daily featured challenges, shareable results and creative modes. Its first audience includes peripheral enthusiasts, programmers, and people using adaptive controls and accessible switches. Accessible play and comparable competition presets are core requirements, without disability disclosure.

## Repository and delivery baseline

* Repository: `/home/earl/Documents/KeydialCommander`, remote `the3dcoder/KeydialCommander`.
* Current development branch: `feat/keycommand-foundation`.
* Starting commit for this handoff: `97e6835`, after the input editor fixes and game planning documents.
* Existing [draft PR 1](https://github.com/the3dcoder/KeydialCommander/pull/1) targets main. It has not been merged.
* The separate game lives at `/home/earl/Documents/KeyCommand`, private remote `the3dcoder/KeyCommand`, and https://keycommand.io.
* Architecture: Python asyncio, evdev input, uinput output, YAML profiles, a private Unix control socket, loopback aiohttp HTTP/WebSocket API, React/TypeScript frontend and optional GTK/WebKit shell.
* The first integration is the importable `examples/keycommand-profile.yaml`. There is no paired live game bridge.

Read `ARCHITECTURE.md`, `docs/AUDIT-2026-10-29.md`, `docs/ROADMAP.md`, the current source, and the existing PR before proposing changes. Historical checked roadmap items are not proof of current behavior.

The last completed delivery passed 140 Python tests with the hardware capture case excluded, 14 browser regressions, frontend build and lint. Those are historical results, not a fresh check for the next release. The checkout's `.venv` is inconsistent; the prior checks used `/tmp/keycommand-python`. Inspect the environment before relying on it.

## Architecture review findings

The following were checked against source during this handoff. Reproduce source-inferred risks with focused tests before changing behavior.

| Area | Evidence and consequence |
| --- | --- |
| Macro dispatch | `evdev_source.py:139` awaits the input callback; `action_engine.py:60` awaits macro delays. A long macro blocks its originating event reader. |
| Command dispatch | `action_engine.py:67` awaits subprocess creation and returns a detached child. The child's lifetime does not block input. This corrects the October audit's broad wording about commands and macros. |
| Device state | `device.py:45` creates one translator for all matching nodes. One physical K20 can have several nodes, but separate physical devices need independent state. |
| Disconnect | `evdev_source.py:115` drops a node without resetting translator state or releasing its owned outputs. Define cleanup and resume semantics explicitly. |
| Lost events | `evdev_source.py:150` has no `SYN_DROPPED` recovery. The kernel requires clients to discard incomplete events and query current state. |
| Profile changes while held | `keybind_manager.py:93` replaces active bindings; `uinput_handler.py:99` resolves the current binding on release. A held action may release different keys after a profile edit or switch. This is an unconfirmed failure inferred from source. |
| Output ownership | `uinput_handler.py:134` writes key states directly. Overlapping sticky modifiers and macro taps need ownership tests before adding concurrent actions. |
| Discovery | `input_map.py:59` accepts a name containing `keydial` independently of VID/PID. Tighten matching and virtual-output exclusion as part of the adapter design. |
| Sensitivity | The saved setting is not applied by the evdev path. Agree on units and direction/reset behavior before implementing it. |
| Packaging | Frontend build/install ordering and stale Arch, Nix and Debian references remain. Qualify one supported distribution before claiming the others work. |

The current host was identified as Ubuntu 26.04.1. July hardware evidence came from Ubuntu 24.04. Current Bluetooth behavior and USB behavior need dated physical qualification; do not silently carry the older claim forward.

## Approaches to discuss

| Approach | Benefit | Cost and timing |
| --- | --- | --- |
| Harden the current K20 stack | Builds on the current code and regression suite; resolves practical reliability and installation problems. | Recommended first and consistent with the agreed direction. |
| Become a Linux capability host with curated adapters | Separates physical discovery/grouping, decoding, translation and action execution; supports other devices without forking the app. | Recommended after a reliable K20 release and a second real device establish the requirements. |
| Build a cross-platform companion and live game bridge | Could support platform-specific backends and selected-device game input. | Later option. Requires a concrete unmet need, transport/permission research, installers and separate consent design. |

Keep the Python/evdev/uinput architecture for the next reliability proposal. A rewrite is not justified by the current requirements. Prefer built-in reviewed adapters and descriptive manifests before executable third-party plugins.

## Candidate release sequence

These are planning proposals, not an approved implementation checklist.

1. **Recovery and output ownership.** Reproduce disconnect-while-held, profile edits while held, lost input, overlapping modifiers and macro cancellation. Define how pause, failure, reconnect and shutdown release owned outputs. Acceptance candidates: no owned keys remain after cleanup; no stale macro resumes after reconnect; a delayed macro cannot prevent emergency cleanup.
2. **One installable artifact.** Build web assets before packaging. Install the produced artifact in a clean supported Ubuntu environment without the checkout or Node. Exercise CLI, GUI and user service; preserve profiles across upgrade; uninstall only application-owned files. Label other distribution packages unqualified.
3. **Useful diagnostics and hardware evidence.** Distinguish discovery, permission, grab, translation, output and UI connection failures. Offer previewable sanitized reports and explicitly chosen short selected-device traces. Qualify Bluetooth and USB separately.
4. **A curated adapter boundary.** Keep per-physical-device state while grouping each device's nodes. Extract the K20 without changing its behavior, then support one owned or borrowed peripheral with fixtures and physical evidence.

Two product hypotheses worth testing are a local explanation of why a control failed through each processing stage, and a support record attached to each adapter claim. These combine established techniques; neither is a claim of global novelty.

## Interview queue

Continue the interview one small round at a time. Each question should have a recommendation and explain what its answer changes. Skip answers already recorded above.

| Priority | Open question | Recommended starting answer |
| --- | --- | --- |
| 1 | What exact computers, Linux distributions, K20 connections and data cables can Earl physically test for the next release? | Qualify the current Ubuntu host and Bluetooth first; add USB claims only after a real data-cable check. Keep unconfirmed equipment unknown. |
| 2 | What should happen when a device disappears, events are lost, or output fails? | Release affected owned outputs, cancel affected work, explain the state, and require released controls before resuming. |
| 3 | What should a profile change do to held actions and running macros? | Release original outputs and cancel old-profile macros. Preserve ordinary release-triggered behavior unless the interview changes it. |
| 4 | What should dial sensitivity mean to a person configuring it? | Use explicit detents-per-action or actions-per-detent, with agreed reset and direction-change rules. |
| 5 | Which installation path should be publicly supported first? | One tested Ubuntu artifact and user service, with no root runtime; qualify other packages later. |
| 6 | What information may diagnostics keep or export? | Local state/counters; previewable sanitized reports; explicit short selected-device traces. Exclude unrelated input, serials, addresses and command arguments by default. |
| 7 | What should be accessible using the peripheral itself within Commander's UI? | Define a usable keyboard path and clear focus/state feedback; test with the relevant users before broader accessibility claims. |
| 8 | Which second physical peripheral should get an adapter? | Choose a real available simple dial or accessible switch after K20 reliability, rather than promising all devices. |
| 9 | Is automatic application-based profile switching worth platform-specific helpers? | Defer until reliability and packaging; make any Wayland/desktop helper optional and explicit. |
| 10 | What support, maintenance and release workload is realistic? | A small verified support matrix, documented issue reproduction and reproducible tagged artifacts before broad promotion. |

The next session should begin with question 1 and the most disruptive current failure Earl experiences, rather than re-asking the product direction.

## Research references

* [Linux input event protocol](https://docs.kernel.org/input/event-codes.html): event synchronization and lost-event recovery.
* [input-remapper](https://github.com/sezanzeb/input-remapper): an established Linux reference for combinations, macros, wheels and multiple input types. Research its behavior instead of assuming those features are unexplored.
* [OpenDeck](https://github.com/nekename/OpenDeck): a reference for separating core hardware support and additional device support.
* [OpenTabletDriver configuration guide](https://opentabletdriver.net/Wiki/Documentation/ConfigurationGuide): device configuration and override diagnostics as prior art, not a proposed dependency.
* [Chrome Local Network Access](https://developer.chrome.com/docs/modern-web-guidance/guides/security/local-network-access) and [native messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging): possible companion transport constraints. A browser bridge requires its own feasibility check.

## Working agreement for this session

Work only in Commander. Use explicit working directories. The KeyCommand session owns the game's source, content, cloud service and boards. Exchange a reviewed contract proposal when either project needs something from the other; do not quietly change both repositories.

Use a principal software architect for architecture/reliability decisions and a principal game designer for the peripheral interaction and game boundary. Delegate bounded research or review work rather than starting duplicate implementations.

Keep a decision record separating explicit answers, provisional recommendations, measured results and open questions. Ask 1–3 focused questions per round. Earl permits proceeding with a stated recommended planning assumption after 15 seconds; silence does not establish unknown hardware facts or grant a new permission. Continue independent research while waiting. Existing answers persist.

After the interview narrows a milestone, compare two or three grounded approaches, write a concrete design, review it, and obtain the appropriate design decision before producing an implementation plan. Use small vertical changes, focused regressions, relevant full checks and a release evidence matrix. Define the criterion that would make an experiment fail before building it.

Use the configured Earl Git identity and natural prose, without coauthor trailers or assistant credits. Preserve existing work. Do not merge the existing draft PR as part of planning. Do not grab devices, install system rules, change the running service or profiles, or expose the local API while researching.

## Contract with KeyCommand

Commander owns physical adapters, node grouping, permissions, capture/release lifecycle, local output actions, profiles and diagnostics. KeyCommand owns game control requirements, assistance, rules, scores, competition identity, moderation and cloud storage.

A small versioned capability schema and golden fixtures, mirrored by review, are a candidate collaboration tool. No third repository or shared runtime package is needed yet. Distinguish buttons, releases, relative turns with units, axes and switches. Keep observed device metadata separate from gameplay attribution.

The next game can use ordinary discrete browser input and the existing preset. A future selected-device bridge would need consent, exact-origin pairing, expiry/revocation, loss/reset events, monotonic relative timing and explicit capture-versus-remapping behavior. It must not expose command execution or profile mutation to game origins. Pairing alone would not establish cheat-proof hardware identity.
