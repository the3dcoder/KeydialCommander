# DEVICE-K20 — Huion Keydial Mini protocol reference

**Probed:** 2026-07-19, live unit "Keydial mini-504" (MAC `20:23:06:01:8A:B0`) on Ubuntu 24.04 /
BlueZ, kernel 6.17. Read-only probe: sysfs report descriptors, BlueZ D-Bus GATT database,
characteristic reads. **No writes were performed.**

## A. Identity

| Field | Value | Source |
|---|---|---|
| BLE name | `Keydial mini-504` | BlueZ Device1 |
| MAC | `20:23:06:01:8A:B0` (public) | BlueZ |
| Appearance | `0x03C1` (keyboard) | BlueZ |
| Manufacturer string | `HUION` | GATT 2a29 |
| PnP ID | source 0x02 (USB), VID `0x256C`, PID `0x8251`, version 0x0001 | GATT 2a50 |
| Modalias | `usb:v256Cp8251d0001` | BlueZ |
| Battery | 90% at probe time | GATT 2a19 |
| Adapter | **hci1** on this machine (⚠ driver hardcodes hci0 — audit M9 confirmed real) | BlueZ path |

## B. GATT database (as exported by BlueZ D-Bus)

| Service | Characteristic | Flags | Meaning |
|---|---|---|---|
| 1801 Generic Attribute | 2a05 | indicate | Service Changed |
| 180A Device Information | 2a29 | read | Manufacturer ("HUION") |
| | 2a50 | read | PnP ID |
| 180F Battery | 2a19 | read, notify | Battery level |
| **FFE0 (vendor)** | **FFE1** | **read, notify** | **Event stream — what the Python driver actually parses (see §E/F)** |
| | FFE2 | read, write-without-response, notify, indicate | Vendor command/response channel |
| **00010203-0405-0607-0809-0a0b0c0d1912 (Huion/UGEE vendor)** | 00010203-…-0a0b0c0d**2b12** | read, write-without-response | Huion command channel (init / LED / sleep in Huion's ecosystem — Phase 3 target) |

**Critical fact:** the HID service (1812) and its Report characteristics are **NOT exported** on
D-Bus. BlueZ's HoG profile claims them internally (keyboard-sniffing protection) and feeds the
kernel via uhid. **bleak can never subscribe to the real HID reports.** The only notify-capable
data characteristic visible to this driver is vendor **FFE1** — which is therefore the actual
event source of the entire project (never stated in the original docs). The udev unbind script
exists precisely because the kernel HID path stays alive in parallel and must be silenced to
stop the fixed firmware hotkeys double-typing.

## C. HID report map (kernel copy, `/sys/bus/hid/devices/0005:256C:8251.*/report_descriptor`)

Two HID interfaces over uhid:

**Interface .0013 — Radial controller** (Surface-Dial-class; used by the official driver's
"Radial" mode on Windows):

| Report ID | Layout (after ID) | Content |
|---|---|---|
| 3 (input) | 1 byte const pad · 1 bit button · 1 bit touch · 6 bits pad · int16 LE relative rotation (log. ±32767, phys. 0–3600 tenths-of-degree) · 5 bytes pad | Dial click + rotation, Generic Desktop / Digitizer Puck usages; Resolution Multiplier feature present |

**Interface .0014 — composite keyboard/consumer/mouse:**

| Report ID | Layout (after ID) | Content |
|---|---|---|
| 1 (input) | byte0 modifier bits (E0–E7: bit0 LCtrl, bit1 LShift, bit2 LAlt, …) · byte1 reserved · bytes2–7 key array (usages 0x00–0xF1) | Standard boot-style keyboard — the fixed firmware hotkeys |
| 1 (output) | 5 LED bits + 3 pad | Keyboard LEDs |
| 2 (input) | uint16 consumer usage (0–0x380) | Media keys |
| 5 (input) | 5 button bits + 3 pad · int16 X · int16 Y · int8 wheel | Mouse |

Kernel input nodes (both from .0014): "Keydial mini-504 Keyboard" (event26, kbd+leds) and
"Keydial mini-504 Mouse" (event27, rel). The radial interface (.0013) creates no usable input
node under hid-generic.

## D. Fixed firmware key table (stock mapping, keyboard report ID 1)

From the driver's empirically derived scancode table (`hid_parser.py`), cross-checked against
HID usage IDs:

| Physical btn (driver #) | Usage sent | Key | | Physical btn | Usage | Key |
|---|---|---|---|---|---|---|
| 1 | 0x0E | K | | 10 | 0x1D | Z |
| 2 | 0x0A | G | | 11 | 0x06 | C |
| 3 | 0x0F | L | | 12 | 0x19 | V |
| 4 | 0x4C | Delete | | 13 | mod bit0 | LeftCtrl |
| 5 | 0x0C | I | | 14 | mod bit2 | LeftAlt |
| 6 | 0x07 | D | | 15 | mod bit1 | LeftShift |
| 7 | 0x05 | B | | 16 | 0x28 | Enter |
| 8 | 0x08 | E | | 17 | 0x2C | Space |
| 9 | 0x16 | S | | 18 | 0x11 | N |

(Physical-position ↔ number mapping is the driver's numbering; on-hardware verification happens
via the GUI "identify mode" — spec §9.)

## E. Vendor characteristics FFE0/FFE1/FFE2 — NOT the input channel  ⚠ corrected

> **Correction (live-verified 2026-07-19, evening).** An earlier revision of this document
> claimed with "high confidence" that button/dial input arrives as Huion vendor frames on
> **FFE1**. **That was wrong.** Direct testing disproved it. The original Python driver's whole
> premise (subscribe to FFE1 via bleak, parse vendor frames) does not receive input on this
> firmware. See §G for what actually happens.

What FFE0/FFE1/FFE2 really are, per live probing:
- **FFE1** (`0000ffe1`): notify-capable, but its User-Description descriptor (0x2901) reads
  **`HUION_T21h_230628`** — a firmware/build identifier. Subscribing to it and pressing every
  key/dial produced **zero** notifications. It is not an input channel.
- **FFE2** (`0000ffe2`): emits occasional **status frames** (e.g. `06 d1 63 5a 00 00`, trailing
  byte = battery 0x5a). Not input.
- Vendor char `…2b12` (service `00010203-…1912`): User-Description = **`OTA`** — firmware update
  channel. `write-without-response`. Not input.
- Battery `2a19` emits the level (`0x5a` = 90%). Service-Changed `2a05` indicates.

The parser's expected "vendor frame" formats (`0xf1`-prefixed dial, byte0-modifier key frames)
correspond to **nothing this device sends over BLE GATT**. They were reverse-engineered against a
different assumption and never matched this hardware.

## F. What the driver must do instead: evdev grab + uinput

**This K20 is a standard BLE HID keyboard.** Input flows: BLE HID service `0x1812` → BlueZ
HoG (Human-interface-over-GATT) plugin → kernel uhid → standard evdev/hidraw nodes. BlueZ
consumes the HID reports internally; they are **never exposed on D-Bus GATT**, so a bleak client
cannot see them. This is why the device types as a plain keyboard, and why FFE1 is silent.

The correct architecture (same as `keyd` / `xremap` / `input-remapper`):
1. Open the device's **evdev event nodes** (found by name/VID:PID), `EVIOCGRAB` them so the
   original keystrokes don't reach the rest of the system.
2. Read decoded `KEY_*` / `REL_*` events, translate to action IDs, look up the binding.
3. Emit the mapped keys via the existing `uinput` handler.

No BLE, no `hid-generic` unbind, no vendor reverse-engineering. USB wired mode uses the **same**
evdev nodes (bonus: transport-agnostic).

## G. Live-verified input map (2026-07-19, evdev read, no sudo, 70- uaccess rule)

Two evdev nodes appear for the connected K20:

| Node | Name | Carries |
|---|---|---|
| `event26` | `Keydial mini-504 Keyboard` | all 18 buttons (as `KEY_*`) + dial **click** |
| `event27` | `Keydial mini-504 Mouse` | dial **rotation** (as scroll wheel) |

**Buttons → `KEY_*` on event26** (pressed in physical reading order; confirms BUTTON_1..18 order):

| Btn | Key (code) | | Btn | Key (code) | | Btn | Key (code) |
|---|---|---|---|---|---|---|---|
| 1 | KEY_K (37) | | 7 | KEY_B (48) | | 13 | KEY_LEFTCTRL (29) |
| 2 | KEY_G (34) | | 8 | KEY_E (18) | | 14 | KEY_LEFTALT (56) |
| 3 | KEY_L (38) | | 9 | KEY_S (31) | | 15 | KEY_LEFTSHIFT (42) |
| 4 | KEY_DELETE (111) | | 10 | KEY_Z (44) | | 16 | KEY_ENTER (28) |
| 5 | KEY_I (23) | | 11 | KEY_C (46) | | 17 | KEY_SPACE (57) |
| 6 | KEY_D (32) | | 12 | KEY_V (47) | | 18 | KEY_N (49) |

**Dial → event27 / event26:**
- Rotate: `REL_WHEEL` ∓1 per detent (with `REL_WHEEL_HI_RES` ±120). One clean event per detent →
  maps directly to `DIAL_CW` / `DIAL_CCW`. (Sign: one direction = −1, the other = +1.)
- Press (center): `KEY_PLAYPAUSE` (164) on event26 → maps to `DIAL_CLICK`.

**Implications for the rebuilt device layer:**
1. Grab `event26` (keyboard) + `event27` (mouse); identify the pair by name `*Keydial*` and/or
   VID:PID `256C:8251`. Handle hotplug (grab on connect, release on disconnect).
2. Fixed firmware key → action-ID map is the table above (invert it): incoming `KEY_K` = BUTTON_1,
   `KEY_PLAYPAUSE` = DIAL_CLICK, etc. `REL_WHEEL` sign → DIAL_CW/CCW.
3. Chords (multiple buttons at once) = multiple simultaneous `KEY_*` down — detectable from the
   grabbed stream; the peak-set combo logic can be reused conceptually.
4. Battery for the GUI status strip: still available via BlueZ `2a19` over D-Bus (read + notify),
   independent of the input path.
5. USB wired mode (now folded into the pivot): same evdev nodes, same VID:PID; the grab layer is
   transport-agnostic. Only difference is the udev matching for the USB interface.
6. The `hid-generic` **unbind** script and rule become **unnecessary** — `EVIOCGRAB` suppresses
   the original keys. Delete that subsystem in the pivot; keep the `70-` uaccess rules (event
   nodes + `/dev/uinput`).

**Vendor Phase 3 note (LED/sleep):** the vendor write channels (`…2b12` = OTA, FFE2 = status)
remain candidates for LED brightness / sleep-timer control but require capturing the official
driver's writes first. **Never write blind.**
