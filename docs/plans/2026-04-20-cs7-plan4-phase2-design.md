# CS7 Plan 4 — Phase 2: Designer Agent + Archetype Templating — Design

> **Status:** Design draft from 2026-04-20 brainstorm. Slice 1 built.
> **Date:** 2026-04-20
> **Roadmap:** `docs/plans/2026-04-03-review-feedback-loop-roadmap.md` (CS7 Plan 4)
> **Parent plan:** `docs/plans/2026-04-17-cs7-plan4-archipelago-agents-plan.md`
> **Previous phase:** `docs/plans/2026-04-17-cs7-plan4-phase1-implementation-plan.md` (Phase 1 markdown machinery — shipped)
> **Vision doc:** `docs/archipelago-vision.md` (§3.1 harness-competing-tensions method justifies the agent split)
> **First feature-def to test against:** `examples/features/run-observability.md`

> **Archetype package (OSS-bound):** During Slice 1 implementation, the
> markdown + templating code was extracted into a new top-level `archetype`
> package inside agent-foundry. This package is intended for open-source
> extraction within days — its mission is "Pydantic as source of truth for
> agentic systems," covering typed markdown documents (`archetype.markdown`),
> Jinja-based template resolution with markdown-aware globals
> (`archetype.templating`), and eventually JSON schemas, prompts, and state
> management. Phase 2 references below use the `archetype.*` naming.

## 1. Purpose

Phase 2 delivers the first real product consumer of `AgentAction` — the **Designer agent** — plus the minimum platform machinery it needs: instruction templating, a workspace-bootstrap `FunctionAction`, and a terminal entry point. Together these form the smallest runnable Archipelago system that takes a feature definition and a target codebase and produces a design document.

## 2. Phase 2 scope

**In:**
- Designer agent (`AgentAction`).
- Workspace-bootstrap function action (`FunctionAction`) — creates the Docker volume, clones the target codebase, stages the feature definition.
- Minimal system: `Sequence[workspace_bootstrap → Designer]`.
- Agent Foundry markdown-package extension: Jinja-based instruction templating with `template_fields()` and `render_template()` accessors.
- Agent Foundry `AgentAction` contract change: `instructions_provider` takes state input.
- Terminal entry point: script that reads a feature-definition markdown file and invokes the system.
- First end-to-end test feature: **Run Observability** (at `examples/features/run-observability.md`), targeting the agent-foundry codebase.

**Out (deferred to future phases):**
- Decomposer agent (Cluster B in the tensions lens).
- Planner agent (Cluster C).
- Reviewer, Integrator, Dispatcher agents.
- `CommitAction`, `SubmitPRAction` function actions.
- Design-Critic debate experiment.
- Instruction-appendix auto-generation.
- Semantic (LLM-checked) validation of produced documents.

## 3. Agent architecture — why three agents (Designer / Decomposer / Planner)

Applying §3.1 of the vision doc (harness competing tensions) to the feature-implementation middle layer — the space between a job specification and the implementation kernel — yields three agents. The full worked example lives in the vision doc; the short version:

| Cluster | Mode | Horizon | Functions |
|---|---|---|---|
| **A — Understand + envision** | synthesis | feature | codebase context, design, feature-level AC refinement, feature-level test strategy |
| **B — Slice + order** | pragmatic shipping | change set | decomposition, sequencing, CS-level AC, CS-level test-strategy hints |
| **C — Verify + execute rigor** | discipline | step | step planning, step-level AC, step-level test strategy |

Phase 2 implements **Designer** (Cluster A). **Decomposer** (B) and **Planner** (C) are deferred. Codebase context-gathering is a tool Designer wields (delegating to `Explore` subagent for broad surveys), not a separate Investigator agent.

## 4. Data models

All models are Pydantic `BaseModel` subclasses. Markdown-document models use Phase 1's `archetype.markdown` machinery.

### 4.1 `FeatureDefinition`

Nine fields; list-heavy sections use wrapper `MarkdownHeader` subclasses to preserve `list[str]` typing while satisfying Phase 1's body-order rule.

```python
from typing import Annotated
from pydantic import BaseModel, Field
from archetype.markdown import (
    MarkdownDocument,
    MarkdownHeader,
    AsHeading,
    AsBulletList,
)


class FeatureDefinitionFrontmatter(BaseModel):
    feature_slug: str
    created_at: str                  # ISO timestamp


# Wrappers for heading + bullet-list sections

class UserOutcomes(MarkdownHeader):
    title: str = "User outcomes"
    items: Annotated[list[str], AsBulletList()]


class BusinessOutcomes(MarkdownHeader):
    title: str = "Business outcomes"
    items: Annotated[list[str], AsBulletList()]


class DesiredOutcomes(MarkdownHeader):
    title: str = "Desired outcomes"
    user_outcomes: UserOutcomes
    business_outcomes: BusinessOutcomes


class ScopeBoundaries(MarkdownHeader):
    title: str = "Scope boundaries"
    items: Annotated[list[str], AsBulletList()]


class Assumptions(MarkdownHeader):
    title: str = "Assumptions"
    items: Annotated[list[str], AsBulletList()]


class Dependencies(MarkdownHeader):
    title: str = "Dependencies"
    items: Annotated[list[str], AsBulletList()]


class Constraints(MarkdownHeader):
    title: str = "Constraints"
    items: Annotated[list[str], AsBulletList()]


class AcceptanceCriteria(MarkdownHeader):
    title: str = "Acceptance criteria"
    items: Annotated[list[str], AsBulletList()]


# The document

class FeatureDefinition(MarkdownDocument):
    frontmatter: FeatureDefinitionFrontmatter
    title: str = Field(
        description="Feature name (renders as the top heading of the document)."
    )

    problem_statement: Annotated[str, AsHeading()] = Field(
        description=(
            "The current pain or gap this feature addresses. What's "
            "broken or missing today, before this feature exists?"
        )
    )

    feature_intent: Annotated[str, AsHeading()] = Field(
        description=(
            "Why this feature is the chosen answer to the problem — what "
            "makes this the right solution (vs. other solutions to the "
            "same problem)."
        )
    )

    desired_outcomes: DesiredOutcomes = Field(
        description=(
            "What good looks like after the feature ships, split into "
            "outcomes for users and outcomes for the business."
        )
    )

    scope_boundaries: ScopeBoundaries = Field(
        description=(
            "Explicit statements of what is out of scope. What this "
            "feature does NOT try to do."
        )
    )

    assumptions: Assumptions = Field(
        description=(
            "Truth-claims about the world the design will rest on. "
            "Beliefs we're betting on without having verified."
        )
    )

    dependencies: Dependencies = Field(
        description=(
            "External things this feature relies on — services, prior "
            "changes, deployed infrastructure."
        )
    )

    constraints: Constraints = Field(
        description=(
            "Hard limits the solution must respect: must-do's, "
            "must-not-do's, non-functional requirements."
        )
    )

    acceptance_criteria: AcceptanceCriteria = Field(
        description=(
            "Concrete, testable statements of 'done.' What must be true "
            "when this feature is complete."
        )
    )
```

Design notes:
- All wrapper classes have default `title` values so construction is `ScopeBoundaries(items=[...])` — users don't pass title.
- All body fields are heading-introducing (AsHeading or nested `MarkdownHeader`), so body-order rule is trivially satisfied.
- Descriptions live on the top-level Field declarations; wrapper `items` fields have no description (template_fields() surfaces the outer field's description).

### 4.2 `DesignDocument`

Eight top-level sections; all `Annotated[str, AsHeading()]` — free markdown body per section, matching the "keep it light" principle. Designer uses H3s internally as it sees fit.

```python
from typing import Annotated
from pydantic import BaseModel, Field
from archetype.markdown import (
    MarkdownDocument,
    AsHeading,
    TextTemplate,
)


class DesignDocumentFrontmatter(BaseModel):
    feature_slug: str
    feature_name: str
    feature_definition_path: str     # "/workspace/documents/feature_definition.md"
    codebase_ref: str                # as passed to bootstrap
    codebase_resolved_sha: str       # what the run actually saw
    generated_at: str                # ISO timestamp


class DesignDocument(MarkdownDocument):
    frontmatter: DesignDocumentFrontmatter
    title: Annotated[str, TextTemplate("Design for {value}")]

    summary: Annotated[str, AsHeading()] = Field(
        description="A one-paragraph framing of the proposed design."
    )

    current_state_context: Annotated[str, AsHeading()] = Field(
        description=(
            "Relevant existing codebase state found during investigation. "
            "Include only what's load-bearing for understanding the proposal. "
            "Do not summarize the entire codebase."
        )
    )

    components: Annotated[str, AsHeading()] = Field(
        description=(
            "The components — new or modified — that make up the design. "
            "Name each one, state its purpose, and what concern it owns."
        )
    )

    architecture: Annotated[str, AsHeading()] = Field(
        description=(
            "How the components interact: interfaces between them, control "
            "flow (orchestration and sequencing), and data flow (what moves, "
            "in what shape, from where to where)."
        )
    )

    acceptance_criteria: Annotated[str, AsHeading()] = Field(
        description=(
            "Feature-level acceptance criteria refined from the feature "
            "definition. Concrete, testable statements of what must be "
            "true when the feature is complete."
        )
    )

    test_strategy: Annotated[str, AsHeading()] = Field(
        description=(
            "Feature-level test approach: what to test, at what level "
            "(unit, integration, end-to-end), what fixtures or harnesses "
            "are needed."
        )
    )

    risks_and_open_items: Annotated[str, AsHeading()] = Field(
        description=(
            "Concerns and uncertainties the design leaves open: bets made, "
            "decisions deferred, areas where later stages will need judgment."
        )
    )

    resolved_assumptions: Annotated[str, AsHeading()] = Field(
        description=(
            "Disposition of each assumption in the feature definition — "
            "accepted, refined, promoted to constraint, or contradicted — "
            "plus any new assumptions introduced during design."
        )
    )
```

Design notes:
- `title` uses `TextTemplate("Design for {value}")` so H1 reads "# Design for Authentication" (disambiguates from the feature definition).
- Frontmatter records feature identity + codebase snapshot + generation time for traceability.

### 4.3 `DesignerOutput` (structured envelope payload)

Minimal. Just the path.

```python
class DesignerOutput(BaseModel):
    design_document: AgentFilePath   # "/workspace/documents/design.md"
```

### 4.4 `CodebaseSource`

```python
class CodebaseSource(BaseModel):
    repo_url: str       # e.g. "https://github.com/730alchemy/agent-foundry.git"
    ref: str            # commit SHA, branch, or tag
```

Auth via ambient credentials (SSH agent / env token) for v1.

### 4.5 `WorkspaceHandle`

```python
class WorkspaceHandle(BaseModel):
    volume_name: str
    root: str                        # "/workspace"
    documents_path: str              # "/workspace/documents"
    codebase_path: str               # "/workspace/codebase"
    feature_definition_path: str     # "/workspace/documents/feature_definition.md"
    codebase_source_ref: str         # as passed in
    codebase_resolved_sha: str       # actual commit the run sees
```

## 5. Workspace-bootstrap function action

```python
class BootstrapInput(BaseModel):
    feature_definition: FeatureDefinition
    codebase_source: CodebaseSource


class BootstrapOutput(BaseModel):
    workspace_handle: WorkspaceHandle


workspace_bootstrap = FunctionAction[BootstrapInput, BootstrapOutput](
    function=bootstrap_fn,
)
```

Steps `bootstrap_fn` performs:

1. Create a Docker volume with a slug-based name (e.g. `archipelago-ws-{feature_slug}-{timestamp}`).
2. Create `/workspace/documents/` and `/workspace/codebase/` inside the volume.
3. `git clone <repo_url>` into `/workspace/codebase/`; `git checkout <ref>`.
4. Resolve the ref to a commit SHA; record both in the returned `WorkspaceHandle`.
5. Keep `.git/` intact (Designer benefits from `git log` / `git blame` for investigation).
6. `chmod -R 555` on `/workspace/codebase/` — codebase is read-only.
7. Render the `FeatureDefinition` instance to markdown via Phase 1's `render_instance()`; write to `/workspace/documents/feature_definition.md`; `chmod 444`.
8. Return the `WorkspaceHandle`.

**Volume lifecycle:** persists after the run for inspection. Cleanup is a separate concern (possibly a future `workspace_cleanup` function action; not in Phase 2 scope).

## 6. Designer agent

### 6.1 AgentAction configuration

```python
class DesignerInput(BaseModel):
    workspace_handle: WorkspaceHandle
    feature_definition: FeatureDefinition


class DesignerSlice(BaseModel):
    designer_output: DesignerOutput


designer = AgentAction[DesignerInput, DesignerSlice](
    name="designer",
    prompt_builder=designer_prompt_builder,
    instructions_provider=designer_instructions_provider,
    executor=run_agent_in_container,
    reuse_policy=ContainerReusePolicy.REUSE_NEW_SESSION,
    timeout_seconds=1800,              # 30 minutes
    visible_dirs=["/workspace"],
    writable_dirs=["/workspace/documents"],
    skip_permissions=True,
)
```

Read-only protection of inputs rests on chmod bits set by bootstrap (`feature_definition.md` → 444, `codebase/` tree → 555). Designer can write freely in `/workspace/documents/` but can't modify the locked files.

### 6.2 Callables

```python
def designer_prompt_builder(state: DesignerInput) -> str:
    return (
        f"The workspace is mounted at {state.workspace_handle.root}. "
        f"Follow your instructions to produce the design document."
    )


def designer_instructions_provider(state: DesignerInput) -> str:
    template_text = _load_designer_template()   # bundled with the code
    env = Environment(trim_blocks=True, lstrip_blocks=True, autoescape=False)
    env.globals['template'] = template_accessor
    env.globals['render_template'] = render_template   # lifted from Phase 1
    return env.from_string(template_text).render(feature=state.feature_definition)
```

The instructions template file lives in the repo (e.g. `src/archipelago/agents/designer/instructions_template.md`); `_load_designer_template()` reads it at container-start.

### 6.3 Instructions template (Jinja-resolved, six sections)

```markdown
# Designer

You are the Designer for Archipelago — an autonomous software
engineering system. Your job is to produce a design document for
a given feature, informed by the feature definition and the target
codebase. Your document is the input to the three downstream
stages: decomposition into change sets, planning of TDD steps,
and implementation. Write for them.

## Your input

Read the feature definition at `/workspace/documents/feature_definition.md`.

The feature definition has these sections:
{% for field in template_fields(FeatureDefinition) %}
- **{{ field.heading }}** — {{ field.description }}
{% endfor %}

This run, you are designing for the feature **{{ feature.title }}**.

**Problem statement:** {{ feature.problem_statement }}

**Feature intent:** {{ feature.feature_intent }}

**User outcomes:**
{% for outcome in feature.desired_outcomes.user_outcomes.items %}
- {{ outcome }}
{% endfor %}

**Business outcomes:**
{% for outcome in feature.desired_outcomes.business_outcomes.items %}
- {{ outcome }}
{% endfor %}

**Scope boundaries:**
{% for item in feature.scope_boundaries.items %}
- {{ item }}
{% endfor %}

**Assumptions:**
{% for item in feature.assumptions.items %}
- {{ item }}
{% endfor %}

**Dependencies:**
{% for item in feature.dependencies.items %}
- {{ item }}
{% endfor %}

**Constraints:**
{% for item in feature.constraints.items %}
- {{ item }}
{% endfor %}

**Acceptance criteria:**
{% for item in feature.acceptance_criteria.items %}
- {{ item }}
{% endfor %}

The target codebase is mounted read-only at `/workspace/codebase/`.

## Your output

Write the design document at `/workspace/documents/design.md`. It must
match this structure exactly:

{{ render_template(DesignDocument) }}

The placeholder comments describe what each section is for.

## How to investigate

Build an understanding of the current state relevant to this feature
before drafting the design.

**Delegate broad surveys.** When you want to explore a subsystem,
discover patterns across many files, or map relationships between
modules, use an Explore subagent via the Agent tool and consume
its summary. Do not read many files directly — delegation keeps
your own context focused on synthesis.

Use Read, Grep, Glob, and LSP tools directly only for narrow,
targeted lookups — confirming a function signature, reading one
specific file you already know matters, checking a single symbol's
references.

As a starter for what to investigate, consider:
- Package structure around areas this feature touches.
- Public interfaces and conventions in those areas.
- Patterns already established for similar concerns.
- Test conventions and fixtures available.

Use judgment. Skip items that don't apply; add investigations the
list doesn't cover.

When you have enough context, write a short investigation summary
(what you learned; what's still uncertain) before drafting. Do not
begin the design before this checkpoint.

## How to design

Design for the target state — the ideal shape of the feature once
complete. Do not design for incremental shippability; how the work
is sliced into change sets is handled downstream.

### Design principles

Good design produces software that is **easy to understand, easy to
change, easy to test and debug, and easy to extend**. These are the
qualities implementers, reviewers, debuggers, and future changers
will depend on — and the qualities a future Critic agent will judge
your design against.

Modularity is the primary means to those ends. A system properly
modularized is comprehensible, testable, and safe to change. The
principles below are either constituents of good modularity, or
consequences that good modularity enables, or disciplines that keep
modular designs honest.

**Modularity done well rests on:**

- **Separation of concerns.** Each component owns one concern;
  unrelated concerns live in different components.
- **Cohesion.** Pieces within a component belong together; they
  serve its single concern.
- **Loose coupling.** Components depend on stable interfaces, not
  each other's internals. A change inside one component should
  not ripple.
- **Abstraction and information hiding.** Interfaces expose what
  callers need; implementation detail stays hidden behind them.

**What modularity done well enables:**

- **Composition over inheritance.** Well-modularized pieces combine
  through composition. Inheritance creates tight coupling between
  base and derived; composition keeps seams clean.
- **Explicit dependencies.** A component's dependencies appear in
  its signature — no hidden globals, no implicit reads. Explicit
  dependencies are what make collaboration injectable.
- **Testability.** Injectable collaborators, pure functions where
  practical, deterministic behavior where the domain allows.
  Well-modularized code is testable almost by definition.

**Support disciplines:**

- **Strong typing.** Use the target language's type system to make
  design contracts visible and enforceable. Boundary types,
  discriminated unions, and named enumerations (rather than raw
  strings or dicts) turn contracts into navigable code that resists
  drift.
- **Observability.** Design so runtime behavior is inspectable:
  meaningful names, structured events at boundaries, errors that
  carry context. Good module boundaries are natural observation
  points.

### Avoid over-engineering

Do not add abstractions, flags, extension points, or plumbing for
hypothetical future needs. Design for the current target state;
generalize later when a second real use case emerges. Don't
premature-optimize — design for clarity first, tune when a real
bottleneck is found.

### Follow project-specific conventions

Read `/workspace/codebase/CLAUDE.md` early in investigation (if
present) for project-specific conventions — type conventions,
framework choices, naming patterns — and respect them. If your
design would require changing a convention, surface that in
`risks_and_open_items` rather than making the change silently.

### Respect the feature's boundaries

Your design must stay within the feature's declared scope boundaries,
satisfy every declared constraint, and be consistent with its
declared dependencies. If any of these are in tension with a design
choice, pull back the design or surface the conflict in
`risks_and_open_items`.

### Resolve every input assumption explicitly

For every assumption in the feature definition, decide its
disposition (accepted, refined, promoted to constraint, or
contradicted) and record it in `resolved_assumptions`. Record any
new assumptions you introduce during design in the same section.

### Surface uncertainty

Anything the design leaves uncertain — bets you're making, decisions
you deferred, places where later stages will need judgment — belongs
in `risks_and_open_items`.

### Clarification vs. risk

If a design decision materially depends on information you lack, and
no reasonable bet can substitute, emit `clarification_needed` with
the specific question. Otherwise, make the bet and record it as a
risk.

### Completeness

Fill every section of the design document meaningfully. If a section
truly doesn't apply, write "none" with reasoning rather than leaving
it empty.

## Output protocol

When you complete the design, emit a **success** outcome with:
- `design_document`: path to the design doc
  (`/workspace/documents/design.md`).

Before emitting success, verify the design doc exists at the expected
path and has every required section filled meaningfully.

If you need specific information that a reasonable bet cannot
substitute for, emit **clarification_needed** with:
- `question`: the specific question to answer.
- `context`: enough background that the answerer can respond without
  re-reading the whole design.

If you need a permission you don't currently have (network access to
an external resource, a tool not currently available), emit
**permission_needed** with:
- `action`: what you want to do.
- `reason`: why it's needed for the design.

If you hit an unrecoverable error — the workspace is broken, inputs
are malformed, tools repeatedly fail — emit **failed** with:
- `reason`: what went wrong.
```

## 7. Agent Foundry platform changes

Three items, all small.

### 7.1 `AgentAction.instructions_provider` signature change

```python
# Before
instructions_provider: Callable[[], str]

# After
instructions_provider: Callable[[I], str]
```

Breaking change, but the blast radius is narrow — Agent Foundry has no external consumers yet. Matches the pattern of `prompt_builder`. Agents that don't need state for instructions ignore the argument.

### 7.2 Instruction-templating module

New: `archetype.templating` (or similar — name TBD during planning).

Provides:
- A Jinja `Environment` factory with `trim_blocks=True`, `lstrip_blocks=True`, `autoescape=False`.
- The `template_fields()` accessor — returns an iterable of `(heading, description)` pairs for a `MarkdownHeader` subclass's top-level heading fields.
- A helper that composes the environment, registers `template` and `render_template` as globals, and renders a template string against a context.

Convention (documented, enforced by review):
- In instruction templates, use only `{{ path }}`, `{% for x in path %}...{% endfor %}`, and the two registered globals.
- No filters, conditionals, macros, includes, or inheritance.

### 7.3 Expose `render_template` as a Jinja global

`render_template` exists in Phase 1. Phase 2 adds its registration in the Jinja environment set up by 7.2 — no new code, just wiring.

## 8. Sequence wiring

```python
class Phase2State(BaseModel):
    feature_definition: FeatureDefinition
    codebase_source: CodebaseSource
    workspace_handle: WorkspaceHandle | None = None
    designer_output: DesignerOutput | None = None


phase_2_system = Sequence[Phase2State, Phase2State](
    steps=[workspace_bootstrap, designer],
)
```

The Sequence accumulates state: `workspace_bootstrap` writes `workspace_handle`; `designer` reads `workspace_handle` (and `feature_definition`) and writes `designer_output`.

## 9. Terminal invocation

A single script — `scripts/run_phase2.py` (or similar) — parses CLI flags and invokes the system.

Invocation:
```bash
python scripts/run_phase2.py \
  --feature examples/features/run-observability.md \
  --repo https://github.com/730alchemy/agent-foundry.git \
  --ref main
```

Script flow:
1. Read the feature-definition markdown file.
2. Parse via Phase 1's `validate_markdown(text, FeatureDefinition)` → instance.
3. Construct `CodebaseSource(repo_url, ref)` from CLI args.
4. Call `run_phase2(feature_definition=instance, codebase_source=source)`.

`run_phase2(...)` builds and executes the `Sequence`. Exit code reflects terminal outcome.

## 10. First end-to-end test

**Feature:** Run Observability (per-agent-turn metrics capture, JSONL persistence behind an abstraction, streamed emission, per-run summary helper).

**Feature-definition file:** `examples/features/run-observability.md`.

**Target codebase:** agent-foundry (`https://github.com/730alchemy/agent-foundry.git`, ref `main`).

**Expected flow:** bootstrap creates the volume, clones agent-foundry, stages the feature definition. Designer reads the feature definition (via Jinja-inlined content in its instructions) and investigates the agent-foundry codebase to produce a design document at `/workspace/documents/design.md`. Script exits when Designer emits `success`; the workspace volume remains for human inspection.

**Success criteria:** the design document exists, has all eight sections filled meaningfully, and proposes a coherent design for Run Observability that respects the declared constraints and resolves the declared assumptions.

## 11. Open items (to resolve during or after implementation)

- **Physical location of the Designer instructions template.** Proposed: `src/archipelago/agents/designer/instructions_template.md`. Finalize in plan.
- **Token / tool-call / subagent metric extraction.** The feature-def assumes Claude Code's stream-json exposes these; verify during implementation and adjust if the shape doesn't match.
- **Volume-name slug collisions** if the same feature is run multiple times in sequence. Name includes a timestamp; verify uniqueness properties hold.
- **Image that the Designer container runs.** Phase 3 base image should be sufficient; confirm during plan.

## 12. Deferred / future

- **Decomposer** (Cluster B) and **Planner** (Cluster C) agents — future phases of CS7 Plan 4.
- **Design-Critic debate experiment** — its own future phase (likely CS7 Plan 5 or later). Designer v1 is built with hooks for it: output is a complete markdown artifact, input is reproducible, workspace layout leaves room for `design_v{N}.md`.
- **Instruction-appendix auto-generation** — ADR gap #2 partially addressed by Phase 2's templating; full auto-appendix deferred.
- **Semantic validation** of produced documents (LLM-checked "does content satisfy field description") — deferred.

## 13. Change log

- **2026-04-20** — Initial design captured from 2026-04-20 brainstorm. Covers: three-agent architecture derived via the tensions method; FeatureDefinition and DesignDocument Pydantic models; Designer instructions (hand-authored content with Jinja-templated input/output references); workspace-bootstrap function action with git-ref-only codebase source; single-mount `/workspace` layout with `codebase/` and `documents/` subfolders; Sequence wiring; AgentAction `instructions_provider` signature change; terminal entry point with feature-def markdown CLI flag; run-observability as first E2E feature; agent-foundry as target codebase.
