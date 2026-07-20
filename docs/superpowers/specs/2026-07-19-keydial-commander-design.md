# Keydial Commander — Design Specification

**Date:** 2026-07-19 · **Status:** approved by Earl (structure + behavior rounds) · **Visual contract:** `docs/mockups/mockup-a-deck.html` (Direction A "Deck", re-skinned teal)
**Related:** `docs/AUDIT-2026-07-19.md` (defect IDs), `docs/ROADMAP.md` (phases, decisions log)

## 1. Purpose

Turn the huion-keydial-mini CLI driver into a real desktop application: **Keydial Commander**, a
Stream-Deck-class configurator for the Huion Keydial Mini (K20). Users visually assign, edit and
delete actions for 18 keys, chords, and the dial (CW/CCW/click), organize them into profiles,
build macros, launch apps, see live device status, and have every change persist. Bluetooth-only
in v1; USB later (roadmap Phase 3).

Non-goals for v1: LED-brightness/sleep vendor settings, dial multi-mode cycling, per-app
auto-switching, USB wired mode, raw event monitor page, text-snippet typing. All tracked in
`ROADMAP.md`.

## 2. Locked product decisions

Web UI + Python backend embedded in the daemon · React + TypeScript + Vite frontend ·
Deck layout (action library / device stage / inspector) · drag-and-drop AND click-to-edit ·
dark-first + light theme + follow-system, **teal/green accent** · desktop shell = PyGObject
window (WebKitGTK) + GNOME AppIndicator tray · name **Keydial Commander** · auto-persist every
mutation (no Save button — the mockup's Save/Revert buttons are superseded by Done/Clear; the
mockup remains the *layout* contract, this spec overrides interaction details) · distribution:
local-first, share-ready packaging later.

## 3. System architecture

One asyncio daemon process (the existing `huion-keydial-mini` service) plus one thin shell process.

> **Input-layer note (updated 2026-07-19 eve, Phase 1.5):** the device is a standard HID keyboard;
> input is read from **grabbed kernel evdev nodes**, not BLE. `EvdevSource` + `input_map` replace
> the old `BluetoothWatcher`/`bleak`/`HIDParser` chain. Everything downstream is unchanged.

```
┌─ daemon: huion-keydial-mini ─────────────────────────────────────────┐
│ EvdevSource (grab event26/27) ─→ input_map ─→ (action IDs)          │
│                                        │                             │
│                                        ▼                             │
│            ┌─ EventBus (in-proc pub/sub) ─→ WS clients               │
│            │                           │                             │
│            ▼                           ▼                             │
│  ProfileStore ◄──── shared ops/validation layer ────► ActionEngine   │
│      │  ▲                ▲         ▲                     │           │
│      ▼  │                │         │                     ▼           │
│  profiles/*.yaml   Unix socket   ApiServer (aiohttp)   UInputHandler │
│  config.yaml       (keydialctl)  127.0.0.1:<port>      /dev/uinput   │
│                                  REST + WS + static UI               │
└──────────────────────────────────────────────────────────────────────┘
┌─ shell: keydial-commander (PyGObject) ─┐
│ GTK4 window ⋅ WebKitGTK view of the UI │
│ AppIndicator tray: Open ⋅ profiles ⋅ Quit │
└────────────────────────────────────────┘
```

- **Shared ops layer** (`src/huion_keydial_mini/ops.py` + `validation.py`): every mutation/query
  used by BOTH the Unix socket and HTTP handlers. Single validator for action IDs, key names
  (against KEY_MAPPING), action schemas, profile names. Kills audit L3 drift.
- **EventBus**: async pub/sub; publishers = parser (action press/release), device (connect/
  disconnect/battery), ProfileStore (profile/bindings changed); subscribers = WS sessions,
  future monitor page.
- **ApiServer**: aiohttp `AppRunner` attached to the daemon's existing loop; binds
  `127.0.0.1` only; port from config (default 8137), actual port written to
  `$XDG_RUNTIME_DIR/huion-keydial-mini/port` for the shell to discover. Serves the built SPA
  from package data at `/`.
- **Unix socket** stays for `keydialctl` (framed protocol v2 per Phase 1), moved to
  `$XDG_RUNTIME_DIR/huion-keydial-mini/control.sock`, dir 0700 / sock 0600.
- **Shell process**: launches/focuses a GTK4 window with a WebKitGTK view of
  `http://127.0.0.1:<port>`; tray via AyatanaAppIndicator3 (Open, profile radio list from
  `GET /api/profiles`, Quit). Ships a `.desktop` file + icon. If the daemon is down, the shell
  shows the same "service down" page the SPA renders (served state is unreachable, so the shell
  embeds a minimal static fallback).

**Phase-1 dependency:** this design assumes the driver hardening lands first (audit H1–H6, M5,
M8, M10, L1–L4): fixed systemd unit, device-identity filter, persistence bridge, IPC v2,
detent-accumulator sensitivity, closeable async uinput. The GUI builds on those primitives.

## 4. Data model & persistence

### Files
```
~/.config/huion-keydial-mini/
  config.yaml          # device/bluetooth/uinput/api settings
  profiles/active      # active-profile pointer (single-writer ProfileStore;
                       # amended from config.yaml placement — Phase 1 plan deviation)
  profiles/
    Default.yaml       # one file per profile; filename == profile name
    Krita.yaml
```
- All writes via ruamel.yaml round-trip mode: user comments survive (fixes H3).
- One-time migration: legacy `key_mappings`/`sticky_key_mappings`/`dial_settings` sections in
  config.yaml move into `profiles/Default.yaml`; originals removed with a comment noting the move.
- Every mutation persists immediately and atomically (write temp + rename).

### Profile schema (YAML)
```yaml
# profiles/Krita.yaml
schema: 1
dial_sensitivity: 1.0          # detents per emitted event, applied by accumulator
bindings:
  BUTTON_1: {type: keystroke, keys: [KEY_LEFTCTRL, KEY_Z]}
  BUTTON_13: {type: keystroke, keys: [KEY_LEFTCTRL], sticky: true}
  BUTTON_1+BUTTON_2: {type: command, argv: [xdg-open, "https://docs.krita.org"]}
  BUTTON_16:
    type: macro
    steps:
      - {keys: [KEY_LEFTCTRL, KEY_LEFTSHIFT, KEY_E]}
      - {delay_ms: 400}
      - {keys: [KEY_ENTER]}
  DIAL_CW:  {type: keystroke, keys: [KEY_RIGHTBRACE]}
  DIAL_CCW: {type: keystroke, keys: [KEY_LEFTBRACE]}
  DIAL_CLICK: {type: profile_switch, profile: next}
```

### Action types (engine level)
| type | fields | notes |
|---|---|---|
| `keystroke` | `keys: [KEY_*/BTN_*]`, `sticky: bool=false` | chords pressed in order, released in reverse (existing behavior); sticky = hold semantics (existing parser support) |
| `macro` | `steps: [{keys: […]} \| {delay_ms: int}]`, caps: ≤32 steps, ≤10 s total | executes on press; ignores repeat while running |
| `command` | `argv: [str]`, `detach: true` | no shell by default; UI sugar "Launch app" (desktop entry → argv) and "Open URL" (`xdg-open`) compile to this |
| `profile_switch` | `profile: <name> \| next` | daemon swaps active bindings atomically |

Media keys are keystroke presets in the UI library, not a distinct type. `action_id` grammar is
unchanged (`BUTTON_1..18`, sorted `+`-chords, `DIAL_CW/CCW/CLICK`).

## 5. API (v1)

REST, JSON, `127.0.0.1` only. Errors: `{error: {code, message}}` with 4xx/5xx.

| Method & path | Purpose |
|---|---|
| `GET /api/status` | `{device: {connected, name, mac, battery, transport}, service: {version, uptime}, active_profile}` |
| `GET /api/profiles` | list `[{name, binding_count, active}]` |
| `POST /api/profiles` | create `{name, clone_from?}` |
| `PUT /api/profiles/{name}` | rename `{new_name}` |
| `DELETE /api/profiles/{name}` | delete (400 if last remaining profile) |
| `POST /api/profiles/{name}/activate` | make active |
| `GET /api/profiles/{name}/bindings` | full binding map + dial_sensitivity |
| `PUT /api/profiles/{name}/bindings/{action_id}` | upsert action (validated) |
| `DELETE /api/profiles/{name}/bindings/{action_id}` | remove |
| `PUT /api/profiles/{name}/settings` | `{dial_sensitivity}` |
| `POST /api/test-fire` | `{action}` — execute once now (no binding required) |
| `GET /api/keys` | grouped KEY_MAPPING names for pickers |
| `GET /api/profiles/{name}/export` | download profile YAML |
| `POST /api/profiles/import` | upload YAML `{name_override?}` |

WebSocket `/api/events` (server→client):
`{type: key_event, action_id, pressed}` · `{type: device_state, connected, battery}` ·
`{type: profile_changed, name}` · `{type: bindings_changed, profile}`.
No client→server commands over WS (REST does mutations); WS reconnect is client-driven.

Consistency: mutations broadcast `bindings_changed`; a second open UI refetches. Last write wins.

## 6. Frontend

Stack: React 18 + TypeScript + Vite; TanStack Query (REST cache, invalidated by WS events);
zustand for UI-local state (selection, drag, capture mode); dnd-kit for drag-and-drop; no CSS
framework — hand-rolled CSS variables per the mockup, teal accent, `[data-theme]` dark/light +
follow-system.

Layout (per mockup A): ProfileBar (top) · ActionLibrary (left) · DeviceStage (center) ·
Inspector (right) · StatusStrip (bottom).

- **DeviceStage**: faithful K20 — dial (three drop/click zones: CW arc, CCW arc, center click)
  top-left; 4×5 grid, bottom-left double-wide, right-column double-tall; keys numbered 1–18 with
  assigned-action labels. WS `key_event` pulses keys live. "Identify mode": next physical press
  selects that key (also the empirical check that BUTTON_n numbering matches physical positions —
  see §9 Open items).
- **ActionLibrary**: searchable templates grouped Input / System / Media / Device. Dragging onto
  a key/dial zone creates a binding with sensible defaults and opens the Inspector; templates are
  also clickable when a key is selected.
- **Inspector**: per-type editors — keystroke (ShortcutCapture + sticky toggle), macro (step list
  editor with reorder/delete, delay rows), command (app picker from installed .desktop entries,
  URL field, raw argv mode), profile_switch (profile dropdown / "next"). Test-fire button
  (`POST /api/test-fire`). Clear removes the binding. Edits apply on Done (single PUT).
- **ShortcutCapture**: focused field captures a real key combo via KeyboardEvent.code with a
  code→KEY_* mapping table; Wayland-unreliable keys (e.g. Super in some browsers) covered by a
  manual picker fallback (grouped from `GET /api/keys`).
- **ProfileBar**: chips + create/duplicate/rename/delete (modals), import/export.
- **StatusStrip**: connection, battery, daemon version; click opens Settings modal
  (dial sensitivity for active profile, theme, service info, port).

## 7. Error handling & resilience

- **Daemon down**: SPA full-screen state with `systemctl --user restart huion-keydial-mini-user`
  hint + auto-retry; shell embeds equivalent static fallback. WS reconnects with capped backoff.
- **Device disconnected/asleep**: stage dims + banner ("Press any key on the device to wake it");
  editing remains fully functional — daemon owns state, nothing needs pushing to hardware.
- **Conflicts**: UI warns when a drop/edit targets an already-bound action_id, offers overwrite.
- **Validation**: UI makes invalid input hard; shared validator rejects it anyway (unknown keys,
  malformed IDs, oversize macros). API never trusts the client.
- **ActionEngine safety**: macros capped (32 steps/10 s), one at a time (re-trigger ignored while
  running); commands run detached without shell, failures logged + surfaced as toast via WS.
  Commands execute as the user — same trust level as their own shell; documented plainly.
- **Daemon integrity**: all API/socket handlers exception-bounded; a GUI-path failure can never
  kill BLE/uinput; `Restart=on-failure` (Phase 1) as backstop. Persistence failures toast+retry,
  never crash.
- **Concurrency**: single-writer daemon; atomic file writes; last-write-wins + WS refresh.

## 8. Testing

- **Backend (pytest)**: ProfileStore round-trip incl. comment preservation + migration;
  ActionEngine per type (fake clock for macro delays; command uses a stub argv); API contract
  tests (aiohttp test client) for every endpoint incl. validation failures; socket-v2 framing;
  EventBus fan-out; existing parser suite stays green.
- **Frontend (vitest + Testing Library)**: ShortcutCapture code→KEY_* table; inspector form
  logic per action type; reducer/store behavior for drag-assign.
- **End-to-end**: qa-verifier agent drives REST+WS against a running daemon with simulated HID
  input at the parser boundary; manual hardware checklist (live highlight = smoke test).
  Playwright deferred to Phase 4 CI.

## 9. Open items (tracked, non-blocking)

1. **Physical key numbering**: BUTTON_n → physical position hypothesis (numpad-like reading
   order) is unverified; the DeviceStage "identify mode" doubles as the verification tool during
   first hardware session. Layout map kept as a single frontend constant for easy correction.
2. **BLE protocol probe** (agent report pending): GATT report map may refine parser assumptions
   (M6 byte-window) and informs Phase 3 vendor features; does not change this design.
3. **Tray dependency**: GNOME requires the AppIndicator extension for tray icons; shell degrades
   gracefully (window-only) when absent. Documented in install notes.
4. **Port default 8137**: revisit only if it collides on the user's machine.

## 10. Implementation phasing

Phase 1 (driver hardening) precedes GUI work — see `ROADMAP.md`. The GUI lands as Phase 2 in
vertical slices: (a) API+status+one profile read-only stage → (b) binding CRUD via inspector →
(c) drag-and-drop + library → (d) macros/commands → (e) profiles UX → (f) live events/highlight →
(g) shell+tray → (h) import/export+settings. Each slice ships tested.
