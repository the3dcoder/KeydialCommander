# KeyCommand foundation implementation plan

> For implementation, use Superpowers execution and verification skills. Complete the tasks below with tests and a fresh review before delivery.

Goal: improve Commander and build a separate playable KeyCommand repository with a Cloudflare shared leaderboard backend.

Architecture: Commander remains a Linux remapper. A standalone React game consumes browser input; a Cloudflare Worker issues challenges, validates replays and stores score summaries in D1. A YAML preset links the two projects without a privileged live bridge.

Tech stack: existing Commander Python and React stack; React, TypeScript, Vite, Wrangler and D1 for KeyCommand; Node test runner for domain tests and browser smoke tests for interaction.

Spec: `docs/superpowers/specs/2026-10-29-keycommand-design.md`.

## Global constraints

* Keep the applications in separate Git repositories.
* Preserve the user's configured authorship; no assistant attribution or coauthor trailers.
* Use plain writing without em dashes in new material.
* Device access is optional and starts from an explicit user action.
* Basic keyboard, keypad, wheel, gamepad and touch input must not require Commander.
* First-release public device categories are self reported, never hardware verified.
* Server-calculated scores use single-use challenges and bounded replay validation.
* Remote account access, domain connection and deployment must be observed before claiming success.

## Review focus

* Input from a different source during play makes a run mixed or practice, rather than preserving an inaccurate device claim.
* Correcting a typing mistake does not erase the previous accuracy penalty.
* Tab suspension or focus loss cannot extend the ranked deadline.
* Repeated or concurrent score submissions cannot create duplicate scores.
* Missing API, blocked hardware APIs and failed storage still leave practice playable.

## Files and interfaces

Commander changes are limited to shortcut capture, action drafts, synthetic test isolation, current architecture docs and the game preset.

The new repository uses `src/game.ts` for shared deterministic game rules, `src/input.ts` for input normalization, `src/App.tsx` and `src/styles.css` for UI, `src/api.ts` for typed API calls, `worker/index.ts` for HTTP handlers, `migrations/0001_initial.sql` for D1 and `wrangler.jsonc` for deployment. Tests live under `tests/`.

Shared types exported by `src/game.ts`:

* `Mode = 'typing' | 'circuit'`, `Scheme = 'text' | 'buttons' | 'dial' | 'hybrid'`.
* `Category = 'keyboard' | 'keypad' | 'dial' | 'gamepad' | 'touch' | 'mixed'`.
* `Challenge = { id: string; seed: number; mode: Mode; scheme: Scheme; duration: 30 | 60; startedAt: number; rulesVersion: 1 }`.
* `TraceEvent = { t: number; action: string }`. Relative `t` is milliseconds from start. Typing actions are a single supported practice character, `backspace`, or `miss` for an unsupported character. Circuit actions are `lane1`, `lane2`, `lane3`, `lane4`, `left`, `right`, `press`.
* `replay(challenge: Challenge, events: TraceEvent[]): Score` returns `{ score: number; correct: number; attempts: number; accuracy: number; wpm: number }`.
* `passage(seed: number): string` supplies bounded fixed practice text. `targets(seed: number, scheme: Scheme, count?: number): string[]` supplies deterministic circuit targets.

HTTP interfaces:

* `POST /api/challenges` with `{mode, scheme, duration}` returns `Challenge`.
* `POST /api/scores` with `{challengeId, name, category, events}` returns the stored score summary. No client score or hardware descriptor is accepted as authority.
* `GET /api/leaderboard?mode=...&scheme=...&duration=...&category=...` returns `{ scores: LeaderboardEntry[] }`, with at most 25 entries.
* `LeaderboardEntry = Score & { id: string; name: string; category: Category; createdAt: number }`.

### Task 1: Commander input repairs

Files: `web/src/components/ShortcutCapture.tsx`, `web/src/codeToKey.ts`, `web/src/App.tsx`, `web/src/store.ts`, `web/src/components/Inspector.tsx`, `web/src/components/ActionLibrary.tsx`, `tests/test_evdev_source.py`, new focused frontend regression checks.

- [ ] Reproduce modifier capture and invalid-template submission before changing implementation.
- [ ] Add focused regression checks for Ctrl+C, multiple modifiers, modifier-only release and template staging without network mutation.
- [ ] Accumulate modifier keydowns and finish on a primary key or modifier release. Reset on blur and ignore repeats.
- [ ] Stage a template in UI state, scoped to the selected profile and control. Clicking or dragging a template opens a draft; only Save persists it.
- [ ] Restrict the synthetic evdev integration source to its own virtual node.
- [ ] Run frontend checks, build and Python regressions using an isolated test environment; do not start or reconfigure the user's daemon.

### Task 2: Game rules and shared leaderboard service

Files: `/tmp/KeyCommand/src/game.ts`, `/tmp/KeyCommand/worker/index.ts`, `/tmp/KeyCommand/migrations/0001_initial.sql`, `/tmp/KeyCommand/tests/game.test.ts`, `/tmp/KeyCommand/tests/worker.test.ts`.

- [ ] Write and run failing domain tests for deterministic challenges, correct and incorrect actions, corrections, duration boundaries and invalid traces.
- [ ] Implement the exported interfaces above. Practice passages use lowercase ASCII and spaces in this first rules version; UI input still honors composition and explains unsupported characters without transmitting them.
- [ ] Write and run failing API tests for valid submissions, malformed input, early/expired/replayed challenges and category-filtered results.
- [ ] Implement bounded JSON endpoints, prepared SQL, indexed queries, single-use atomic submission and score calculation on the server. Challenge cleanup removes records older than ten minutes; score history remains.
- [ ] Use 256 KiB body limits, 4096 events, 20 events per second maximum averaged over the full round, at most 24 display-name characters and at most 25 results. Enforce a maximum of 30 issued challenges per minute per ephemeral hashed client identifier, without storing raw IP addresses.
- [ ] Run Node tests and a real local D1 migration/API smoke check with Wrangler before accepting the service.

### Task 3: Playable browser interface

Files: `/tmp/KeyCommand/package.json`, `index.html`, TypeScript/Vite config, `src/main.tsx`, `src/App.tsx`, `src/styles.css`, `src/input.ts`, `src/api.ts`, `tests/input.test.ts`, browser smoke script.

- [ ] Create the separate local Git repository and install only needed dependencies. Use the user's Git identity when committing.
- [ ] Implement a responsive game interface with mode selection, source setup, duration, display name, category and custom mappings.
- [ ] Add input normalization tests before implementing wheel threshold/cooldown, key repeat rejection, mapping conflicts and gamepad button/axis edges.
- [ ] Connect the shared deterministic rules and typed HTTP API. Use practice mode when challenge creation fails. Freeze setup during a round and finish on a monotonic deadline or focus loss.
- [ ] Add explicit optional HID identification, gamepad connection, permission failure states, local metadata removal and honest device labels. Do not open HID reports.
- [ ] Show results, explicit submission with privacy copy, shared leaderboard filtering, loading/error/empty states, local history and retry.
- [ ] Test typing, circuit, corrections, focus loss, keyboard navigation, touch layout, denied HID and API fallback in a real headless browser.

### Task 4: Integration, documentation and delivery

Files: `ARCHITECTURE.md`, `docs/AUDIT-2026-10-29.md`, `docs/ROADMAP.md`, `examples/keycommand-profile.yaml`; new game's `README.md`, `LICENSE`, `wrangler.jsonc`, deployment docs and CI workflow.

- [ ] Record the complete current app map, tested baseline, confirmed issues, fixed issues and remaining packaging/API concerns.
- [ ] Add an importable K20 game preset in both repositories and explain mapping/timing limits.
- [ ] Configure Worker Static Assets and a D1 binding, with a local database ID for development and an explicit production setup step.
- [ ] Run game tests, typecheck, build, Worker dry-run, local database/API smoke and browser smoke checks. Run Commander regression checks and build.
- [ ] Dispatch a fresh review of both projects. Address material defects and rerun affected checks.
- [ ] Copy the completed independent repository to `/home/earl/Documents/KeyCommand` and verify its Git root differs from Commander.
- [ ] Inspect Cloudflare CLI authentication without exposing tokens. Deploy and connect the domain only if account access is available and the domain is ready. Otherwise deliver exact remaining commands without claiming deployment.
- [ ] Leave Commander changes reviewable on a feature branch. Do not push, merge, create a public GitHub repository or buy services without an established destination and authorization.
