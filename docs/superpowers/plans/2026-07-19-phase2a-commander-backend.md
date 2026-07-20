# Phase 2A — Keydial Commander Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or subagent-driven-development) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Extend the daemon with the Keydial Commander backend — a typed action engine (keystroke / macro / command / profile-switch) and an embedded aiohttp REST + WebSocket API on `127.0.0.1` that the React frontend (Phase 2B) and any client can drive — without changing the proven Phase 1/1.5 input pipeline.

**Architecture:** The daemon keeps `EvdevSource → InputTranslator → device._dispatch`. `_dispatch` now routes each action through a new `ActionEngine` (keystroke still emits via `UInputHandler`; macro/command/profile-switch fire on press). An `ApiServer` (aiohttp `AppRunner` on the daemon's loop) exposes REST CRUD over `ProfileStore`/`KeybindManager` plus a WebSocket that relays `EventBus` events, and serves the built SPA as static files.

**Tech Stack:** Python ≥3.8, aiohttp (new dep), asyncio, existing ProfileStore/KeybindManager/EventBus/UInputHandler, pytest + aiohttp test utilities.

## Global Constraints

- Python floor 3.8: `typing.Optional/List/Dict`, no `X | Y`, no `match`.
- API binds **`127.0.0.1` only**, default port **8137** (config `api.port`); the actual bound port is written to `$XDG_RUNTIME_DIR/huion-keydial-mini/port` (via `ipc.runtime_dir()`).
- Never block the loop: macro delays use `asyncio.sleep` (injectable for tests); subprocess launch is non-blocking (`asyncio.create_subprocess_exec`, detached, **no shell**).
- REST mutations reuse the SAME `ProfileStore`/`KeybindManager` operations as the Unix socket — no duplicate logic. All validation goes through `validation.py`.
- Action types persisted by `ProfileStore` as `type: keystroke|macro|command|profile_switch`; `keyboard` accepted as an alias for `keystroke` on read.
- Freeze Phase 1/1.5 interfaces: `EvdevSource`, `InputTranslator`, `EventBus.publish/subscribe`, `ProfileStore`, `KeybindManager.get_action/switch_profile`, `UInputHandler.send_event`.
- Serve the SPA from package data dir `src/huion_keydial_mini/web/` (create with a placeholder `index.html` now; Phase 2B fills it). `GET /` serves `index.html`; unknown non-`/api` paths fall back to `index.html` (SPA routing).
- Errors: JSON `{"error": {"code": <str>, "message": <str>}}` with 4xx/5xx; success bodies are plain JSON.
- All work on branch `feat/commander-backend`; `.venv/bin/pytest tests/ -q` stays green.
- Commit messages end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

### Task 0: Branch + aiohttp dependency

- [ ] **Step 1:** `git checkout main && git checkout -b feat/commander-backend`
- [ ] **Step 2:** add `"aiohttp>=3.9"` to `pyproject.toml` `dependencies`; `.venv/bin/pip install -e ".[test]"` → installs aiohttp.
- [ ] **Step 3:** `.venv/bin/pytest tests/ -q` → 99 passing baseline.
- [ ] **Step 4:** commit `add aiohttp dependency for Commander API`.

---

### Task 1: Typed action model (keystroke / macro / command / profile_switch)

**Files:** Modify `keybind_manager.py` (`KeybindAction`), `validation.py` (add `validate_action`), `profile_store.py` (load/save all types), `uinput_handler.py` (keystroke type check); Test `tests/test_action_model.py`

**Interfaces produced:**
- `KeybindAction` fields: `type: str` (`"keystroke"|"macro"|"command"|"profile_switch"`), `keys: Optional[List[str]]`, `sticky: bool=False`, `steps: Optional[List[dict]]=None` (macro: `{"keys":[...]}` or `{"delay_ms":int}`), `argv: Optional[List[str]]=None` (command), `profile: Optional[str]=None` (profile_switch), `description: Optional[str]=None`. `to_dict()`/`from_dict()` round-trip; `from_dict` maps legacy `"keyboard"`→`"keystroke"`.
- `validation.validate_action(data: dict) -> dict` — returns a normalized action dict or raises `ValidationError`. Enforces per-type required fields; keystroke keys via `validate_keys`; macro ≤32 steps and total delay ≤10000 ms; command argv non-empty list of str; profile_switch profile is non-empty str or `"next"`.

- [ ] **Step 1 (test):** `tests/test_action_model.py`:
```python
import pytest
from huion_keydial_mini.keybind_manager import KeybindAction
from huion_keydial_mini.validation import validate_action, ValidationError

def test_keystroke_roundtrip():
    a = KeybindAction.from_dict({"type": "keystroke", "keys": ["KEY_LEFTCTRL", "KEY_C"]})
    assert a.type == "keystroke" and a.keys == ["KEY_LEFTCTRL", "KEY_C"]
    assert a.to_dict()["type"] == "keystroke"

def test_legacy_keyboard_alias():
    assert KeybindAction.from_dict({"type": "keyboard", "keys": ["KEY_A"]}).type == "keystroke"

def test_macro_roundtrip():
    a = KeybindAction.from_dict({"type": "macro", "steps": [
        {"keys": ["KEY_LEFTCTRL", "KEY_S"]}, {"delay_ms": 100}, {"keys": ["KEY_ENTER"]}]})
    assert a.type == "macro" and len(a.steps) == 3

def test_validate_action_ok():
    validate_action({"type": "keystroke", "keys": ["KEY_A"]})
    validate_action({"type": "command", "argv": ["xdg-open", "https://x"]})
    validate_action({"type": "profile_switch", "profile": "next"})
    validate_action({"type": "macro", "steps": [{"keys": ["KEY_A"]}, {"delay_ms": 50}]})

@pytest.mark.parametrize("bad", [
    {"type": "keystroke", "keys": ["KEY_BOGUS"]},
    {"type": "keystroke", "keys": []},
    {"type": "command", "argv": []},
    {"type": "command"},
    {"type": "profile_switch", "profile": ""},
    {"type": "macro", "steps": [{"delay_ms": 99999}]},          # > 10s
    {"type": "macro", "steps": [{"keys": ["KEY_A"]}] * 40},      # > 32 steps
    {"type": "nope"},
])
def test_validate_action_rejects(bad):
    with pytest.raises(ValidationError):
        validate_action(bad)
```
- [ ] **Step 2:** run → fails.
- [ ] **Step 3:** Implement.
  - `KeybindAction`: change `type` to `str`; add `steps`/`argv`/`profile`; `from_dict` normalizes `"keyboard"`→`"keystroke"`, defaults `type="keystroke"`; `to_dict` emits only the fields relevant to the type (omit `None`s). Keep `EventType` enum for backward import but stop using it as the `type` value.
  - `validation.validate_action`: dispatch on `type`; reuse `validate_keys`; enforce the caps above; return normalized dict.
  - `profile_store`: `save_binding` serializes by type (`entry = action.to_dict()` minus `description` if empty); `load_bindings` builds `KeybindAction.from_dict(raw)` for ALL types (remove the "unsupported type" skip + `_TYPE_ALIASES` special-case, now handled in `from_dict`).
  - `uinput_handler._send...`/`send_event`: change `action.type == BindEventType.KEYBOARD` to `action.type in ("keystroke", "keyboard")`.
- [ ] **Step 4:** run new test + full suite → green (existing keystroke bindings still load/save).
- [ ] **Step 5:** commit `add typed action model (keystroke/macro/command/profile_switch)`.

---

### Task 2: ActionEngine

**Files:** Create `src/huion_keydial_mini/action_engine.py`; Test `tests/test_action_engine.py`

**Interfaces produced:**
- `class ActionEngine:`
  - `__init__(self, keybind_manager, uinput_handler, sleep=asyncio.sleep, spawn=None)` — `sleep`/`spawn` injectable for tests; default `spawn` = `asyncio.create_subprocess_exec`.
  - `async execute(self, event: InputEvent) -> None` — look up `keybind_manager.get_action(event.key_code)`; if `keystroke` → `await uinput_handler.send_event(event)` (press+release handled by the event stream); other types fire **only on `KEY_PRESS`**: `macro` runs steps (keys via a synthetic press+release InputEvent through `uinput_handler.send_event`, delays via `sleep`), `command` spawns detached (no shell), `profile_switch` calls `keybind_manager.switch_profile(profile or resolves "next")`.
  - Macro guard: ignore re-trigger while a macro for the same action is already running.

- [ ] **Step 1 (test):** `tests/test_action_engine.py` with a fake keybind_manager (returns typed `KeybindAction`s), a fake uinput_handler recording `send_event` calls, an injected `sleep` recording delays, and an injected `spawn` recording argv. Assert: keystroke press → one `send_event`; macro press → key steps emit press+release events in order and delays are awaited (fake clock); command press → `spawn` called with exact argv and no shell; profile_switch press → `keybind_manager.switch_profile` called; RELEASE of a macro/command does nothing.
- [ ] **Step 2:** run → fails.
- [ ] **Step 3:** implement `action_engine.py` per the interface.
- [ ] **Step 4:** run → pass; full suite green.
- [ ] **Step 5:** commit `add action engine for macro/command/profile-switch`.

---

### Task 3: Route dispatch through the ActionEngine

**Files:** Modify `device.py`; Test `tests/test_device_evdev.py` (extend)

- [ ] **Step 1 (test):** extend `test_device_evdev.py`: patch `ActionEngine.execute` (AsyncMock); feed an `InputEvent` through `device._dispatch`; assert `ActionEngine.execute` awaited with the event AND the EventBus `key_event` still published.
- [ ] **Step 2:** run → fails (device still calls uinput directly).
- [ ] **Step 3:** in `device.py.__init__` construct `self.action_engine = ActionEngine(self.keybind_manager, self.uinput_handler)`; in `_dispatch` replace `await self.uinput_handler.send_event(event)` with `await self.action_engine.execute(event)` (keep the EventBus publish).
- [ ] **Step 4:** run → full suite green; the live behavior for keystroke bindings is unchanged.
- [ ] **Step 5:** commit `route device dispatch through the action engine`.

---

### Task 4: ApiServer skeleton — status, keys, static SPA, port file

**Files:** Create `src/huion_keydial_mini/api_server.py`, `src/huion_keydial_mini/web/index.html` (placeholder); Modify `config.py` (add `api_port`); Test `tests/test_api_basic.py`

**Interfaces produced:**
- `class ApiServer:` `__init__(self, keybind_manager, profile_store, event_bus, action_engine, version, host="127.0.0.1", port=8137)`; `async start()` (binds, writes port file, returns actual port); `async stop()`; `.app` (aiohttp `Application`) exposed for the test client.
- Endpoints: `GET /api/status` → `{"device": {"connected": bool}, "service": {"version": str}, "active_profile": str}`; `GET /api/keys` → grouped key names from `keymap.SUPPORTED_KEYS`; `GET /` and SPA fallback → `web/index.html`.
- `config.api_port: int` (default 8137, from `api.port`).

- [ ] **Step 1 (test):** `tests/test_api_basic.py` using `aiohttp.test_utils.TestClient`/`TestServer` on `ApiServer.app` with fake managers:
```python
async def test_status_and_keys(aiohttp_client, ...):
    client = await aiohttp_client(make_api_app())
    r = await client.get("/api/status"); body = await r.json()
    assert body["service"]["version"] and "active_profile" in body
    r = await client.get("/api/keys"); assert "KEY_F1" in (await r.text())
    r = await client.get("/"); assert r.status == 200          # SPA placeholder
```
- [ ] **Step 2:** run → fails.
- [ ] **Step 3:** implement `api_server.py` (aiohttp `Application`, routes, `AppRunner`+`TCPSite` in `start()`, port file write via `ipc.runtime_dir()`), the placeholder `web/index.html` ("Keydial Commander — API running"), and `config.api_port`. Register `web/` as package data in `pyproject.toml` (`[tool.setuptools.package-data]`).
- [ ] **Step 4:** run → pass; full suite green.
- [ ] **Step 5:** commit `add Commander API server skeleton (status, keys, static SPA)`.

---

### Task 5: Profiles + bindings REST

**Files:** Modify `api_server.py`; Test `tests/test_api_profiles.py`

**Endpoints** (all reuse `ProfileStore`/`KeybindManager`; validation via `validate_action`/`normalize_action_id`):
- `GET /api/profiles` → `[{"name","binding_count","active"}]`; `POST /api/profiles` `{name, clone_from?}`; `PUT /api/profiles/{name}` `{new_name}`; `DELETE /api/profiles/{name}`; `POST /api/profiles/{name}/activate`.
- `GET /api/profiles/{name}/bindings` → `{"bindings": {...}, "dial_sensitivity": float}`; `PUT /api/profiles/{name}/bindings/{action_id}` (validated action) ; `DELETE .../{action_id}`; `PUT /api/profiles/{name}/settings` `{dial_sensitivity}`.
- `GET /api/profiles/{name}/export` → YAML download; `POST /api/profiles/import` `{name?, yaml}`.
- Editing the ACTIVE profile must refresh the live map: call `keybind_manager.switch_profile(active)` (or a lighter reload) so grabbed input uses the new binding immediately; broadcast `bindings_changed` on the EventBus.

- [ ] **Step 1 (test):** `tests/test_api_profiles.py` (aiohttp client, real `ProfileStore` in `tmp_path`): create profile, list shows it, activate, PUT a keystroke binding then GET it back, PUT a macro binding, DELETE it, PUT invalid action → 400, export returns YAML containing the binding, import round-trips. Assert active-profile edits update `keybind_manager.get_action`.
- [ ] **Step 2:** run → fails.
- [ ] **Step 3:** implement the handlers.
- [ ] **Step 4:** run → pass; full suite green.
- [ ] **Step 5:** commit `add profiles and bindings REST endpoints`.

---

### Task 6: test-fire + WebSocket event stream

**Files:** Modify `api_server.py`; Test `tests/test_api_events.py`

- `POST /api/test-fire` `{action}` — validate, then `await action_engine.execute(InputEvent(KEY_PRESS, "__test__"))` against a transient binding (register the action under a reserved id, fire press+release, unregister) OR execute the action directly via a small `ActionEngine.fire(action)` helper (add it). Returns `{"status":"ok"}`.
- `GET /api/events` (WebSocket) — on connect, `queue = event_bus.subscribe()`; forward each event as JSON until the socket closes; unsubscribe in `finally`. Watch for client close concurrently (mirror the socket-stream EOF handling from Phase 1's `keybind_manager._maybe_stream`).

- [ ] **Step 1 (test):** `tests/test_api_events.py`: (a) `POST /api/test-fire` with a keystroke action → 200 and the fake uinput recorded emission; (b) open the WS, `event_bus.publish({"type":"key_event",...})`, assert the client receives it; closing the WS unsubscribes (bus has no leaked queue).
- [ ] **Step 2:** run → fails.
- [ ] **Step 3:** implement; add `ActionEngine.fire(action)` (execute a one-off action object without a stored binding).
- [ ] **Step 4:** run → pass; full suite green.
- [ ] **Step 5:** commit `add test-fire endpoint and WebSocket event stream`.

---

### Task 7: Wire ApiServer into the daemon + docs

**Files:** Modify `device.py` (start/stop the ApiServer), `main.py` (nothing, or log the URL), `README.md`, `docs/ROADMAP.md`; Test `tests/test_daemon_api.py`

- [ ] **Step 1 (test):** `tests/test_daemon_api.py`: with `EvdevSource`/`UInputHandler.start` patched (as in `test_device_evdev`), start `HuionKeydialMini`; assert an `ApiServer` was started and `GET /api/status` responds on the bound port; `stop()` shuts it down and removes the port file.
- [ ] **Step 2:** run → fails.
- [ ] **Step 3:** in `device.py`: construct `self.api_server = ApiServer(...)`; `start()` calls `await self.api_server.start()` after the socket server; `stop()` calls `await self.api_server.stop()`. Log the URL at INFO. Update README (Commander API section) and tick roadmap Phase 2 backend items.
- [ ] **Step 4:** full suite green; manual smoke: run the daemon, `curl http://127.0.0.1:8137/api/status` → JSON; `curl -X PUT .../bindings/BUTTON_1 -d '{"type":"keystroke","keys":["KEY_F9"]}'` then press button 1 on the live device → F9 emitted.
- [ ] **Step 5:** commit `serve the Commander API from the daemon`; then `git checkout main && git merge --no-ff feat/commander-backend` (present to user before pushing).

## Verification checklist (whole phase)

- [ ] `pytest` green; aiohttp endpoints covered by the test client
- [ ] All four action types execute correctly (macro timing via fake clock; command with no shell; profile-switch swaps the live map)
- [ ] REST edits to the active profile take effect on the grabbed device immediately
- [ ] WebSocket relays live `key_event`/`device_state`/`bindings_changed`; closing unsubscribes
- [ ] `GET /` serves the SPA placeholder; `/api/*` unaffected by the SPA fallback
- [ ] Daemon starts/stops the API cleanly; port file written/removed

---

## Phase 2B — Frontend (React SPA) + Desktop Shell (outline; detail after 2A)

Detailed once the 2A API contract is frozen. Prerequisite: **Node/npm** (currently half-configured
on this machine — resolve the `dpkg --configure -a` kernel-package issue first, or install a
user-local Node via `nvm`). Scope, per the design spec §6 and mockup A:

- **Vite + React + TypeScript** app in `web/` (build output → `src/huion_keydial_mini/web/dist`,
  served by the 2A ApiServer). TanStack Query over REST, invalidated by the `/api/events` WS;
  zustand for selection/drag state; dnd-kit for drag-and-drop; hand-rolled CSS (teal accent,
  dark-first + light, `[data-theme]`).
- **Components:** ProfileBar, ActionLibrary (drag sources), DeviceStage (K20 render: 4×5 grid +
  dial, live key highlight from WS `key_event`, "press a key to select"), Inspector (per-type
  editors incl. ShortcutCapture via `KeyboardEvent.code`→`KEY_*`), StatusStrip, Settings modal.
- **States:** daemon-down, device-disconnected, empty profile, binding conflict, unsaved edit.
- **Shell:** PyGObject GTK4 window hosting a WebKitGTK view of `http://127.0.0.1:<port>` (read
  from the port file), AyatanaAppIndicator3 tray (Open, profile radio list, Quit), `.desktop`
  entry + icon; graceful window-only fallback when the tray extension is absent.
- **Tests:** vitest + Testing Library (ShortcutCapture map, inspector forms, drag-assign reducer);
  Playwright happy-path deferred to Phase 4 CI.
