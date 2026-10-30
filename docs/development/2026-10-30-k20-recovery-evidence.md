# K20 recovery investigation evidence

Date: 2026-10-30. Baseline: `12d07d3`, `feat/keycommand-foundation`.
This record concerns Commander only. No production code, device capture, running
service, installed profile, package installation or deployment was changed.

## Environment and limits

- Read the full continuation handoff, architecture, October audit, roadmap,
  relevant current source/tests and the existing open draft PR #1.
- Checkout was clean before investigation. Git identity: Earl,
  `earl@bigbwain.com`; no commits were made.
- `/etc/os-release`: Ubuntu 26.04.1 LTS. This is environment identification,
  not physical K20 qualification.
- The checkout `.venv/pyvenv.cfg` still records Python 3.12.3. The existing
  `/tmp/keycommand-python/bin/python` runs Python 3.14.4 with pytest 9.2.0 and
  the required imported dependencies. It was reused without installation.
- Bluetooth evidence remains historical. Current physical availability,
  disruptive symptoms, a USB data cable and USB behavior remain unknown.

## Existing focused tests

Initial selection: `test_evdev_source.py`, `test_device_evdev.py`,
`test_input_translator.py`, `test_uinput_lifecycle.py`, `test_action_engine.py`,
excluding `test_end_to_end_grab_and_read`.

The run stalled at `test_start_retries_then_succeeds` and was interrupted.
A separate minimal program awaited `run_in_executor(None, lambda: 1)`, printed
its result and then hung during `asyncio.run()` shutdown. Faulthandler showed
the main thread in `selectors.select` under `asyncio.runners.close`; a shell
timeout ended that diagnostic with exit 124. This reproduces an environment
limitation outside the application; it does not establish its root cause.
Neither executor-based uinput test is counted as passing.

The bounded rerun was:

```sh
PYTHONDONTWRITEBYTECODE=1 timeout --signal=TERM --kill-after=3s 25s \
  /tmp/keycommand-python/bin/python -m pytest -p no:cacheprovider \
  tests/test_evdev_source.py tests/test_device_evdev.py \
  tests/test_input_translator.py tests/test_uinput_lifecycle.py \
  tests/test_action_engine.py \
  -k 'not test_end_to_end_grab_and_read and not test_start_retries_then_succeeds and not test_start_raises_after_exhaustion'
```

Result: **24 passed, 3 deselected, 2 warnings**, exit 0. The warnings were
aiohttp `NotAppKeyWarning` from the existing WebSocket app dictionary key.
No frontend source changed, so frontend checks were not rerun for this research.
The historical full-suite counts are not fresh results for this session.

## In-memory reproductions

Used the real `KeybindManager`, `UInputHandler`, `ActionEngine`,
`InputTranslator` and `EvdevSource` with `Config({})`, an unused explicit socket
path, a fake output storing pressed numeric keycodes, and fake input events.
No output device was opened, no real discovery ran and no source was started.
Each observation was asserted before printing a small JSON result; both
diagnostic commands completed with exit 0. These assertions confirm current
defects, not successful fixes.

| Scenario and sequence | Observed result |
| --- | --- |
| Sticky `BUTTON_13` presses Ctrl; replace active map entry with sticky Shift; release original button | Ctrl remains down. Release resolves the replacement binding. |
| Sticky `BUTTON_13` presses Ctrl; clear active map; release original button | Ctrl remains down. Missing current binding suppresses release. |
| Sticky Ctrl active; call `emit_keys([Ctrl, C])` | Ctrl is released although the translator still records the sticky owner. |
| Sticky Ctrl active; register a fake node; call `_drop_device` | Ctrl and `translator.current_buttons` remain held. |
| Fake reader yields button 1 down/up, then button 2 down/up; button 1 macro waits on an `asyncio.Event` | Only the first two of four available input events are consumed while delayed. Button 2 emits only after the macro barrier opens. |
| Button 1 down; `SYN_DROPPED`; button 2 down inside invalid frame; `SYN_REPORT`; button 1 up | Translator emits `BUTTON_1+BUTTON_2` despite loss. Invalid-frame input was not discarded. |
| Fake reader raises `OSError`; discovery still returns its registered path; call `_sync_devices` | Old reader task remains done and registered; connection remains true; reader is not restarted. |

The profile scenarios mutate the manager's in-memory map to isolate the common
release-lookup defect. They do not independently test every GUI/IPC persistence
entry point. The disconnect scenario directly exercises node removal with a
fake device; it does not simulate Bluetooth/kernel disconnection timing.

## Bounded reviews and primary references

Two independent read-only reviews covered principal software architecture and
peripheral/game interaction design. They agreed on a capture-session boundary,
original-key ownership, managed macro cancellation and neutral rearm. Their
findings are incorporated as proposals in the
[draft design](../superpowers/specs/2026-10-30-k20-recovery-design.md).

A fresh builder reviewer then read the draft and source. They identified two
material ambiguities: readiness for silent but neutral nodes, and GUI previews
after complete device removal. The draft now explicitly allows an already-
neutral synchronized snapshot without a future idle-node frame, and allows
deliberate previews after complete removal plus finished cleanup when output is
healthy. These are agent design choices, not answers attributed to Earl.

The [Linux input protocol](https://docs.kernel.org/input/event-codes.html#ev-syn)
requires dropping events through the next `SYN_REPORT` and querying state after
`SYN_DROPPED`. The
[python-evdev API](https://python-evdev.readthedocs.io/en/latest/apidoc.html#evdev.device.InputDevice.active_keys)
documents querying held keys. Both were consulted during this investigation.
No global novelty or hardware support claim follows from this research.
