# Review Feedback Loop Design

## Problem Statement

Archipelago's current pipeline runs agents sequentially (test writer, code writer, reviewer, evaluator) per commit slice but lacks a feedback mechanism. The reviewer produces findings but they don't feed back into the implementation cycle. This means quality issues are identified but never addressed within the working session.

This design adds a review-driven feedback loop where must-fix findings cycle back through the implementation pipeline, deferred findings are routed to future change sets, and unresolvable issues escalate to a human.

## Approved Approach

Extend the pipeline with a review-fix cycle, introduce new agents (Integrator, Dispatcher redesign, Planner, Reviewer redesign), and extend Agent Foundry's plan format with composable control flow primitives that decouple the system definition from LangGraph.

### Rationale

- Review feedback is essential to producing correct, high-quality software
- Agent Foundry needs richer orchestration primitives to support the control flow patterns Archipelago requires (nested loops, retries, gates, conditionals)
- A declarative, composable plan format enables rapid experimentation with agent system topology — a primary motivation for Agent Foundry
- Decoupling from LangGraph's specific model makes it possible to swap execution engines without changing system definitions

## Architecture and Component Breakdown

### Data Models

#### New Models

**Implementation Task** (Planner output)

- `origin`: either a Change Set Step or a Review Finding
- `interface_specifications`: function signatures, data shapes, contracts introduced or modified
- `unit_test_changes`: list of test behaviors to add/remove, each mapped to acceptance criteria
- `implementation_change`: behavioral description of the software change needed

**Review Finding** (Reviewer output)

- `description`: what the issue is
- `severity`: `must_fix` or `can_defer`
- `category`: design quality, code quality, test complexity, naming, etc.
- `affected_files_and_locations`: where in the code
- `suggested_resolution`: what should change
- `source_commit_hashes`: which commits introduced the issue

**Change Set Step** (component of Change Set)

- `description`: what to do
- `acceptance_criteria_addressed`: references to the parent change set's acceptance criteria

**Dispatched Finding** (routing decision for a single finding)

- `finding`: the original Review Finding
- `disposition`: `route_to_change_set` | `defer_to_post_job` | `escalate`
- `target_change_set_name`: which change set (when disposition is `route_to_change_set`)
- `rationale`: why the Dispatcher chose this routing

**Dispatcher Output** (categorized findings)

- `routed_findings`: list of Dispatched Findings with disposition `route_to_change_set`, grouped by target change set
- `deferred_findings`: list of Dispatched Findings with disposition `defer_to_post_job`
- `escalations`: list of Dispatched Findings with disposition `escalate`

**Integrator Output** (revised step sequence for a change set)

- `target_change_set_name`: which change set was revised
- `revised_steps`: updated ordered list of Change Set Steps
- `changes_made`: list describing what was inserted, modified, reordered, or removed and why

#### Modified Models

**Job Specification** — add:

- `test_paths`: directories containing test code (for write permission enforcement). Will move to a repo-level Archipelago config in a future version.

**Change Set** — restructure:

- `name`: short title (used as PR title)
- `intent`: purpose and motivation
- `acceptance_criteria`: success conditions
- `interface_specifications` (optional): contracts this change set introduces or modifies
- `steps`: ordered list of Change Set Steps

#### Removed Models

- `CurrentTask`: replaced by Implementation Task
- `KernelState`: replaced by new state model aligned with the extended plan format
- `CodeReview` / `CodeReviewFinding`: replaced by Review Finding

### Agent Definitions

#### Planner Agent

- **Purpose**: Analyze repo and step context to produce an Implementation Task with interface specifications, test behaviors, and implementation change description
- **Input**: Change Set Step (or Review Finding during fix cycles), Change Set (for acceptance criteria and interface specs), Job Specification (for constraints and scope), current repo state
- **Output**: Implementation Task
- **Context**: preserved across invocations within a change set
- **Repo access**: read-only
- **Notes**: Handles both Change Set Step and Review Finding origins. Does moderate repo analysis — defines interfaces (function signatures, data shapes, contracts) but leaves test implementation and code design to downstream agents.

#### Test Agent

- **Purpose**: Add and remove unit tests per the Implementation Task
- **Input**: Implementation Task
- **Output**: modified test files
- **Context**: cleared between invocations
- **Repo access**: read all, write test paths only

#### Implementer Agent

- **Purpose**: Modify software implementation to make all tests pass and resolve lint/format issues
- **Input**: Implementation Task (implementation change and interface specifications), current repo state including modified tests
- **Output**: modified implementation files (all tests green, lint/format clean)
- **Context**: cleared between invocations
- **Repo access**: read all, write non-test paths only
- **Timeout**: configured via Agent Foundry, escalates to human on expiry

#### Reviewer Agent

- **Purpose**: Review change set commits for code quality, design quality, and test complexity
- **Input**: commit hashes for the change set, Job Specification (for quality constraints)
- **Output**: list of Review Findings divided into must-fix and can-defer
- **Context**: preserved across invocations within a change set (review-fix cycles build on prior review context)
- **Repo access**: read-only

#### Dispatcher Agent

- **Purpose**: Route deferred review findings to appropriate destinations
- **Input**: can-defer Review Findings, remaining Change Sets (names, intents, steps), Job Specification (for scope)
- **Output**: Dispatcher Output (routed, deferred, escalations)
- **Context**: cleared between invocations
- **Repo access**: read-only
- **Routing rules**:
  - Finding fits one remaining change set -> add to that change set
  - Finding cross-cuts multiple change sets -> route the same finding to each affected change set (the Integrator scopes it per change set's intent)
  - Finding doesn't fit any remaining change set but is in scope -> escalate to human
  - Finding outside job scope -> defer to post-job report

#### Integrator Agent

- **Purpose**: Revise a change set's step sequence to coherently incorporate routed findings
- **Input**: routed findings for one change set, the change set's current state (intent, acceptance criteria, existing steps)
- **Output**: Integrator Output (revised steps with change descriptions)
- **Context**: cleared between invocations
- **Repo access**: read-only
- **Notes**: This agent exists because step integration is backward-looking (incorporating findings into an existing plan) while the Planner is forward-looking (transforming steps into implementation tasks). These objectives are in tension per the guiding principle of cohesive agent objectives.

#### Commit Action (deterministic, not an agent)

- **Purpose**: Commit the current state after Implementer completes
- **Input**: workspace state
- **Output**: commit hash
- **Logic**: `git add`, `git commit` with message derived from the Implementation Task

#### Submit PR Action (deterministic, not an agent)

- **Purpose**: Submit a pull request for the completed change set
- **Input**: change set name, commit hashes, workspace state
- **Output**: PR URL
- **Logic**: `git push`, `gh pr create` with title from Change Set name

## Data Flow

### Control Flow

``` text
working_session:
  loop(change_sets):

    # 1. Implement all steps
    loop(steps):
      sequence: [planner, test_agent, implementer, commit]

    # 2. Review-fix cycle
    retry(max=2, until=no_must_fix_findings):
      reviewer
      conditional(has_must_fix):
        loop(must_fix_findings):
          sequence: [planner, test_agent, implementer, commit]

    # 3. Escalate if must-fix findings remain after 2 cycles
    conditional(must_fix_findings_remain):
      gate_action(human_escalation)

    # 4. Submit PR
    submit_pr

    # 5. Post-PR: triage deferred findings
    conditional(has_deferred_findings):
      dispatcher

      # 6. Handle escalations from dispatcher
      conditional(has_escalations):
        gate_action(human_escalation)

      # 7. Integrate routed findings into future change sets
      loop(affected_change_sets):
        integrator

  # 8. Generate post-job report
  write_deferred_findings_report
```

### Flow Details

- The **step loop** (#1) executes sequentially. Each iteration sees the repo as left by the previous commit.
- The **review-fix cycle** (#2) reviews all commits from the step loop. If must-fix findings exist, each finding goes through the full Planner -> Test Agent -> Implementer -> Commit sequence, then the Reviewer runs again. Up to 2 cycles.
- **Escalation** (#3): a Conditional checks whether must-fix findings survive 2 cycles. If so, routes to a GateAction that blocks on stdin — human provides resolution guidance, which is fed as a Review Finding origin to the Planner.
- **Submit PR** (#4) is a deterministic action. PR title from Change Set name.
- **Post-PR flow** (#5-7) only runs if the Reviewer produced can-defer findings. Dispatcher routes them, Integrator revises affected future change sets.
- **Post-job report** (#8) writes all accumulated deferred findings to a markdown file, prints file path to stdout.

### Mutable State

- The Job Specification's change sets are mutable — the Integrator modifies steps in future change sets
- A post-job findings collection accumulates deferred findings across all change sets

## Error Handling Strategy

### Human Escalation Points

1. **Must-fix findings survive 2 review-fix cycles**: stdout displays unresolved findings with context (review cycle history, what was attempted). Stdin receives human resolution guidance. System resumes by feeding guidance as a Review Finding origin to the Planner.

2. **Dispatcher can't route a finding**: stdout displays the finding, remaining change set names/intents, and options (create new change set or defer to post-job). Stdin receives human choice. If new change set, human provides name/intent/acceptance criteria via stdin.

### Agent Timeouts

Each agent has a timeout via Agent Foundry's `quality_controls.timeout_seconds`. On timeout: capture current state (failing tests, last error output), escalate to human via stdout/stdin. Human can provide guidance or abort the current step.

### Non-Escalation Errors

- **Docker container failure**: retry once, then escalate to human
- **Git operations failure** (commit, push, PR creation): capture error, escalate to human
- **Agent produces invalid output** (doesn't match expected model): retry once with error context appended to prompt, then escalate

### Out of Scope

- CI check failures on PRs
- Merge conflicts
- Branch protection issues
- Human escalation timeouts (human never responds)

## Agent Foundry Extensions

### System Definition Format: Python

System definitions are authored as **typed Python data structures** using Pydantic models. This was chosen over YAML/JSON because:

- **Compile-time type safety**: Pyright validates all type relationships statically — input/output compatibility between primitives, collection element types in loops, boolean conditions in conditionals
- **Runtime validation**: Pydantic validates constraints on actual values at every state boundary
- **No sync problem**: the schema is the model — no separate declaration format to keep in sync
- **Generics work naturally**: a `Loop[ChangeSetStep]` carries its item type through the primitive graph, resolved by Pyright automatically
- **No custom type system**: avoids building a type checker inside the compiler to validate a YAML-based type system that mirrors Python's

For human comprehension and visualization, tooling will generate read-only views (diagrams, topology maps, data flow views) from the Python object graph. The Python definitions are introspectable — Pydantic exposes full schemas, and the primitive tree can be walked to extract topology, isolation boundaries, and type flow.

### New Plan Primitives

Composable, typed building blocks. Primitives compose by direct Python object reference — no string-based naming or indirection. Diagnostic labels (for logging, visualization) are inferred from class names via introspection.

Each primitive declares **`input`** and **`output`** types that define its data boundary:
- **`input`**: state keys the primitive reads from the parent scope, with declared types
- **`output`**: state keys the primitive writes back to the parent scope, with declared types
- Anything not in `output` is discarded when the primitive completes (isolation)
- The compiler validates type compatibility: a primitive's output types must match the expected input types of downstream primitives

**Validation is both compile-time and runtime:**
- **Compile-time** (Pyright): structural type checking — field types, generic constraints, input/output compatibility across the primitive graph
- **Runtime** (Pydantic): value constraints — patterns, ranges, non-empty, custom validators — enforced at every state boundary transition

**`Sequence`** — execute steps in order, passing state between them

```python
implement_change_set = Sequence(
    input=ChangeSetInput,
    output=ChangeSetOutput,
    steps=[step_loop, review_fix_cycle, submit_pr, post_pr_dispatch],
)
```

**`Loop[T]`** — iterate over a collection in state, executing a body per item

```python
change_set_loop = Loop(
    input=WorkingSessionInput,
    output=WorkingSessionOutput,
    over=lambda state: state.change_sets,
    item_key="current_change_set",
    body=implement_change_set,
    max_iterations=100,
)
```

**`Retry`** — execute body, evaluate condition, repeat up to N times. When attempts are exhausted, Retry exits normally — the domain state carries the signal (e.g., `done=False`). The parent reads that state and routes accordingly (e.g., via a Conditional to a GateAction for escalation).

```python
review_fix_cycle = Retry(
    input=ReviewCycleInput,
    output=ReviewCycleOutput,
    max_attempts=2,
    until=lambda state: state.no_must_fix_findings,
    body=review_and_fix,
)
```

**`Conditional`** — branch based on state

```python
fix_if_needed = Conditional(
    input=ReviewOutput,
    output=FixOutput,
    condition=lambda state: state.has_must_fix,
    then_branch=fix_must_fix_findings,
    else_branch=None,
)
```

#### Action Primitives

Action primitives are leaves — they do work. Each variant has a different execution mechanism, but all share the same contract: typed input in, typed output out.

**`FunctionAction`** — synchronous, in-process function call (deterministic, non-AI)

```python
commit_changes = FunctionAction(
    input=CommitInput,
    output=CommitOutput,
    function=commit_changes_fn,
)
```

**`GateAction`** — block execution until external input is received. Always blocks when reached — routing to the gate is the parent's responsibility (e.g., a Conditional checking whether escalation is needed). The human sees the `prompt_key` field value and provides a response that becomes typed output.

```python
escalate_unresolved = GateAction(
    input=EscalationInput,
    output=EscalationOutput,
    interaction="human_stdin",
    prompt_key="escalation_context",
)
```

Future action variants: `ServiceAction` (API calls), `AgentAction` (containerized AI agents), etc.

### Composability

Primitives compose by direct Python object reference. A `Sequence` step can be any primitive instance. This enables reuse — for example, the `planner -> test_agent -> implementer -> commit` sequence appears in both the step loop and the review-fix cycle and can be assigned to a variable once.

```python
implement_task = Sequence(
    input=TaskInput,
    output=TaskOutput,
    steps=[planner, test_agent, implementer, commit_changes],
)

step_loop = Loop(
    input=StepLoopInput,
    output=StepLoopOutput,
    over=lambda state: state.current_change_set.steps,
    item_key="current_step",
    body=implement_task,
)

fix_findings_loop = Loop(
    input=FixLoopInput,
    output=FixLoopOutput,
    over=lambda state: state.must_fix_findings,
    item_key="current_finding",
    body=implement_task,
)
```

### Compiler Changes

The Agent Foundry compiler translates the typed primitive graph directly into LangGraph (no intermediate `GraphWiringPlan`). The old `compile_plan(GraphWiringPlan)` path is deleted.

1. **Typed public API**: `run_primitive_plan(plan, input: I) -> O` — accepts and returns Pydantic models, never raw dicts. LangGraph's dict internals are encapsulated.
2. **Compiler registry**: Per-type compiler functions registered in `dict[type[Primitive], CompilerFn]`. New primitive types register their own compiler without modifying core code.
3. Walk the primitive graph, validating input/output type compatibility at each boundary
4. Translate into LangGraph constructs (conditional edges for branching, subgraphs with cycles for loops/retry, interrupt nodes for gates)
5. Enforce runtime validation at state boundary transitions using Pydantic

### What Doesn't Change

- Role definitions (YAML specs for agents — these are simple metadata, not typed data flow)
- Registry and role discovery

### Mock Adapter

A new `MockClaudeCodeAdapter` implementing `AdapterBase` that returns pre-scripted response sequences. Enables integration testing of full pipeline orchestration without Docker or LLM calls. This is an Agent Foundry addition benefiting all products.

## Test Strategy

### Tier 1: Unit Tests

**Data models**: Validation, serialization round-trips, edge cases for all new and modified models.

**Agent handlers**: Each agent tested with stubbed interactions, verifying input validation, output model conformance, and behavior (e.g., Planner handles both Step and Finding origins, Reviewer categorizes findings correctly).

**Agent Foundry primitives**: Each primitive tested independently — sequence ordering, loop iteration and binding, retry conditions and exhaustion, conditional branching, gate blocking/resuming, action execution. Composability tests: named primitives referenced from sequences, nested loops, retry containing a sequence containing a loop.

**Compiler**: Extended plan format compiles correctly for each primitive and nested combinations.

**Control flow**: End-to-end pipeline tests with stub agents verifying step loop, review-fix cycle, escalation after max retries, post-PR dispatch, integrator step replacement, and post-job report generation.

### Tier 2: Integration Tests with Mock Adapter

`MockClaudeCodeAdapter` returning scripted responses. Tests full pipeline orchestration, state flow, agent handler integration, and protocol messages. No Docker, no LLM.

- Planner produces valid Implementation Task from a Change Set Step
- Test Agent writes tests targeting correct paths
- Implementer makes tests pass and resolves lint/format
- Reviewer produces correctly categorized Review Findings
- Dispatcher routes findings to appropriate change sets
- Integrator produces coherent revised step sequences
- Multi-agent pipeline segments (e.g., full review-fix cycle)
- Human escalation via simulated stdin input

### Tier 3: Integration Tests with Stub CLI

Real Docker container, fake `claude` binary outputting canned `stream-json` events. Tests container lifecycle, entrypoint, WebSocket communication, and event mapping through the protocol adapter.

## Concerns Checklist Results

| Concern | Applies? | Notes |
|---------|----------|-------|
| i18n | N/A | No user-facing text |
| analytics | N/A | No analytics in this version |
| feature-flags | N/A | No feature flags |
| migrations | N/A | No database |
| caching | N/A | No caching layer |
| webhooks | N/A | No external notifications |
| event-publishing | N/A | No event bus (future Agent Foundry direction) |
| security-auth | N/A | Auth unchanged (existing env vars) |
| responsive | N/A | No UI |
| error-handling | Yes | Agent timeouts, invalid outputs, Docker/git failures, human escalation via stdin/stdout |
| security | Yes | Write permission enforcement via test_paths on Job Specification |
| test-strategy | Yes | Three-tier testing: unit, mock adapter integration, stub CLI integration |

## Open Questions and Deferred Decisions

- **Repo-level Archipelago config**: `test_paths` lives on Job Specification for now, will move to a dedicated config file in a future version
- **Post-job report format**: markdown file, specific structure TBD during implementation
- **Commit message format**: derived from Implementation Task, specific template TBD during implementation
- **Human escalation UX**: functional via stdin/stdout, could be improved with structured prompts in a future version
- **State management inside loops**: The current design does not specify how state is managed across loop iterations. Considerations include: (1) whether to store state snapshots at each iteration boundary for debugging, replay, or recovery; (2) how to handle separate loops that iterate over the same state (e.g., the step loop and the review-fix findings loop both operate within the same change set's scope — what happens if one loop's mutations to shared state conflict with another loop's expectations); (3) whether loop state should support rollback to a previous iteration if an error occurs mid-loop
