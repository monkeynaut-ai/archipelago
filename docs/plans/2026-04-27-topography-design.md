# Topography Design — Archipelago v0.1 working session

> **Status:** Working draft, 2026-04-27. Expected to iterate.
> **Stage 2 roadmap:** `docs/plans/2026-04-27-stage2-roadmap.md`
> **Vision:** `docs/product/archipelago-vision.md` (§3.1 tensions, §3.2 workspace-mediated, §3.3 single source of truth, §3.4 experimentation-first)
> **Predecessor (historical, Designer-side):** `docs/plans/stage1/2026-04-20-cs7-plan4-phase2-design.md`

## 1. Purpose and method shift

Stage 1 went deep on a single vertical slice (Designer): full Pydantic model set, full Jinja-templated instruction template, full investigation/drafting discipline, end-to-end smoke. That depth was right for proving the platform machinery on a real agent.

This iteration inverts that. The goal is **system topography** — how the working session's primitives compose, what state flows through them, what artifacts live in the workspace, what the loops iterate over. Agent internals (instructions, prompts, deep data models) stay *minimal* — just enough to make the topology runnable end-to-end with stub-quality outputs. We thicken each agent in later iterations.

This is horizontal-first by design. We learn more from a thin pipeline that runs end-to-end than from one perfect agent in isolation.

## 2. Scope

**In:**
- Renames in docs only: Decomposer → **Change Set Planner**, Planner → **TDD Planner**.
- Pipeline topology: composed `Sequence` containing `workspace_bootstrap`, `designer`, `change_set_planner`, an outer `Loop` over change sets, and an inner `Loop` over change set steps.
- Two new agents (`change_set_planner`, `tdd_planner`) declared as `AgentAction` primitives, with minimal Pydantic input/output models, minimal `archetype.markdown` document types, and short placeholder instruction templates.
- Two `FunctionAction`s that print the current change set / step name to stdout.
- Workspace layout extension: per-change-set sub-workspace under `/workspace/documents/change-sets/{slug}/`.
- State model: a single `FullPipelineState` carrying every field the pipeline produces or consumes.
- Composition decision: keep `design_pipeline` alongside the new `full_pipeline` for now; both reference the same constituent primitives.

**Out (deferred to later iterations and other Stage 2 work items):**
- Test Agent, Implementer, Reviewer, Dispatcher, Integrator agents.
- `CommitAction`, `SubmitPRAction`.
- Review feedback loop topology (Reviewer → Dispatcher → Integrator routing back into the inner loop).
- Gates and human escalation paths.
- Run summary aggregation, structured run events.
- Rich agent instructions, prompts, schema-driven JSON outputs beyond the bare minimum.
- **Tests.** Per the fluid-work decision (§13), no Archipelago unit or integration tests are added in this iteration.

## 3. Renames (docs only)

| Old name | New name | Cluster (vision §3.1) |
|---|---|---|
| Decomposer | **Change Set Planner** | B — slice + order |
| Planner | **TDD Planner** | C — verify + execute rigor |

Source-level identifiers (modules, classes, primitive names) are introduced fresh under the new names; no renaming of existing source is required (these agents don't exist yet). Roadmap docs and the vision doc's agent roster are updated separately.

## 4. Pipeline topology

```
workspace_bootstrap
  └─▶ designer
        └─▶ change_set_planner                          ← NEW
              └─▶ Loop over change sets:                ← NEW (outer)
                    log_change_set_name                 ← NEW (FunctionAction)
                    tdd_planner                         ← NEW
                    └─▶ Loop over change set steps:     ← NEW (inner)
                          log_change_set_step_name      ← NEW (FunctionAction)
```

In primitives, with each Loop and each body Sequence narrowed to its own typed input/output (see §5):

```python
full_pipeline = Sequence[FullPipelineState, FullPipelineState](steps=[
    workspace_bootstrap,
    designer,
    change_set_planner,
    Loop[ChangeSetsLoopState, ChangeSetsLoopState](
        over=lambda s: ChangeSetsDocument.from_markdown_file(
            s.change_set_planner_output.change_sets_document
        ).change_sets,
        item_key="current_change_set",
        body=Sequence[ChangeSetProcessingState, ChangeSetProcessingState](steps=[
            prepare_change_set_workspace,
            log_change_set_name,
            tdd_planner,
            Loop[StepsLoopState, StepsLoopState](
                over=lambda s: StepsDocument.from_markdown_file(
                    s.tdd_planner_output.steps_document
                ).steps,
                item_key="current_step",
                body=Sequence[StepProcessingState, StepProcessingState](steps=[
                    log_change_set_step_name,
                ]),
            ),
        ]),
    ),
])
```

Each `Loop`'s `over` reads from its own typed input state and parses the markdown document via `archetype.markdown`. The outer Loop operates on `ChangeSetsLoopState`; the inner Loop operates on `StepsLoopState`. Each Loop's body is a Sequence over the per-iteration scope — `ChangeSetProcessingState` for the outer body, `StepProcessingState` for the inner. The current item is bound into the body's state via Agent Foundry's `item_key` mechanism. This iteration does not introduce a Loop helper that abstracts the markdown-parse step — it stays inline.

## 5. State model — narrowed scope per primitive

Each primitive declares its own typed input/output reflecting only what it consumes and produces. There's no requirement that a child primitive's state match its parent's — Sequence steps already have varied input types as slices of the Sequence's state, and the same applies to nested Loops and to Sequences inside Loop bodies. The platform projects between any pair of nested primitives via field-level slicing (the same mechanism that handles agent input slicing inside a Sequence).

For the working session pipeline, this gives us four scoped types beyond `FullPipelineState`:

```
Sequence[FullPipelineState]
  └─▶ Loop[ChangeSetsLoopState]
        └─▶ Sequence[ChangeSetProcessingState]
              └─▶ Loop[StepsLoopState]
                    └─▶ Sequence[StepProcessingState]
```

Each primitive's state contains only what that primitive needs: a Loop's state has the field its `over` lambda reads plus the body's inheritable context; a body Sequence's state has the inherited context plus the bound iteration item plus per-iteration write slots. Per-iteration scopes are independent — naturally parallelism-safe and minimally coupled.

Agent Foundry's existing primitive types support this without changes — `Loop[I, O]` is generic, `body: Primitive` is unconstrained on inner shape, and field-level slicing handles projection across nesting boundaries.

### 5.1 `FullPipelineState` — pre-loop fields

```python
class FullPipelineState(BaseModel):
    # Provided at pipeline start
    feature_definition: FeatureDefinition
    codebase_source: CodebaseSource

    # Workspace bootstrap
    workspace_handle: WorkspaceHandle | None = None

    # Designer
    designer_output: DesignerOutput | None = None

    # Change Set Planner
    change_set_planner_output: ChangeSetPlannerOutput | None = None
```

`tdd_planner_output` is *not* a `FullPipelineState` field — it lives inside `ChangeSetProcessingState`.

### 5.2 `ChangeSetsLoopState` — outer Loop's view

What the outer Loop reads (for `over`) plus what the body needs to inherit.

```python
class ChangeSetsLoopState(BaseModel):
    # Read by `over` to extract the change-set list:
    change_set_planner_output: ChangeSetPlannerOutput
    # Inherited into ChangeSetProcessingState:
    workspace_handle: WorkspaceHandle
    designer_output: DesignerOutput
    feature_definition: FeatureDefinition
```

Projected from `FullPipelineState` by the platform's field-level slicing.

### 5.3 `ChangeSetProcessingState` — outer body Sequence's view

What each outer-loop iteration's body sees: the bound iteration item, the inherited context, and slots for per-iteration writes.

```python
class ChangeSetProcessingState(BaseModel):
    # Bound by outer Loop's item_key:
    current_change_set: ChangeSetRef

    # Inherited from ChangeSetsLoopState:
    workspace_handle: WorkspaceHandle
    designer_output: DesignerOutput
    feature_definition: FeatureDefinition

    # Written by body steps:
    change_set_workspace_path: str | None = None
    tdd_planner_output: TDDPlannerOutput | None = None
```

Agent input slices (e.g., `ChangeSetPlannerInput` with `design_document_path: AgentFilePath`) are extracted from this state by the same slicing mechanism — the platform handles nested-field access (`designer_output.design_document` → `design_document_path`) where needed.

### 5.4 `StepsLoopState` — inner Loop's view

```python
class StepsLoopState(BaseModel):
    # Read by `over` to extract the steps:
    tdd_planner_output: TDDPlannerOutput
    # Inherited into StepProcessingState:
    change_set_workspace_path: str
```

### 5.5 `StepProcessingState` — inner body Sequence's view

```python
class StepProcessingState(BaseModel):
    # Bound by inner Loop's item_key:
    current_step: StepRef

    # Inherited from StepsLoopState:
    change_set_workspace_path: str
```

Future iterations widen this as Test Agent / Implementer / CommitAction need design context, current change set, etc.

### 5.6 Aggregation back to `FullPipelineState`

For this iteration of work, outer-loop iterations do **not** aggregate back into `FullPipelineState`. Each iteration writes its artifacts to the per-CS workspace; downstream consumers read those artifacts from `/workspace/documents/change-sets/{slug}/...` directly. If a later iteration needs an in-memory aggregate (e.g., a data-driven Run Summary), `FullPipelineState` grows a `dict[slug, ...]` slot at that point. See §14e.

## 6. Document set and workspace layout

```
/workspace/
    documents/
        feature_definition.md           (provided by workspace_bootstrap; read-only after)
        design.md                       (Designer output; read-only after written)
        change-sets.md                  (Change Set Planner output; read-only after written)
        change-sets/
            {slug-1}/                   (one per change set, created per outer-loop iteration)
                steps.md                (TDD Planner output for this CS)
                ... future: implementation/, review.md, etc.
            {slug-2}/
                steps.md
            ...
    codebase/                           (read-only working tree, .git/ writable)
```

**Who creates each path:**
- `workspace_bootstrap` creates `/workspace/documents/` and `/workspace/codebase/`, writes `feature_definition.md`, and creates the empty `change-sets/` directory.
- `designer` writes `design.md`.
- `change_set_planner` writes `change-sets.md`.
- The outer-loop body (before `tdd_planner` runs) creates `/workspace/documents/change-sets/{slug}/`. **Open question §14a**: is this a small `FunctionAction` step at the top of the loop body, or does `tdd_planner`'s pre-execution machinery handle it? This iteration assumes a small `FunctionAction` for clarity; revisit if it adds visible ceremony.
- `tdd_planner` writes `steps.md` inside the per-CS directory.

## 7. Data flow and I/O boundaries

### 7.1 Path-threading principle

> **No implicit workspace contracts.** Document paths are typed `AgentFilePath` values threaded through each agent's input/output models. Agents receive paths telling them exactly which file to read and write; instruction templates inject those paths via Jinja. No agent hardcodes `/workspace/documents/X.md`.

**Why.** Parallel branches of work (e.g., parallel processing of multiple change sets in a future iteration) carry different paths through the same agent action without collision. Renaming a document is a state-model change, not a multi-agent instruction-template edit. Slug-based per-iteration paths fall out trivially — the slug is data, not a template constant.

**Caveat.** Designer (shipped) currently hardcodes `/workspace/documents/feature_definition.md` and `/workspace/documents/design.md` in its instruction template. That is now formally a small design debt against this principle — not urgent (Designer works), but new agents start clean. Cleanup belongs in a later iteration.

### 7.2 What each agent reads and writes

| Agent | Reads | Writes |
|---|---|---|
| `workspace_bootstrap` (existing) | `feature_definition`, `codebase_source` from state | `feature_definition.md`, `codebase/`, `change-sets/` (empty) |
| `designer` (existing) | `feature_definition.md`, `codebase/` | `design.md` |
| `change_set_planner` | `design.md` (path passed in) | `change-sets.md` (path passed in) |
| `tdd_planner` | `design.md` (path passed in), current `ChangeSetRef`, current change-set workspace path | `steps.md` (path passed in) |
| `log_change_set_name` | current `ChangeSetRef` | stdout |
| `log_change_set_step_name` | current `StepRef` | stdout |

## 8. Change Set Planner — minimal definition

**Cluster:** B (slice + order). Reads the design, breaks it into a sequence of change sets that ship independently.

### 8.1 Data model

```python
class ChangeSetRef(BaseModel):
    name: str        # human-readable name
    slug: str        # filesystem-safe; used for /workspace/documents/change-sets/{slug}/
    summary: str     # one-paragraph statement of what this change set delivers

class ChangeSetsDocument(MarkdownDocument):
    frontmatter: ChangeSetsDocumentFrontmatter   # feature_slug, generated_at
    title: Annotated[str, TextTemplate("Change sets for {value}")]
    change_sets: ListSection[ChangeSetRef]       # archetype.markdown wrapper TBD
```

The `ListSection` shape (what `archetype.markdown` machinery exposes for "a heading with a list of structured items beneath it") is one of two open machinery questions for this iteration — see §14b.

### 8.2 Input / Output

```python
class ChangeSetPlannerInput(BaseModel):
    workspace_handle: WorkspaceHandle
    design_document_path: AgentFilePath          # /workspace/documents/design.md
    change_sets_document_path: AgentFilePath     # /workspace/documents/change-sets.md (where to write)
    feature_definition: FeatureDefinition        # for instruction-template injection

class ChangeSetPlannerOutput(BaseModel):
    change_sets_document: AgentFilePath          # echoes the input path
```

Path-threading per §7.1: paths are inputs, the agent writes to where it's told.

### 8.3 Configuration

```python
change_set_planner = AgentAction[ChangeSetPlannerInput, ChangeSetPlannerSlice](
    name="change_set_planner",
    prompt_builder=change_set_planner_prompt_builder,
    instructions_provider=change_set_planner_instructions_provider,
    executor=run_agent_in_container,
    reuse_policy=ContainerReusePolicy.REUSE_NEW_SESSION,
    timeout_seconds=1800,
    visible_dirs=["/workspace"],
    writable_dirs=["/workspace/documents"],
    skip_permissions=True,
)
```

Mirrors Designer's container-execution shape. Cluster B's API/SDK execution path (cheaper, no codebase access needed) is captured in the Stage 2 roadmap under platform extensions.

### 8.4 Instructions (placeholder, intent only)

This iteration's instruction template is intentionally short:
- "You are the Change Set Planner. Read the design document at `{{ design_document_path }}`."
- "Produce an ordered list of change sets that, taken together, deliver the feature. Each change set should be a self-contained slice that can ship independently. For each, provide a name, a slug, and a one-paragraph summary."
- "Write the result to `{{ change_sets_document_path }}` matching the schema below."
- `{{ render_template(ChangeSetsDocument) }}`

No CS-level acceptance criteria, no test-strategy hints, no investigation discipline, no clarification protocol — those land in later iterations. The agent need only produce a structurally valid `ChangeSetsDocument` with at least one `ChangeSetRef` so the outer loop has something to iterate over.

## 9. TDD Planner — minimal definition

**Cluster:** C (verify + execute rigor). Reads the design and a single change set; produces an ordered list of TDD steps for that change set.

### 9.1 Data model

```python
class StepRef(BaseModel):
    name: str        # human-readable name
    slug: str        # filesystem-safe
    summary: str     # one-paragraph description of what this step does

class StepsDocument(MarkdownDocument):
    frontmatter: StepsDocumentFrontmatter   # change_set_slug, generated_at
    title: Annotated[str, TextTemplate("Steps for change set {value}")]
    steps: ListSection[StepRef]
```

### 9.2 Input / Output

```python
class TDDPlannerInput(BaseModel):
    workspace_handle: WorkspaceHandle
    design_document_path: AgentFilePath          # /workspace/documents/design.md
    change_set_ref: ChangeSetRef                 # current outer-loop item
    change_set_workspace_path: str               # /workspace/documents/change-sets/{slug}/
    steps_document_path: AgentFilePath           # {change_set_workspace_path}/steps.md (where to write)
    feature_definition: FeatureDefinition        # for instruction-template injection

class TDDPlannerOutput(BaseModel):
    steps_document: AgentFilePath                # echoes the input path
```

The current `ChangeSetRef` and per-CS workspace path are bound into the input by the outer loop's body (see §10).

### 9.3 Configuration

Same shape as Change Set Planner — container execution, REUSE_NEW_SESSION, timeout 1800, writable `/workspace/documents`.

### 9.4 Instructions (placeholder, intent only)

- "You are the TDD Planner. Read the design at `{{ design_document_path }}` and focus on change set `{{ change_set_ref.name }}` (`{{ change_set_ref.summary }}`)."
- "Produce an ordered list of TDD steps that, executed in sequence, deliver this change set. Each step should be a coherent red-green-refactor unit with a name, slug, and one-paragraph summary."
- "Write the result to `{{ steps_document_path }}` matching the schema below."
- `{{ render_template(StepsDocument) }}`

No step-level acceptance criteria, no test-strategy detail, no interface specs — minimal for this iteration.

## 10. Function actions

### 10.1 `log_change_set_name`

```python
class LogChangeSetNameInput(BaseModel):
    change_set_ref: ChangeSetRef     # current outer-loop item

class LogChangeSetNameOutput(BaseModel):
    pass

def log_change_set_name_fn(state: LogChangeSetNameInput) -> LogChangeSetNameOutput:
    print(f"[change set] {state.change_set_ref.name} ({state.change_set_ref.slug})")
    return LogChangeSetNameOutput()

log_change_set_name = FunctionAction[LogChangeSetNameInput, LogChangeSetNameOutput](
    function=log_change_set_name_fn,
)
```

### 10.2 `log_change_set_step_name`

Identical shape, swapping `ChangeSetRef` for `StepRef`.

```python
def log_change_set_step_name_fn(state: LogChangeSetStepNameInput) -> LogChangeSetStepNameOutput:
    print(f"[step] {state.step_ref.name} ({state.step_ref.slug})")
    return LogChangeSetStepNameOutput()
```

### 10.3 (Optional) `prepare_change_set_workspace`

If §6's open question lands on "small FunctionAction at top of outer loop body," it's:

```python
def prepare_change_set_workspace_fn(state: PrepareChangeSetWorkspaceInput) -> PrepareChangeSetWorkspaceOutput:
    cs_path = Path(state.workspace_handle.documents_path) / "change-sets" / state.change_set_ref.slug
    cs_path.mkdir(parents=True, exist_ok=True)
    return PrepareChangeSetWorkspaceOutput(change_set_workspace_path=str(cs_path))
```

This iteration includes this as a third FunctionAction unless we find it unnecessary in implementation.

## 11. Composition

```python
# Sequence kept as-is from Stage 1 — runnable independently for design-only smoke runs.
design_pipeline = Sequence[DesignPipelineState, DesignPipelineState](steps=[
    workspace_bootstrap,
    designer,
])

# New full pipeline. References the same primitive declarations
# (workspace_bootstrap, designer) that design_pipeline uses, but composes them over
# FullPipelineState alongside the new working-session steps.
# Each Loop and each body Sequence is narrowed to its own scope per §5.
full_pipeline = Sequence[FullPipelineState, FullPipelineState](steps=[
    workspace_bootstrap,
    designer,
    change_set_planner,
    Loop[ChangeSetsLoopState, ChangeSetsLoopState](
        over=lambda s: ChangeSetsDocument.from_markdown_file(
            s.change_set_planner_output.change_sets_document
        ).change_sets,
        item_key="current_change_set",
        body=Sequence[ChangeSetProcessingState, ChangeSetProcessingState](steps=[
            prepare_change_set_workspace,    # §10.3, may collapse
            log_change_set_name,
            tdd_planner,
            Loop[StepsLoopState, StepsLoopState](
                over=lambda s: StepsDocument.from_markdown_file(
                    s.tdd_planner_output.steps_document
                ).steps,
                item_key="current_step",
                body=Sequence[StepProcessingState, StepProcessingState](steps=[
                    log_change_set_step_name,
                ]),
            ),
        ]),
    ),
])
```

Both Sequences live in a single `archipelago/systems/pipeline.py` module. Each is independently runnable via its own orchestrator function (`run_design_pipeline`, `run_full_pipeline`) and CLI entry. The design-only smoke loop survives this iteration; we drop it whenever it stops being useful, which is not yet.

## 12. CLI

`scripts/run_design_pipeline.py` is preserved unchanged (still runs `design_pipeline`).

A new `scripts/run_full_pipeline.py` runs `full_pipeline` end-to-end. Same input arguments as `run_design_pipeline.py` (`--feature`, `--repo`, `--ref`); same `.env` loading; same stdout flow.

## 13. No-test policy for this iteration (Archipelago side)

For this iteration, **no Archipelago unit or integration tests are added**. The work is fluid and prioritizes rapid iteration on topology, control flow, and data flow over coverage. Tests are added once the topology stabilizes — not before.

This is a conscious deviation from the project's standard TDD discipline (`CLAUDE.md`) for Stage 2's fluid period. Existing tests stay green; the policy applies only to new Archipelago code introduced during fluid topographic work.

Agent Foundry tests are unaffected — any platform extensions needed to support the topology (e.g., `Loop` primitive enhancements) remain TDD-disciplined per agent-foundry's own conventions.

## 14. Open questions

**a. Per-CS directory creation.** Does it belong in a dedicated `prepare_change_set_workspace` `FunctionAction` at the top of the outer-loop body, or absorbed into `tdd_planner`'s pre-execution machinery? This iteration assumes the dedicated action; revisit during implementation.

**b. `archetype.markdown` list-section shape.** `ChangeSetsDocument.change_sets` and `StepsDocument.steps` need to render as a markdown heading with a list of structured items beneath it, and parse back to `list[ChangeSetRef]` / `list[StepRef]`. What's the right archetype annotation? Possibilities: a new `AsItemList[ItemType]` annotation; a wrapper-class pattern like `FeatureDefinition.scope_boundaries` extended to typed items; something else. Decide during implementation by trying the simplest shape first.

**c. `MarkdownDocument.from_markdown_file(path)` helper.** Loop's `over` lambda needs this. Already in `archetype.markdown`? Or a small extension? Confirm during implementation.

**d.** *(Resolved: per-loop scoping is the locked decision; see §5 and §15. Agent Foundry's `Loop[I, O]` with `item_key` already supports this — no platform extension required.)*

**e. Aggregation of outer-iteration outputs back to `FullPipelineState`.** The outer loop currently does **not** aggregate per-iteration outputs back to the parent state — agents downstream read per-CS artifacts from the workspace directly. If a later iteration needs an in-memory aggregate (e.g., a data-driven Run Summary, or a downstream agent that consumes a `dict[slug, OuterIterationOutput]` rather than walking the workspace), `FullPipelineState` grows a slot at that point. Open: the shape of that slot when it lands.

**f. Path threading for Designer (existing).** Designer hardcodes paths in its instruction template — small design debt against §7.1. Does not block this iteration; cleanup belongs in a later one.

## 15. Locked decisions

- **Narrowed scope per primitive is the state model.** Each primitive declares its own typed input/output reflecting only what it consumes and produces. Pre-loop fields live in `FullPipelineState`; the working session adds four scoped types: `ChangeSetsLoopState`, `ChangeSetProcessingState`, `StepsLoopState`, `StepProcessingState`. The platform projects between any pair of nested primitives via field-level slicing. Per-iteration scopes are independent — naturally parallelism-safe and minimally coupled. Agent Foundry's existing primitive types support this; no platform changes required.
- Single `Sequence` at the top level (`Sequence[FullPipelineState, FullPipelineState]`) containing every primitive — application minimalism preserved.
- Both `design_pipeline` and `full_pipeline` declared in `archipelago/systems/pipeline.py`; both runnable independently.
- Loop's `over` is an inline lambda that reads an `AgentFilePath` and parses via `archetype.markdown`. No Loop helper that abstracts the parse step.
- Change Set Planner and TDD Planner each: container execution (`REUSE_NEW_SESSION`), placeholder Jinja-templated instruction, minimal Pydantic input/output, minimal markdown document type with a list-section field.
- Per-change-set sub-workspace: `/workspace/documents/change-sets/{slug}/`.
- Path threading principle (§7.1): paths flow through agent input/output models; no hardcoded workspace paths in instruction templates.
- Logging: bare `print()` to stdout, no run-event helper.
- No early-exit in either loop; process every item.
- No Archipelago tests in this iteration (§13).
- Renames doc-only for this iteration; source identifiers introduced fresh under the new names.
- Designer and the existing `design_pipeline` shipped in Stage 1 are untouched.

## 16. Successive iterations

Topology grows in successive iterations. Each preserves the "topography stable, agents thicken" rhythm; scope for the next iteration locks once the current one is stable. The Stage 2 roadmap is the source of truth for what's planned; the entries below sketch likely grouping but do not commit ordering.

- **Inner-loop body** — Test Agent + Implementer + CommitAction. The inner loop's body grows from `log_change_set_step_name` to a tight `(test_agent → implementer → commit_action)` sequence. Per-step artifacts land under `/workspace/documents/change-sets/{slug}/` (exact layout TBD).
- **Per-change-set review** — Reviewer. After the inner loop completes for a change set, Reviewer reads the diff and emits findings.
- **Review feedback routing** — Dispatcher + Integrator. The review feedback loop closes: findings route back into the inner loop topology.
- **Pipeline closure** — SubmitPRAction.
- **Run Summary** — replaces stdout logging with structured run events and a domain-aware `summary.txt`. Logging FunctionActions retire.
- **Tests / hardening** — once topology stabilizes, the no-test policy lifts; coverage catches up; legacy items from the Stage 2 roadmap's cleanup list start landing as new work touches them.

Each iteration produces an updated topography document if topology changes, or a thin diff doc if only agent depth changes.
