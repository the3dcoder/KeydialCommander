# Worklog — Keydial Commander project

Running log of what was done, newest first. Companion to `ROADMAP.md` (plan) and
`AUDIT-2026-07-19.md` (findings).

## 2026-07-20 — Finishing touches: standalone repo, service, defaults, independence

- **New standalone public repo:** https://github.com/the3dcoder/KeydialCommander — created via
  `gh` (Node/gh installed user-local; no system-package changes). Pushed as a single fresh initial
  commit (full build history kept locally on the `feat/*`/`docs/*` branches + `full-history-backup`
  tag). MIT LICENSE retained.
- **Auto-start service:** `~/.config/systemd/user/keydial-commander.service` (points at the venv),
  enabled — starts on login, serves the GUI, grabs the K20.
- **Sensible default bindings** seeded into the Default profile so the K20 is useful out of the box:
  buttons 1–12 = Undo/Redo/Copy/Paste/Cut/Save/Select-All/Find/New/Open/Close/Print; 13–15 = sticky
  Ctrl/Alt/Shift; 16–18 = Enter/Space/Esc; dial = Volume ±/Mute.
- **Renamed the working folder** to `KeydialCommander` (recreated the venv at the new path since
  venvs hard-code paths; re-pointed the systemd unit; 128 tests still pass; app still served).
- **Fixed a shutdown hang** exposed by `systemctl restart`: with a browser/GUI WebSocket open,
  aiohttp waited on it for up to 90 s. The API now tracks open `/api/events` sockets and closes
  them on shutdown (+ bounded cleanup). A graceful restart with 8 clients connected now takes
  ~0.2 s.
- **Independence pass:** made every doc/file present the project as its own standalone thing —
  README (title → Keydial Commander, install/clone → KeydialCommander), a rewritten CONTRIBUTING
  for the current evdev architecture, `pyproject` URLs/description/keywords/author, NIXOS/flake/
  example Nix URLs, BRANCHING, ROADMAP, `.claude/agents/*`, and author metadata (`__init__`,
  pyproject). Renamed the uinput virtual-device name to `keydial-commander-uinput`.

## 2026-07-19 (deep night) — Phase 2B Commander frontend + shell COMPLETE

Set up Node via nvm (git-clone, no curl|bash; v24 at ~/.nvm — system node v18 shadows it, so
PATH-prepend every command; see memory `node-toolchain`). Built the full "Deck" GUI in 9 slices
on `feat/commander-frontend`, verifying each in the Browser pane against the live daemon:

- **Vite + React + TS** SPA in `web/`, building to the package's `web/dist` (served by the
  daemon's ApiServer; SPA + assets route added).
- Typed API client + TanStack Query + live WebSocket hook (pulse/identify/invalidation) + zustand.
- App layout + teal dark-first/light/system theme; ProfileBar (switch/create), StatusStrip.
- **DeviceStage**: K20 render (18 keys + dial zones), live key-highlight from WS, click-to-select,
  identify mode.
- **Inspector**: per-type editors — keystroke (ShortcutCapture via KeyboardEvent.code→KEY_* +
  manual picker + sticky), macro (step list), command (argv), profile_switch; save/clear/test-fire.
- **ActionLibrary** + dnd-kit drag-and-drop onto keys; **Settings** (dial sensitivity, theme,
  profile rename/duplicate/export/import/delete); edge states (daemon-down, disconnected,
  drop-conflict confirm).
- **GTK3/WebKit2 desktop shell** (`packaging/shell/commander_shell.py`, runs under system python3),
  `.desktop` + icon + `make install-shell` (user-local). Launched a real window on the session.
- **Verified in-browser end-to-end:** clicked BUTTON_1 → picked KEY_F9 → Save → key labeled "F9"
  and live in the daemon map; dragged "Mute" onto BUTTON_4 (created binding); Settings modal;
  rebound BUTTON_1→KEY_1 via API and confirmed in `keydialctl list-bindings`.
- Fixed a real CLI bug: `keydialctl list-bindings` showed "None" for keystroke bindings (still
  checked the old `keyboard` type name). Added `make build-web`. Python suite: 128 passing.

## 2026-07-19 (very late) — Phase 2A Commander backend COMPLETE

Executed the 8-task backend plan inline, TDD, one commit per task on
`feat/commander-backend`.

- **Typed action model:** `KeybindAction` gains `keystroke|macro|command|profile_switch`
  with per-type fields; `validate_action` enforces schemas + macro caps (≤32 steps, ≤10s);
  `ProfileStore` persists/loads all types; `keyboard`→`keystroke` alias.
- **ActionEngine:** executes each type (keystroke via uinput; macro with fake-clock-testable
  delays; command via `create_subprocess_exec`, **no shell**, detached; profile_switch incl.
  `"next"` cycling). Routed into `device._dispatch`.
- **Embedded aiohttp API** (`127.0.0.1:8137`): `/api/status`, `/api/keys`, full profiles +
  bindings CRUD (reusing ProfileStore/KeybindManager — active-profile edits reload the live
  map), settings, YAML export/import, `test-fire`, and `/api/events` WebSocket relaying the
  EventBus with clean unsubscribe. Serves the SPA placeholder; port written to XDG_RUNTIME_DIR.
- **Tests:** 99 → 127 passing (action model, action engine, api basic/profiles/events, daemon
  API). **Live smoke on the running daemon:** `GET /api/status` → `device.connected: true`
  (K20 grabbed), created a profile + macro binding over REST, read it back — all working.
- Added `aiohttp` dep; registered `web/` as package data. Phase 2B (React SPA + GTK shell)
  remains — needs Node/npm (still half-configured from the kernel dpkg issue).

## 2026-07-19 (late night) — Phase 1.5 evdev device layer COMPLETE + hardware-verified

Executed the 7-task evdev-grab plan inline, TDD, one commit per task on
`feat/evdev-device-layer`. New modules: `input_events`, `input_map`,
`input_translator` (combo/sticky parity), `evdev_source` (grab + async read +
hotplug rescan). Rewrote `device.py` to drive EvdevSource → translator → uinput
+ EventBus. Retired `hid_parser`, `bluetooth_watcher`, the unbind script/rule,
and the `bleak` + `dbus-next` dependencies. Rewrote `event_logger` as a live
evdev monitor. Caught + fixed a real bug (the daemon would grab its own uinput
output device, whose name also contains "keydial" — now excluded by name).

- **Tests:** 99 passing (parser-format tests replaced by `input_translator`/
  `input_map`/`evdev_source` suites incl. a live synthetic-uinput grab test).
- **LIVE HARDWARE E2E (the proof):** ran the real daemon → it grabbed
  event26+event27; bound BUTTON_1/2/3 → KEY_1/2/3 and dial CW/CCW/click →
  KEY_9/8/0; Earl typed into a text field and got **`1239998880`**
  (1,2,3 · 999 · 888 · 0) with **no k/g/l** — every layer works: EVIOCGRAB
  suppression, key mapping, dial rotation + click, uinput re-emit, and binding
  persistence across daemon restarts. Clean start/stop; device released to
  normal keyboard on exit.
- Confirmed the wheel sign convention (CW = REL_WHEEL −1 = DIAL_CW); INVERT_WHEEL
  stays False for this unit.

## 2026-07-19 (night) — Live hardware verification → ARCHITECTURE PIVOT

- **udev uaccess fix merged to main:** split rules into `70-` (uaccess for event nodes +
  `/dev/uinput`, must sort before systemd's `73-seat-late.rules`) and `99-` (unbind only).
  This is what finally gave the user session access to `/dev/uinput`.
- **Ran the real daemon end-to-end on the live K20.** It connected, subscribed to vendor
  `FFE1`, and received **zero input** on keypress. Diagnosed via three independent methods
  (all-notify D-Bus capture, real daemon, kernel evdev read).
- **CRITICAL FINDING (C1):** the K20 is a **standard BLE HID keyboard**; input flows through the
  standard HID service `0x1812` → BlueZ HoG → kernel evdev, invisible to bleak/D-Bus. `FFE1` is
  a firmware/status channel (its descriptor literally reads `HUION_T21h_230628`; sibling char =
  `OTA`). **The original driver's bleak→FFE1→hid_parser design never worked on this hardware.**
- **Proved the fix:** read the kernel evdev nodes directly (no sudo, via the `70-` uaccess rule) —
  all 18 buttons arrive as clean `KEY_*` on `event26`, dial rotation as `REL_WHEEL` on `event27`,
  dial-click as `KEY_PLAYPAUSE`. Full live-verified map in `DEVICE-K20.md` §G.
- **Decided (with user): pivot the device layer to evdev-grab + uinput** (keyd/xremap pattern),
  fold USB in (same evdev path). All Phase 1 control-plane work stays valid; only `device.py` +
  `hid_parser.py` get replaced. Corrected `DEVICE-K20.md` §E/F (my earlier "high confidence" FFE1
  conclusion was wrong), added audit addendum C1, inserted **Phase 1.5** in the roadmap, updated
  the design-spec architecture. Wrote the Phase 1.5 plan.

## 2026-07-19 (evening) — Phase 1 driver hardening COMPLETE

Executed the full 12-task plan (`docs/superpowers/plans/2026-07-19-phase1-driver-hardening.md`)
inline, TDD per task, one commit per task on `feat/phase1-driver-hardening`.

- **Audit findings closed:** H1 H2 H3 H4 H5 H6 · M1 M2 M3 M4 M5 M6 M8 M9 M10 · L1 L2 L3 L4
  L6 L7 L9 (+ most of L5/L8: event-logger test data fixed, poll loop → Event, `--user` flag
  removed). Remaining open: M7 (deb/rpm pipelines — Phase 4), L5's logger `--test` full rework,
  L8's monkey-patch pattern (works, noted).
- **New capabilities:** on-disk profiles with auto-persist + migration; `keydialctl profile
  list/switch/create/delete`; framed IPC v2 with timeouts at `$XDG_RUNTIME_DIR`; event
  streaming (`subscribe_events`) with battery/device state; Huion-only attach filter with
  D-Bus name lookup; FFE1-targeted subscription; async closeable uinput; real dial
  sensitivity; working systemd unit + udev rules.
- **Tests: 59 → 122 passing.** New suites: validation, keymap, config IO, profile store,
  IPC, manager persistence, event bus, device identity, uinput lifecycle, parser fixes,
  CLI, packaging meta.
- **Execution notes:** Tasks 8+9 landed in one commit (identity tests require the lazy
  uinput constructor — plan sequencing flaw found at runtime). Two test-design bugs caught
  and fixed during TDD (Python 3.12 `Server.wait_closed` semantics; event-stream needed
  client-EOF detection — the latter was a REAL production deadlock the test exposed).
  `KEY_CTRL`→`KEY_LEFTCTRL` corrected across legacy tests (the audit's landmine).
- Kernel packages on Earl's machine remain half-configured (`linux-*-7.0.0-28`), nodejs/npm
  in `iU` state — `sudo dpkg --configure -a` needed before Phase 2 frontend work.

## 2026-07-19 (later) — Spec approved, protocol probe, branch setup

- **Spec approved by Earl** (both design rounds + written document).
- **Branching model adopted** (`docs/BRANCHING.md`): GitHub-flow; today's work on
  `docs/audit-and-design`.
- **Device probe completed inline** (two background agent attempts were lost to process
  restarts) → `docs/DEVICE-K20.md`. Headline findings:
  - BlueZ does **not export** the HID service — the driver's true event source is vendor
    characteristic **FFE1**, previously undocumented. Explains the udev unbind design.
  - Kernel HID descriptors decoded: keyboard(1)/consumer(2)/radial(3)/mouse(5) report IDs;
    the radial interface is Surface-Dial-class.
  - Device connects via **hci1** here — audit M9 (hardcoded hci0) confirmed as a real,
    machine-breaking bug, not theoretical.
  - Vendor command channel candidates for Phase 3 LED/sleep: `…2b12`, FFE2. No writes made.
- **Phase 1 implementation plan** started per writing-plans skill (Phase 2 plans follow at
  their phase boundary).

## 2026-07-19 — Audit day

- **Full audit completed** (lead + senior code-audit agent): entire repo read, 25 defects
  confirmed (6 high), dead-code/duplication/doc-drift catalogued, test suite statically
  verified as implementation-matching but with major coverage gaps. → `AUDIT-2026-07-19.md`
- **Live device inspected**: K20 connected via BT as "Keydial mini-504" (90% battery),
  hid-generic currently handling it (driver not installed on this machine). USB confirmed
  charge-only with present cable; manual confirms USB-C data mode exists.
- **Official K20 manual retrieved** — exact physical layout (dial top-left; 4×5 grid, one
  double-wide + one double-tall key), LED/sleep vendor-settable, official driver's
  press-dial-to-cycle-3-modes behavior documented as parity target.
- **BLE protocol probe agent** dispatched (GATT table, report map decode) — report pending.
- **Product interview held.** Decisions locked (see ROADMAP Decisions log): web UI +
  Python backend; v1 = editor + profiles + macros + live status; Direction A "Deck"
  mockup; drag+click; dark-first + light; teal accent; webview window + tray;
  name **Keydial Commander**; BT now / USB later; user runs apt line for dev tooling.
- **Three UI mockups produced** → `docs/mockups/mockup-{a-deck,b-studio,c-commandgrid}.html`
  (A chosen).
- **Project agent team created** → `.claude/agents/` (gui-architect, ux-designer,
  driver-engineer, qa-verifier).
- Docs created: `AUDIT-2026-07-19.md`, `ROADMAP.md`, this worklog.
- Next: backend API approach proposal → design spec → implementation plan.
