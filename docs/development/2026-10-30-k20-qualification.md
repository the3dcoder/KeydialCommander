# K20 recovery qualification

Date: 2026-10-30. Baseline: `12d07d3`; approved recovery design implemented in
the current Commander feature checkout. No installed service, user profile,
physical device, system rules or deployment was changed.

## Software evidence

| Check | Result |
| --- | --- |
| Python suite, `/tmp/keycommand-python/bin/python -m pytest -q -p no:cacheprovider -k 'not test_end_to_end_grab_and_read'` | 192 passed; one hardware capture test excluded; 36 existing-style aiohttp/legacy mock warnings. Executed outside the restricted sandbox with temporary runtime fixtures. |
| Frontend production build, Node 24.18.0, `npm run build` | Passed. Generated assets remain ignored. |
| Frontend lint, Node 24.18.0, `npm run lint` | Passed. |
| Browser regression suite, Node 24.18.0, fixture APIs and isolated Chromium, `npm test` | 15 passed, zero failures. |
| Independent code review | Three Important findings reproduced with failing regressions and addressed in one fix pass. Final verification: 192 Python tests and 15 browser tests passed. No Critical or Minor findings; no deferred review findings. |

The executor tests that were inconclusive during sandbox-only investigation
passed outside that sandbox. The original seven diagnostic scenarios are
recorded in [the investigation](2026-10-30-k20-recovery-evidence.md), which is a
historical pre-fix record, not the final test result.

Coverage includes original output ownership, shared modifiers, uncertain output
failures, bounded/cancellable macros, effective-map publication, neutral rearm,
lost frames, reader failure/EOF, partial node loss, complete-disconnect previews,
shutdown ordering and healthy held controls during routine scans. All input and
output endpoints in these regressions are fake or explicitly mocked.

## Review disposition

- A split `SYN_DROPPED` recovery frame could rearm before discarding the rest of
  its already-read batch. Recovery completion now advances the batch epoch; a
  regression proves buffered gestures cannot invoke the new session.
- Cancelling an engine task did not prove an actual HTTP client abort cancelled
  its preview. The local server now enables aiohttp handler cancellation. A
  real loopback client-abort regression uses a controlled macro barrier and
  fake output to verify cancellation before any later key emission. This option
  is supported by the existing aiohttp 3.9 minimum; see the
  [aiohttp 3.9 changelog](https://docs.aiohttp.org/en/v3.14.5/changes.html).
- Runtime binding publication copied candidates without complete validation.
  Candidates now canonicalize control IDs and validate complete action schemas
  before active-name or binding persistence and before invalidation. Invalid
  initial profiles and reloads are rejected; descriptions survive normalization.
  Profile activation reports a structured validation error. Valid macro actions
  also work through IPC rather than requiring a keystroke-only payload.

Review boundaries follow the approved design: physical Bluetooth/USB behavior,
desktop receipt of releases after backend failure, installed-service/deployment
behavior and packaging were not measured. KeyCommand remains in its own session
and was not changed. The cost of these boundaries is that software regressions
cannot establish a supported physical setup or an installable release. Output
cleanup failures remain explicitly uncertain rather than being declared safe.

Implementation stayed in the provided feature checkout; commits were deferred
until verification so the existing shared PR was not changed during development.

## Physical evidence matrix

The current host identifies as Ubuntu 26.04.1 LTS. This does not establish
physical availability or current K20 behavior. No row below was performed.

| Transport / scenario | Status | Evidence still required |
| --- | --- | --- |
| Bluetooth: startup with released controls | Unqualified | Confirm available host/K20, capture permission and dated successful remapping. |
| Bluetooth: startup with held button/dial click | Unqualified | No output until release and a fresh gesture. |
| Bluetooth: disconnect/power-cycle during hold or macro | Unqualified | Owned outputs release, no later macro step, and reconnect requires neutral controls. |
| Bluetooth: profile edit/switch during hold | Unqualified | Original outputs release and no new-profile action from the trailing release. |
| Bluetooth: shutdown with held output | Unqualified | Observe desktop output release and normal device return. |
| USB: known data cable and enumeration | Unqualified | Earl has not confirmed a data cable or actual USB behavior. |
| USB: startup, held-control recovery and shutdown | Unqualified | Separate dated transport evidence after enumeration is confirmed. |
| Multiple physical devices | Unqualified | Independent grouping/state is a later adapter milestone. Current nodes form one conservative session. |

Hardware checks need Earl's available equipment and explicit selected-device
capture authorization. Software checks do not authorize those actions or
establish transport support. Packaging remains the following milestone.
