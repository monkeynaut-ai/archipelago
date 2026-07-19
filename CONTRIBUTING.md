# Contributing to Archipelago

Thanks for your interest. Archipelago is an experimental research project, so before
you invest time in a change, read the caveat: the topology, agent roster, and
interfaces are deliberately unstable, and a change that locks any of them down is
likely to be declined even if it is well made. [`docs/product/archipelago-vision.md`](docs/product/archipelago-vision.md)
is the canonical frame — read it before proposing anything architectural.

## Before you open a pull request

- **Open an issue first** for anything beyond a small fix. It is cheaper to find out
  that a direction conflicts with an in-flight design than to find out in review.
- **Run the full gate.** `pdm test-all` must pass. Integration tests that cannot run in
  your environment (no Docker daemon, for instance) skip gracefully — a skip is
  acceptable, a failure is not.
- **Never claim tests pass without running them.** The pre-commit hook runs unit tests
  and the pre-push hook runs the full suite, but the claim is yours to make honestly.

## Development practices

- **Test-Driven Development.** A failing test precedes every piece of production code;
  red, green, refactor. All code changes are covered by tests.
- **Trunk-Based Development.** Work on `main` with short-lived branches. Small, atomic
  commits. No long-lived feature branches.

## Testing conventions

Run tests through the `pdm` scripts — they set `PYTHONPATH=src`, so a bare `pytest`
invocation will not resolve the `archipelago` package.

| Command | Scope |
|---|---|
| `pdm test-unit` | Everything except `integration`, `benchmark`, `e2e` |
| `pdm test-integration` | `integration` only — needs Docker or external services |
| `pdm test-all` | Everything except `benchmark` and `e2e`; the commit/PR gate |
| `pdm test-e2e` | `e2e` only; hits real LLMs, minutes per run, explicit invocation |

Markers for a new test:

- `integration` — needs Docker or an external service.
- `e2e` — hits a real LLM. Excluded from normal runs.
- `benchmark` — performance measurement. Excluded from normal runs.
- none — a fast, self-contained unit test. Unmarked tests run in every gate, so keep
  them hermetic and fast.

**Do not assert on pipeline topology.** Tests that pin composition, step counts,
wiring, or which state model a field lives on clamp the very experimentation the
project exists to do — every such test has to be rewritten each time the topology is
varied, which makes varying it expensive. Test observable behavior and validity
instead.

## Data model conventions

- **Enumerated values** → `StrEnum` if any code branches on the value; free `str` (with
  a suggested taxonomy in the field description) if the value is only displayed or
  logged.
- **`Literal` is forbidden** for enumerated values. `StrEnum` members are first-class
  symbols that LSP operations can navigate; `Literal` string values are not, so an
  agent (or human) tracing usage cannot distinguish "genuinely unused" from "invisible
  to the tooling." The only allowed fallback is a discriminator tag on a tagged union
  when the pinned Pydantic version rejects `StrEnum`-typed discriminator fields.
- **Discriminated unions** use tagged wrapper types with a `kind: SomeEnum = SomeEnum.VARIANT`
  field and `Annotated[Union[...], Field(discriminator="kind")]`. Do not rely on
  Pydantic's smart-union field-uniqueness matching.
- **Agent boundaries** use JSON-schema injection — inject `Model.model_json_schema()`
  into the prompt; never hand-enumerate valid values in role markdown.
- **Every boundary type is a Pydantic `BaseModel`.** Plain dataclasses only for
  internal, non-serialized types.
- **Composition over inheritance for state models.** No subclass hierarchies between
  state types; type boundaries use exact identity checks (`is`), not `issubclass`.

## Importing from Agent Foundry

Agent Foundry exposes a tiered public API. Import symbols from the **package facade**,
never from the deep module that defines them — a ruff `banned-api` guard fails lint on
the deep path.

```python
from agent_foundry.orchestration.run_outcome import RunOutcome   # wrong — banned
from agent_foundry.orchestration import RunOutcome               # right
```

Facades: `agent_foundry.constructs`, `agent_foundry.ai_models`, `agent_foundry.models`,
`agent_foundry.agents`, `agent_foundry.compiler`, `agent_foundry.orchestration`,
`agent_foundry.responders`.

A symbol that its facade does not re-export is Internal-tier and not meant for use
here. Do not reach past the facade to get it.

## Tech stack and commands

Python 3.14 · Pydantic · Docker · Pytest · [PDM](https://pdm-project.org/).

| Command | Purpose |
|---|---|
| `pdm add <package>` | Add a dependency |
| `pdm lint` | Run ruff |
| `pdm format` | Apply ruff formatting |
| `pdm typecheck` | Run Pyright |

## Reporting bugs and security issues

Bugs and feature requests go in [GitHub Issues](https://github.com/730alchemy/archipelago/issues).
Security vulnerabilities do **not** — see [SECURITY.md](SECURITY.md) for private
reporting channels.

## Code of conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
