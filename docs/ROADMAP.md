# Roadmap — Huion Keydial Mini Controller → **Keydial Commander**

Working document. Updated as phases complete; see `WORKLOG.md` for the running change log and
`AUDIT-2026-07-19.md` for defect IDs referenced below (H1…L9).

## Vision

Take the existing Bluetooth CLI driver and grow it into a real desktop application —
**Keydial Commander** — a Stream-Deck-class configurator for the Huion Keydial Mini (K20):
assign/edit/delete every key, chord, and dial action visually, with profiles, macros,
live device status, and settings that persist.

## Decisions log

| Date | Decision |
|---|---|
| 2026-07-19 | GUI = **web UI + Python backend** (extends the existing daemon; no Electron/Qt) |
| 2026-07-19 | v1 scope = visual binding editor **+ profiles + macros/app-launch + live status/testing** |
| 2026-07-19 | Distribution = **works great locally first**, packaging kept share-ready for later releases |
| 2026-07-19 | **Bluetooth now, USB wired mode on the roadmap** (Phase 3) — USB-C is data-capable per the official manual, but current cable is charge-only |
| 2026-07-19 | Visual direction = **mockup A "Deck"** (`docs/mockups/mockup-a-deck.html`): action library ⋅ device stage ⋅ inspector |
| 2026-07-19 | Interaction = **drag-and-drop AND click-to-edit** |
| 2026-07-19 | Theme = **dark-first + light option**; accent = **teal/green** |
| 2026-07-19 | App shell = **desktop window (webview) + GNOME tray indicator**, `.desktop` launcher |
| 2026-07-19 | Name = **Keydial Commander** |
| 2026-07-19 | Dev tooling: user runs one apt line when implementation starts (python3-venv, pip, nodejs, npm) |
| 2026-07-19 | Backend API = **embedded aiohttp in the daemon** + React/TS/Vite frontend (approved) |
| 2026-07-19 (eve) | **ARCHITECTURE PIVOT (live-verified):** K20 is a standard BLE HID keyboard; input is on kernel evdev, NOT vendor FFE1. Driver device layer pivots from bleak/FFE1 to **evdev-grab + uinput**. USB folded in (same evdev path). See `AUDIT` addendum C1 + `DEVICE-K20` §E–G. |

## Phase 0 — Environment & baseline (prerequisite) — ✅ done 2026-07-19

- [x] User installed `python3.12-venv` (pip arrived via venv bootstrap; **nodejs/npm remain half-configured** pending `sudo dpkg --configure -a` — needed before Phase 2 frontend)
- [x] Create venv, install `-e .[test]`, **run the full pytest suite** — 59 passed baseline
- [ ] Baseline lint (`ruff`) added to dev extras (deferred to Phase 2 CI groundwork)

## Phase 1 — Driver hardening — ✅ done 2026-07-19 (branch `feat/phase1-driver-hardening`)

Everything the GUI will stand on. Fixed audit findings:

- [x] **Persistence** (H5, H3): ProfileStore (one YAML per profile + `profiles/active`), every mutation auto-persisted atomically; comment-preserving config IO (ruamel.yaml)
- [x] **Working systemd unit** (H1) + phantom entry point removed (M1)
- [x] **Device identity** (H2): Huion/Keydial name filter for auto-discover with D-Bus name lookup; `clear-device` fixed (H4); real MAC validation (L4)
- [x] **IPC v2** (L1, M8, L3): newline-framed protocol, client timeouts, single shared validator (action IDs + key names), socket in `$XDG_RUNTIME_DIR` at 0600
- [x] **Profiles engine** (pulled forward from Phase 2): create/clone/switch/delete via socket + `keydialctl profile` group
- [x] **Dial sensitivity semantics** (M5): detent accumulator
- [x] **uinput lifecycle** (H6, M10): async open with backoff, `.close()` on stop, static `list-keys`
- [x] **Event stream**: `subscribe_events` (EventBus) streaming key events + device state incl. battery
- [x] Parser state reset on disconnect (L9); full type-1 byte window bytes 2–7 (M6); dial config chords split correctly via migration (L2)
- [x] Doc truth pass: README bind syntax (M2), claims (M3), version single-sourcing (L7)
- [x] Dead code / unused import sweep (audit §4); udev uaccess rule matches real device names (M4)
- [x] Tests: 122 passing (was 59) — config round-trips, socket framing, CLI, dial < 1.0, identity filter, uinput lifecycle, fixtures fixed
- Deferred: `scan_devices` socket command → dropped (BLE-scan pairing is not part of the evdev architecture; the daemon auto-detects the device by name/VID:PID)

## Phase 1.5 — Device-layer pivot to evdev-grab — ✅ DONE + hardware-verified 2026-07-19

The BLE/FFE1 input path never worked on this hardware (audit addendum C1). Replace it with the
standard Linux input-remapper architecture. Plan:
`docs/superpowers/plans/2026-07-19-phase1.5-evdev-device-layer.md`.

- [x] `evdev_source.py`: find + open + `EVIOCGRAB` the K20 evdev nodes (event26 keyboard,
      event27 mouse) by name `*Keydial*` / VID:PID `256C:8251`; async read loop; hotplug
      (grab on appear, release on disappear) via a udev/pyudev monitor or periodic rescan
- [x] `input_map.py`: fixed-firmware `KEY_*`→action-ID table (DEVICE-K20 §G), `REL_WHEEL` sign →
      DIAL_CW/CCW, `KEY_PLAYPAUSE` → DIAL_CLICK; chord detection from simultaneous key-downs
- [x] Rewrite `device.py` to drive `evdev_source` → `input_map` → keybind_manager → uinput +
      EventBus (keep the exact same downstream interfaces so Phase 1 stays intact)
- [x] Retire `hid_parser.py` (vendor-frame parser), `bluetooth_watcher.py`, bleak dependency,
      the `hid-generic` unbind script + rule (grab replaces them)
- [ ] Battery via BlueZ `2a19` over D-Bus, decoupled from the input path (optional, for status) — deferred to Phase 2 status strip; `_on_state` currently publishes `battery: None`
- [ ] USB wired mode: same evdev nodes; add USB udev match; verify with a data cable — code path is transport-agnostic but not yet verified on USB (needs a data cable)
- [x] Tests: input_map table, chord detection, grab/release lifecycle (mock evdev), device
      hotplug; end-to-end with a virtual uinput source device
- [x] Live verify: real K20 — press → remapped output observed; original keys suppressed by grab

## Phase 2 — Keydial Commander v1 (the GUI)

Design spec: `docs/superpowers/specs/2026-07-19-keydial-commander-design.md`. Direction A mockup is
the visual contract. Split into **2A backend** (plan:
`docs/superpowers/plans/2026-07-19-phase2a-commander-backend.md`) and **2B frontend + shell**
(outlined at the end of the 2A plan; detailed after the 2A API contract is frozen; needs Node/npm).

### Phase 2A — Backend — ✅ DONE 2026-07-19 (branch `feat/commander-backend`)

- [x] Backend: embedded aiohttp API server in the daemon — REST CRUD + WebSocket live events
- [x] Profiles engine already in place (Phase 1); REST exposes create/rename/delete/activate + export/import
- [x] Action types: keystroke (+chords, sticky), macro (steps + delays), command (detached, no shell), profile_switch (name or "next") — via ActionEngine
- [x] `test-fire`, `/api/keys`, `/api/status`, `/api/events` WebSocket; serves the SPA statically; port written to `$XDG_RUNTIME_DIR`
- [x] 127 tests passing; live-smoke-verified against the running daemon on hardware

### Phase 2B — Frontend + Shell — ✅ DONE 2026-07-19 (branch `feat/commander-frontend`)

- [x] Frontend (Direction A, teal accent, dark-first + light + system): Vite/React/TS SPA — device stage with live key highlight + identify mode, drag-and-drop action library, per-type inspector (shortcut capture + macro/command/profile editors), profile bar, status strip
- [x] Profiles UX (create/clone/rename/duplicate/delete, YAML import/export), Settings modal (dial sensitivity, theme), edge states (daemon-down, disconnected, drop-conflict)
- [x] Served by the daemon from `web/dist`; `make build-web`
- [x] GTK3/WebKit2 desktop shell + `.desktop` launcher + icon (`make install-shell`); window-only (no AppIndicator on this host)
- [x] Verified in-browser end-to-end: bound BUTTON_1→KEY_F9/KEY_1 and BUTTON_4→Mute via the UI, reflected live in the daemon map; drag-drop, inspector, settings all confirmed
- [ ] Import/export profiles (JSON)
- [ ] App shell: webview window + `.desktop` entry + GNOME AppIndicator tray (profiles, open, quit)
- [ ] E2E happy-path tests (backend API + frontend build in CI-able form)

## Phase 3 — Deeper device integration

- [ ] **Dial modes**: press-dial-to-cycle N dial function sets (parity with official driver) — now a
      pure daemon-side feature (dial-click cycles the active dial mapping set)
- [ ] **Vendor GATT features**: LED brightness + sleep timer (reverse-engineer vendor `…2b12`/FFE2
      write commands from official-driver captures; safe read-only probe first) — the one place
      BLE/D-Bus is still needed
- [ ] Battery low warnings; reconnect UX (via BlueZ 2a19 + connection state)
- [ ] Per-app auto-profile-switching — **Wayland caveat**: no portable active-window API; GNOME path = small shell-extension or D-Bus introspection; design as optional helper
- [ ] Live event monitor page (grabbed evdev stream, parsed), replacing `event_logger --test` (L5)
- [ ] ~~USB wired mode~~ — folded into Phase 1.5 (same evdev path); ~~multi-adapter (M9)~~ moot (no BLE input)

## Phase 4 — Share-ready

- [ ] Fix Debian/RPM packaging (M7), refresh Arch/Nix, add Commander to packages
- [ ] CI: lint + pytest + frontend build + package smoke
- [ ] Docs overhaul (install, GUI guide, protocol doc), screenshots
- [ ] Publish tagged releases + built artifacts on the KeydialCommander repo

## Later / wishlist

- Text-snippet typing action (uinput sequence)
- Long-press alternate key actions
- Profile sync/backup; mobile-browser access to the UI
- Community profile sharing format
