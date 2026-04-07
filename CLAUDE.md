This project uses **Jig** for development workflow management.
See `jig.config.md` for pipeline configuration.

# Archipelago

An system of agents (AI, human, services, programs) for autonomous software engineering.

## Development Practices

- **Test-Driven Development (TDD)**: Write tests before implementation. Red-green-refactor cycle. All code changes must be covered by tests.
- **Trunk-Based Development**: Work directly on `main` with short-lived branches. Keep commits small and atomic. No long-lived feature branches.
- **Full test gate**: All tests (unit + integration) must pass before every commit and before creating a PR. Use `pdm test-all` to run the full suite in one command. Integration tests that cannot run in the current environment (e.g., no Docker daemon) will skip gracefully — that is acceptable; a *failure* is not. Never claim tests pass without running them. The pre-commit hook runs unit tests on every `git commit` and the pre-push hook runs the full suite on every `git push` to enforce this automatically.

## Tech Stack

- **Python 3.14**

## Project Structure

- `pyproject.toml`: Project configuration and dependencies (PDM)

## Commands

- `pdm add <package>`: Add a dependency
- `pdm test-unit`: Run unit tests
- `pdm test-integration`: Run integration tests

## Data Model Conventions

When designing or modifying Pydantic models, follow these rules:

- **Enumerated values** → `StrEnum` if code branches on the value;
  free `str` with suggested taxonomy in the field description if the
  value is only displayed or logged. Decision rule: "Does any code
  branch on this value?"
- **`Literal` is forbidden** for enumerated values. `StrEnum` members
  are first-class symbols that LSP operations (`findReferences`,
  `goToDefinition`, `rename`, `workspaceSymbol`) can navigate; `Literal`
  string values are not symbols and are invisible to LSP navigation.
  An agent following the LSP-first rule cannot distinguish "genuinely
  unused" from "LSP can't see it" when a routing value is a `Literal`.
  Only allowed fallback: discriminator tags on tagged unions when the
  pinned Pydantic version rejects `StrEnum`-typed discriminator fields —
  in that case write `kind: Literal[SomeEnum.VARIANT] = SomeEnum.VARIANT`.
- **Discriminated unions** use tagged wrapper types with a `kind:
  SomeEnum = SomeEnum.VARIANT` field and
  `Annotated[Union[...], Field(discriminator="kind")]`. Don't rely
  on Pydantic's smart-union field-uniqueness matching.
- **Agent boundaries** use JSON schema injection — role handlers
  inject `Model.model_json_schema()` into the agent prompt; never
  hand-enumerate valid values in role markdown.
- **Every boundary type is a Pydantic `BaseModel`** — runtime
  validation, schema generation, JSON round-trip. Plain dataclasses
  only for internal, non-serialized types.
