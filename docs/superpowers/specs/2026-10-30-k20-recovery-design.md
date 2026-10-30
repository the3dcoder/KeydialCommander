# K20 recovery and output ownership

Date: 2026-10-30
Status: approved by Earl on 2026-10-30: "I approve, proceed."

## Intent and decision record

Make the existing Linux K20 remapper recover predictably without stuck keys,
unexpected release-triggered actions or delayed macro output after a reset.
Retain Python asyncio, evdev, uinput, YAML profiles and the local Commander UI.

| Kind | Record |
| --- | --- |
| Explicit direction | Earl said, "Please go with your recommendations," after the recommendation to pursue K20 reliability first, keep the current architecture and initially target the current Ubuntu host and Bluetooth. Commander and KeyCommand remain separate projects and sessions. |
| Measured environment | The checkout was clean at `12d07d3` on `feat/keycommand-foundation`; Git is configured as Earl. `/etc/os-release` reports Ubuntu 26.04.1 LTS. |
| Provisional planning choices | The recommended scope and detailed behavior below use the handoff's 15-second planning-default rule. They are agent recommendations, not additional answers or permission from Earl. The asynchronous profile-behavior and scope questions were unanswered when this draft was written. |
| Measured software evidence | Seven in-memory scenarios reproduced lifecycle/ownership gaps. A focused existing-test run passed 24 tests; two executor-based cases remain inconclusive and the hardware case was excluded. Details are in the evidence record linked below. |
| Unknown | Physically available computers, current K20/Bluetooth behavior, a known USB data cable, USB behavior and Earl's most disruptive current failure. Host OS identification does not establish physical test availability. |
| Design approval | Earl approved this design and instructed implementation on 2026-10-30. Hardware capture, installed-service changes and deployment remain outside this authorization. |

Evidence: [investigation record](../../development/2026-10-30-k20-recovery-evidence.md).
Existing context: [handoff](../../development/CONTINUE.md),
[architecture](../../../ARCHITECTURE.md), and
[October audit](../../AUDIT-2026-10-29.md).

## Approaches

These alternatives were presented in the ongoing interview. The recommendation was initially provisional under the planning agreement.
Earl selected it by approving this concrete design and instructing implementation.

| Approach | Benefit | Limit or cost |
| --- | --- | --- |
| Ownership-only containment | Snapshot original outputs and prevent overlapping taps from releasing another hold. Smallest first change. | Leaves macro-delayed readers, lost input and recovery semantics unresolved. Useful as a first implementation slice, insufficient for the whole milestone. |
| **One K20 session boundary with managed macros** | Makes owned-output release, profile changes and input recovery obey the same cancellation rule. Builds on existing layers. | Touches the source, translator, action engine, binding manager, output writer and local status integration. Recommended scope. |
| Packaging first | Produces a simpler installation and clean-environment evidence. | Installs the existing input failures. Retain as the following release milestone. |

A generic per-physical-device actor/adapter rewrite is deferred until a second
real peripheral supplies requirements. All currently matched K20 nodes belong to
one conservative capture session for this milestone. This deliberately does not
establish independent multi-device support.

## Goals and boundaries

The healthy-output invariant is: a virtual key is down exactly while at least
one live Commander activation owns it. An activation releases only its own
original keys. A reset closes action admission immediately and prevents old work
from creating later effects.

Qualify one physical K20 over Bluetooth on the current Ubuntu host once Earl
confirms availability and authorizes physical checks. USB remains unqualified.
Simulated checks are required first and do not establish physical support.

Packaging repairs, sensitivity units, generic adapters, application-based
switching, public diagnostics/export, a pause control and a live game bridge
remain outside this milestone. Existing commands keep their detached child
lifetime. No game repository, cloud service, board or deployment is touched.

Preserve these ordinary interactions outside recovery:

- Ordinary buttons produce one peak-chord tap on release.
- Sticky actions mean hold while physically pressed, rather than toggle.
- Dial click follows down/up; dial rotation produces the existing pulses.
- Key repeats remain suppressed. The preset and browser-input boundary stay as
  documented; remapping events do not become verified physical game timing.

## Cancellation and readiness contract

Any relevant node loss, reader failure, input overrun, output failure, effective
active-map change or shutdown invalidates the current session generation.
New node attachment also establishes a fresh synchronization boundary so input
already held at attachment cannot trigger an action.

Cancellation is distinct from a physical release. Discard pending ordinary taps,
chord sessions and queued work; release original output ownership directly.
Do not synthesize releases through `InputTranslator.feed_button`, because normal
releases can fire commands, macros or profile switches.

The reset sequence is:

1. Close action admission and invalidate the generation synchronously.
2. Cancel tracked old-generation macros and release their owned outputs.
3. Clear translated interactions while retaining separate raw synchronization
   state needed to observe held physical controls.
4. Await cancelled work without permitting any obsolete-generation write.
5. If input and output remain healthy, synchronize all relevant nodes and wait
   for neutral controls before admitting a fresh interaction.

Cleanup is idempotent and cannot depend on a lossy EventBus subscription. A task
must not wait for its own cancellation. Shutdown revokes admission and releases
outputs before waiting for HTTP/WebSocket teardown.

Reconnection never resumes an old hold or macro. During recovery, suppress all
button and dial-click actions until those controls are observed released; their
release events are discarded. Discard recovery-time relative dial movement.
Require a fresh press or turn after readiness returns. There is no timer, rapid
gesture or second control required to rearm.

The initial policy waits for the whole K20 to be neutral. This is simpler with
peak-chord recognition but temporarily blocks other controls while a switch is
held. Per-control quarantine is a later alternative, requiring actual adaptive
control testing before broader accessibility claims.

## Original actions and shared outputs

At activation, capture the effective action, generation and ordered concrete
keycodes. Give each held action and each macro/preview tap an owner token.
Resolve a release against that activation before looking up any current binding.
Removal or a change of action type must not prevent original-key cleanup.

The writer records owners by numeric output keycode, deduplicating aliases
within an activation. Send down on first acquisition and up on last release.
An overlapping tap of an already-owned key does not manufacture up/down events
that interrupt the hold. Example: sticky Ctrl plus a Ctrl+C macro taps C while
Ctrl remains down until its sticky owner releases it.

All action output, including GUI test-fire, uses this same ownership path.
No path may bypass it with direct key writes. Write success and uncertain
partial writes are tracked separately from logical owner bookkeeping.

## Macros and command effects

Physical macro dispatch registers a managed task and returns to reading input;
macro delays cannot hold up subsequent releases or loss notices. Preserve step
order and one running instance per originating action within a generation.
Ignore a duplicate physical retrigger while that action is running, as today.

Agent proposal: cap concurrent macro tasks at eight, including previews, with
no pending backlog. A full supervisor rejects new physical macro admissions and
records busy state; an API preview receives a structured busy response. Every
admitted task has a captured generation and cannot emit after invalidation.

API test-fire joins the same supervisor and cleanup boundary. Preserve its
existing await-completion behavior for an admitted preview. A preview can run
without a connected K20 when output is healthy, but cannot bypass a physical
session that is recovering or waiting for neutral controls. After the last K20
node disappears and old-generation cleanup finishes, there is no physical
session to rearm: deliberate previews are allowed with healthy output. A partial
node set with missing required roles remains unready and blocks previews. Any
new node attachment cancels previews and establishes the new input boundary.
Output fault and shutdown always block admission. Cancelling a preview returns
a non-success outcome; HTTP request cancellation removes its work.

Cancellation prevents future macro steps; it cannot undo an emitted tap or
terminate a program whose launch was already committed. Check generation before
starting any new launch; do not add command-child termination or promise rollback
of an in-flight subprocess launch.

## Input recovery

Handle reader exceptions and unexpected EOF directly, even while discovery
still lists the path. Evict and close that failed instance; retry opening through
normal discovery. A path retained or reused after reader death must not stay
registered as healthy. An old task's finalizer cannot remove a new instance at
the same path.

Do not use `bool(any nodes)` as the cleanup trigger. Losing the keyboard while
the dial node survives still invalidates the session. Report connection and
readiness separately.

For the currently documented K20 mapping, readiness requires the mapped-key
role (buttons and dial click) and the `REL_WHEEL` role. Determine roles from
capabilities; do not hardcode event paths or exactly two nodes. Missing roles or
failure to grab/query any relevant discovered node keeps the session unready.
This is a K20 requirement based on existing evidence, not a generic adapter API
or a claim that USB is verified.

On `SYN_DROPPED`, invalidate immediately, discard through and including that
node's next `SYN_REPORT`, then query current state. The kernel explicitly
requires discard and state query after overrun; relative movement lost in the
gap cannot be reconstructed. See the
[Linux event protocol](https://docs.kernel.org/input/event-codes.html#ev-syn).
The library exposes current held-key state via
[`InputDevice.active_keys()`](https://python-evdev.readthedocs.io/en/latest/apidoc.html#evdev.device.InputDevice.active_keys).

Startup, topology changes, profile changes and loss recovery must establish a
queue boundary on each relevant node: discard buffered pre-boundary gestures,
query mapped key state on key-capable nodes, and observe subsequent neutral
state at complete frame boundaries before opening admission. Serialize draining
and reading for each file descriptor; do not race a second reader against the
normal reader. Only data known to belong after this boundary may trigger a new
action. If trustworthy state cannot be obtained, remain unready and explain why.

An already-neutral snapshot after fully draining the node is sufficient; do not
wait for a future `SYN_REPORT` from an idle node or a wheel with no movement. If
controls are held, suppress input until their releases reach complete frames and
the observed raw state is neutral. The special `SYN_DROPPED` discard-through-
report requirement still applies before taking its recovery snapshot. These
rules avoid requiring an extra gesture just to start or finish a profile change.

## Profile and binding publication

Validate/stage the candidate map before interrupting the current session. For a
successful profile switch or effective active-binding change, invalidate before
publishing the new map, release old ownership, cancel old-profile macros, then
apply the neutral barrier. A trailing release from a translated pair belongs to
its old generation and cannot invoke a newly installed action.

Use one binding-publication boundary for GUI active-profile edits, profile
activation, Unix set/remove/clear and public in-process mutation helpers.
Inactive-profile edits and failed validation do not reset active input.
Metadata-only changes and identical effective maps do not interrupt a hold.
Changing to another profile cancels old-profile work even if its mappings happen
to match. Persistence failures retain the prior live state and return an error.

## Output failure and user feedback

A write or synchronization failure closes admission for all owners sharing that
output backend. Attempt best-effort release of known or possibly pressed keys,
retire/close the backend, cancel old work and remain faulted. Do not claim the
desktop received releases merely because a logical ledger was cleared.

Agent proposal for this bounded milestone: no automatic runtime recreation of
failed uinput. Report output unavailable and require an ordinary Commander
restart after the underlying cause is resolved. Restart creates a new backend
and applies startup synchronization; no new privileged recovery endpoint is
needed. Input reconnect recovery remains automatic when the output is healthy.

Expose readiness and reason through additive local status/event fields while
preserving the existing connection flag. The current status strip should explain
"Release controls to resume," missing/capture-failed K20 input, or "Output
unavailable" as appropriate. Keep implementation details out of these messages.
REST state is authoritative; bounded WebSocket events only notify clients.
Only successful output is reported as successful. Faults and cancelled/busy
previews return structured non-success results. This is operational state, not
an event recorder or new exported diagnostics product.

## Acceptance and failure criteria

Use deterministic fake nodes, fake output and controlled macro barriers first.
No real capture is part of the default test suite. The milestone fails if any
owned key remains logically held after healthy cleanup, if an obsolete task
emits afterward, or if recovery creates an action without a fresh interaction.

| Scenario | Required result |
| --- | --- |
| Hold Ctrl; replace/remove binding, change type, clear bindings or switch profile | Original Ctrl releases; replacement keys receive no stray release/action. A new action requires rearm and a fresh gesture. |
| Sticky Ctrl plus Ctrl+C macro or preview | C taps; Ctrl stays down until the last owner releases. Repeated owner cleanup is harmless. |
| One K20 node disappears while another survives | Session cancels and releases owned output; readiness remains false until required roles and neutral input return. |
| Reader dies while its path remains listed, or that path is reused | Failed instance is evicted/reopened; stale finalizer cannot evict the replacement. |
| Macro is parked at a long-delay barrier; another control releases or reset occurs | Release/reset completes without opening the delay barrier. No later macro step executes after cancellation, even if the barrier later opens. |
| Incomplete frames after `SYN_DROPPED` | Discard through next report, query state, suppress false chords and dial movement, and await neutral plus a fresh gesture. |
| Startup/reconnect while buttons or dial click are held | No inherited hold, tap, command or profile switch. Releasing controls only rearms. |
| Reset during a press/release pair or GUI preview | Trailing events and tasks cannot affect the new generation. |
| Failure halfway through chord acquisition or release | Attempt cleanup/close, expose uncertain output truthfully, and suppress later actions. |
| Stop with held output and slow API teardown | Release/invalidation precedes API shutdown; delayed previews cannot outlive ownership. |
| Inactive-profile edit, invalid candidate or metadata-only change | Current valid held interaction continues. |
| Eight running macros, duplicate retrigger and ninth admission | Existing tasks remain ordered; duplicate/new work follows the documented bounded busy policy; no backlog survives reset. |
| Existing ordinary tap, peak chord, sticky hold, dial and repeat behavior | Existing regressions continue to pass, with staggered releases and rearm cases added. |

Run relevant lifecycle/profile/API regressions, then the hardware-excluded Python
suite and frontend checks for any status changes. Report environment failures
separately; do not count excluded/hung tests as passed.

A later physical evidence matrix must date Bluetooth startup, held-button and
dial-click reconnect, power-cycle recovery, profile changes and shutdown checks.
Earl's availability and explicit selected-device capture permission are required
before those checks. An unperformed row stays unqualified. USB gets a separate
data-cable and transport qualification row.

## Builder discretion and next decision

Module/class names, internal generation-envelope representation, fixture layout
and additive status-field names are left to the builder. Keep safety state
synchronous at mutation boundaries and supervised asynchronous teardown separate.
Use small vertical implementation slices and meaningful failing regressions.

Earl approved this behavior contract on 2026-10-30, including whole-device
neutral rearm, immediate profile cancellation, the eight-macro limit and restart
after output failure. Implementation is authorized; physical hardware facts and
capture permission remain unknown.

Builder review: a fresh reviewer identified silent-node readiness and previews
after complete disconnection as the only material planning ambiguities. The
rules above resolve both as explicit agent proposals; no hardware/workflow facts
were inferred. The architecture and interaction reviews are also incorporated.
