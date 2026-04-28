# Archipelago v0.1 — Stage 2 Roadmap

> **Status:** Working roadmap, last revised 2026-04-27. Updated as Stage 2 progresses.
> **Stage 1 (completed):** `docs/plans/stage1/2026-04-03-review-feedback-loop-roadmap.md`
> **Topography (in progress):** `docs/plans/2026-04-27-topography-design.md`
> **Vision:** `docs/product/archipelago-vision.md`
> **Original feature design (historical):** `docs/plans/stage1/2026-04-03-review-feedback-loop-design.md`

## What Stage 2 delivers

**Archipelago v0.1** — a working-session pipeline that takes a feature definition and a target codebase, produces a design, decomposes the work into change sets, executes each change set through TDD-disciplined steps, reviews the result, routes findings back into the work, and ships a PR. End-to-end runnable, exercised by integration tests against a mock adapter.

Stage 1 delivered the platform foundations (`AgentAction` primitive, structured-output protocol, `archetype` markdown + templating package, Designer agent, design pipeline). Stage 2 builds the rest of the working session on top.

## Working principles for Stage 2

- **Topology first.** The pipeline's wiring is the conceptual image that ties this roadmap together. Every other work item plugs into a named slot in that wiring.
- **Horizontal-first.** Build system topography end-to-end with stub agents, then thicken each agent. We learn faster from a thin pipeline running end-to-end than from one perfect agent.
- **Rapid iteration over coverage.** Topology and agent shapes will change. **No new Archipelago unit or integration tests during fluid topographic work** — tests land once topology stabilizes. This is a conscious deviation from the project's standard TDD discipline (see `CLAUDE.md`) for Stage 2's fluid period only.
- **Path-threading.** Document paths are typed `AgentFilePath` values threaded through agent inputs/outputs. No hardcoded `/workspace/documents/X.md` in instruction templates. Designer's hardcoded paths are tolerated debt; new agents start clean.
- **Workspace-mediated communication.** Inter-agent exchange via markdown documents in the shared workspace, not direct typed RPC. Vision §3.2.
- **Single-source-of-truth data models.** Pydantic models drive markdown templates, parsers, validators, schemas, instructions. Vision §3.3.
- **Application minimalism.** Topology, control flow, and data flow are expressed in Agent Foundry primitives (`Sequence`, `Loop`, `AgentAction`, `FunctionAction`) declared once by Archipelago. Agent Foundry runs the topology. State-boundary mechanics are a platform concern, not an application one.

---

## Topology

The topology is the conceptual image that organizes this roadmap. Every agent and every action below plugs into a named slot in the wiring shown here.

### Eventual end-state

```
PRE-PIPELINE
  workspace_bootstrap  →  designer  →  change_set_planner
                                              │
                                              ▼
        ┌─────────────────────────────────────────────────────────────┐
        │  OUTER LOOP — per change set                                 │
        │                                                              │
        │  prepare_change_set_workspace                                │
        │  tdd_planner                                                 │
        │                                                              │
        │  ┌────────────────────────────────────────────────────┐      │
        │  │  INNER LOOP — per change-set step                   │      │
        │  │                                                     │      │
        │  │  test_agent  →  implementer  →  commit_action       │      │
        │  └────────────────────────────────────────────────────┘      │
        │                                                              │
        │  reviewer                                                    │
        │                                                              │
        │  ┌────────────────────────────────────────────────────┐      │
        │  │  REVIEW FEEDBACK — if findings                      │      │
        │  │                                                     │      │
        │  │  dispatcher  →  integrator                          │      │
        │  │  ↻ re-enter inner loop                              │      │
        │  └────────────────────────────────────────────────────┘      │
        └─────────────────────────────────────────────────────────────┘
                                              │
                                              ▼
        submit_pr_action  →  run_summary
```

### Topology slots

Each work item below references the slot(s) it fills:

- **Pre-pipeline** — feature definition + codebase → design + change-set list. Filled by: `workspace_bootstrap` (shipped), `designer` (shipped), `change_set_planner`.
- **Outer-loop preamble** — set up per-change-set workspace, plan the steps. Filled by: `prepare_change_set_workspace`, `tdd_planner`.
- **Inner-loop body** — execute one TDD step. Filled by: `test_agent`, `implementer`, `commit_action`.
- **Per-change-set review** — assess whether the change set meets its acceptance criteria. Filled by: `reviewer`.
- **Review feedback routing** — decide what to do with findings; revise the step list; re-enter the inner loop. Filled by: `dispatcher`, `integrator`.
- **Pipeline closure** — ship the PR; emit the run summary. Filled by: `submit_pr_action`, `run_summary`.

### Current snapshot

The first horizontal pass — pre-pipeline + outer-loop preamble + minimal inner-loop body (logging only) — is captured in `docs/plans/2026-04-27-topography-design.md`. That document evolves as the topology fills in. When the inner-loop body, review slot, and feedback routing slot land, the topography doc updates accordingly.

### Platform implications

Topology evolution will surface platform extensions Agent Foundry needs to support:

- **Per-iteration state binding** in `Loop` primitives — outer-loop body sees the current `ChangeSetRef`; inner-loop body sees the current `StepRef`. Likely a small platform extension.
- **Single-state-shape Sequences with rich state** — `FullPipelineState` accumulates every field; child Sequences and Loops slice into it. State-boundary mechanics are an Agent Foundry concern.
- **`Loop`'s `over` callable parses markdown** via `archetype` — initially inline lambdas; whether to grow a Loop helper that abstracts the parse step is a future platform decision.
- **Inner-loop re-entry from review feedback routing** — re-running the inner loop with an integrator-revised step list. May need a new primitive variant or a higher-level construct.

---

## Agents

Each agent fills a topology slot. Each ships with minimal definition first — Pydantic input/output, `archetype.markdown` document(s), short Jinja-templated instructions — and thickens later. Per the working principles, no Archipelago tests during fluid work.

### Change Set Planner

- **Slot:** Pre-pipeline.
- **Cluster (vision §3.1):** B — slice + order.
- **Behavior:** Reads the design; breaks the feature into ordered, independently-shippable change sets.
- **Reads:** `design.md`.
- **Writes:** `change-sets.md` (lists `ChangeSetRef` items consumed by the outer loop).
- **Renamed from:** "Decomposer" in original design.
- **Initial spec:** topography design doc.

### TDD Planner

- **Slot:** Outer-loop preamble.
- **Cluster:** C — verify + execute rigor.
- **Behavior:** Reads the design and one change set; produces an ordered TDD-step list for that change set.
- **Reads:** `design.md`, current `ChangeSetRef`.
- **Writes:** `change-sets/{slug}/steps.md` (lists `StepRef` items consumed by the inner loop).
- **Renamed from:** "Planner" in original design.
- **Initial spec:** topography design doc.

### Test Agent

- **Slot:** Inner-loop body (first half of the TDD pair).
- **Cluster:** Pessimism partner of TDD Planner — step rung.
- **Behavior:** Writes failing tests for the current step.
- **Reads:** Current `StepRef`, design + change-set context, the codebase.
- **Writes:** Test files in the codebase.
- **Notes:** Writable directories constrained to test paths.

### Implementer

- **Slot:** Inner-loop body (second half of the TDD pair).
- **Cluster:** Optimism partner of Test Agent — step rung.
- **Behavior:** Writes implementation that turns the failing tests green.
- **Reads:** Current `StepRef`, the failing tests, the codebase.
- **Writes:** Implementation files in the codebase.

### Reviewer

- **Slot:** Per-change-set review.
- **Behavior:** Reviews the diff for the change set against its acceptance criteria; emits findings categorized by severity and disposition (must-fix-now / can-defer / drop).
- **Reads:** Diff for the change set, change-set AC, design.
- **Writes:** `change-sets/{slug}/review.md` (or similar — naming TBD when this slot lands).

### Dispatcher

- **Slot:** Review feedback routing.
- **Behavior:** Routes Reviewer's findings — must-fix-now (re-enter inner loop), deferred (post-merge follow-up), drop.
- **Reads:** Reviewer's findings, change-set context.
- **Writes:** `change-sets/{slug}/dispatch.md` (or similar — TBD).
- **Notes:** Reasoning-only; no codebase access. Eventual candidate for API/SDK execution path.

### Integrator

- **Slot:** Review feedback routing.
- **Behavior:** Folds must-fix-now findings into the existing step list; produces a revised step list that re-enters the inner loop.
- **Reads:** Dispatched findings, current step list.
- **Writes:** Revised `change-sets/{slug}/steps.md` (or `steps-v{N}.md` if we preserve history — TBD).
- **Notes:** Reasoning-only; no codebase access. Eventual candidate for API/SDK execution path.

---

## Function actions

Deterministic, no LLM. Each fills a topology slot.

### prepare_change_set_workspace

- **Slot:** Outer-loop preamble.
- **Behavior:** Creates `/workspace/documents/change-sets/{slug}/`. Computes paths threaded into TDD Planner's input.

### CommitAction

- **Slot:** Inner-loop body (after Test Agent + Implementer).
- **Behavior:** `git add` test + impl files; `git commit` with a message derived from the current `StepRef`.
- **Notes:** Runs git commands inside the container; works on the codebase volume.

### SubmitPRAction

- **Slot:** Pipeline closure.
- **Behavior:** `git push`, `gh pr create` with a body summarizing the working session.
- **Notes:** GH credential passthrough already supported by workspace bootstrap.

### Logging actions (transient)

`log_change_set_name` and `log_change_set_step_name` print to stdout. Scaffolding for the topography skeleton; retired when Run Summary lands. Defined in the topography design doc.

---

## Pipeline machinery

### Pipeline module (`archipelago/systems/pipeline.py`)

The application's single composed declaration of the topology. Contains both `design_pipeline` (preserved for design-only smoke runs) and `full_pipeline` (the working session as a whole). Both are `Sequence[FullPipelineState, FullPipelineState]` (or `Sequence[DesignPipelineState, DesignPipelineState]` for the smaller design-only one). `design_pipeline` is dropped whenever it stops being useful.

### CLI (`scripts/run_full_pipeline.py`)

Same input arguments as `run_design_pipeline.py` (`--feature`, `--repo`, `--ref`); runs `full_pipeline` end-to-end. Loads `.env`; output flows to stdout. The existing `run_design_pipeline.py` is preserved for design-only smoke runs.

### Run Summary

- **Slot:** Pipeline closure.
- **Behavior:** Domain-aware `summary.txt` renderer that groups run events by change set, step, and review cycle. Builds on Agent Foundry's per-agent `lifecycle.jsonl` and generic `summary.txt`. Archipelago emits domain events (`change_set_started`, `step_completed`, `review_cycle_finished`, etc.) via Agent Foundry's `append_run_event` helper; the renderer produces a domain-aware summary at run teardown.
- **Notes:** Replaces the transient stdout logging actions. Invoked from the runner's `finally` block so partial runs still produce a readable summary.

---

## Platform extensions (Agent Foundry side)

Cross-repo work that supports the topology.

### Mock adapter

- **Goal:** `MockClaudeCodeAdapter` implements `AdapterBase`; accepts scripted responses; supports `AgentTurnEnvelope[T]` payloads.
- **Lives in:** agent-foundry.
- **Notes:** Built when end-to-end integration tests need it, not before.

### Alternative execution strategies

- **Goal:** `AgentAction` gains the ability to execute via API/SDK call instead of container. Reasoning-only agents (Change Set Planner, TDD Planner, Dispatcher, Integrator) can opt into the API path; agents that touch code (Designer, Test Agent, Implementer, Reviewer) stay container-bound.
- **Includes:** Model-parameter configuration on `AgentAction` (model selection, effort levels, other LLM parameters).
- **Notes:** By the time this lands, the full pipeline runs in containers and we have real cost / latency data to inform the design.

### Claude Code version-gating CI pipeline

- **Goal:** Outside-the-container CI pipeline that detects new Claude Code versions, runs the contract integration test (`test_claude_code_stream_shape.py`) against the new binary, and either rebuilds the Docker image (contract passes) or files an issue (contract fails).
- **Replaces:** the `ARCHIPELAGO_UPDATE_AVAILABLE` marker (text-marker protocol already deleted).
- **Notes:** ~30 lines of GitHub Action shell. Typed event models + integration test already exist; only the workflow file is new.

### `Loop` primitive support for per-iteration state binding

- **Goal:** Agent Foundry's `Loop` cleanly exposes the current iteration item to its body's state.
- **Notes:** May already partially exist; verify against current `Loop` semantics when the outer-loop body lands.

---

## Quality and closure

### End-to-end integration tests

- **Goal:** Test pipeline segments and full sessions against `MockClaudeCodeAdapter` — step loop, review-fix cycle, gate escalation (if gates land), post-PR follow-up routing (if it survives the topology), full multi-change-set session.
- **Timing:** Land once topology stabilizes — not during fluid work. Once these land, the no-test policy lifts for new Archipelago code.

### Legacy cleanup (scrub-as-we-go)

Delete leftover dead code as new work makes it visibly dead. No dedicated cleanup item; happens organically as new work touches the surrounding code. Known candidates:

- `src/archipelago/docker/CLAUDE-*.md` files (4 files; leftover from the deleted Archipelago Docker image).
- `models_v2.py` if still extant; merge into `models.py`.
- `archipelago_system.json` if still extant.
- Deprecated test files: `test_archipelago_e2e.py`, `test_archipelago_pipeline_plan.py`, `test_archipelago_checkpoint.py`, plus stale test classes in surviving files.
- Deprecated models: `CurrentTask`, `KernelState`, `CodeReview*` family — verify which still exist.
- Deprecated output models: `DecomposerOutput`, `EvaluatorOutput`, old `DispatcherOutput` from `io_models.py` if it still exists.

### Residual ACP-rename audit

- **Goal:** Catch any residual `acp` references not absorbed into Stage 1's main rename pass — class names, comments, docs, env-var prefixes.
- **Scope:** Both repos.
- **Notes:** Mostly cosmetic.

---

## Open threads

Cross-cutting design questions to resolve as topology fills in. Not work items in themselves.

- **Inner-loop re-entry mechanic.** The "↻ re-enter inner loop" arrow in the review feedback routing slot needs a primitive shape. Options: a new `Loop` variant with a restart branch; a higher-level construct; nesting the inner loop inside its own retry-style primitive. Decide when topology fills in to that depth.
- **Per-change-set state lifetime.** `tdd_planner_output` and per-CS artifacts overwrite across outer-loop iterations in `FullPipelineState`. Acceptable for early work; later iterations may need per-CS state slots or a `dict[slug, ...]` shape.
- **Reviewer / Dispatcher / Integrator artifact paths.** Each writes to `/workspace/documents/change-sets/{slug}/...`. Naming TBD when those agents land.
- **Gate primitives.** Human escalation when must-fix findings survive N review cycles. Position: in the review feedback routing slot, between Dispatcher and Integrator. Exact mechanism TBD.
- **Post-PR follow-up loops.** Whether a post-PR Dispatcher → Integrator path for routing deferred findings lives in v0.1 or post-v0.1. TBD.
- **`archetype.markdown` list-section shape.** `ChangeSetsDocument.change_sets` and similar list-of-typed-items fields need an annotation shape. Decide during the topography skeleton implementation.
- **Designer path-threading retrofit.** Designer hardcodes paths in its instruction template (small design debt against the path-threading principle). Retrofit before or after the new agents stabilize. TBD.
- **`Loop` `over` markdown-parse helper.** Whether to grow a Loop primitive helper for archetype-backed iteration over a `MarkdownDocument` field, or keep inline lambdas. Decide once 2–3 instances exist.
- **CS-level acceptance criteria.** Change Set Planner's minimal initial output is `name + slug + summary`. CS-level AC will be added when Reviewer needs them. The vision doc's AC ladder (feature / CS / step) drives this.
- **Test-strategy ladder.** Feature-level (Designer), CS-level (Change Set Planner), step-level (TDD Planner). Currently captured only as a vision-doc note; will inform agent-thickening work.

---

## Live artifacts

- **`docs/plans/2026-04-27-stage2-roadmap.md`** — this document. Revised as topology evolves and work lands.
- **`docs/plans/2026-04-27-topography-design.md`** — current topography snapshot.
- New design / iteration documents land at `docs/plans/` top level with `YYYY-MM-DD-<descriptive-name>.md` filenames. No `Phase N` / `CS#` / `Slice#` prefixes; descriptive names only.
