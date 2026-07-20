# Tests

Pytest suite for the driver. Run it from a project venv:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/pytest tests/ -v
```

## Layout

- `conftest.py` — shared fixtures (sample configs, HID report builders)
- `test_hid_parser.py`, `test_combo_hid_parser.py`, `test_parser_fixes.py` — report decoding,
  chords, sticky state, dial detent accumulator
- `test_keybind_manager.py`, `test_manager_persistence.py` — binding store + profile persistence
- `test_ipc.py`, `test_event_bus.py` — framed socket protocol v2, event streaming
- `test_profile_store.py` — on-disk profiles, legacy migration
- `test_config_io.py` — comment-preserving config round-trips
- `test_device_identity.py` — Huion-only attach filter, any-adapter paths
- `test_uinput_lifecycle.py` — async open/close, device-free `list-keys`
- `test_validation.py`, `test_keymap.py`, `test_cli.py`, `test_packaging_meta.py`

## Report formats

The authoritative description of what the device actually sends lives in
`docs/DEVICE-K20.md` (vendor FFE1 frames: byte 0 modifier bits, bytes 2–7 key
scancodes; dial frames prefixed `0xf1`). Tests build reports with those shapes.

Marker names (`unit`, `integration`, `hid_parser`, `combo`, `keybind_manager`,
`asyncio`) are declared in `pyproject.toml`.
