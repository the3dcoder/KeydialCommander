# Keydial Commander

A Linux driver **and** a Stream-Deck-style GUI for the Huion Keydial Mini (K20). Remap all 18
buttons and the dial to any keys, shortcuts, chords, macros, app launches, or profile switches —
visually in the app, or from the command line — with persistent profiles.

- **Driver:** grabs the device at the kernel input layer and re-emits your bindings via `uinput`.
- **GUI (Keydial Commander):** a web app served by the driver — a visual device with live key
  highlighting, drag-and-drop action library, per-key inspector, profiles, and a desktop window.

## How it works

The K20 is a standard Bluetooth (and USB) HID keyboard: pressing its buttons sends fixed
keystrokes (`K`, `G`, `L`, …) and the dial acts as a scroll wheel. This driver:

1. **Grabs** the device's kernel input nodes (`EVIOCGRAB`) so those fixed keys are suppressed;
2. **Maps** each physical control to an action ID (`BUTTON_1..18`, `DIAL_CW/CCW/CLICK`);
3. **Re-emits** your configured binding through a virtual `uinput` device.

It runs as a user-level service (no root), stores bindings in on-disk profiles, and applies
changes live via `keydialctl`. Because it works at the evdev layer, the same driver handles
both Bluetooth and wired USB connections. See [docs/DEVICE-K20.md](docs/DEVICE-K20.md) for the
verified hardware protocol and [docs/ROADMAP.md](docs/ROADMAP.md) for the GUI (Keydial Commander)
and roadmap.

> **Access:** the driver needs the udev rule in `packaging/udev/70-huion-keydial-mini.rules`
> (grants your session access to the device event nodes and `/dev/uinput`). Install it with
> `sudo make install-udev`.

## Features

- **evdev-grab remapping** — intercepts the device at the kernel input layer (Bluetooth *and* USB)
- **Virtual input device creation** using uinput
- **On-disk profiles** with automatic persistence; switch profiles at runtime
- **Runtime keybind management** via Unix socket (`keydialctl`)
- **User-level systemd service** (no root required)
- **Chords and sticky (hold) bindings**; mouse-button actions
- **Real-time configuration** without service restart
- **Automatic device detection** and hotplug (grab on connect, release on disconnect)
- **Comprehensive key support**: 167+ keyboard keys and mouse buttons

## Installation

### NixOS

See [NIXOS.md](./NIXOS.md) for NixOS-specific installation instructions using the provided flake.

### Other Linux Distributions

```bash
# Clone the repository
git clone https://github.com/the3dcoder/KeydialCommander.git
cd KeydialCommander

# Install the driver + systemd unit + udev rules (prompts for sudo where needed)
make install-all

# Build the web UI (needs Node/npm) and, optionally, the desktop app window
make build-web
make install-shell        # optional: GTK/WebKit window + app launcher

# Start the user-level service (no root)
systemctl --user enable --now huion-keydial-mini-user.service
```

The `70-huion-keydial-mini.rules` udev rule grants your logged-in session access to the device
event nodes and `/dev/uinput`, so **no `input`-group membership is required**. Then open the app
from your menu ("Keydial Commander"), run `keydial-commander`, or browse to
`http://127.0.0.1:8137`.

## Usage

### Basic Usage

1. **Start the service**:
   ```bash
   systemctl --user start huion-keydial-mini-user.service
   ```

2. **Connect your device** via Bluetooth settings or `bluetoothctl`

3. **Configure key bindings** (changes persist automatically to the active profile):
   ```bash
   # List current bindings
   keydialctl list-bindings

   # Show all supported key codes
   keydialctl list-keys

   # Bind button 1 to F1 key
   keydialctl bind BUTTON_1 KEY_F1

   # Bind dial clockwise to volume up
   keydialctl bind DIAL_CW KEY_VOLUMEUP

   # Sticky bind button 13 to hold Ctrl until released
   keydialctl bind --sticky BUTTON_13 KEY_LEFTCTRL

   # Remove a binding
   keydialctl unbind BUTTON_1

   # Clear all bindings in the active profile
   keydialctl reset
   ```

4. **Manage profiles** (named binding sets stored under `~/.config/huion-keydial-mini/profiles/`):
   ```bash
   keydialctl profile list                      # active profile marked with *
   keydialctl profile create Krita --clone-from Default
   keydialctl profile switch Krita
   keydialctl profile delete Krita
   ```

### Supported Action Types

**Keyboard Actions:**
- Single keys: `KEY_F1`, `KEY_ENTER`, `KEY_SPACE`
- Key combinations: `KEY_LEFTCTRL+KEY_C`, `KEY_LEFTALT+KEY_TAB`
- **Comprehensive key support**: 167+ keys including F1-F24, all letters/numbers, modifiers, media keys, system keys, and more
- Examples: `KEY_BRIGHTNESSUP`, `KEY_BLUETOOTH`, `KEY_WLAN`, `KEY_MICMUTE`, `KEY_CALCULATOR`
- Use `keydialctl list-keys` to see all supported keys

**Mouse Buttons:**
- `BTN_LEFT`, `BTN_RIGHT`, `BTN_MIDDLE`, `BTN_SIDE`, `BTN_EXTRA`, `BTN_FORWARD`, `BTN_BACK` can be bound like keys (momentary clicks; combine with `--sticky` to hold)
- Mouse movement/scroll actions are on the roadmap (see `docs/ROADMAP.md`)

**Sticky Actions:**
- Key bindings can be set as 'sticky', meaning they press and hold until released.
- Sticky key bindings block other key bindings from being triggered until they are released.

**Macros, commands, and profile switching** (via the GUI or the API): multi-step key sequences
with delays, launching apps / running commands, and binding a key to switch the active profile.

### Service Management

```bash
# Check service status
systemctl --user status huion-keydial-mini-user.service

# Restart service
systemctl --user restart huion-keydial-mini-user.service

# Stop service
systemctl --user stop huion-keydial-mini-user.service

# View logs
journalctl --user -u huion-keydial-mini-user.service -f
```

### Device Configuration

```bash
# Set specific device address
keydialctl set-device AA:BB:CC:DD:EE:FF

# Clear device address (auto-discover)
keydialctl clear-device
```

## Configuration

The configuration file is located at `~/.config/huion-keydial-mini/config.yaml`:

```yaml
# Device settings
device_address: null  # Auto-discover if not set

# Initial key mappings (loaded into memory)
key_mappings: {}

# Dial settings
dial_settings:
  DIAL_CW: "KEY_VOLUMEUP"      # Send volume up when dial is turned clockwise
  DIAL_CCW: "KEY_VOLUMEDOWN"   # Send volume down when dial is turned counterclockwise
  DIAL_CLICK: "KEY_MUTE"       # Send mute when dial is clicked
  sensitivity: 1.0             # Dial sensitivity (1.0 = normal, 2.0 = double, 0.5 = half)

# UInput device settings
uinput_device_name: "keydial-commander-uinput"

# Connection settings
connection_timeout: 10.0

# Debug mode
debug_mode: false
```

**Note**: Legacy `key_mappings`/`sticky_key_mappings`/`dial_settings` sections are migrated
once into `~/.config/huion-keydial-mini/profiles/Default.yaml` on first start. After that,
profiles are the source of truth and every `keydialctl` change persists automatically —
config-file comments are preserved by all tooling.

## Keydial Commander (GUI backend)

The daemon embeds a local HTTP + WebSocket API (`127.0.0.1:8137` by default) that powers the
**Keydial Commander** GUI and any client. It reuses the same profiles/bindings as `keydialctl`.

```bash
curl http://127.0.0.1:8137/api/status
curl -X PUT http://127.0.0.1:8137/api/profiles/Default/bindings/BUTTON_1 \
     -H 'Content-Type: application/json' -d '{"type":"keystroke","keys":["KEY_F9"]}'
```

Action types: `keystroke` (keys, chords, `sticky`), `macro` (steps of keys + `delay_ms`),
`command` (`argv`, launched detached — no shell), and `profile_switch` (`profile` name or
`"next"`). Endpoints cover profiles CRUD/activate, per-binding get/put/delete, dial sensitivity,
YAML export/import, `test-fire`, and a `/api/events` WebSocket streaming live key/device events.

### The GUI (Keydial Commander)

A React "Deck"-style web app — a visual device with all 18 keys + dial, drag-and-drop action
library, per-key inspector (shortcut capture, macros, commands, profile switching), profiles,
and live key highlighting.

```bash
make build-web       # build the SPA (needs Node/npm) into the package
make install-shell   # optional: a desktop app window + launcher (GTK/WebKit)
```

With the service running, open the app from your menu ("Keydial Commander"), run
`keydial-commander`, or just browse to `http://127.0.0.1:8137`. The desktop shell is a
GTK/WebKit window; on desktops without an AppIndicator there is no tray (window-only).

## Additional Documentation

- **[Architecture Details](ARCHITECTURE.md)** - Technical architecture and component overview
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Common issues and solutions
- **[Contributing Guide](CONTRIBUTING.md)** - Development setup and contribution guidelines

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

Built with:
- [python-evdev](https://github.com/gvalkov/python-evdev) — Linux input device handling (grab + uinput)
- [aiohttp](https://docs.aiohttp.org/) — the local REST + WebSocket API
- [Click](https://click.palletsprojects.com/) — the `keydialctl` CLI
- [ruamel.yaml](https://yaml.readthedocs.io/) — comment-preserving config/profile IO
- [React](https://react.dev/) + [Vite](https://vite.dev/) + [dnd-kit](https://dndkit.com/) + [TanStack Query](https://tanstack.com/query) — the web UI
