# KeyCommand focused play, analytics and Code implementation plan

Goal: carry the user's Monkeytype-inspired clarity into KeyCommand while adding setup-specific analytics and real Code exercises.

Spec: `docs/superpowers/specs/2026-10-29-keycommand-focus-code-design.md`.

Architecture: extend the separate game repository. Shared deterministic rules remain authoritative in the Worker, analytics are local, and vetted JavaScript examples run only in a dedicated browser worker. No new paid service or runtime dependency is needed.

## Constraints

Keep all existing modes and scores compatible. Preserve old D1 data during migration. Separate board keys by mode, exact exercise/scheme, duration and declared category. No automatic hardware permission or server code execution. No assistant attribution or coauthor trailers; use Earl's configured identity. New comments and copy use plain writing.

## Review focus

* A 120-second Code choice must not leak into the other modes.
* Code source, downloads and executable JavaScript references must match.
* Runs from a different device category, exercise or duration must not affect a personal best.
* Old or malformed history must not fabricate trend data or crash play.
* The code runner must never evaluate arbitrary textarea content or leave a worker running after navigation.

### Task 1: Code catalog, rules, API and migration

Own `src/code.ts`, changes to `src/game.ts`, `worker/index.ts`, `migrations/0002_code_mode.sql`, `public/code-examples/*`, `public/code-runner.js`, new Code domain/API/migration tests, and necessary changes to existing domain/API test helpers.

- [x] Write failing tests for language/exercise catalog uniqueness, runnable/download source equality, indentation/newlines, duration restrictions and remaining-character scoring.
- [x] Implement the exact exported interfaces and exercise IDs in the spec. Use explicit first-party source strings and generate static assets from those strings. The catalog must not read files in a browser/Worker runtime.
- [x] Extend validation, replay and filtered leaderboards without changing existing typing/circuit behavior. Add optional server-derived Code completionMs, retain the timed round after early completion, and rank complete Code source before incomplete source, with earlier completion breaking equal score/accuracy ties.
- [x] Write a populated-schema migration regression, then implement a preserving D1 migration. Test all Code scheme/duration/category partitions.
- [x] Implement a classic worker with a fixed JavaScript file allowlist, bounded output and no evaluation of user-provided source.
- [x] Run the full domain/API suite and typecheck. Report interfaces and actual verification.

### Task 2: Local analytics

Own `src/analytics.ts` and `tests/analytics.test.ts` only. Consume shared Challenge/Score/Mode/Scheme/Duration interfaces. Do not change UI or game rules.

- [x] Write failing tests for net/raw speed, cumulative accuracy/error counts, timeline samples, empty/partial runs and both gameplay unit systems.
- [x] Implement `analyzeRun`, reusing `replay` for the score calculations at sample boundaries.
- [x] Write tests for full/clean/matching setup filtering, best/average, last-five vs previous-five trend and insufficient history.
- [x] Implement `personalStats` and bounded, validated storage with safe quota/parse failure behavior. Do not store replay actions or source strings.
- [x] Run focused and full tests. Report actual results and any integration choices.

### Task 3: Focused play, Code interface and performance results

Own `src/App.tsx`, `src/input.ts` as needed for Code characters, `src/api.ts`, `src/components/PerformancePanel.tsx`, `src/components/SpeedChart.tsx`, `src/components/CodeRunner.tsx`, styles and browser checks.

- [x] Add a focus preference that hides surrounding content only during an active round and leaves an End control available.
- [x] Add Code mode, language/exercise selectors, source rendering, Tab indentation and the 120-second option. Preserve typing/composition/focus-loss protections.
- [x] Record clean/full-round metadata and local analytics on finish without uploading it. Keep existing last-five history compatible.
- [x] Show setup-scoped personal bests and averages, raw/net metrics, errors and interactive, keyboard-accessible timeline controls. Keep no-data states truthful.
- [x] Show a complete-source gated JavaScript runner and downloads for the exercise files. Terminate workers on timeout and cleanup.
- [x] Add browser regressions before fixing any newly identified behavior. Verify all original browser tests plus new focus, Code, chart and runner paths.

### Task 4: Review and publish

- [x] Refresh the game's design/README/verification notes and record the device-native roadmap.
- [x] Run all tests, typecheck, build, formatting and Worker dry run. Run a local populated D1 migration/API check.
- [x] Request a fresh review; resolve material issues with regression checks.
- [x] Apply the preserving remote D1 migration, deploy the tested release, and verify public Code challenge/board behavior and runnable output.
- [x] Remove only exact test score/challenge IDs, update the persistent local checkout and private GitHub repository, and leave Commander changes in their existing draft PR.

## Delivery

Completed and deployed to https://keycommand.io. The separate private [KeyCommand repository](https://github.com/the3dcoder/KeyCommand) contains the game, shared backend and detailed verification record. The release passed 44 domain/API/analytics tests, 15 browser regressions, the original full browser flow and public Code/API/browser checks. Commander changes remain in [draft PR 1](https://github.com/the3dcoder/KeydialCommander/pull/1).
