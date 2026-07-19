---
paths:
  - "**/*.py"
---

# Testing conventions

TDD, red-green-refactor: a failing test precedes every piece of production code.

Run tests through the `pdm` scripts — they set `PYTHONPATH=src`, so a bare
`pytest` invocation won't resolve the `archipelago` package.

- `pdm test-unit` — everything except `integration`, `benchmark`, `e2e`
- `pdm test-integration` — `integration` only (needs Docker / external services)
- `pdm test-all` — everything except `benchmark` and `e2e`; the pre-commit/PR gate
- `pdm test-e2e` — `e2e` only; hits real LLMs, minutes per run, run explicitly

Marker to apply to a new test:

- `integration` — needs Docker or an external service. Skips gracefully when
  the dependency is absent; a skip is acceptable, a failure is not.
- `e2e` — hits a real LLM. Excluded from normal runs.
- `benchmark` — performance measurement. Excluded from normal runs.
- (none) — a fast, self-contained unit test.

An unmarked test runs in every gate, so keep it hermetic and fast.
