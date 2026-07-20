# Contributing to Keydial Commander

Thanks for your interest in contributing! Keydial Commander is a Linux driver **and** GUI for the
Huion Keydial Mini (K20). This guide covers the development setup, architecture, and workflow.

## Getting started

```bash
git clone https://github.com/the3dcoder/KeydialCommander.git
cd KeydialCommander

# Python driver + tests (a virtualenv is recommended)
python3 -m venv .venv
.venv/bin/pip install -e ".[test]"

# Device access for local testing (grants your session /dev/uinput + event nodes)
sudo make install-udev
```

No `input`-group membership is needed — the `70-huion-keydial-mini.rules` udev rule grants the
logged-in session access to the device and `/dev/uinput`.

### Web UI (frontend)

The GUI lives in `web/` (Vite + React + TypeScript) and builds into `src/huion_keydial_mini/web/dist`,
which the daemon serves. It needs Node/npm:

```bash
cd web && npm install
npm run dev      # dev server on :5173, proxying /api to the running daemon on :8137
npm run build    # production build into the package (also: `make build-web` from the repo root)
```

## Architecture

Input flows entirely through the Linux input layer (the K20 is a standard HID keyboard — see
[docs/DEVICE-K20.md](docs/DEVICE-K20.md)):

```
EvdevSource (grab event nodes) → input_map → InputTranslator (combos/sticky)
    → ActionEngine (keystroke/macro/command/profile_switch) → UInputHandler (uinput)
                                   │
                                   └→ EventBus → WebSocket clients
ProfileStore (on-disk YAML profiles)  ·  KeybindManager (live map + Unix socket)
ApiServer (aiohttp REST + WS + static SPA on 127.0.0.1)
```

Key modules under `src/huion_keydial_mini/`: `evdev_source`, `input_map`, `input_translator`,
`action_engine`, `uinput_handler`, `keybind_manager`, `profile_store`, `config`, `validation`,
`ipc`, `event_bus`, `api_server`, `device` (wiring), `keydialctl` (CLI).

## Running for development

```bash
# Run the driver directly (grabs the device, serves the API + GUI on :8137)
.venv/bin/python -m huion_keydial_mini --log-level DEBUG

# Watch decoded input live (grabs the device, prints action IDs)
.venv/bin/python -m huion_keydial_mini.event_logger

# Inspect / set bindings against the running daemon
.venv/bin/keydialctl list-bindings
.venv/bin/keydialctl bind BUTTON_1 KEY_LEFTCTRL+KEY_Z
```

## Testing

```bash
.venv/bin/pytest tests/ -q                                  # all tests
.venv/bin/pytest tests/ --cov=huion_keydial_mini            # with coverage
.venv/bin/pytest tests/test_action_engine.py -v             # a single file
```

Tests are hardware-free (evdev/uinput are exercised via a synthetic device or mocks; the API via
the aiohttp test client). Please add tests for new behavior.

## Code style

- **Python** ≥ 3.8 — use `typing.Optional/List/Dict` (no `X | Y` unions, no `match`); PEP 8;
  type hints and docstrings on public functions; keep files focused.
- **Validation** lives in one place (`validation.py`) — reuse it, don't duplicate action/key checks.
- **TypeScript/React** — the existing components are hand-styled with CSS variables (teal accent,
  dark-first + light). Match the surrounding patterns.

## Workflow

To contribute:

1. Create a branch from `main` (`feat/…`, `fix/…`, `docs/…`, `chore/…` — see [docs/BRANCHING.md](docs/BRANCHING.md)).
2. Make focused changes **with tests**; run `pytest` (and `npm run build` if you touched the UI).
3. Commit in the imperative mood ("Add …", not "Added …"); reference issues (`Fix #123: …`).
4. Open a pull request against `main`.

## Project structure

```
KeydialCommander/
├── src/huion_keydial_mini/     # driver + API (Python package)
│   ├── evdev_source.py         # grab + read kernel input nodes
│   ├── input_map.py            # evdev code → action ID
│   ├── input_translator.py     # combo + sticky state machine
│   ├── action_engine.py        # keystroke/macro/command/profile_switch
│   ├── uinput_handler.py       # virtual input device
│   ├── keybind_manager.py      # live binding map + Unix socket
│   ├── profile_store.py        # on-disk profiles
│   ├── api_server.py           # aiohttp REST + WebSocket + static SPA
│   ├── keydialctl.py           # CLI
│   └── web/                    # built SPA is served from web/dist
├── web/                        # frontend source (Vite + React + TS)
├── packaging/                  # systemd, udev, shell launcher, distro packaging
├── tests/                      # pytest suite
└── docs/                       # audit, device protocol, roadmap, design/plan specs
```

## Reporting issues

Open an issue at <https://github.com/the3dcoder/KeydialCommander/issues>. Include your OS, kernel,
and Python versions, the device model/firmware if known, relevant logs
(`journalctl --user -u keydial-commander -e` or the `--log-level DEBUG` output), and clear
reproduction steps.

## License

By contributing, you agree that your contributions are licensed under the project's MIT License.
