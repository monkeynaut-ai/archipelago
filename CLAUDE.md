# Archipelago

A system of agents (AI, human, services, programs) for autonomous software engineering.

## Core documents

- **`docs/product/archipelago-vision.md`** — the canonical frame for the project: vision, north stars, operating philosophy (including the "harness competing tensions" design method), current shape, open threads. Read this first when orienting to the project or making architectural choices. Living document; evolves as understanding deepens.
- **`docs/knowledge/`** — recurring-correction archive (`corrections-required.md`, `review-lessons-log.md`, `lessons-learned-configuration.md`, `docker-worker-fixes.md`). Skim before designing or reviewing to avoid repeating past mistakes.

## Development Practices

- **Test-Driven Development (TDD)**: Write tests before implementation. Red-green-refactor cycle. All code changes must be covered by tests.
- **Trunk-Based Development**: Short-lived branches off `main`; small atomic commits; no long-lived feature branches. Branch name format: `{type}/gh-{number}-{kebab-title}`.
- **Linear history, fast-forward only**: `main` allows no merge commits. Rebase the branch on current `main` before merging; CI (`ff-only.yml`) rejects a branch that isn't a descendant of `main`. Merges happen via `git merge --ff-only`, not GitHub's merge button. See `docs/engineering/development-workflow.md` for the full procedure.
- **Full test gate**: All tests (unit + integration) must pass before every commit and before creating a PR. Use `pdm test-all` to run the full suite in one command. Integration tests that cannot run in the current environment (e.g., no Docker daemon) will skip gracefully — that is acceptable; a *failure* is not. Never claim tests pass without running them. The pre-commit hook runs unit tests on every `git commit` and the pre-push hook runs the full suite on every `git push` to enforce this automatically.

## Tech Stack & Commands

- **Python 3.14**, `src/` layout, managed with PDM. Run code via the `pdm` scripts (they set `PYTHONPATH=src`); a bare `pytest`/`python` won't resolve the package.
- Package: `src/archipelago/` → `models/`, `actions/`, `agents/`, `systems/`, `telemetry/`, `docker/`.
- Depends on the published **agent-foundry-ai** package; import from its public facades, not deep modules — see `.claude/rules/agent-foundry-imports.md`.
- `pdm add <package>`: Add a dependency
- `pdm test-all`: Full suite — required before commit/PR (test conventions in `.claude/rules/testing.md`)
- `pdm lint` / `pdm format`: ruff check / format
- `pdm typecheck`: pyright

<!-- Pydantic/data-model conventions live in .claude/rules/data-model-conventions.md (path-scoped to *.py) -->

