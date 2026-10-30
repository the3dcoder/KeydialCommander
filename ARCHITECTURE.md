# Keydial Commander architecture

Keydial Commander is a Linux remapper for the Huion Keydial Mini K20. One Python asyncio process owns the device, profiles, virtual output, Unix control socket, and local HTTP service. The React interface and optional GTK3/WebKit2 window talk to that service.

## Input and output

```text
K20 Bluetooth or USB HID
  -> Linux input event nodes
  -> EvdevSource: discover, grab, read, rescan
  -> input_map: firmware keys and wheel direction to control IDs
  -> InputTranslator: button chords, sticky holds, dial pulses
  -> ActionEngine: shortcut, macro, program, profile switch
  -> UInputHandler: virtual keyboard and mouse output
```

The device is a standard HID keyboard. Bluetooth input arrives through the kernel input subsystem, rather than through a vendor GATT notification. `hid_parser.py`, `bluetooth_watcher.py`, bleak, and the HID unbind helper were removed during the evdev migration. The verified firmware map is in `docs/DEVICE-K20.md`, section G.

`EvdevSource` discovers matching event nodes by Keydial name or vendor/product IDs, excludes the configured virtual output device, and grabs the nodes to suppress factory keystrokes. It rescans every two seconds for connection changes. Bluetooth was verified on physical hardware in the July worklog. USB shares this Linux input path, but its physical verification is still outstanding.

Normal button actions fire on release so the translator can recognize the peak chord. Sticky actions hold until release. Each wheel event produces a direction pulse. This behavior is suitable for remapping; it is not a timestamped physical-input stream for competitive game timing.

Macros are awaited by the dispatch path. Commands use argument arrays and `create_subprocess_exec`, without a shell. They run with the user's privileges. Profile switches reload the live binding map. See the current audit for remaining lifecycle and sensitivity issues.

## Configuration and profiles

`Config` reads global settings and supports legacy binding configuration. `ProfileStore` initializes the first profile from that configuration, then stores one YAML file per profile under `~/.config/huion-keydial-mini/profiles/`. The `active` file records the selected profile. YAML round trips preserve comments; writes use a temporary file and rename.

`KeybindManager` holds the active in-memory map. GUI mutations write the profile and reload the map if that profile is active. The shared `validation.py` module defines control IDs, key names and action schemas. The Unix binding command still focuses on keystrokes; it does not expose every GUI action type equally.

## Local control interfaces

* `ApiServer` serves REST, `/api/events` WebSocket events and built frontend assets on `127.0.0.1:8137` by default.
* The API checks loopback Host headers and browser Origin headers. The local UI, matching loopback origins, development UI on port 5173, and command-line requests without an Origin remain supported. Cross-origin browser requests and WebSocket upgrades are rejected.
* Unix socket messages are newline-framed JSON with protocol version 2, client timeouts and bounded frames. The runtime directory is mode 0700 and the control socket is mode 0600.
* The actual service port is advertised through the runtime directory for the shell.

`EventBus` is a bounded, nonblocking in-process fan-out. Slow subscribers lose the oldest queued item. Events describe executed action IDs, profile changes and connection state. They do not identify a physical source device, carry reliable hardware timestamps, or attest which peripheral produced browser text. Battery information is not implemented.

Loopback checks prevent outside browser pages from using the API. The service remains a trusted local application, with no remote pairing protocol or per-device game permission system. Do not expose its port publicly or grant an external game access to its command and binding endpoints.

## Frontend and desktop shell

The frontend uses React, TypeScript and Vite. TanStack Query owns server state; Zustand owns selection, scoped action drafts, identify mode, key pulses and theme. WebSocket events refresh cached state and animate controls. The layout is the action library, K20 stage, inspector, profile bar and status strip.

A shortcut is captured after a primary key, or on release when the shortcut contains only modifiers. Library actions are editable drafts scoped to the selected profile and control; Save persists them. The K20 layout remains deliberately device-specific.

Vite builds `web/` into `src/huion_keydial_mini/web/dist/`. Build these assets before building a Python wheel. The optional GTK3/WebKit2 shell loads the local URL; it is a window, with browser fallback, rather than a general cross-platform desktop runtime.

## Device permissions

The udev rule grants the active desktop session access to matching K20 event nodes and `/dev/uinput`. It does not require root at runtime or blanket membership in the `input` group. Installing the rule and system service files requires administrator access.

Session access is different from consent to share device metadata with a website. Commander does not currently implement individual browser-game pairing, selected-device capture permissions, revocation or ranked hardware attestation.

## KeyCommand boundary

KeyCommand is a separate browser game and repository for keycommand.io. Its game rules, scores, optional device metadata and Cloudflare service belong there. This repository remains the original control center.

`examples/keycommand-profile.yaml` maps four K20 buttons to D/F/J/K and the dial to Left/Right/Enter. Import it as a new profile in Settings, select it explicitly, then use Control Circuit in KeyCommand. Switch back to the previous profile when finished. Nothing in the game installs system rules or changes profiles automatically.

A future live integration must introduce an authenticated, origin-scoped, revocable game session and a separate raw-control stream before sharing physical input. Existing remapping events must not be presented as verified timing or hardware identity. The full design is in `docs/superpowers/specs/2026-10-29-keycommand-design.md`.

## Verification

Python tests cover profiles, validation, actions, IPC, API and input translation with temporary configuration and mocked device access. One opt-in integration case requires writable `/dev/uinput`; its discovery is restricted to its own synthetic node. Frontend browser regressions use fixture APIs and an isolated Vite server, without the real daemon.

Current findings and verification evidence are recorded in `docs/AUDIT-2026-10-29.md`. Historical design documents describe earlier decisions and should not override the current implementation.
