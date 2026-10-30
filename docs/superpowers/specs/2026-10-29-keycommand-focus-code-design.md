# KeyCommand focused play, analytics and Code mode

Date: 2026-10-29

## Direction

Use Monkeytype as a reference for focused typing, readable results and useful statistics. Keep KeyCommand's own identity: games shaped around peripheral capabilities, boards grouped by the declared setup, and more ways to play than ordinary text copying. Do not copy its code, branding or assets.

The user selected focused play and device-scoped analytics as the next pass, then requested Code mode. They chose timed Code tests with JavaScript, Python and TypeScript, snippet or runnable-file exercises, separate exercise boards, and 30/60/120-second rounds. Completed provided JavaScript examples can run locally on request; other languages have runnable downloads.

## Approaches

The selected approach extends the standalone browser game and current Worker/D1 service. Analytics remain local, and Code uses the same server-checked replay protocol with its own exercise partitions. Replacing the app with a typing-only clone would lose the device focus. An arbitrary-code compilation service would add hosting, isolation and abuse costs beyond this first Code release.

## Focused play

Offer a Focus while playing preference, enabled by default. During an active round, hide the hero, setup, boards, history and promotional content. Center the play surface with larger practice text, live metrics, remaining time and the selected setup. Keep End round available. Return to the results and analytics when the round finishes. Existing focus-loss and practice rules still apply.

## Personal analytics

Store at most 100 validated run summaries in this browser, separately from the existing last-five history for migration compatibility. Do not upload analytics, typed code, device descriptors or raw replay traces. A summary includes mode, exercise/scheme, duration, declared peripheral category, completion/clean flags, aggregate scores and one speed sample per second.

Show current-run net speed, raw speed, accuracy, errors and an interactive net/raw timeline. Typing and Code use five correct characters per normalized word; Control Circuit uses correct actions per minute. Raw speed counts all insertion/action attempts. Corrections keep their existing accuracy penalty. Display the metric definition so code WPM is not mistaken for identifiers or language words.

Personal best, average, run count and recent trend include only completed, clean rounds with matching mode, scheme/exercise, duration and category. Offline or deliberately chosen practice can count locally if the full round is clean. Paste, source changes, selection edits and early termination do not establish personal bests. Compare the last five qualifying runs with the preceding five for trend, otherwise show an insufficient-history state. Never invent results for old summaries that lack the required metadata.

## Code mode

Add a third mode with six first-party exercises: one snippet and one complete runnable file for each of JavaScript, Python and TypeScript. Source strings and downloadable files must match exactly. Use LF newlines and meaningful indentation. The code is original, small, deterministic, and has no network, filesystem or package dependencies.

The source textarea accepts punctuation, case, spaces and newlines. Tab inserts the exercise's configured indentation. There is no autocomplete or automatic source completion in ranked play. The same tail-edit/composition rules apply, with paste and other non-tail edits remaining practice. Unknown characters become mismatch tokens; they do not expose arbitrary text to the API.

Code rounds use 30, 60 or 120 seconds. Typing and Control Circuit retain 30/60. Switching away from Code resets a 120-second selection to 60 seconds. Complete files and snippets have separate rankings, even within a language. Keep mode, exercise ID, duration and declared category visible in the board and analytics context.

When the reference is completed early, keep the timer running and allow corrections. Record the first correct completion time. A final exactly complete source ranks ahead of an incomplete source; otherwise sort by the existing score and accuracy, then faster completion time before the existing timestamp tiebreaker. Run becomes available only after the round has ended with an exact match. Code scores expose optional `completionMs: number | null`, calculated by replay rather than accepted from the client; other modes keep their existing scoring behavior.

The server chooses Code source from a fixed exercise catalog, validates replay actions, and calculates score. Code uses the same remaining-correct-character WPM and cumulative accuracy rules as Type Sprint. The browser does not submit an authoritative score or source file. Existing challenge records and scores must survive the schema migration that adds Code mode and exercise schemes.

## Runnable examples

Only the supplied JavaScript examples can run in the browser, only after the text exactly matches the reference and the user clicks Run. Use a dedicated worker that imports a hardcoded allowlisted static reference file. Do not evaluate the textarea, accept arbitrary worker URLs, or execute code on the Cloudflare server. Capture bounded console output, terminate after two seconds, and terminate on exercise changes or component cleanup. Python and TypeScript offer explicit file downloads for running in the user's own environment.

This is a demonstration of the completed reference program, not a general code execution service. The same file is the exercise target, download and runnable JavaScript asset, so it cannot drift between display and execution.

## Shared interfaces

Extend `Mode` with `code`, and export `Duration = 30 | 60 | 120`. Code schemes are:

* `code:javascript:snippet`, `code:javascript:file`
* `code:python:snippet`, `code:python:file`
* `code:typescript:snippet`, `code:typescript:file`

Export the catalog and helpers from `src/code.ts`:

* `CodeExercise = { id: CodeScheme; language: 'javascript' | 'python' | 'typescript'; kind: 'snippet' | 'file'; title: string; filename: string; indent: 2 | 4; code: string; assetPath: string }`.
* `CODE_EXERCISES: readonly CodeExercise[]`, `getExercise(id: string): CodeExercise | undefined`, `challengeText(challenge: Challenge): string`.

Keep `passage(seed)` for Type Sprint and `targets` for Control Circuit. `game.ts` may import the catalog; `code.ts` imports game types only to avoid a runtime cycle.

Analytics live in `src/analytics.ts`:

* `SpeedPoint = { second: number; net: number; raw: number; accuracy: number }`.
* `RunAnalysis = { rawSpeed: number; netSpeed: number; errors: number; timeline: SpeedPoint[] }`.
* `RunRecord = Score & RunAnalysis & { id: string; date: number; mode: Mode; scheme: Scheme; duration: Duration; category: Category; elapsedMs: number; complete: boolean; clean: boolean }`.
* `analyzeRun(challenge: Challenge, events: TraceEvent[], elapsedMs: number): RunAnalysis`.
* `personalStats(records: RunRecord[], config: Pick<Challenge, 'mode' | 'scheme' | 'duration'>, category: Category): { count: number; best: number | null; average: number | null; trend: number | null }`.
* `loadRecords(storage: Pick<Storage, 'getItem'>): RunRecord[]` and `saveRecords(storage: Pick<Storage, 'setItem'>, records: RunRecord[]): boolean`, using `keycommand-runs-v2` and a 100-record cap. Invalid storage is ignored safely.

## Verification and delivery

Test scoring and API partitions across all six exercises and durations; migrate a populated old schema and verify existing records survive. Check indentation, newlines, corrections, complete-file matching and JavaScript allowlist execution. Test analytics units, clean/full-round filtering, setup isolation, trends, malformed storage and bounded history. Browser checks cover focused active play, restored results, keyboard-accessible chart controls, Code selection, Tab handling, runnable output and downloads.

Deploy only after the existing suite and new checks pass. Preserve the user's authorship and private game repository. Keep the original Commander draft PR separate from game implementation. Verify public HTTPS, exercise-specific shared scores and the running example after deployment, then remove only the exact temporary test records.

## Later device-native games

* Turn-only Glyphs: wheel or dial direction challenges that do not require a press switch.
* Chord Garden: build patterns from combinations on compact keypads, with boards for the available control set.
* Signal Memory: repeat a growing sequence using buttons, dial movement or accessible switches.
* Adaptive Rhythm: generate patterns for the capabilities the player chooses, with assistance and control schemes declared in the board key.

Add device families through explicit adapter/capability definitions and tested browser combinations. Keep model observation separate from actual input attribution. Public categories remain self reported until a trusted, consented physical-input integration exists.
