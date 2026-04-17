# Implementation Roadmap: Review Feedback Loop

**Design doc**: `docs/plans/2026-04-03-review-feedback-loop-design.md`
**Issue**: 730alchemy/archipelago#1

## Scope Updates (post-planning)

- **CS4 (MockClaudeCodeAdapter) is deferred** until CS12 needs it. CS4 builds a generic mock mechanism whose only consumer is the CS12 integration tests; building it ahead of CS12 would be speculative (we wouldn't know what agent I/O shapes the scripts need to emit until CS5–CS7 define them). Revisit when CS12 starts.
- **CS5 scope was broadened** to absorb transition cleanup originally deferred to CS11. The Archipelago package is already non-functional as a runtime (`runner.py`, `cli.py`, several tests, and `archipelago_system.json` all depend on `agent_foundry.compiler`/`agent_foundry.planner` modules that agent-foundry CS3 deleted), so CS5 removes the dead code wholesale rather than leaving it broken through CS11. The three agents with no transition value (`decomposer`, `dispatcher`, `evaluator`) are also deleted in CS5. See `docs/plans/2026-04-07-cs5-data-models-plan.md`.
- **CS6 shipped as "Option A"** — radically trimmed from the original plan. Only `ReviewerPayload` (a thin wrapper around `list[ReviewFinding]`) was added to `models.py`. The originally planned agent wrapper types (`PlannerOutput`, `NewDispatcherOutput`, `IntegratorAgentOutput`, `CommitActionOutput`, `SubmitPRActionOutput`) were intentionally not built — the `--json-schema` structured-output design (CS6.5) requires LLM-facing types to contain only fields the LLM can populate. Execution metadata (`worker_result`, `workspace_volume`) is adapter/runner concern, not in the schema. CS7 will call `to_claude_code_schema(AgentTurnEnvelope[ImplementationTask])` etc. on the CS5 domain types directly. See `docs/plans/2026-04-08-cs6-agent-output-models-plan.md`.
- **CS6.5 was inserted between CS6 and CS7** — a new cross-repo change set for structured-output protocol extension in Agent Foundry. Motivated by the discovery that Claude Code's `--json-schema` works on Pro subscriptions. CS6.5 adds: schema flattener (`to_claude_code_schema`), `StructuredOutputMessage` protocol type, adapter integration (`--json-schema` plumbing, `StructuredOutput` tool-use detection, hybrid stderr-on-error, local retry on missing structured output with stop-reason-aware skip for refusals/max_tokens), and `AgentTurnEnvelope[T]` generic discriminated-union envelope with four outcome kinds. All work in Agent Foundry — Archipelago gains no new files. See `docs/plans/2026-04-08-cs6.5-structured-output-protocol-plan.md`.

- **CS7 scope expanded** to span both repos. Design work uncovered that `AgentAction` — a new primitive for running LLM agents in containers — belongs in Agent Foundry, not Archipelago. CS7 now includes: (1) Agent Foundry: `AgentAction[I, O]` primitive with a composition-based two-sided interface (platform side handles execution, product side declares agent configuration via collaborator callables), lifecycle orchestration (re-implemented from Archipelago's `DockerLifecycle`), progress tracking, recovery, and the `lessons-learned` skill (moved from Archipelago). (2) Archipelago: four agent implementations (Planner, Reviewer, Dispatcher, Integrator) and two `FunctionAction`s (CommitAction, SubmitPRAction) built on `AgentAction`. The Archipelago Docker image is eliminated — all agents use the base ACP image with instructions injected at runtime via `write_file_to_container`. Key design decisions: structured output via `AgentTurnEnvelope[T]` as default response channel with file collection as fallback; container reuse across loop iterations with resume-or-new-session policy; prompt construction via `prompt_builder: Callable[[I], str]`; independently testable collaborators (prompt builder, instructions provider, response handler) replace monolithic agent classes.
- **CS10.5 inserted between CS10 and CS11** — a cross-repo change set for execution strategy abstraction and ACP rename. Motivated by the observation that three of four CS7 agents (Planner, Dispatcher, Integrator) are pure reasoning over data and don't need container sandboxing — a direct API/SDK call would be faster and simpler. CS10.5 adds: alternative execution strategies for `AgentAction` (API/SDK alongside container), model parameter configuration (model selection, effort levels), and renames the "ACP" concept and all associated folder names, image names, and references to a more descriptive name. Deferred to CS10.5 because by then the full pipeline is working in containers, providing real experience to inform the design.

## Overview

14 change sets across two repos. Agent Foundry (CS1-4, CS6.5, CS7-AF) comes first — Archipelago (CS5-12) depends on the new primitives and protocol. TDD throughout: tests before implementation in every task.

## Dependency Graph

```
CS1 (Primitives) → CS2 (Validators) → CS3 (Compiler) ──┐
                                                         ├→ CS9 (System Def) → CS10 (Runner/CLI) → CS10.5 (Exec Strategy + ACP Rename) → CS11 (Cleanup) → CS12 (Integration)
CS4 (MockAdapter) ───────────────────────────────────────┤
CS5 (Data Models) → CS6 (Payload + Roles) → CS6.5 (Structured Output Protocol) → CS7 (AgentAction + New Agents) ──┤
CS5 (Data Models) → CS8 (Evolve Agents) ───────────────────────────────────────────────────────────────────────────┘
```

CS1-3 are sequential. CS4 is independent of CS1-3. CS5-8 can start after CS1 (they don't need the compiler yet). CS6.5 is in Agent Foundry (not Archipelago) and must complete before CS7 — it provides the `AgentTurnEnvelope[T]` and `to_claude_code_schema` that every CS7 agent handler uses. CS7 spans both repos: Agent Foundry gets `AgentAction` primitive and execution infrastructure; Archipelago gets the agent implementations built on top. CS9 needs CS3 + CS7 + CS8. CS10.5 needs CS10. CS12 needs CS10 + CS4.

---

## Change Set 1 (Agent Foundry): Primitive Pydantic Models

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

## Change Set 4 (Agent Foundry): MockClaudeCodeAdapter

**Goal**: Mock adapter for integration testing without Docker or LLM.

### Tasks

1. **Tests for mock adapter** — scripted `TurnResult` sequences, multi-turn conversations, script exhaustion behavior, marker mapping on scripted output
   - Create: `agent-foundry/tests/agent_foundry/acp/test_mock_adapter.py`

2. **MockClaudeCodeAdapter** — implements `AdapterBase`, accepts scripted responses in constructor, pops one per `run_turn`
   - Create: `agent-foundry/src/agent_foundry/acp/adapters/mock.py`

---

## Change Set 5 (Archipelago): New and Modified Data Models

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

**Goal**: Minimum LLM-facing payload type for the Reviewer agent and four role spec YAMLs for the new agents. Shipped as "Option A" — no agent wrapper types.

**Plan**: `docs/plans/2026-04-08-cs6-agent-output-models-plan.md`

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

**Goal**: Protocol machinery so CS7 agent handlers can invoke `claude --json-schema`, receive typed agent outcomes via `AgentTurnEnvelope[T]`, and route all four outcome kinds (success, clarification, permission, failed) through a single code path.

**Plan**: `docs/plans/2026-04-08-cs6.5-structured-output-protocol-plan.md`

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

**Goal**: Introduce `AgentAction[I, O]` as a new Agent Foundry primitive for running LLM agents in containers, then build four Archipelago agents and two function actions on top.

### Plan Structure

CS7 is broken into four plans, drafted just-in-time after the prior plan lands so implementation learnings shape the next plan. Task numbers below refer to the task list in this roadmap section.

- **Plan 1** — Tasks 1–2 (primitive + compiler) plus a validator registry refactor that emerged during planning. Compiler delegates to a stub `run_agent_in_container` that raises `NotImplementedError`. Path: `docs/plans/2026-04-13-cs7-plan1-agent-action-primitive-plan.md`.
- **Plan 2** — Task 3 (lifecycle orchestration, replaces the stub) and Task 4 (basic lifecycle tracking). Container reuse is part of Task 3's scope. Also defines the contract for non-success envelope outcomes (Plan 1 deferred this decision).
- **Plan 3** — **Complete** (2026-04-17). Task 5 (`lessons-learned` skill move) and Task 6 (base `CLAUDE.md` added). Widened to include: `acp` → `agents` rename across agent-foundry (package, image `agent-worker`, env vars `WORKSPACE_*` / `AGENT_*`), `container.py` → `lifecycle.py`, end-to-end deletion of the text-marker protocol (`MarkerMapping`, `_match_marker`, `marker-config.json`, `AgentEventMessage`), and full removal of the Archipelago Docker image. Plan: `docs/plans/2026-04-17-cs7-plan3-base-image-plan.md`. PRs: agent-foundry `feat/cs7-plan3-base-image`, archipelago `feat/cs7-plan3-drop-archipelago-image`. CS11 scope reduced accordingly: steps 9 (marker deletion), 10 (update-available marker sunset), and the Archipelago-image removal are now done; CI pipeline for Claude Code version gating still pending.
- **Plan 4** — Tasks 7–12 (four agents, two function actions, four instruction files). First real product consumer. Depends on Plans 1 and 2.

Dependency shape: Plan 1 → Plan 2 → Plan 4; Plan 3 is independent.

### Design Decisions

- **`AgentAction` is a two-sided interface** — platform side (Agent Foundry) handles container lifecycle, instruction injection, prompt delivery, structured output handling, progress tracking, recovery, and container reuse. Product side (Archipelago) declares agent configuration via composable collaborators: `prompt_builder`, instructions provider, response handler.
- **Composition over inheritance** — product-side logic (prompt building, instruction assembly, response handling) is provided as collaborator callables, not subclass overrides. Each collaborator is independently unit-testable without Docker or Claude Code.
- **Structured output by default** — agents return `AgentTurnEnvelope[T]` via `--json-schema`. File collection available as fallback (configured per agent or as runtime fallback on structured output failure).
- **Container reuse** — product declares reuse policy per agent. Platform manages container pool with two modes: resume (same Claude Code session/context) or new session (fresh session, filesystem state persists). Containers stay alive across loop iterations.
- **Instructions injected at runtime** — handwritten instruction files read from host filesystem and written into container via `write_file_to_container` before startup. No Archipelago Docker image; all agents use the base ACP image. Base `CLAUDE.md` updated for structured output protocol (no text markers).
- **Archipelago `docker_worker` package superseded** — lifecycle orchestration, progress tracking, and recovery re-implemented in Agent Foundry. Archipelago's `docker_worker/lifecycle.py`, `progress.py`, `recovery.py`, `interrupts.py`, and `protocol.py` become dead code (cleaned up in CS11).
- **`lessons-learned` skill moved to Agent Foundry** — generally useful for any product's agents, not Archipelago-specific.

### Agent Foundry Tasks

1. **`AgentAction[I, O]` primitive** — new primitive type alongside `FunctionAction` and `GateAction`. Fields: `prompt_builder`, instructions path/provider, output schema, container config (with platform defaults), reuse policy, file collection paths.
   - Create: `agent-foundry/src/agent_foundry/primitives/models.py` (extend)
   - Create: `agent-foundry/tests/agent_foundry/primitives/test_agent_action.py`

2. **`AgentAction` compiler** — compiles `AgentAction` into a LangGraph node that executes the container lifecycle: inject instructions, build prompt from input state, start container, send prompt, receive and validate response, handle all four envelope outcomes.
   - Modify: `agent-foundry/src/agent_foundry/compiler/primitive_compiler.py`
   - Create: `agent-foundry/tests/agent_foundry/test_agent_action_compiler.py`

3. **Lifecycle orchestration** — re-implement orchestrator-side container lifecycle (from Archipelago's `DockerLifecycle`): WebSocket server, prompt delivery, message processing, file collection, container reuse with resume/new-session modes.
   - Create: `agent-foundry/src/agent_foundry/acp/lifecycle.py` (or equivalent)
   - Create: `agent-foundry/tests/agent_foundry/acp/test_lifecycle.py`

4. **Basic lifecycle tracking** — started/completed/failed status for agent invocations. Full commit-aware progress tracking (progress.jsonl parsing, resume points, PatchInfo/CommitEvidence) deferred to CS8 alongside the code-writing agents that need it.

5. **`lessons-learned` skill** — move from Archipelago Docker image to Agent Foundry base image.
   - Move: `archipelago/src/archipelago/docker/skills/lessons-learned/SKILL.md` → `agent-foundry/src/agent_foundry/acp/docker/skills/lessons-learned/SKILL.md`
   - Modify: Agent Foundry base Dockerfile

6. **Update base `CLAUDE.md`** — remove text-marker communication protocol, add structured output protocol via `AgentTurnEnvelope`.
   - Modify: `archipelago/src/archipelago/docker/CLAUDE.md` (until Archipelago image is eliminated; then this lives in Agent Foundry base image only)

### Archipelago Tasks (each agent: tests first, then implementation)

7. **Planner** — handles ChangeSetStep and ReviewFinding origins, produces ImplementationTask with interface specs. Provides `prompt_builder` and instruction file.
   - Create: `archipelago/src/archipelago/agents/planner.py`
   - Create: `archipelago/tests/archipelago/unit/test_planner.py`

8. **Reviewer** — reviews commit hashes, categorizes findings into must_fix/can_defer. Provides `prompt_builder` and instruction file.
   - Create: `archipelago/src/archipelago/agents/reviewer.py`
   - Create: `archipelago/tests/archipelago/unit/test_reviewer.py`

9. **Dispatcher** (new) — routes deferred findings per routing rules. Provides `prompt_builder` and instruction file.
    - Create: `archipelago/src/archipelago/agents/finding_dispatcher.py`
    - Create: `archipelago/tests/archipelago/unit/test_finding_dispatcher.py`

10. **Integrator** — revises change set step sequences to incorporate routed findings. Provides `prompt_builder` and instruction file.
    - Create: `archipelago/src/archipelago/agents/integrator.py`
    - Create: `archipelago/tests/archipelago/unit/test_integrator.py`

11. **Actions** — CommitAction (git add/commit), SubmitPRAction (git push, gh pr create). These are `FunctionAction`s, not `AgentAction`s — deterministic, no LLM.
    - Create: `archipelago/src/archipelago/actions.py`
    - Create: `archipelago/tests/archipelago/unit/test_actions.py`

12. **Agent instruction files** — handwritten role instructions for each of the four agents.
    - Create: `archipelago/src/archipelago/instructions/planner.md`
    - Create: `archipelago/src/archipelago/instructions/reviewer.md`
    - Create: `archipelago/src/archipelago/instructions/dispatcher.md`
    - Create: `archipelago/src/archipelago/instructions/integrator.md`

---

## Change Set 8 (Archipelago): Evolve Test Agent and Implementer

**Goal**: Evolve UnitTestWriter → TestAgent and CodeWriter → Implementer, accepting ImplementationTask.

### Tasks

1. **TestAgent** — accepts ImplementationTask, builds prompt from unit_test_changes, enforces test_paths write restriction
   - Create: `archipelago/src/archipelago/agents/test_agent.py`
   - Modify: `archipelago/tests/archipelago/unit/test_unit_test_writer.py` (add new test class)

2. **Implementer** — accepts ImplementationTask, builds prompt from implementation_change + interface_specifications
   - Create: `archipelago/src/archipelago/agents/implementer.py`
   - Modify: `archipelago/tests/archipelago/unit/test_code_writer.py` (add new test class)

3. **Update env builder** — `build_agent_env()` supports ImplementationTask
   - Modify: `archipelago/src/archipelago/docker_worker/env.py`

---

## Change Set 9 (Archipelago): Python System Definition

**Goal**: Replace `archipelago_system.json` with typed Python system definition using new primitives.

### Tasks

1. **Tests for system definition** — validates as PrimitivePlan, type boundaries compatible, topology matches design
   - Create: `archipelago/tests/archipelago/unit/test_system_definition.py`

2. **State boundary models** — `WorkingSessionInput/Output`, `ChangeSetInput/Output`, `TaskInput/Output`, `ReviewCycleInput/Output`, etc.
   - Create: `archipelago/src/archipelago/state_models.py`

3. **System definition** — Python primitives encoding the full control flow: change set loop → step loop → review-fix retry → gate → submit PR → post-PR dispatch → integrator loop → post-job report
   - Create: `archipelago/src/archipelago/system.py`

4. **Domain-level run summary** — Archipelago-specific `summary.txt` renderer that groups run events by change set, step, and review cycle. Builds on the generic per-agent summary shipped in CS7 Plan 2 (Agent Foundry writes `lifecycle.jsonl` and a generic `summary.txt`). Archipelago emits its own domain events (`change_set_started`, `step_completed`, `review_cycle_finished`, etc.) via the `append_run_event(event: dict)` helper exposed by Agent Foundry, then ships a renderer that produces a domain-aware summary at run teardown. Invoke the renderer from the runner's `finally` block so partial runs still produce a readable summary.
   - Create: `archipelago/src/archipelago/run_summary.py`
   - Create: `archipelago/tests/archipelago/unit/test_run_summary.py`
   - Modify: `archipelago/src/archipelago/system.py` (wrap primitives that mark domain boundaries with `append_run_event` calls)

---

## Change Set 10 (Archipelago): Update Runner and CLI

**Goal**: Wire the new system definition into the runner. Add stdin/stdout human escalation.

### Tasks

1. **Tests for runner** — loads PrimitivePlan from system.py, compiles and runs via primitive compiler
   - Modify: `archipelago/tests/archipelago/unit/test_runner.py`

2. **Update runner** — `load_archipelago_plan()` imports from system.py, `run_archipelago()` uses `run_primitive_plan()`
   - Modify: `archipelago/src/archipelago/runner.py`

3. **Tests for CLI escalation** — Gate blocks → stdout displays context → stdin receives input
   - Modify: `archipelago/tests/archipelago/unit/test_cli.py`

4. **Update CLI** — stdin/stdout interaction for Gate callbacks
   - Modify: `archipelago/src/archipelago/cli.py`
   - Call `archipelago.logging_config.configure_logging()` at process startup (extracted from the old `cli.py` during CS5 follow-up; location: `src/archipelago/logging_config.py`)

5. **[Deferred from CS5] Recreate the config-to-env pipeline tests** — the original `tests/archipelago/integration/test_config_to_lockdown.py` exercised the full plan → `compile_plan` → node config → env builder pipeline. Its `TestConfigToEnvPipeline` class was deleted during CS5 because `compile_plan`/`GraphWiringPlan` no longer exist. The lockdown enforcement half (env → container) was already recreated in CS5 at `tests/archipelago/integration/test_docker_worker_lockdown.py` by constructing `WorkerInput` directly. CS10 must complete the coverage by adding new integration tests that verify a `PrimitivePlan` node config with `acp_hidden_dirs`/`acp_readonly_dirs` propagates correctly through the new runner into `build_container_env` (or its CS10 successor) and then through the env → container lockdown path. This closes the security regression gap introduced by CS5's deletion of the old pipeline tests.
   - Create: `archipelago/tests/archipelago/integration/test_plan_to_lockdown.py` (or equivalent)
   - Cross-reference: `tests/archipelago/integration/test_docker_worker_lockdown.py` (CS5 follow-up) for the env → container half that is already covered.

---

## Change Set 10.5 (Agent Foundry + Archipelago): Execution Strategy Abstraction and ACP Rename

**Goal**: Add alternative execution strategies to `AgentAction` (API/SDK alongside container), model parameter configuration, and rename the "ACP" concept throughout both repos.

### Motivation

Three of four CS7 agents (Planner, Dispatcher, Integrator) are pure reasoning over data — they don't touch repos, write files, or execute code. Running them in Docker containers is overhead for no safety benefit. A direct API/SDK call to Claude with structured output would be faster, cheaper, and simpler. By CS10, the full pipeline is working in containers, providing real experience to inform this design.

### Tasks

1. **Alternative execution strategies** — `AgentAction` gains the ability to execute via API/SDK call instead of container. Product declares which strategy per agent. Platform provides both execution paths. Container strategy for agents that touch code (Reviewer, TestAgent, Implementer); API strategy for reasoning-only agents (Planner, Dispatcher, Integrator).
   - Modify: `agent-foundry/src/agent_foundry/primitives/models.py`
   - Create: `agent-foundry/src/agent_foundry/acp/api_executor.py` (or equivalent)

2. **Model parameter configuration** — `AgentAction` accepts model selection (e.g., Opus, Sonnet), effort levels, and other LLM parameters. Product declares per agent.
   - Modify: `agent-foundry/src/agent_foundry/primitives/models.py`

3. **Rename ACP** — replace the "ACP" name with a descriptive name throughout both repos: folder names, image names, class names, comments, documentation. Scope: `agent-foundry/src/agent_foundry/acp/` folder, `acp-cc-worker` image name, all `ACP_*` environment variable prefixes, all code references.

4. **Update Archipelago references** — rename all Archipelago references to the old ACP name.
   - Modify: `archipelago/src/archipelago/docker_worker/` (references to agent_foundry.acp)
   - Modify: `archipelago/src/archipelago/docker/Dockerfile` (base image name)

---

## Change Set 11 (Archipelago): Remove Deprecated Code

**Goal**: Clean cut of old models, agents, role specs, and JSON system definition.

### Tasks

1. **Remove deprecated agents** — delete `decomposer.py`, `evaluator.py`, old `dispatcher.py`
2. **Remove deprecated role specs** — delete `decompose_job_specification.yaml`, `evaluate_commit.yaml`, `dispatch_commit.yaml`
3. **Remove deprecated models** — `CurrentTask`, `KernelState`, `CodeReview`, `CodeReviewFinding`, `CodeReviewLocation`, `CodeReviewSuggestion`, `CodeReviewVerification`, `CodeReviewScope`, `CodeReviewSummary`, `CodeReviewConstraints` from `models.py`
4. **Remove deprecated output models** — `DecomposerOutput`, `EvaluatorOutput`, old `DispatcherOutput` from `io_models.py`
5. **Merge models_v2.py into models.py**, delete `models_v2.py`
6. **Delete `archipelago_system.json`**
7. **Remove deprecated test files**:
   - Delete `test_archipelago_e2e.py` (tests old decomposer→dispatcher→kernel pipeline)
   - Delete `test_archipelago_pipeline_plan.py` (tests JSON GraphWiringPlan compilation)
   - Delete `test_archipelago_checkpoint.py` (tests old pipeline checkpointing)
8. **Remove deprecated test classes from surviving files**:
   - `test_archipelago_models.py` — remove `TestCurrentTask`, `TestKernelState`, `TestCodeReview` classes; keep new model tests
   - `test_io_models.py` — remove tests for `DecomposerOutput`, `EvaluatorOutput`, old `DispatcherOutput`
   - `test_unit_test_writer.py` — remove old `UnitTestWriter` tests (keep `TestAgent` tests added in CS8)
   - `test_code_writer.py` — remove old `CodeWriter` tests (keep `Implementer` tests added in CS8)
   - `test_software_reviewer.py` — remove old `SoftwareReviewer` tests (replaced by `test_reviewer.py` in CS7)
   - `test_docker_worker_env.py` — remove tests referencing `CurrentTask` (updated in CS8)
   - `test_runner.py` — remove tests for old `load_archipelago_plan()` JSON path (updated in CS10)
   - `test_archipelago_role_specs.py` — remove tests for deleted role specs

9. **Delete `marker-config.json` and the text-marker protocol** — the `ARCHIPELAGO_TASK_COMPLETE`, `ARCHIPELAGO_NEED_CLARIFICATION`, `ARCHIPELAGO_NEED_PERMISSION` markers are fully replaced by the `AgentTurnEnvelope` structured-output protocol (CS6.5). Remove `marker-config.json` from `archipelago/src/archipelago/docker/`. Remove the marker instructions from the agent's `docker/CLAUDE.md`. In agent-foundry, the `_match_marker` method and `_compiled_markers` field on `ClaudeCodeAdapter` can be deleted, along with the `MarkerMapping` class in `acp/protocol.py` and all marker-related tests — but only after confirming no agent handler still references them.

10. **Sunset `ARCHIPELAGO_UPDATE_AVAILABLE` marker and replace with CI pipeline** — the `ARCHIPELAGO_UPDATE_AVAILABLE` marker (defined in `marker-config.json` but never referenced in the agent's CLAUDE.md) was a container-internal signal for detecting Claude Code updates at startup. This approach is wrong: it checks for updates inside a container that can't act on them, and it relies on the text-marker protocol being deleted in this same change set.

    **Replacement: a CI pipeline that runs outside the container.**

    The pipeline:
    1. **Detect** — scheduled job (daily or on Anthropic release webhook) compares `claude --version` on the host against the version pinned in the Dockerfile.
    2. **Verify** — if a newer version exists, run `test_claude_code_stream_shape.py` (the integration test from CS6.5 that asserts every event type, field name, and structure the adapter depends on) against the new binary. If the parsing contract holds, the update is safe.
    3. **Rebuild** — if the contract passes, rebuild the Docker image with the new Claude Code version and open a PR that bumps the pinned version.
    4. **Block** — if the contract fails, file an issue with the specific assertion that broke (e.g., "StructuredOutput tool renamed to JsonOutput") and do NOT rebuild. A human updates `claude_code_events.py` in agent-foundry, the integration test passes, and the pipeline re-runs.

    This makes the update decision automated and contract-gated. The container never needs to know whether it's outdated. The typed event models (`claude_code_events.py`) are the lock; the integration test is the gate; the CI pipeline is the guard.

    **Implementation**: ~30 lines of shell in a GitHub Action. The integration test and typed models already exist. The only new artifact is the workflow file.

---

## Change Set 12 (Archipelago): Integration Tests

**Goal**: End-to-end pipeline tests using MockClaudeCodeAdapter with scripted responses.

### Tasks

1. **Integration tests for pipeline segments**:
   - Step loop: planner → test_agent → implementer → commit over multiple steps
   - Review-fix cycle: reviewer finds must_fix → fix loop → reviewer passes
   - Gate escalation: must_fix survives 2 cycles → gate → scripted stdin
   - Post-PR dispatch: can_defer → dispatcher → integrator revises future steps
   - Full working session: multiple change sets end-to-end
   - Create: `archipelago/tests/archipelago/integration/test_pipeline_orchestration.py`

---

## Verification

After all change sets:
- `pdm run test-unit` passes in both repos
- `pdm run test-integration` passes in both repos
- `pdm run lint` clean in both repos
- `pdm run typecheck` clean in both repos (Pyright strict on new code)
- Manual smoke test: run CLI with a sample JobSpecification containing 2 change sets with steps, verify the pipeline executes the full control flow with MockClaudeCodeAdapter
