# Branching model

GitHub-flow for the KeydialCommander repository:

- **`main`** — stable, always-working state of the project. Never commit directly.
- **Work branches** — one per coherent unit of work, short-lived, branched from `main`:
  - `feat/<topic>` — new functionality (e.g. `feat/commander-api`)
  - `fix/<topic>` — bug fixes outside a feature effort
  - `docs/<topic>` — documentation/design work
  - `chore/<topic>` — tooling, CI, packaging
- **Merging** — a branch merges to `main` when its milestone is complete and reviewed
  (open a PR against `main`; `--no-ff` merges keep branch history legible).

Commit style: short imperative subject, body when the "why" isn't obvious.
