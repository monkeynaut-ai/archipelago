# Implementation Roadmap: Review Feedback Loop — Stage 1 (Completed)

**Design doc**: `docs/plans/stage1/2026-04-03-review-feedback-loop-design.md`
**Issue**: 730alchemy/archipelago#1
**Stage 2 (remaining work)**: `docs/plans/2026-04-27-stage2-roadmap.md`

> **Note (2026-04-27):** The original 14-change-set roadmap was split into two documents on 2026-04-27. This file records the change sets that have shipped. Some sections describe original CS-level intent that was later refined or partially superseded — see status notes inside each section. Remaining work, including the deferred CS7 Plan 4 phases (Decomposer / Planner / Reviewer / Dispatcher / Integrator), lives in the Stage 2 roadmap.

## Scope Updates (post-planning, historical record)

- **CS4 (MockClaudeCodeAdapter) is deferred** until CS12 needs it. CS4 builds a generic mock mechanism whose only consumer is the CS12 integration tests; building it ahead of CS12 would be speculative (we wouldn't know what agent I/O shapes the scripts need to emit until CS5–CS7 define them). Revisit when CS12 starts. *(Stage 2.)*
- **CS5 scope was broadened** to absorb transition cleanup originally deferred to CS11. The Archipelago package is already non-functional as a runtime (`runner.py`, `cli.py`, several tests, and `archipelago_system.json` all depend on `agent_foundry.compiler`/`agent_foundry.planner` modules that agent-foundry CS3 deleted), so CS5 removes the dead code wholesale rather than leaving it broken through CS11. The three agents with no transition value (`decomposer`, `dispatcher`, `evaluator`) are also deleted in CS5. See `docs/plans/stage1/2026-04-07-cs5-data-models-plan.md`.
- **CS6 shipped as "Option A"** — radically trimmed from the original plan. Only `ReviewerPayload` (a thin wrapper around `list[ReviewFinding]`) was added to `models.py`. The originally planned agent wrapper types (`PlannerOutput`, `NewDispatcherOutput`, `IntegratorAgentOutput`, `CommitActionOutput`, `SubmitPRActionOutput`) were intentionally not built — the `--json-schema` structured-output design (CS6.5) requires LLM-facing types to contain only fields the LLM can populate. Execution metadata (`worker_result`, `workspace_volume`) is adapter/runner concern, not in the schema. CS7 will call `to_claude_code_schema(AgentTurnEnvelope[ImplementationTask])` etc. on the CS5 domain types directly. See `docs/plans/stage1/2026-04-08-cs6-agent-output-models-plan.md`.
- **CS6.5 was inserted between CS6 and CS7** — a new cross-repo change set for structured-output protocol extension in Agent Foundry. Motivated by the discovery that Claude Code's `--json-schema` works on Pro subscriptions. CS6.5 adds: schema flattener (`to_claude_code_schema`), `StructuredOutputMessage` protocol type, adapter integration (`--json-schema` plumbing, `StructuredOutput` tool-use detection, hybrid stderr-on-error, local retry on missing structured output with stop-reason-aware skip for refusals/max_tokens), and `AgentTurnEnvelope[T]` generic discriminated-union envelope with four outcome kinds. All work in Agent Foundry — Archipelago gains no new files. See `docs/plans/stage1/2026-04-08-cs6.5-structured-output-protocol-plan.md`.
- **CS7 scope expanded** to span both repos. Design work uncovered that `AgentAction` — a new primitive for running LLM agents in containers — belongs in Agent Foundry, not Archipelago. CS7 was further broken into four plans, each drafted just-in-time: Plan 1 (AgentAction primitive + compiler), Plan 2 (lifecycle orchestration), Plan 3 (base image, end-to-end deletion of the text-marker protocol, removal of the Archipelago Docker image), and Plan 4 (the Archipelago agents themselves). Plan 4 was further phased: Phase 1 shipped the markdown machinery; Phase 2 shipped the Designer agent and the `design_pipeline` Sequence (Cluster A from the harness-competing-tensions analysis in vision §3.1). Decomposer (Cluster B), Planner (Cluster C), Reviewer, Dispatcher, and Integrator are deferred to Stage 2.

## Overview

Stage 1 covers the platform foundations and the design half of the pipeline: 9 change sets across two repos. Agent Foundry (CS1–CS3, CS6.5, CS7 Plans 1–3) provides the primitives and protocol; Archipelago (CS5, CS6, CS7 Plan 4 Phases 1–2) provides the data models, structured-output payloads, markdown machinery, and the Designer agent. TDD throughout: tests before implementation in every task.

## Dependency Graph (Stage 1)

```
CS1 (Primitives) → CS2 (Validators) → CS3 (Compiler) ───────────────────────────────────────────────────────────────────┐
                                                                                                                          │
CS5 (Data Models) → CS6 (Payload + Roles) → CS6.5 (Structured Output Protocol) → CS7 Plan 1 (AgentAction primitive) ──────┤
                                                                                  → CS7 Plan 2 (Lifecycle)                │
                                                                                  → CS7 Plan 3 (Base image)               │
                                                                                  → CS7 Plan 4 Phase 1 (Markdown)         │
                                                                                  → CS7 Plan 4 Phase 2 (Designer + pipeline)
```

CS1–3 are sequential. CS5–6 can start after CS1. CS6.5 is in Agent Foundry and must complete before CS7. CS7's plan tree is sequential within Plan 4 (Phase 2 depends on Phase 1) but Plans 1–3 can interleave.

---

## Change Set 1 (Agent Foundry): Primitive Pydantic Models

**Status**: Shipped. Plan: `docs/plans/stage1/2026-04-03-cs1-primitive-models-plan.md`.

**Goal**: Define the six composable primitive types as Pydantic models with typed input/output boundaries.

### Tasks

1. **Tests for primitive models** — construction, validation, error cases (type mismatches, missing fields)
   - Create: `agent-foundry/tests/agent_foundry/primitives/test_primitive_models.py`
   - Create: `agent-foundry/tests/agent_foundry/primitives/test_primitive_plan.py`

2. **Primitive base and models** — `Primitive` base with `input` and `output` types. Then `Sequence`, `Loop`, `Retry`, `Conditional`, `Gate`, `Action`. Composition by direct object reference.
   - Create: `agent-foundry/src/agent_foundry/primitives/__init__.py`
   - Create: `agent-foundry/src/agent_foundry/primitives/models.py`

3. **PrimitivePlan** — top-level container holding root primitive with graph walking for introspection
   - Create: `agent-foundry/src/agent_foundry/primitives/plan.py`

### Key Decisions
- No `name` field on primitives — composition is by direct Python object reference, diagnostic labels inferred from class names via introspection
- `input`/`output` are Pydantic model types (not dicts)
- `Callable` fields (`over`, `until`, `condition`) require `model_config = ConfigDict(arbitrary_types_allowed=True)`
- Primitives are not JSON-serializable — this is intentional (Python is source of truth)
- Primitives are declarations, not executable — the compiler (CS3) translates them to LangGraph

---

## Change Set 2 (Agent Foundry): Primitive Validators

**Status**: Shipped. Plan: `docs/plans/stage1/2026-04-04-cs2-primitive-validators-plan.md`.

**Goal**: Validate primitive graphs for structural correctness before compilation.

### Tasks

1. **Tests for validation** — type mismatches between connected primitives, missing loop termination, nested validation
   - Create: `agent-foundry/tests/agent_foundry/test_primitive_validators.py`

2. **Validators** — `validate_primitive_plan()` walks the graph, checks all constraints
   - Create: `agent-foundry/src/agent_foundry/primitives/validators.py`

3. **Error types** — primitive-specific validation errors
   - Create: `agent-foundry/src/agent_foundry/primitives/errors.py`

---

## Change Set 3 (Agent Foundry): Primitive Compiler

**Status**: Shipped. Plan: `docs/plans/stage1/2026-04-05-cs3-primitive-compiler-plan.md`.

**Goal**: Translate typed primitive graph into executable LangGraph. Existing `compile_plan(GraphWiringPlan)` path stays intact.

### Tasks

1. **Tests for primitive compilation** — each primitive type individually, nested compositions (Sequence containing Loop containing Sequence), state boundary validation
   - Create: `agent-foundry/tests/agent_foundry/test_primitive_compiler.py`

2. **Primitive compiler** — `compile_primitive_plan()` walks the primitive tree, validates types at boundaries, produces LangGraph `StateGraph`. Translation strategies:
   - `Sequence` → linear node chain
   - `Loop[T]` → subgraph with conditional back-edge + iteration counter
   - `Retry` → subgraph with conditional back-edge + counter + `on_exhausted` routing
   - `Conditional` → conditional edges from router node
   - `Gate` → interrupt node (requires MemorySaver checkpointer)
   - `Action` → simple node wrapping function
   - Pydantic runtime validation injected at each state boundary
   - Create: `agent-foundry/src/agent_foundry/compiler/primitive_compiler.py`

3. **Entry point** — `run_primitive_plan()` convenience function
   - Modify: `agent-foundry/src/agent_foundry/compiler/compiler.py`

### Anticipated Challenges
- **Gate + LangGraph**: `interrupt_before` requires a checkpointer. Compiler must auto-inject `MemorySaver` when Gate is present.
- **Loop[T] generics**: `TypeVar` with bounds, ensuring `T` flows through to runtime validation of collection items.
- **State isolation in nested loops**: each iteration must get proper scoping per declared input/output.

---

## Change Set 5 (Archipelago): New and Modified Data Models

**Status**: Shipped. Plan: `docs/plans/stage1/2026-04-07-cs5-data-models-plan.md`. Scope was broadened to absorb transition cleanup originally deferred to CS11 (see Scope Updates above).

**Goal**: All new data models. Old models stay intact until CS11.

### Tasks

1. **Tests for new models** — construction, validation, serialization, edge cases
   - Modify: `archipelago/tests/archipelago/unit/test_archipelago_models.py`

2. **New models** — `ChangeSetStep`, `ReviewFinding`, `ImplementationTask`, `DispatchedFinding`, `DispatcherOutput` (renamed), `IntegratorOutput`
   - Create: `archipelago/src/archipelago/models_v2.py`

3. **Modify existing models** — `JobSpecification` gets `test_paths` (optional), `ChangeSet` gets `name`, `intent`, `steps` (optional with defaults during transition)
   - Modify: `archipelago/src/archipelago/models.py`

---

## Change Set 6 (Archipelago): Agent Payload Models and Role Specs

**Status**: Shipped as "Option A" (radically trimmed). Plan: `docs/plans/stage1/2026-04-08-cs6-agent-output-models-plan.md`. The four role specs landed but the agents that would have consumed them (Planner / Reviewer / Dispatcher / Integrator) were deferred — see CS7 section and Stage 2.

**Goal**: Minimum LLM-facing payload type for the Reviewer agent and four role spec YAMLs for the new agents. Shipped as "Option A" — no agent wrapper types.

### Tasks

1. **ReviewerPayload** — thin wrapper around `list[ReviewFinding]` in `models.py`. Exists because `AgentTurnEnvelope[T]` (CS6.5) requires `T` to be a single BaseModel, not a bare list.
   - Modify: `archipelago/src/archipelago/models.py`
   - Modify: `archipelago/tests/archipelago/unit/test_archipelago_models.py`

2. **Role spec test harness** — parses each YAML with PyYAML, asserts structural schema with exact-match key checks.
   - Create: `archipelago/tests/archipelago/unit/test_archipelago_role_specs.py`

3. **Role specs** — four new agents, each referencing CS7 classes (dangling until CS7; safe because role specs are lazy-loaded).
   - Create: `archipelago/src/archipelago/roles/plan_implementation_task.yaml`
   - Create: `archipelago/src/archipelago/roles/review_change_set.yaml`
   - Create: `archipelago/src/archipelago/roles/dispatch_findings.yaml`
   - Create: `archipelago/src/archipelago/roles/integrate_findings.yaml`

### Key Decisions
- **No PlannerOutput / NewDispatcherOutput / IntegratorAgentOutput wrappers** — the domain types from CS5 (`ImplementationTask`, `DispatcherOutput`, `IntegratorOutput`) are the LLM-facing payloads directly. Execution metadata (`worker_result`, `workspace_volume`) is adapter/runner concern.
- **No CommitActionOutput / SubmitPRActionOutput** — deterministic `FunctionAction` primitives in CS7, not agents.
- **`io_models.py` untouched** — legacy wrappers stay until CS11 deletes them.

---

## Change Set 6.5 (Agent Foundry): Structured-Output Protocol Extension

**Status**: Shipped. Plan: `docs/plans/stage1/2026-04-08-cs6.5-structured-output-protocol-plan.md`.

**Goal**: Protocol machinery so CS7 agent handlers can invoke `claude --json-schema`, receive typed agent outcomes via `AgentTurnEnvelope[T]`, and route all four outcome kinds (success, clarification, permission, failed) through a single code path.

### Tasks

1. **Schema-flattening helper** — `to_claude_code_schema(model)` inlines `$defs`/`$ref` and strips OpenAPI `discriminator` keyword. Claude Code silently disables on `discriminator`; fails retries on `$ref`.
   - Create: `agent-foundry/src/agent_foundry/acp/schema_tools.py`
   - Create: `agent-foundry/tests/agent_foundry/acp/test_schema_tools.py`

2. **StructuredOutputMessage protocol type** — carries the raw dict payload from Claude Code's synthetic `StructuredOutput` tool call. Distinct from `AgentEventMessage` (mid-stream signals from free text).
   - Modify: `agent-foundry/src/agent_foundry/acp/protocol.py`

3. **TurnResult.structured_output field** — optional `dict[str, Any] | None` on the adapter's return value.
   - Modify: `agent-foundry/src/agent_foundry/acp/adapter.py`

4. **Adapter integration** (five sub-steps):
   - 4a: `_build_claude_cmd` accepts optional `json_schema` param, emits `--json-schema` flag
   - 4b: `_map_event_to_protocol` detects `tool_use` with `name == "StructuredOutput"`, emits typed message, sets `task_complete`, skips generic tool summary
   - 4c: `run_turn` plumbs `json_schema` to the CLI command and populates `TurnResult.structured_output`
   - 4d: Hybrid stderr-on-error — fold stderr into existing `turn_complete` on `is_error=True`; synthetic `error` status only when process crashes before `result` event. One terminal status per turn.
   - 4e: Local retry on missing structured output — if `--json-schema` set but no `StructuredOutput` tool call captured, retry once via `--resume` with correction prompt. Domain-agnostic (checks tool-call presence, not payload shape), local to container (no orchestrator round-trip), bounded (one retry). Skips retry on non-recoverable `stop_reason` values (`refusal`, `max_tokens`).
   - Modify: `agent-foundry/src/agent_foundry/acp/adapters/claude_code.py`

5. **AgentTurnEnvelope[T]** — generic Pydantic envelope wrapping a discriminated union of four outcome kinds. Lives in Agent Foundry because the four outcomes are properties of Claude Code headless execution, not any domain. Generic `T` lets consumers bring their own payload type.
   - Create: `agent-foundry/src/agent_foundry/acp/turn_outcome.py`
   - Create: `agent-foundry/tests/agent_foundry/acp/test_turn_outcome.py`

### Key Decisions
- **Envelope in Agent Foundry, not Archipelago** — the four outcomes are execution-mode properties. A second product imports from the platform, not from a peer.
- **No `build_outcome_schema` wrapper** — consumers call `to_claude_code_schema(AgentTurnEnvelope[PayloadType])` directly; they import the envelope for validation anyway.
- **`FailureOutcome` uses `reason: str`** — no `FailureCategory` enum. Let field data inform future categorization.
- **Text-marker protocol untouched** — CS6.5 is strictly additive. `marker-config.json` and `_match_marker` stay intact. CS11 deletes them.
- **`Literal[TurnOutcomeKind.VARIANT]` required** — Pydantic 2.12 rejects bare StrEnum discriminator fields. Fallback clause per project convention.

### Anticipated Challenges
- **Claude Code `--json-schema` quirks**: silently disables on OpenAPI `discriminator` keyword; fails retries on `$defs`/`$ref`. Both handled by `to_claude_code_schema` flattener. Empirically verified during planning.
- **Cold-start pattern** (anthropics/claude-code#23265): first `--json-schema` invocation sometimes fails, retry succeeds. Handled by Task 4e local retry.

---

## Change Set 7 (Agent Foundry + Archipelago): AgentAction Primitive and New Agent Implementations

**Status**: Plans 1–3 shipped; Plan 4 Phase 1 shipped; Plan 4 Phase 2 shipped (Designer agent only). The remaining agents originally listed in CS7 — Planner, Reviewer, Dispatcher, Integrator — are deferred to Stage 2 alongside the new Decomposer agent that emerged from the Phase 2 tensions analysis. Phase 2 also produced a new top-level `archetype` package (markdown + templating, OSS-bound) inside agent-foundry.

**Goal**: Introduce `AgentAction[I, O]` as a new Agent Foundry primitive for running LLM agents in containers, then build the Archipelago agents and function actions on top.

### Plan Structure

CS7 was broken into four plans, drafted just-in-time after the prior plan lands so implementation learnings shape the next plan.

- **Plan 1** — AgentAction primitive + compiler plus a validator registry refactor that emerged during planning. Compiler delegates to a stub `run_agent_in_container` that raises `NotImplementedError`. Path: `docs/plans/stage1/2026-04-13-cs7-plan1-agent-action-primitive-plan.md`.
- **Plan 2** — Lifecycle orchestration (replaces the stub) and basic lifecycle tracking. Container reuse is part of Plan 2's scope. Also defines the contract for non-success envelope outcomes (Plan 1 deferred this decision).
- **Plan 3** — `lessons-learned` skill move and base `CLAUDE.md`. Widened to include: `acp` → `agents` rename across agent-foundry (package, image `agent-worker`, env vars `WORKSPACE_*` / `AGENT_*`), `container.py` → `lifecycle.py`, end-to-end deletion of the text-marker protocol (`MarkerMapping`, `_match_marker`, `marker-config.json`, `AgentEventMessage`), and full removal of the Archipelago Docker image. Plan: `docs/plans/stage1/2026-04-17-cs7-plan3-base-image-plan.md`. PRs: agent-foundry `feat/cs7-plan3-base-image`, archipelago `feat/cs7-plan3-drop-archipelago-image`. CS11 scope reduced accordingly.
- **Plan 4** — The Archipelago agents themselves. Parent plan: `docs/plans/stage1/2026-04-17-cs7-plan4-archipelago-agents-plan.md`. Phased delivery:
  - **Phase 1** — markdown machinery (typed `MarkdownDocument` types, render/parse, `template_fields()`). Design: `docs/plans/stage1/2026-04-17-cs7-plan4-phase1-markdown-machinery-design.md`. Plan: `docs/plans/stage1/2026-04-17-cs7-plan4-phase1-implementation-plan.md`. **Shipped (PR #12).**
  - **Phase 2** — Designer agent (Cluster A from the harness-competing-tensions analysis), `archetype` package extraction (markdown + Jinja templating, OSS-bound), `AgentAction.instructions_provider` signature change, workspace-bootstrap `FunctionAction`, and `design_pipeline: Sequence[workspace_bootstrap → designer]` with a CLI entry point. Design: `docs/plans/stage1/2026-04-20-cs7-plan4-phase2-design.md`. Slice 1 plan: `docs/plans/stage1/2026-04-20-cs7-plan4-phase2-slice1-implementation-plan.md`. Slices 2–5 plan: `docs/plans/stage1/2026-04-21-cs7-plan4-phase2-slices-2-5-implementation-plan.md`. **Shipped (PRs #7 and #8).**
  - **Phase 3+** — Decomposer (Cluster B), Planner (Cluster C), Reviewer, Dispatcher, Integrator agents; `CommitAction` and `SubmitPRAction` function actions; the inner Implementer/TestAgent loop and the outer review-feedback loop. **Deferred to Stage 2.**

### Design Decisions Carried Forward

- **`AgentAction` is a two-sided interface** — platform side (Agent Foundry) handles container lifecycle, instruction injection, prompt delivery, structured output handling, progress tracking, recovery, and container reuse. Product side (Archipelago) declares agent configuration via composable collaborators: `prompt_builder`, instructions provider, response handler.
- **Composition over inheritance** — product-side logic (prompt building, instruction assembly, response handling) is provided as collaborator callables, not subclass overrides. Each collaborator is independently unit-testable without Docker or Claude Code.
- **Structured output by default** — agents return `AgentTurnEnvelope[T]` via `--json-schema`. File collection available as fallback (configured per agent or as runtime fallback on structured output failure).
- **Container reuse** — product declares reuse policy per agent. Platform manages container pool with two modes: resume (same Claude Code session/context) or new session (fresh session, filesystem state persists). Containers stay alive across loop iterations.
- **Instructions injected at runtime** — handwritten instruction files read from host filesystem and written into container via `write_file_to_container` before startup. No Archipelago Docker image; all agents use the base agents-foundry image. Base `CLAUDE.md` updated for structured output protocol (no text markers).
- **Workspace-mediated markdown for inter-agent communication** — locked 2026-04-17. Pydantic models are the source of truth; annotations (`AsHeading`, `AsCodeBlock`, ...) derive rendering, parsing, validation, JSON schema, and instruction appendix.
- **Three-agent split for the feature-implementation middle layer** (Designer / Decomposer / Planner) derived from the harness-competing-tensions method (vision §3.1).
- **Archipelago `docker_worker` package superseded** — lifecycle orchestration, progress tracking, and recovery re-implemented in Agent Foundry. Archipelago's `docker_worker/lifecycle.py`, `progress.py`, `recovery.py`, `interrupts.py`, and `protocol.py` become dead code (cleaned up in CS11 — Stage 2).
- **`lessons-learned` skill moved to Agent Foundry** — generally useful for any product's agents, not Archipelago-specific.

### Tasks Shipped in Stage 1

**Agent Foundry:**

1. **`AgentAction[I, O]` primitive** — Plan 1.
2. **`AgentAction` compiler** — Plan 1.
3. **Lifecycle orchestration** — Plan 2.
4. **Basic lifecycle tracking** — Plan 2. Full commit-aware progress tracking (progress.jsonl parsing, resume points, PatchInfo/CommitEvidence) deferred alongside the code-writing agents that need it.
5. **`lessons-learned` skill** — Plan 3.
6. **Base `CLAUDE.md` update** — Plan 3.
7. **`archetype` package** (sibling to `agent_foundry`, OSS-bound) — Phase 2 Slice 1. Provides `archetype.markdown` (typed markdown documents) and `archetype.templating` (Jinja-based template resolution with markdown-aware globals).

**Archipelago:**

8. **Data models for the design half** — Phase 2 Slice 2. `FeatureDefinition`, `DesignDocument`, `CodebaseSource` as `archetype.markdown` types. Public API at `archipelago.models`.
9. **Workspace bootstrap `FunctionAction`** — Phase 2 Slice 3. Provisions Docker volume, clones codebase (read-only working tree, `.git/` writable), stages feature definition (read-only), creates writable `documents/` dir. GitHub token passthrough for private-repo cloning. Integration test against real Docker daemon. Public API at `archipelago.actions`.
10. **Designer `AgentAction`** — Phase 2 Slice 4. `prompt_builder`, `instructions_provider`, Jinja-templated instructions, input/output models. Public API at `archipelago.agents.designer`.
11. **`design_pipeline` Sequence + orchestrator + CLI + first E2E** — Phase 2 Slice 5. Composes `workspace_bootstrap → designer`. `run_design_pipeline(feature_definition, codebase_source)` orchestrator; `scripts/run_design_pipeline.py` CLI. E2E integration test against `examples/features/run-observability.md` targeting agent-foundry. Public API at `archipelago.systems`.
12. **Designer hardening (post-merge)** — fenced `DesignDocument` skeleton in instructions; de-inlined feature values; delegation-first investigation; investigation-summary gate; `/workspace/documents` chown fix; pyright cleanup across `archipelago/src`.

### Tasks Deferred to Stage 2

The following tasks were originally part of CS7 but did not ship in Stage 1. They reappear in the Stage 2 roadmap, reframed where appropriate to reflect the harness-competing-tensions decomposition that emerged during Phase 2 design:

- Decomposer agent (Cluster B — slice + order, change set boundary).
- Planner agent (Cluster C — verify + execute rigor, change set step boundary).
- Reviewer, Dispatcher, Integrator agents.
- `CommitAction` and `SubmitPRAction` function actions.
- Per-agent instruction templates for the deferred agents.
