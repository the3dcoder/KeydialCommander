# KeyCommand design

Date: 2026-10-29

## Purpose and project boundary

Keydial Commander stays the Linux control center for the Huion K20. KeyCommand is a separate browser game and Git repository intended for keycommand.io. It should be enjoyable with a full keyboard, a small keypad, a wheel or dial, a gamepad, or touch controls. Devices contribute different controls, so the game offers different challenges rather than requiring every peripheral to type arbitrary text.

The user selected browser first, two separate game modes, optional device access, broad input support, a shared leaderboard service, and a standalone game with an importable Commander profile. The working display name is KeyCommand, matching the domain. The user's first spelling was KeyCommmand; capitalization and spelling remain easy to change.

## Approaches

1. Standalone game with a Commander profile preset. Browser input works immediately, hosting is independent, and the K20 can use ordinary remapped keys. This is the selected approach.
2. Embed the game in Commander. This would make the existing Linux daemon an installation requirement and mix game rules with system command execution.
3. Add a paired live Commander bridge immediately. This could eventually expose physical input with provenance, but first needs origin validation, authentication, explicit selected-device capture, revocation, and a new timestamped input stream. Existing executed-action events are unsuitable for timing.

Cloudflare Workers Static Assets and D1 are the proposed hosting choice because the user is setting up Cloudflare for the domain and wants a simple, inexpensive shared backend. Azure would add a separate deployment and account configuration without an established benefit. No paid plan is required by the design. Actual account limits and availability determine launch capacity.

## First playable release

### Type Sprint

A 30 second or 60 second typing challenge uses a fixed, versioned English practice passage. Players type into a real text input so keyboard layouts and composition work. Show elapsed time, gross attempts, correct characters, accuracy, and words per minute based on five correct characters per word. WPM counts matching characters remaining in the passage at the deadline, so deleting and retyping cannot inflate throughput. Accuracy counts correct insertion attempts divided by all insertion attempts, including corrected mistakes. Backspace can correct the current passage but does not erase previous error attempts. Ranked typing allows tail insertions and backspaces; selection replacement, forward deletion, paste, drop, focus loss, and input-source changes make the current run practice only. Composition is committed once at composition end. Unsupported characters are represented as a mismatch token in the replay, never uploaded as arbitrary text. Pasting remains available outside scored gameplay.

### Control Circuit

A 30 second or 60 second sequence challenge presents the next action and a preview queue. Three control schemes have separate rankings:

* Buttons: four lanes, default keys D, F, J, K.
* Dial: turn left, turn right, and press, default keys Left, Right, Enter and scroll or click alternatives.
* Hybrid: four lanes plus turn left and turn right.

Each correct action advances the queue and earns 100 points. Incorrect attempts reduce accuracy and leave the target in place. Ignore key auto-repeat. Wheel input is normalized by direction with a deadzone and cooldown so trackpad bursts do not produce dozens of actions. Gamepad buttons use rising edges; axes use a neutral deadzone and require a return to neutral. Touch buttons expose the same actions. Mappings can be changed before a run, with duplicate assignments rejected.

The game must remain usable when a browser does not expose a peripheral. A device emitting ordinary keyboard or wheel events needs no special device API. Hardware support is described as input-method support until a physical device/browser combination has been tested.

### Session lifecycle

Setup, start, play, finish, retry. Settings and source selection are frozen while playing. Use a monotonic clock for local timing. The ranked server issues its own challenge identifier, seed and start timestamp. A run ends on its deadline, including when a tab is throttled. Losing window focus ends the run as practice to avoid hidden background capture and pause-based scoring advantages. Input listeners only consume controls while the play area is focused and a run is active.

Practice works when the shared service is unavailable. The interface clearly distinguishes practice, local history, and shared submissions. Submission is an explicit action after the result; it does not upload input automatically.

## Device access and privacy

Basic play never prompts for hardware access. Setup asks the player to choose a category: keyboard, keypad, dial, gamepad, touch, or mixed. A model label is optional and not part of the primary ranking key.

An optional Identify device button explains the browser chooser before requesting a single HID device. Inspect only the selected device's public product name and vendor/product IDs, locally. Do not open HID reports, request broad USB access, enumerate previously granted devices on load, collect serial numbers or Bluetooth addresses, or claim that a chooser proves which device produced keyboard input. Generic keyboard and mouse collections may be protected and WebHID is not available in every browser. Unsupported, dismissed, rejected, and revoked states have clear fallback messages. Forget uses the browser's device-forget capability where supported and clears local metadata.

Gamepad access starts only after the player chooses the gamepad source and presses Connect. Poll only during setup testing or a focused game session, and stop on disconnect or source change. Browser gamepad APIs may expose device information after interaction without showing a permission dialog; explain this distinction in the interface.

The result records input source separately from peripheral declaration. A manually chosen keyboard category is self reported. A browser device chooser adds an observed model label, not verified input attribution. All first-release public rankings are explicitly open, self-reported rankings. There is no hardware-verified tier until a trusted physical-input integration exists.

Scores sent to the service contain a display name, category, mode, scheme, duration, normalized gameplay actions or committed practice-text edits with relative times, and challenge ID. Device descriptors and arbitrary typed text are never sent. Text edits are represented as append/backspace commands against the issued fixed practice text, without transmitting character values outside that alphabet. Explain this on the submission control. No accounts, email addresses, advertising identifiers, or third-party analytics are required. The service does not store raw IP addresses. Keep bounded input traces for validation during a request and retain only score summaries afterward.

## Shared leaderboards

Implement a real Worker API backed by D1, with local D1 simulation for development. A browser-only localStorage table is a history view, never presented as a shared leaderboard.

Leaderboard partition: rules version, mode, scheme, duration, peripheral category. Text and arcade scores never share a board. Mixed-source runs use the mixed category. Device model is optional local context, not a separate board that fragments participation. Scores sort by correct throughput or points, then accuracy, then timestamp. Return a bounded top 25.

The server issues a challenge before a ranked run. A challenge is single use, expires after ten minutes, and cannot be submitted before the selected duration has elapsed, allowing a small transport tolerance. Validate the replay and calculate score on the server; do not accept a client-supplied score as authority. Reject malformed bodies, unknown enum values, non-finite or decreasing times, excessive input events, impossible high rates, reused challenges and oversized names. Prepared SQL statements and indexes cover every public query. Use an atomic consumed-challenge update and score insertion so concurrent submissions cannot duplicate a score. Use a bounded, short-lived challenge record and scheduled cleanup to prevent indefinite growth.

These checks make fabricated summary scores and accidental duplicates harder. They do not establish human play or prevent a programmable peripheral or scripted browser from replaying plausible input. Display this as an open leaderboard, with hardware self reported. A later competitive release can add accounts, Turnstile, rate limits, moderation, and stronger session attestations without changing the game loop.

## Commander improvements in this update

Keep the current visual style and Python compatibility. Fix modifier shortcut capture so chords can be captured and a modifier alone is committed on release. Make action templates editable drafts, saved only after the user finishes configuring them, and allow clicking a template for a selected control. Isolate synthetic input tests from real devices. Replace the obsolete architecture summary with the actual evdev path and record remaining audit findings separately.

Ship a KeyCommand YAML preset mapping four K20 buttons to D/F/J/K and dial rotation to Left/Right with dial click to Enter. Import creates a new profile. Do not switch profiles, remap hardware, install udev rules, or change the user's running daemon automatically. Explain that Commander's normal button actions fire on release, so this preset supports casual play without claiming physical timing verification.

## Repository and delivery

Create a separate KeyCommand Git repository beside KeydialCommander, with React, TypeScript, Vite, a Cloudflare Worker, D1 migrations, tests, README, and deployment instructions. The game has its own MIT license attributed to the existing copyright holder. Keep git authorship tied to the user's configured identity. Do not add coauthor trailers or assistant credits. Do not publish a GitHub repo without a chosen destination and visibility.

Build and test before deployment. Cloudflare account access and ownership of keycommand.io must be checked before remote changes. If account access is unavailable, deliver the working local game and server, a deployable configuration, and precise remaining setup steps. Do not mark the site deployed or the domain connected without observing it.

## Verification

Domain tests cover scoring, correction attempts, deadlines, duplicate mappings, wheel/gamepad normalization and mixed input. API tests cover challenge creation, replay validation, sorted/category-isolated results, malformed requests, expiration, replay and concurrent submission. Browser smoke checks cover a complete typing run, a control run, explicit shared submission, unavailable API fallback, denied device access, keyboard navigation, and narrow-screen layout. Commander checks cover shortcut capture and draft behavior, Python regressions and frontend build. Physical device tests remain manual and are not claimed from synthetic events.

## Sources

* [WebHID specification](https://wicg.github.io/webhid/index.html)
* [Chrome WebHID security restrictions](https://developer.chrome.com/docs/capabilities/hid)
* [Gamepad specification](https://www.w3.org/TR/gamepad/)
* [Cloudflare Workers Static Assets](https://developers.cloudflare.com/workers/static-assets/)
* [Cloudflare D1 local development](https://developers.cloudflare.com/d1/best-practices/local-development/)
* [Cloudflare D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/)

## Decision record

User decisions: separate game repository and playable version now; keycommand.io domain; browser first; text plus control mode; optional device access; shared backend using the simplest inexpensive service; broad device input; Commander preset before a live bridge.

Recommended defaults used under the user's 15 second instruction: 30/60 second rounds, D/F/J/K mappings, open self-reported rankings, no account requirement, and a single Cloudflare Worker with D1. These are implementation choices, not explicit user approvals of each detail.
