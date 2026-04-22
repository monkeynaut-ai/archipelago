# CS7 Plan 4 — Phase 2 Slice 1: Archetype Templating + AgentAction Signature Change — Implementation Plan

> **Status:** Built.
> **Date:** 2026-04-20
> **Roadmap:** `docs/plans/2026-04-03-review-feedback-loop-roadmap.md` (CS7 Plan 4)
> **Parent plan:** `docs/plans/2026-04-17-cs7-plan4-archipelago-agents-plan.md`
> **Parent phase design:** `docs/plans/2026-04-20-cs7-plan4-phase2-design.md`
> **Cross-repo:** Slice 1 lives entirely in **agent-foundry**. Archipelago is not touched in this slice.

> **Post-build note (2026-04-20):** During implementation, the Slice 1 code
> was decomposed further and extracted into a new top-level `archetype`
> package (intended for open-source extraction within days). The original
> plan referred to `agent_foundry.instructions` and `agent_foundry.markdown`
> as the package locations; the final code lives at `archetype.templating`
> and `archetype.markdown` instead. The `template()` accessor was renamed
> to `template_fields()` and moved into `archetype.markdown.introspection`
> (it's markdown-model introspection, not templating-specific). The
> `render_instructions()` helper was renamed to `resolve()` (name stripped
> of instructions-specific framing). Structure and behavior below reflect
> the initial decomposition; read alongside the final source tree for
> current naming.

## Where this slice fits

Phase 2 delivers the Designer agent plus the platform machinery it depends on. Slice 1 is the agent-foundry foundation: the instruction-templating module (Jinja environment + `template_fields()` accessor + `render_template` global) and the `AgentAction.instructions_provider` signature change. Everything downstream — Archipelago data models, workspace bootstrap, Designer agent, Sequence wiring — depends on Slice 1.

## Goal

Agent Foundry exposes a public API for rendering Jinja-templated agent instructions against per-run state, with `template_fields()` and `render_template()` available as template globals. The `AgentAction.instructions_provider` callable receives the input-state slice so templating can resolve against it.

After Slice 1, a product can write:

```python
from archetype.templating import resolve

def my_instructions_provider(state: MyInput) -> str:
    return resolve(
        template_text=_load_template(),
        feature=state.feature_definition,
    )
```

And its instruction template can use:

```
{% for field in template_fields(MyDomainModel) %}
- **{{ field.heading }}** — {{ field.description }}
{% endfor %}

{{ render_template(MyOutputModel) }}
```

## Tech stack

- Python 3.13+ (Agent Foundry baseline).
- Pydantic v2 (existing).
- **Jinja2 (new runtime dependency)** — pure-Python, widely used, minimal transitive deps.
- pytest + pytest-xdist.

## Scope

### In scope

- New module `agent_foundry/src/archetype/templating/` providing:
  - A `template_fields()` accessor that returns heading-field metadata for a `MarkdownHeader` subclass.
  - A Jinja `Environment` factory preconfigured with `trim_blocks=True`, `lstrip_blocks=True`, `autoescape=False`.
  - A `resolve()` helper that composes the environment, registers globals (`template`, `render_template`), and renders a template string against a context.
- `AgentAction.instructions_provider` signature change: `Callable[[], str]` → `Callable[[I], str]`.
- Updates to every call site of `instructions_provider` in agent-foundry (src + tests).
- Jinja2 added to agent-foundry's `pyproject.toml`.
- Public API exports from `archetype.templating.__init__`.

### Out of scope

- Any archipelago code.
- Jinja features beyond the three-form convention (filters, conditionals, macros, includes, inheritance). These work because Jinja supports them, but the module documents that usage is restricted by convention.
- Automatic enforcement of the convention at runtime. Convention is documented; review is the enforcement.
- `template_fields()` support for `TextTemplate`-annotated titles, `list[MarkdownHeader-subclass]` body fields, or `AsCodeBlock`/`AsTable`/`AsBulletList`/`AsNumberedList` bodies. Deferred until a downstream consumer needs them.

## Architecture

```
archetype/templating/
├── __init__.py         # public API
├── template.py         # template() accessor + FieldInfo dataclass
├── environment.py      # Jinja environment factory with globals
└── render.py           # resolve() helper
```

Pipeline when `resolve(template_text, **ctx)` is called:

```
template_text + context
      │
      ▼
build Jinja Environment  (trim_blocks, lstrip_blocks, no autoescape)
      │
      ▼
register globals         (template, render_template)
      │
      ▼
env.from_string(text).render(**ctx)
      │
      ▼
resolved instructions string
```

`template_fields(ModelClass)` iterates `ModelClass.model_fields` in declaration order, skips structural fields (`title`, `frontmatter`), and yields a `FieldInfo(heading, description)` for each body field:

- `Annotated[str, AsHeading()]` → heading is the field name in Title Case (`problem_statement` → "Problem statement").
- Field typed as a `MarkdownHeader` subclass → heading is the subclass's `title` field default value.
- Other patterns are out of scope for Slice 1; raise a clear `ValueError` so future phases know they need to extend the accessor.

## Locked design decisions

Carried from Phase 2 design:

1. Jinja2, not a custom engine — solved problem; convention handles discipline.
2. Three-form convention: `{{ path }}`, `{% for x in path %}...{% endfor %}`, plus `template_fields()` and `render_template()` as globals. Convention is documented in the module docstring; not enforced at runtime.
3. Resolution at container start (single pass before the agent runs). No mid-run re-resolution.
4. `instructions_provider: Callable[[I], str]` — takes input-state slice. Matches `prompt_builder`'s pattern.
5. `template_fields()` returns a dataclass with `.heading` and `.description` attrs (not a Pydantic model — consumed inside Jinja, doesn't need validation).

## Tasks (TDD, checkbox-tracked)

Tests precede implementation. Mark `- [x]` on completion.

### Task group 1.1 — `template_fields()` accessor

- [ ] **1.1.1** Tests for `template_fields()` (`tests/archetype/templating/test_template.py`):
  - Returns list of `FieldInfo` for an `Annotated[str, AsHeading()]`-only document.
  - Returns correct heading (Title Case from field name) and description for each field.
  - Handles nested `MarkdownHeader` subclass fields — uses subclass's `title` default.
  - Skips `title` and `frontmatter` structural fields.
  - Declaration order preserved.
  - Fields without `description` → `FieldInfo.description is None`.
  - Unsupported body-field shape raises `ValueError` naming the field and shape.
- [ ] **1.1.2** Implement `template_fields()` in `archetype/templating/template.py`:
  - `FieldInfo` dataclass (`frozen=True`): `heading: str`, `description: str | None`.
  - `template_fields(model_class: type[MarkdownHeader]) -> list[FieldInfo]`.
  - Walk `model_class.model_fields`; skip `title` and `frontmatter`; dispatch on annotation/type; build list.

### Task group 1.2 — Jinja environment factory

- [ ] **1.2.1** Add `jinja2` to `agent-foundry/pyproject.toml` (runtime dependency) and refresh `pdm.lock`.
- [ ] **1.2.2** Tests for environment factory (`tests/archetype/templating/test_environment.py`):
  - Factory returns a `jinja2.Environment` with `trim_blocks=True`, `lstrip_blocks=True`, `autoescape=False`.
  - `template` and `render_template` are available as globals.
  - `template_fields(SomeModel)` called from inside a Jinja template iterates correctly.
  - `render_template(SomeModel)` called from inside a Jinja template returns the skeleton.
- [ ] **1.2.3** Implement factory in `archetype/templating/environment.py`:
  - `build_environment() -> jinja2.Environment`.
  - Registers `template` (from task 1.1) and `render_template` (import from `archetype.markdown.renderer`) as globals.

### Task group 1.3 — `resolve()` helper

- [ ] **1.3.1** Tests for `resolve()` (`tests/archetype/templating/test_render.py`):
  - Scalar substitution: `"{{ feature.name }}"` with `feature=obj` produces `obj.name`.
  - Iteration: `"{% for item in feature.items %}- {{ item }}\n{% endfor %}"` produces bullet lines.
  - Structural iteration via `template_fields()`: produces expected heading list.
  - Skeleton rendering via `render_template()`: matches `render_template(Model)` direct call.
  - Missing path raises a `jinja2.UndefinedError` (fail fast).
  - Whitespace behavior: blocks on their own lines don't leave blank lines (confirming `trim_blocks` + `lstrip_blocks`).
- [ ] **1.3.2** Implement helper in `archetype/templating/render.py`:
  - `resolve(template_text: str, **context) -> str`.
  - Calls the factory; renders the template against context; returns the string.

### Task group 1.4 — Public API + module docstring

- [ ] **1.4.1** `archetype/templating/__init__.py`:
  - Re-export `FieldInfo`, `template`, `build_environment`, `resolve`.
  - Module docstring documents the three-form convention and gives a short usage example.
- [ ] **1.4.2** Verify public surface matches exactly (test that nothing else is reachable from `archetype.templating`).

### Task group 1.5 — `AgentAction.instructions_provider` signature change

- [ ] **1.5.1** Update `agent_foundry/src/agent_foundry/primitives/models.py`:
  - `instructions_provider: Callable[[], str]` → `instructions_provider: Callable[[I], str]`.
  - Update docstring.
- [ ] **1.5.2** Update `agent_foundry/src/agent_foundry/orchestration/registry.py`:
  - Find the call site that invokes `instructions_provider()`.
  - Change to `instructions_provider(input_state)`.
  - Update any local docstrings or comments.
- [ ] **1.5.3** Update test call sites to the new signature:
  - `tests/agent_foundry/primitives/test_agent_action_model.py`
  - `tests/agent_foundry/primitives/test_primitive_validators.py`
  - `tests/agent_foundry/orchestration/test_registry.py`
  - `tests/agent_foundry/orchestration/test_container_executor.py`
  - `tests/agent_foundry/orchestration/test_file_path_verification.py`
  - `tests/agent_foundry/compiler/test_agent_action_compiler.py`
  - `tests/agent_foundry/compiler/test_run_pr
Sound right?

✻ Baked for 1m 39s

❯ explain the difference between using template(FeatureDefinition) and using render_template(FeatureDefinition)
imitive_plan.py`
  - `tests/agent_foundry/integration/test_end_to_end.py`
  - Typical shape: `lambda: "instructions"` → `lambda state: "instructions"` (ignore the arg if unused).
- [ ] **1.5.4** Add a signature-specific test in `test_agent_action_model.py`:
  - Instantiating `AgentAction` with a `Callable[[], str]` instructions_provider raises a type validation error.
  - Instantiating with `Callable[[I], str]` succeeds.
  - The provider is invoked with the input state at compile / execution time (verify via mock or recording provider).

### Task group 1.6 — End-to-end integration

- [ ] **1.6.1** Integration test (`tests/archetype/templating/test_integration.py`):
  - Define a small `MarkdownDocument` subclass (e.g., with a few `AsHeading` fields and one nested `MarkdownHeader`).
  - Author a simple instruction template using all three forms (`{{ path }}`, `{% for %}`, `template_fields()`, and `render_template()`).
  - Call `resolve()` and assert the output matches an expected hand-written string.
- [ ] **1.6.2** End-to-end AgentAction test wiring (add to existing `test_end_to_end.py` or a new test):
  - Define an AgentAction whose `instructions_provider` calls `resolve(...)` with state.
  - Verify the provider receives the state and returns the expected rendered output.

## Verification

- [ ] `pdm test-unit` passes in agent-foundry with all new tests.
- [ ] `pdm test-integration` passes (or skips gracefully per project conventions).
- [ ] No new lint or typecheck errors. Pyright strict on the new module.
- [ ] Public API surface of `archetype.templating` matches the documented exports.
- [ ] All existing tests pass after the `instructions_provider` signature change.
- [ ] `jinja2` appears in `pyproject.toml` as a runtime dependency; `pdm.lock` is refreshed.

## Open questions (resolve during implementation)

- **Exact name of the render helper.** I used `resolve()`. Alternatives: `render()`, `render_template_text()`. Finalize when implementing 1.3.2.
- **Whether `FieldInfo` should be a Pydantic model.** I chose `dataclass(frozen=True)` because it's consumed in Jinja and doesn't cross agent boundaries. Confirm during 1.1.2; if downstream needs schema/JSON serialization, promote to BaseModel.
- **Pyright strict compliance** when iterating `model_fields`. Pydantic's `FieldInfo` metadata typing may need some `cast()` or `assert isinstance(...)` to satisfy strict mode. Handle during 1.1.2.

## Change log

- **2026-04-20** — Initial plan. Captures Slice 1 of Phase 2: Jinja-based instruction templating module + `AgentAction.instructions_provider` signature change. Both are Agent Foundry changes with no Archipelago impact.
