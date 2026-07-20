# Phase 2B — Keydial Commander Frontend + Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Build in vertical slices, verify each in the Browser pane, commit per slice.

**Goal:** Build the Keydial Commander web UI (the "Deck" interface from `docs/mockups/mockup-a-deck.html`) against the frozen Phase 2A API, served by the daemon, plus a lightweight GTK WebKit desktop shell.

**Architecture:** Vite + React + TypeScript SPA in `web/`, building to `src/huion_keydial_mini/web/dist/` (served by the Phase 2A `ApiServer`). Data via a small typed API client + TanStack Query, with a WebSocket hook (`/api/events`) driving live updates and query invalidation. zustand for UI-local state (selection, drag, capture). dnd-kit for drag-and-drop. Hand-rolled CSS with variables (teal accent, dark-first + light + follow-system). Desktop shell: a system-python GTK3 + WebKit2 window (`commander_shell.py`) pointing at the daemon's URL, plus a `.desktop` launcher; no tray (no AppIndicator on this host — documented).

**Tech Stack:** Node v24 (nvm — prepend `~/.nvm/versions/node/v24.18.0/bin` to PATH every command), Vite, React 18, TypeScript, @tanstack/react-query, zustand, @dnd-kit/core; GTK3/WebKit2 via system python3 for the shell.

## Global Constraints

- **Every frontend shell command starts with** `export PATH="$HOME/.nvm/versions/node/v24.18.0/bin:$PATH"` (system node v18 shadows nvm — see memory `node-toolchain`).
- Frontend source lives in `web/` (repo root). Build output → `src/huion_keydial_mini/web/dist/`. Keep `src/huion_keydial_mini/web/index.html` placeholder as the pre-build fallback.
- API base: same-origin `/api`. Dev: Vite proxies `/api` (incl. the `/api/events` WebSocket) to `http://127.0.0.1:8137`.
- Vite `base: "/"`; assets emitted under `dist/assets/`. The ApiServer must serve `dist/` (index + assets) when it exists, else the placeholder.
- Theme: CSS variables; default dark; `@media (prefers-color-scheme)` + a `[data-theme]` override toggle. Accent teal `#2dd4a7`.
- Device layout constant (from `DEVICE-K20.md` §G): 18 keys in a 4×5-ish grid with dial top-left; keys numbered BUTTON_1..18; dial zones DIAL_CW/CCW/CLICK. Keep the physical layout as ONE constant (`deviceLayout.ts`) for easy correction.
- Verify each slice in the Browser pane against a running daemon + Vite dev server. Commit per slice on branch `feat/commander-frontend`.
- Commit messages end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

### Task 1: Scaffold + build wiring + ApiServer serves dist

- Branch `feat/commander-frontend`. Scaffold Vite React-TS in `web/` (`npm create vite@latest . -- --template react-ts` in an empty `web/`), set `vite.config.ts`: `build.outDir = "../src/huion_keydial_mini/web/dist"`, `build.emptyOutDir = true`, `server.proxy` for `/api` (with `ws: true`) → `http://127.0.0.1:8137`.
- Update `ApiServer`: if `web/dist/index.html` exists, serve `dist/` (add static route for `/assets`, serve `dist/index.html` at `/` and as SPA fallback); else the placeholder.
- App renders `/api/status` (daemon version + active profile) as a smoke screen.
- **Verify:** run daemon; `npm run dev`; Browser pane → Vite URL shows status. Then `npm run build`; load daemon URL directly → same screen from `dist/`.
- Commit `scaffold Commander SPA and serve built assets from the daemon`.

### Task 2: API client + types + query/WS hooks

- `web/src/api/types.ts` (Action union, Profile, Binding, StatusEvent), `web/src/api/client.ts` (typed fetch wrappers for every 2A endpoint), `web/src/api/queries.ts` (TanStack Query hooks), `web/src/api/useEvents.ts` (WebSocket hook → dispatches to a zustand store + invalidates queries).
- **Verify:** a debug panel logs live `key_event`s while pressing the device.
- Commit `add typed API client, query hooks, and live event socket`.

### Task 3: Layout shell + theme + StatusStrip + ProfileBar

- `App.tsx` grid: ProfileBar (top), ActionLibrary (left), DeviceStage (center placeholder), Inspector (right placeholder), StatusStrip (bottom). CSS variables + theme toggle (`theme.ts`, `theme.css`).
- ProfileBar: chips from `GET /api/profiles`, active highlighted, switch on click; StatusStrip: connection + version.
- **Verify:** switching profiles in the UI flips the active chip and (via WS) reflects everywhere.
- Commit `add app layout, theme, profile bar, and status strip`.

### Task 4: DeviceStage — K20 render + live highlight + selection

- `deviceLayout.ts` (positions for 18 keys + dial zones), `DeviceStage.tsx` rendering the device with each key showing its bound action label (from active profile bindings). WS `key_event` pulses the pressed key. Click a key/dial-zone → sets selection in the zustand store. "Identify mode": next physical press selects that control.
- **Verify:** pressing a physical button highlights the right key; clicking selects it.
- Commit `add device stage with live key highlight and selection`.

### Task 5: Inspector — per-type editors + ShortcutCapture

- `Inspector.tsx`: shows the selected control; action-type dropdown; per-type editors — keystroke (`ShortcutCapture` capturing `KeyboardEvent.code`→`KEY_*` + sticky toggle + manual key picker from `GET /api/keys`), macro (step list add/reorder/delete + delay rows), command (app/URL/raw-argv), profile_switch (profile dropdown / "next"). Save = `PUT` binding; Clear = `DELETE`; Test-fire button = `POST /api/test-fire`.
- `codeToKey.ts` maps browser key codes to `KEY_*` (with Wayland-unreliable-key note + manual fallback).
- **Verify:** bind BUTTON_1 → a captured shortcut; press the device → remapped output; test-fire works.
- Commit `add inspector with per-type editors and shortcut capture`.

### Task 6: ActionLibrary + drag-and-drop

- `ActionLibrary.tsx`: searchable grouped templates (Input/System/Media/Device). dnd-kit: drag a template onto a key/dial-zone → creates a binding with sensible defaults and opens the Inspector. Templates also clickable when a control is selected.
- **Verify:** drag "Copy" onto a key → binding created and persisted.
- Commit `add action library with drag-and-drop assignment`.

### Task 7: Profiles UX + Settings + edge states

- Profile create/duplicate/rename/delete modals; import/export (download/upload YAML). Settings modal (dial sensitivity slider → `PUT settings`; theme; service info/port). Edge states: daemon-down (full-screen + retry), device-disconnected (dimmed stage banner), empty profile, binding conflict (overwrite confirm).
- **Verify:** each state renders; sensitivity change affects the dial live.
- Commit `add profiles management, settings, and edge states`.

### Task 8: Production build wired into the daemon + hardware verify

- `npm run build` → `dist/`; confirm the daemon serves the full app at its URL (assets load, WS connects). Add an npm build step note to README/packaging. `.gitignore` `web/node_modules` and `web/dist` (built on release) — but commit a built `dist/` for now so the daemon works without Node? Decide: gitignore `dist`, document `npm --prefix web run build` as a build step (Makefile target `build-web`).
- **Verify on hardware:** open the daemon URL in the Browser pane; bind a key via the UI; press the device → remapped; live highlight works.
- Commit `wire production SPA build into the daemon serving`.

### Task 9: Desktop shell (GTK WebKit) + launcher

- `packaging/shell/commander_shell.py` (run via **system** python3 — has `gi` + WebKit2-4.1): read the daemon port from `$XDG_RUNTIME_DIR/huion-keydial-mini/port` (fallback 8137), open a GTK3 window with a WebKit2 WebView of `http://127.0.0.1:<port>`. If the daemon/port is absent, load a small "start the service" page. **No tray** (no AppIndicator on this host) — documented; window-only.
- `packaging/shell/keydial-commander.desktop` + an icon; a `make install-shell` target. A `keydial-commander` convenience wrapper that launches the shell (or `xdg-open` the URL as ultimate fallback).
- **Verify:** launch the shell → the app window opens showing the UI.
- Commit `add GTK WebKit desktop shell and launcher`; then merge `feat/commander-frontend` → main (present to user first).

## Verification checklist (whole phase)

- [ ] Daemon serves the full SPA at its URL (assets + WebSocket)
- [ ] Live key highlight on physical press; identify-mode selection
- [ ] Bind/edit/clear each action type from the Inspector; changes hit the live device
- [ ] Drag-and-drop assignment from the library
- [ ] Profiles create/switch/rename/delete + import/export; dial sensitivity live
- [ ] Edge states render (daemon-down, disconnected, empty, conflict)
- [ ] Desktop shell window opens the UI
- [ ] Frontend unit tests (vitest) for `codeToKey` + inspector reducers pass
