# Docker Worker: Problems for Review-Remediation Node

Analysis of potential problems with adding a new node to the implementation kernel that transforms software_reviewer output into job descriptions and routes them back to unit_test_writer or code_writer.

## 1. No conditional/backward routing within the kernel subgraph

The kernel is a linear chain with unconditional edges (`archipelago_system.json` lines 40-44). The new node needs to route back to unit_test_writer or code_writer, creating a cycle. The graph engine supports cycles (dispatcher→kernel→dispatcher proves this) and conditional routing via `condition` fields on edges, but the kernel subgraph has never used either. The kernel edges need restructuring with conditions, and `max_iterations` must be added on the inner review loop to prevent infinite cycling when the reviewer keeps finding issues the code_writer can't fix.

**Files affected:** `archipelago_system.json`, agent-foundry `compiler.py` (lines 283-305 for routing)

## 2. `worker_result` gets overwritten by each node

Every docker worker node writes its output to `state["worker_result"]` (`handler.py:471`). When the new node reads the software_reviewer's `worker_result`, that works — it's the most recent one. But once it routes back to unit_test_writer or code_writer, those nodes overwrite `worker_result` with their own output. By the time the software_reviewer runs again, the previous review is gone. There is no mechanism to accumulate or namespace results per node.

**Files affected:** `handler.py` (line 471), `models.py`

## 3. Review output shape doesn't fit WorkerInput/CommitSpecification

The software_reviewer produces a structured CodeReview JSON (scope, summary, findings with quality/severity/locations/suggestions). The new node must transform this into something the downstream node can consume. But `_build_prompt` (`handler.py:129-155`) is built around `CommitSpecification` — title, acceptance_criteria, test_focus, implementation_focus. Review findings (with their problem/suggestion/location/verification structure) don't map cleanly onto these fields. Either findings must be flattened into acceptance criteria (lossy) or the prompt builder must be extended.

**Files affected:** `handler.py` (`_build_prompt`), `models.py` (`CommitSpecification`, `WorkerInput`)

## 4. `current_commit` is the only task-level input the worker nodes understand

The worker nodes read `current_commit` from state (`handler.py:331-348`) to build their prompt. The new node's output — a job description for fixing review findings — would need to either replace `current_commit` in state (confusing the original commit spec with a review remediation task) or introduce a new state key. Introducing a new key means the existing worker nodes won't read it without changes to the handler.

**Files affected:** `handler.py` (lines 331-348, 350-360), `archipelago_system.json` (state_mapping)

## 5. Role instructions conflict on second pass

The CLAUDE.md files baked into the container are designed for first-pass work. The code_writer instructions say "start by running all unit tests" and "make all tests pass." On a review remediation pass, the intent is narrower — fix specific findings. The code_writer doesn't know it's on a second pass addressing review feedback vs. a first pass implementing from scratch. The test writer has the same issue — its instructions say "Create unit tests for all acceptance criteria" which doesn't fit "update tests to address review finding F3."

**Files affected:** `docker/CLAUDE-unit-test-writer.md`, `docker/CLAUDE-source-code-writer.md`

## 6. Workspace state assumptions on re-entry

The code_writer commits and pushes on first pass (per `docker/CLAUDE.md`: "commit all files... pushed the commit to the remote repository"). When the review loop sends it back to code_writer, the workspace volume already contains those commits. The code_writer might try to redo all work, or get confused by already-passing tests. There is no signal in the workspace or state telling the worker "you're doing an incremental fix, not a fresh implementation."

**Files affected:** `docker/CLAUDE.md`, `docker/CLAUDE-source-code-writer.md`, `handler.py` (volume reuse logic lines 362-364)

## 7. Failure in the review loop is invisible to the parent pipeline

`worker_result` doesn't flow out of the kernel subgraph (output mapping only includes `commit_passed`, `workspace_volume`, `commit_hash`). If the new node fails or the review loop exhausts its iterations without resolution, the evaluator stub still returns `commit_passed: True`. The dispatcher moves to the next commit. The failure is silently swallowed.

**Files affected:** `archipelago_system.json` (state_mapping lines 53-64), `agents/evaluator.py`

## 8. Container overhead for a data transformation task

This node transforms structured JSON into a job description — a data transformation, not a coding task. Running Claude Code in an isolated container with workspace mount, WebSocket server, and headless adapter adds ~2 minutes of setup/teardown overhead. Whether that overhead is justified depends on whether the transformation needs codebase context (e.g., reading files to understand which findings require test changes vs. code-only changes).

**Files affected:** `handlers.py` (handler registry), role YAML for new node

## 9. `handler.py` conflates container lifecycle with task-specific behavior

`docker_worker_handler` is a single 200-line function serving all nodes. It mixes two concerns:

**Container lifecycle** (same for every node): Docker client init, WS server, container create/start, adapter connection wait, message loop, cleanup. This is ~150 lines of shared infrastructure.

**Task-specific behavior** (diverges per node): These are the pressure points where adding the new node (and future nodes) forces branching:

- **Input extraction** (lines 331-348) — hardcoded to expect `current_commit` with `CommitSpecification` fields. The new node reads `worker_result` (review JSON), not `current_commit`.
- **`_build_prompt`** (lines 129-155) — assumes title/acceptance_criteria/test_focus/implementation_focus. Review findings have a completely different shape.
- **Post-execution output** (lines 452-478) — always collects `progress.jsonl`, always builds `WorkerResult` with patches/evidence, always captures `commit_hash`. The reviewer produces review JSON; the new node produces a job description. Neither fits this mold cleanly.
- **`commit_hash` injection** (lines 412-413) — node-specific logic already leaking into the handler via `_spec_declares_field`.

Each new node type adds conditional branches to these four points. With 3 nodes today it's manageable. With 5-6 it becomes a dispatch table hidden inside if/elif chains. The natural fix is separating the container lifecycle (reusable) from a per-node strategy for input-to-prompt and output-to-state transformations.

**Files affected:** `docker_worker/handler.py`

## Deepest problem

Problems 2 and 4 together represent the core architectural gap. The kernel's state model assumes a single pass through a linear pipeline with one `current_commit` and one `worker_result` at a time. A review remediation loop fundamentally changes this to a multi-pass model where the task context shifts between "implement the spec" and "fix the review findings." The current state and prompt machinery don't distinguish between these modes.

## Communication model design decisions

The problems above stem from agent-foundry's communication model: all nodes read/write a shared flat dict with no structure around data flow between nodes. The following design decisions address this.

### 1. Transformations are nodes, not edge logic

Edges are purely topological — they define routing and data flow connections. No transform functions on edges. When data must be reshaped between nodes (e.g., review findings into a job description), an explicit transformer node does the work. This keeps every computation visible, testable, and composable.

**Addresses findings 3, 8:** The review-remediation node is a transformer node. It reads the review output shape and produces the input shape the downstream node needs. It doesn't need a Docker container — it's a data transformation, not a coding task. Finding 8's container overhead concern goes away because transformer nodes use lightweight handlers.

### 2. Two input sources for nodes

Nodes receive inputs from two sources:
- **Upstream transformer nodes** — explicit data flow through edges. Task-specific inputs like commit specifications or review findings.
- **Shared state** — ambient context that multiple nodes need, like `workspace_volume` or `repo_url`.

**Addresses findings 2, 4:** `worker_result` no longer needs to be a single overwritten key in shared state. Each transformer node reads the specific upstream output it needs and writes the specific downstream input required. Shared state is reserved for cross-cutting concerns (`workspace_volume`, `commit_hash`), not task-level data that varies per node.

### 3. Roles declare inputs, not nodes

Roles define the task-level contract via `inputs_schema`. Nodes are participants assigned to roles. This separation means the same role (e.g., `code_implement_from_tests`) can be used in different graph positions with different transformer nodes feeding it, without changing the role definition.

**Addresses finding 9:** The docker worker handler no longer needs to know how to extract inputs for every node type. The handler receives already-transformed inputs that match its role's contract. Input extraction logic moves to transformer nodes, and the handler focuses on container lifecycle.

### 4. Structured control for the implementation kernel

The TDD process is well-understood and sequential. The implementation kernel uses fixed topology with conditional edges. The review remediation loop is a conditional back-edge, not a dynamic dispatch.

**Addresses finding 1:** Conditional routing within the kernel subgraph is a natural extension of the existing edge model. The new topology adds a conditional back-edge from the review-remediation transformer to unit_test_writer or code_writer, with `max_iterations` to bound the loop.

### 5. Shared state is the current task

Shared state represents the current task being worked on. On the first pass, the task is the original commit spec (acceptance criteria, test specs, source modification specs). After a review, an LLM-powered node analyzes the review findings against the current code and produces a new task — same shape, scoped to just the changes the review requested. Downstream nodes (test writer, code writer) don't need delta awareness — they just execute whatever the current task says.

Transformer nodes, if needed, do only mechanical data mapping. The semantic analysis (determining what changes are needed based on review findings) is done by the LLM-powered node.

**Addresses findings 2, 4, 5, 6:** The test writer and code writer don't need to distinguish between a first pass and a review remediation pass. They receive a task and execute it. No mode switching, no delta detection, no workspace state confusion.

### 6. Agent-foundry will expand

These decisions are scoped to what the implementation kernel needs now. Agent-foundry will grow to support additional topologies (not just graphs), communication modes (not just shared state + transformer nodes), and control models (not just structural). Complexity is layered on as we learn, not designed speculatively.

## Implementation plan

### Part 1: Strict typing for subgraph state and shared data structures

Add Pydantic models for:
- **Kernel subgraph state** — the typed shape of the state dict flowing between nodes (current_commit, workspace_volume, commit_hash, worker_result, commit_passed)
- **Current commit / task** — the full current_commit shape (objective, repo_url, repo_ref, constraints plus the CommitSpecification fields) which currently has no model
- **Worker outputs per role** — the software reviewer produces a CodeReview JSON, not a generic WorkerResult. Each role's output should have its own typed model

Files: `src/archipelago/docker_worker/models.py`, `src/archipelago/models.py`

### Part 2: Composition-based agent classes

Create three agent classes in `src/archipelago/agents/`, one per docker worker node (unit_test_writer, code_writer, software_reviewer). Each class:
- Composes a docker lifecycle object (not inheritance)
- Defines its own prompt builder (typed input to prompt string)
- Defines its own output mapper (raw container output to typed result)

Files: `src/archipelago/agents/unit_test_writer.py`, `src/archipelago/agents/code_writer.py`, `src/archipelago/agents/software_reviewer.py`, `src/archipelago/handlers.py`

### Part 3: Refactor handler.py to single responsibility

Extract a `DockerLifecycle` class containing only container lifecycle management: Docker client init, WebSocket server, container create/start, adapter connection, message processing, evidence collection, cleanup. Remove all task-specific code (input extraction, prompt building, commit_hash injection, post-execution state assembly) — these now live in the agent classes.

Files: `src/archipelago/docker_worker/handler.py`
