# Implementation Roadmap: Review Feedback Loop

**Design doc**: `docs/plans/2026-04-03-review-feedback-loop-design.md`
**Issue**: 730alchemy/archipelago#1

## Overview

12 change sets across two repos. Agent Foundry (CS1-4) comes first — Archipelago (CS5-12) depends on the new primitives. TDD throughout: tests before implementation in every task.

## Dependency Graph

```
CS1 (Primitives) → CS2 (Validators) → CS3 (Compiler) ──┐
                                                         ├→ CS9 (System Def) → CS10 (Runner/CLI) → CS11 (Cleanup) → CS12 (Integration)
CS4 (MockAdapter) ───────────────────────────────────────┤
CS5 (Data Models) → CS6 (Output Models) → CS7 (New Agents) ──┤
CS5 (Data Models) → CS8 (Evolve Agents) ─────────────────────┘
```

CS1-3 are sequential. CS4 is independent of CS1-3. CS5-8 can start after CS1 (they don't need the compiler yet). CS9 needs CS3 + CS7 + CS8. CS12 needs CS10 + CS4.

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

## Change Set 6 (Archipelago): Agent Output Models and Role Specs

**Goal**: Per-agent output models for new agents and their YAML role specs.

### Tasks

1. **Tests for output models**
   - Modify: `archipelago/tests/archipelago/unit/test_archipelago_models.py`

2. **New output models** — `PlannerOutput`, `ReviewerOutput`, `NewDispatcherOutput`, `IntegratorAgentOutput`, `CommitActionOutput`, `SubmitPRActionOutput`
   - Modify: `archipelago/src/archipelago/agents/io_models.py`

3. **Role specs**
   - Create: `archipelago/src/archipelago/roles/plan_implementation_task.yaml`
   - Create: `archipelago/src/archipelago/roles/review_change_set.yaml`
   - Create: `archipelago/src/archipelago/roles/dispatch_findings.yaml`
   - Create: `archipelago/src/archipelago/roles/integrate_findings.yaml`

---

## Change Set 7 (Archipelago): New Agent Implementations

**Goal**: Planner, Reviewer, Dispatcher (new), Integrator agents + Commit and SubmitPR actions. Each follows `TypedAgent` pattern.

### Tasks (each agent: tests first, then implementation)

1. **Planner** — handles ChangeSetStep and ReviewFinding origins, produces ImplementationTask with interface specs
   - Create: `archipelago/src/archipelago/agents/planner.py`
   - Create: `archipelago/tests/archipelago/unit/test_planner.py`

2. **Reviewer** — reviews commit hashes, categorizes findings into must_fix/can_defer
   - Create: `archipelago/src/archipelago/agents/reviewer.py`
   - Create: `archipelago/tests/archipelago/unit/test_reviewer.py`

3. **Dispatcher** (new) — routes deferred findings per routing rules
   - Create: `archipelago/src/archipelago/agents/finding_dispatcher.py`
   - Create: `archipelago/tests/archipelago/unit/test_finding_dispatcher.py`

4. **Integrator** — revises change set step sequences to incorporate routed findings
   - Create: `archipelago/src/archipelago/agents/integrator.py`
   - Create: `archipelago/tests/archipelago/unit/test_integrator.py`

5. **Actions** — CommitAction (git add/commit), SubmitPRAction (git push, gh pr create)
   - Create: `archipelago/src/archipelago/actions.py`
   - Create: `archipelago/tests/archipelago/unit/test_actions.py`

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
