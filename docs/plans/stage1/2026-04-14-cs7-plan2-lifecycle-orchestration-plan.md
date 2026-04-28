# CS7 Plan 2: Lifecycle Orchestration and Run Context — Implementation Plan

> **Roadmap:** `docs/plans/stage1/2026-04-03-review-feedback-loop-roadmap.md` (Change Set 7)
> **Prior plan:** `docs/plans/stage1/2026-04-13-cs7-plan1-agent-action-primitive-plan.md`
> **For agents:** Use team-dev (parallel) or sdd (sequential) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Where this plan fits in CS7

CS7 is split into four plans. This is Plan 2.

- **Plan 1 (shipped)** — `AgentAction` primitive + validator registry + compiler node. Compiler delegates to a stub `run_agent_in_container` that raises `NotImplementedError`.
- **Plan 2 (this document)** — roadmap Tasks 3–4. Replaces the stub with a real container executor, defines the non-success envelope contract, introduces `AgentRunContext` + `Responder` + `AgentContainerRegistry`, and writes run artifacts to disk.
- **Plan 3** — `lessons-learned` skill move + base `CLAUDE.md` update. Independent of Plan 2.
- **Plan 4** — four Archipelago agents + two `FunctionAction`s. Depends on Plan 2.

Dependency shape: Plan 1 → Plan 2 → Plan 4; Plan 3 is independent.

**Goal:** Deliver the real `AgentAction` execution path. After Plan 2, a product can invoke `run_primitive_plan` with a `PrimitivePlan` containing `AgentAction`s and watch them actually execute against Claude Code in Docker containers with structured output, responder-mediated clarification/permission, container reuse across invocations, and a durable on-disk artifact trail.

**Architecture:** The new `agent_foundry.orchestration` package owns all run-scoped machinery: `AgentRunContext` (run-scoped dependency bundle), `AgentContainerRegistry` (one container per `AgentAction` per run), `LifecycleWriter` (append-only jsonl), the container-mode `executor` that replaces the Plan 1 stub, and artifact generation (directory bootstrap, `inspect-workspace.sh`, `summary.txt` renderer). The new `agent_foundry.responders` package owns the `Responder` protocol, the request/response types, and the shipped `StdinResponder`. **The executor drives `claude` directly from the host via Docker's `exec_run` API** — no in-container adapter process, no WebSocket server. Each turn is a fresh `claude` CLI process invoked via `handle._container.exec_run(...)` inside the long-running container; `claude --resume <session-id>` threads the session across turns. Stream-json comes back on the exec's stdout and is parsed host-side using the existing `acp/claude_code_events.py` typed models. All retry logic (missing structured output, cold-start, `AgentFilePath` verification) runs host-side. File-backed agent outputs are declared via a new `AgentFilePath` Annotated marker in `agent_foundry.models.markers`; the executor (host-side) walks the schema for these markers, verifies files via `ContainerManager.read_file_from_container` after every successful turn, and issues one bounded `--resume` correction turn if any are missing or oversized. Plan 1's `AgentAction` primitive is tightened: `FileCollectionChannel` / `StructuredOutputChannel` / `response_channel` are removed (every agent is structured-output), `ContainerReusePolicy.NEW_EACH_TIME` is dropped, and `reuse_policy` loses its default. `FunctionAction.function` evolves to `Callable[[I, AgentRunContext], O]` so any primitive that does work can emit lifecycle events.

**Tech Stack:** Python 3.13+, Pydantic v2, LangGraph, Docker SDK for Python, pytest (with pytest-xdist). Archipelago remains Python 3.14. Agent Foundry's existing `websockets` dependency is used only by legacy (`docker_worker/`) agents until CS11; the new executor does not use WebSockets.

**Scope boundary:** This plan stops at the Agent Foundry platform layer. The four Archipelago agents, their instructions, and the `CommitAction`/`SubmitPRAction` `FunctionAction`s are Plan 4. The domain-level `summary.txt` renderer that groups by change set and step is CS9 Task 4. Deprecated `docker_worker/` modules (`interrupts.py`, `progress.py`, `recovery.py`, `protocol.py`, marker machinery) keep functioning for the legacy `UnitTestWriter`/`CodeWriter`/`SoftwareReviewer` agents until CS8 evolves them and CS11 deletes them wholesale — Plan 2 neither modifies nor imports from `docker_worker/`.

---

## Design decisions (from brainstorm)

These are the decisions locked during the brainstorm session on 2026-04-14. They are the premises of this plan; if any needs to change, re-enter the brainstorm before modifying tasks.

1. **Non-success envelope contract.** `success` → return `O`. `clarification_needed` / `permission_needed` → resolve `Responder` via `ResponderProvider`, call `respond()`, feed answer back via session resume, loop within the same turn. `failed` → raise `AgentFailedError(reason=...)`. Responder raising any exception → `AgentFailedError(reason=f"responder failed: ...")`. Escalation bridge (responder → LangGraph interrupt) deferred.
2. **Responder injection is per-system.** A single `ResponderProvider` (callable `() -> Responder`) is passed into `run_primitive_plan`; the executor resolves it per-request, so hosts can swap responders mid-run by mutating what the provider returns. Per-`AgentAction` overrides deferred.
3. **One container per `AgentAction` per run.** Registry keyed by `id(primitive)`. Container is created lazily on first invocation, destroyed at run teardown. No cross-run reuse. No pool.
4. **Two reuse policies only.** `REUSE_RESUME` (same container, `--resume` same session) and `REUSE_NEW_SESSION` (same container, fresh session per invocation). `NEW_EACH_TIME` is dropped. `reuse_policy` is required (no default).
5. **Instructions are run-scoped.** Injected once at container creation (via `ACP_ROLE_INSTRUCTIONS_PATH` env var the existing entrypoint already consumes), never re-injected. Instruction file edits apply to the next run.
6. **Single response channel.** Every agent emits structured output via `--json-schema`. `FileCollectionChannel` is dropped. File-based interchange between agents is expressed as path fields on the output model marked with `Annotated[str, AgentFilePath(...)]`. The **host-side executor** verifies declared files via `ContainerManager.read_file_from_container` after each turn and issues one bounded `--resume` correction turn if any are missing or oversized; the executor also snapshots verified files to the artifacts dir.
7. **Platform default file-size limit: 10MB per `AgentFilePath`-marked field.** Overridable per field.
8. **Executor contract:** `executor(*, primitive: AgentAction, prompt: str, run_ctx: AgentRunContext) -> O`.
9. **`AgentRunContext`** carries `run_id`, `artifacts_dir`, `container_registry`, `responder_provider`, `lifecycle_writer`, `cancel_event`.
10. **`FunctionAction.function`** evolves to `Callable[[I, AgentRunContext], O]`. Every user-supplied primitive callable receives the run context for domain event hooks.
11. **Run artifacts layout** (Agent Foundry-generic; Archipelago-domain rendering is CS9):

    ```
    <artifacts_dir>/<run-id>/
    ├── lifecycle.jsonl
    ├── summary.txt
    ├── inspect-workspace.sh
    └── <agent-name>/
        ├── container.log
        └── turns/<n>/
            ├── prompt.txt
            ├── envelope.json
            ├── output.json
            └── collected_files/
    ```

12. **Workspace volume is one-per-run, shared across all `AgentAction` containers in that run, retained after run end** (no auto-cleanup; deferred).
13. **`docker_worker/` untouched by Plan 2.** Deleted in CS11.

---

## Codebase anchors (verified against current source)

These anchors were confirmed by reading the current Agent Foundry source during plan expansion. They are the integration points Plan 2 extends.

- **`ContainerManager`** — `agent_foundry/acp/container.py`. Sync API. Relevant methods: `create_container(image, workspace_volume, constraints, extra_env) -> ContainerHandle`, `start(handle)`, `validate_image(handle, required_commands)`, `stop(handle, timeout)`, `destroy(handle)`, `read_file_from_container(handle, path) -> str | None`, `copy_from_container(handle, container_path, host_path) -> bool`, `write_file_to_container(handle, container_path, content)`, `cleanup_all()`. No `async` methods — the registry wraps these in `asyncio.to_thread` when called from async contexts.
- **`ClaudeCodeAdapter`** — `agent_foundry/acp/adapters/claude_code.py`. Runs **inside** the container (the `exec gosu claude python /home/claude/adapter.py --protocol $WS_URL ...` line in `agent_foundry/acp/docker/entrypoint.sh`). `run_turn(prompt, ws, protocol_session_id, claude_session_id, timeout, json_schema) -> TurnResult`. Already captures `claude_session_id` from `SystemInitEvent`. Already has one-shot structured-output retry when no `StructuredOutput` tool call is captured (`_in_structured_output_retry`). Plan 2 extends it with an analogous one-shot retry on `AgentFilePath` verification failures.
- **`AgentTurnEnvelope[T]`** — `agent_foundry/acp/agent_turn_envelope.py`. Outcome variants are `SuccessOutcome[T]`, `ClarificationOutcome`, `PermissionOutcome`, `FailureOutcome` (discriminator: `kind: Literal[TurnOutcomeKind.VARIANT]`). Plan 2 maps these envelope outcomes to responder requests without redefining the outcome types.
- **`to_claude_code_schema`** — `agent_foundry/acp/schema_tools.py`. Inlines `$defs/$ref` and strips the OpenAPI `discriminator` keyword. Preserves every other key in the walked tree. `x-agent-file-path` extensions will survive flattening unchanged because the walker only drops keys named `"discriminator"` and `"$defs"`. Task D.3 adds a regression test.
- **`run_primitive_plan`** (existing) — `agent_foundry/compiler/primitive_compiler.py`. Currently sync, accepts `(plan, initial_state, config)` and calls `graph.invoke`. Plan 2 adds an async variant `run_primitive_plan` with the new signature (see G.2). The existing sync function is renamed `run_primitive_plan_sync` and kept for non-`AgentAction` callers; it emits a `DeprecationWarning` nudging toward the async variant.
- **`run_agent_in_container`** — `agent_foundry/acp/agent_runner.py`. Currently a stub raising `NotImplementedError`. Plan 2 replaces it by re-exporting from `orchestration.container_executor`; the first wiring happens in Phase F0 (Task F0.4), and Phase F.4 becomes a confirmation rather than the first wiring point.
- **`_compile_agent_action`** — in `primitive_compiler.py`. Currently calls `executor(primitive=action, prompt=prompt)`. Plan 2 extends this call site to pass `run_ctx=run_ctx`, using a module-level `contextvars.ContextVar[AgentRunContext | None]` that `run_primitive_plan` sets before compilation.
- **`_compile_function_action`** — same module. Calls `fn(model_input)` or `fn()` based on arity. Plan 2 widens this to pass `(model_input, run_ctx)` when arity ≥ 2.

---

## Sequencing note — Phase 0 and Phase F0 precede Phase A

Plan 2 execution begins with two small phases that verify and establish the foundation before the existing Phase A–H work runs. **Phase 0** (foundation smoke test) runs first and exercises the existing base ACP image, `ContainerManager`, and `ClaudeCodeAdapter` end-to-end against real Claude Code — proving the substrate Plan 2 builds on actually works. **Phase F0** (minimum viable executor) runs next and delivers a working `run_agent_in_container` with minimum scope: one turn, success-only envelopes, no responders, no artifacts dir, no container reuse, no file-path markers, no summary, no lifecycle events. **Phase A onward** then proceeds on the verified foundation; nothing in the existing phases is deleted — they elaborate on, tighten, and extend F0.

Phase ordering: **Phase 0 → Phase F0 → Phase A → Phase B → Phase C → Phase D → Phase E → Phase F → Phase G → Phase H**.

## Architecture note — host-driven execution

Plan 2's new executor drives `claude` directly from the host via Docker's `exec_run` API. There is no in-container Python adapter process, and no WebSocket server between host and container, for any new-executor code path. Each turn of an `AgentAction` invocation is a fresh `claude` CLI process spawned inside the long-running container via `handle._container.exec_run(cmd, stream=True)`. Session continuity across turns is provided by `claude --resume <session-id>`. Stream-json output is read from the exec call's stdout and parsed host-side using the existing transport-agnostic typed event models in `agent_foundry/acp/claude_code_events.py`.

- **Unused by the new executor (but retained for legacy agents until CS11):** `ClaudeCodeAdapter` (in-container adapter process), the WebSocket server in `agent_foundry/acp/session.py`, `AdapterBase` / `TurnResult` in `agent_foundry/acp/adapter.py`, the entrypoint's `gosu claude python /home/claude/adapter.py --protocol $WS_URL` adapter launch. `docker_worker/`-backed agents (`UnitTestWriter`, `CodeWriter`, `SoftwareReviewer`) still depend on this path.
- **Ported host-side into `agent_foundry/orchestration/`:** the `_build_claude_cmd` helper (into `orchestration/claude_cmd.py`); stream-json line parsing (continues to delegate to `acp/claude_code_events.py` — transport-agnostic by construction); `StructuredOutput` tool_use detection; one-shot retry on missing structured output (CS6.5 Task 4e logic); cold-start retry (anthropics/claude-code#23265); refusal / `max_tokens` stop-reason handling; turn-completion detection; session-id capture from the first `SystemInitEvent`.
- **Dead code after CS11:** WebSocket transport between host and in-container adapter; the in-container adapter process itself; text-marker protocol detection.

This decision does not change the envelope protocol (`AgentTurnEnvelope[T]` with four outcome variants), the responder model, the reuse-policy semantics, or any Plan 2 design decision. It changes only the transport by which the host talks to `claude`.

## Archipelago leverage

The Archipelago `docker_worker/env.py` composition pattern (how env vars are assembled for a worker container) is lifted into `agent_foundry/orchestration/env.py` as part of Task F0.2. Everything else in Archipelago's `docker/` and `docker_worker/` modules stays where it is until CS11 deletes them. The agent-specific CLAUDE.md append mechanism already exists in the base ACP image's `entrypoint.sh` (`ACP_ROLE_INSTRUCTIONS_PATH` appended to `/home/claude/.claude/CLAUDE.md`); Plan 2 uses this mechanism as-is rather than redesigning instruction injection.

---

## File structure

### Agent Foundry (primary home of Plan 2)

| File | Action | Responsibility |
|------|--------|---------------|
| `agent-foundry/src/agent_foundry/primitives/models.py` | Modify | Drop `NEW_EACH_TIME`, `StructuredOutputChannel`, `FileCollectionChannel`, `ResponseChannel`, `AgentAction.response_channel`; remove `reuse_policy` default; evolve `FunctionAction.function` signature to include `AgentRunContext` (forward-referenced) |
| `agent-foundry/src/agent_foundry/primitives/__init__.py` | Modify | Update exports to match model changes; finalize `FunctionAction` forward ref against `AgentRunContext` |
| `agent-foundry/src/agent_foundry/models/__init__.py` | Create | Package init for new `models` namespace (shared type markers) |
| `agent-foundry/src/agent_foundry/models/markers.py` | Create | `AgentFilePath` Annotated metadata marker; `PLATFORM_DEFAULT_MAX_FILE_BYTES = 10_000_000`; `FilePathFieldSpec`; `walk_file_path_fields`; `extract_paths` |
| `agent-foundry/src/agent_foundry/responders/__init__.py` | Create | Exports |
| `agent-foundry/src/agent_foundry/responders/models.py` | Create | `ResponderKind`, `ClarificationRequest`, `PermissionRequest`, `ResponderRequest` (discriminated union), `ResponderResponse`, `ResponderContext`; `build_request_from_outcome` helper that maps `ClarificationOutcome`/`PermissionOutcome` → request |
| `agent-foundry/src/agent_foundry/responders/protocol.py` | Create | `Responder` Protocol, `ResponderProvider` alias, `static_provider` helper |
| `agent-foundry/src/agent_foundry/responders/stdin.py` | Create | `StdinResponder` concrete implementation; internal `asyncio.Lock` for serialization |
| `agent-foundry/src/agent_foundry/orchestration/__init__.py` | Create | Exports |
| `agent-foundry/src/agent_foundry/orchestration/errors.py` | Create | `AgentFailedError` |
| `agent-foundry/src/agent_foundry/orchestration/run_context.py` | Create | `AgentRunContext` (arbitrary-types Pydantic model); `build_run_context()` factory; module-level `current_run_context: ContextVar[AgentRunContext \| None]` |
| `agent-foundry/src/agent_foundry/orchestration/registry.py` | Create | `LiveContainer`, `AgentContainerRegistry`; lazy `get_or_create()`; `record_session_id()`; `shutdown_all()` |
| `agent-foundry/src/agent_foundry/orchestration/lifecycle_writer.py` | Create | `LifecycleWriter` — append-only jsonl writer with auto-stamped `ts`/`run_id`; thread-safe |
| `agent-foundry/src/agent_foundry/orchestration/artifacts.py` | Create | `bootstrap_run_artifacts`, `agent_turn_dir`, `agent_log_path`, `write_inspect_workspace_script` |
| `agent-foundry/src/agent_foundry/orchestration/summary.py` | Create | `render_summary()` — reads `lifecycle.jsonl`, emits generic `summary.txt` |
| `agent-foundry/src/agent_foundry/orchestration/lifecycle_events.py` | Create | `StrEnum` of event names emitted by the executor + registry + compiler nodes; stable wire constants |
| `agent-foundry/src/agent_foundry/orchestration/container_executor.py` | Create | Real `run_agent_in_container`; inner envelope loop; reuse-policy dispatch; file snapshotting; event emission; host-driven `exec_run` transport |
| `agent-foundry/src/agent_foundry/orchestration/claude_cmd.py` | Create | `build_claude_cmd(prompt, session_id, skip_permissions, json_schema) -> list[str]` ported from `acp/adapters/claude_code.py::_build_claude_cmd`; host-side stream-json driver that iterates `exec_run` output, dispatches to `parse_stream_event`, tracks `SystemInitEvent` and `StructuredOutput` tool-use |
| `agent-foundry/src/agent_foundry/acp/agent_runner.py` | Modify | Delete stub; re-export `run_agent_in_container` from `orchestration.container_executor` for backward-compat import paths |
| `agent-foundry/src/agent_foundry/acp/adapters/claude_code.py` | No change | Retained as-is for legacy (`docker_worker/`) agents until CS11. Plan 2's new executor does not import this module. Host-side equivalents live in `orchestration/claude_cmd.py` and `orchestration/container_executor.py`. |
| `agent-foundry/src/agent_foundry/acp/schema_tools.py` | Modify | No behavior change, only a regression test (D.3) pinning `x-agent-file-path` survival |
| `agent-foundry/src/agent_foundry/compiler/primitive_compiler.py` | Modify | Pass `run_ctx` through to `AgentAction.executor` and widen `FunctionAction.function` call to `(state, ctx)` when arity ≥ 2; use `contextvars.ContextVar` for compilation-time context lookup; propagate `AgentFailedError` |
| `agent-foundry/src/agent_foundry/compiler/__init__.py` | Modify | Export the new async `run_primitive_plan`; keep legacy `run_primitive_plan_sync` |

### Agent Foundry tests

| File | Action | Coverage |
|------|--------|----------|
| `tests/agent_foundry/primitives/test_agent_action_model.py` | Modify | Remove `StructuredOutputChannel`/`FileCollectionChannel`/`NEW_EACH_TIME` tests; add required-`reuse_policy` test; assert no `response_channel` field |
| `tests/agent_foundry/primitives/test_function_action_signature.py` | Create | `FunctionAction.function` must accept `(I, AgentRunContext)`; accepts a callable of arity 2; constructing with arity-1 callable still validates (back-compat) but runtime dispatch passes ctx when callable accepts it |
| `tests/agent_foundry/models/test_agent_file_path_marker.py` | Create | Marker carries size limit; default 10MB; custom value propagates; survives `to_claude_code_schema` as `x-agent-file-path`; `walk_file_path_fields` and `extract_paths` behaviors |
| `tests/agent_foundry/responders/test_responder_protocol.py` | Create | Request/response serialization; discriminator routing; `build_request_from_outcome` mapping |
| `tests/agent_foundry/responders/test_stdin_responder.py` | Create | Happy path via fake stdin; serialization under concurrent calls via `asyncio.gather`; queue-depth prompt indicator |
| `tests/agent_foundry/orchestration/test_run_context.py` | Create | Construction, required fields, `run_id` uniqueness, cancel_event wiring, frozen mutation, `current_run_context` ContextVar |
| `tests/agent_foundry/orchestration/test_registry.py` | Create | Lazy creation, identity keying, shutdown under exceptions, idempotent destroy, `record_session_id` |
| `tests/agent_foundry/orchestration/test_lifecycle_writer.py` | Create | Append-only, auto-stamped fields, concurrency safety (20 threads), durable partial log on crash |
| `tests/agent_foundry/orchestration/test_artifacts.py` | Create | Directory layout, `inspect-workspace.sh` contents + executable bit, collision raises |
| `tests/agent_foundry/orchestration/test_summary.py` | Create | Renders generic summary from a known jsonl fixture; partial runs render cleanly; empty file renders header only |
| `tests/agent_foundry/orchestration/test_container_executor.py` | Create | Envelope outcomes (all four), responder round-trip, file snapshotting, reuse policies, cancel_event, session id recording |
| `tests/agent_foundry/orchestration/fakes.py` | Create | `FakeDockerClient`, `FakeContainerManager` (or direct wrap), `FakeClaudeCodeDriver`, `FakeResponder`, `build_fake_run_context()` |
| `tests/agent_foundry/orchestration/test_file_path_verification.py` | Create | Schema walker finds marked fields; happy path, missing file, oversized file, one retry then success, one retry still failing; host-side executor issues correction-prompt `--resume` turn on violation |
| `tests/agent_foundry/orchestration/test_claude_cmd.py` | Create | `build_claude_cmd` produces correct argv for each combination of `session_id`, `skip_permissions`, `json_schema`; stream-json driver parses a canned line stream into (envelope, session_id) |
| `tests/agent_foundry/acp/test_schema_tools_marker_preserved.py` | Create | `to_claude_code_schema(ModelWithAgentFilePath)` preserves `x-agent-file-path` on the field |
| `tests/agent_foundry/compiler/test_agent_action_compiler.py` | Modify | Pass real `run_ctx` stub; assert executor kwargs include `run_ctx`; `FunctionAction` node passes `run_ctx` through when the callable accepts it |
| `tests/agent_foundry/compiler/test_run_primitive_plan.py` | Create | End-to-end: plan with `AgentAction` + `FunctionAction` runs against a `FakeContainerManager` + `FakeClaudeCodeDriver`; artifacts layout verified; SIGINT triggers clean teardown |
| `tests/agent_foundry/integration/test_plan2_end_to_end.py` | Create | Docker-gated integration test exercising a real container with a scripted claude binary (skipped if no daemon) |

---

## Tech assumptions

- Tests live under `agent-foundry/tests/agent_foundry/` following the package structure.
- Test runner: `pdm test-unit` (from the agent-foundry repo root) for unit tests; `pdm test-integration` for integration tests (Docker-gated — skip if no daemon).
- Commit convention (per `archipelago/jig.config.md`): `type(scope): message`. Scopes used in Plan 2: `primitives`, `responders`, `orchestration`, `acp`, `compiler`, `models`.
- Every step lists exact paths, exact commands, and expected pass/fail states.
- All new code is typed strictly (Pyright strict). Run `pdm run typecheck` before each commit.
- Async style: every new public async function uses `async def` + `await`; never `asyncio.run` inside library code. The one exception is `run_primitive_plan` where the application entry point is a sync caller — but even there we provide both an `async def run_primitive_plan_async` and a thin `run_primitive_plan` sync wrapper that does `asyncio.run(run_primitive_plan_async(...))`.

---

## Phase 0 — Foundation smoke test

Phase 0 verifies, in a single integration test, that the Plan 2 foundation already works: the base ACP image, `ContainerManager`, `ClaudeCodeAdapter`, and `to_claude_code_schema` produce a validated structured-output payload from a real Claude Code process in a real container. If this fails, **halt Plan 2** and fix the substrate before proceeding.

### Task 0.1: Foundation smoke test (integration)

**Files:**
- `agent-foundry/tests/agent_foundry/integration/__init__.py` (create if missing — empty)
- `agent-foundry/tests/agent_foundry/integration/test_foundation_smoke.py` (new)

No T/I split — this is a single end-to-end integration assertion.

- [ ] **Step 1: Create `test_foundation_smoke.py`.** Verbatim:

    ```python
    """Foundation smoke test — proves base ACP image + ContainerManager +
    host-driven `docker exec` of `claude --json-schema` + stream-json
    parsing + AgentTurnEnvelope validation work end-to-end against real
    Claude Code. If this fails, Plan 2 cannot proceed.

    This test exercises the exact transport Plan 2's executor uses
    (docker exec). It does not exercise the in-container adapter or WS
    server — those are legacy paths retained for docker_worker/ agents.
    """
    from __future__ import annotations

    import json
    import os
    import uuid
    from typing import Any

    import pytest
    from pydantic import BaseModel

    from agent_foundry.acp.agent_turn_envelope import AgentTurnEnvelope
    from agent_foundry.acp.container import ContainerManager
    from agent_foundry.acp.schema_tools import to_claude_code_schema


    class Ping(BaseModel):
        echoed: str


    @pytest.mark.integration
    def test_foundation_smoke_real_claude_code() -> None:
        # Fail loudly — not skip — when the OAuth token is missing.
        oauth_token = os.environ["CLAUDE_CODE_OAUTH_TOKEN"]

        # Only skip on Docker unavailability.
        try:
            import docker
            client = docker.from_env()
            client.ping()
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"docker daemon unavailable: {e}")

        base_image = os.environ.get("ACP_BASE_IMAGE", "agent-foundry-base:latest")
        workspace_volume = f"foundation-smoke-{uuid.uuid4().hex[:8]}"

        manager = ContainerManager(client=client, default_image=base_image)
        schema = to_claude_code_schema(AgentTurnEnvelope[Ping])

        handle = manager.create_container(
            workspace_volume=workspace_volume,
            extra_env={"CLAUDE_CODE_OAUTH_TOKEN": oauth_token},
        )
        try:
            manager.start(handle)

            prompt = "Return structured output with echoed='foo'."
            exec_cmd = [
                "claude", "-p", prompt,
                "--output-format", "stream-json", "--verbose",
                "--json-schema", json.dumps(schema),
            ]
            exit_code, output = handle._container.exec_run(exec_cmd, demux=False)
            assert exit_code == 0, f"claude exec failed: {output!r}"

            structured: dict[str, Any] | None = None
            for raw_line in output.decode().splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if evt.get("type") == "assistant":
                    for block in evt.get("message", {}).get("content", []):
                        if (
                            block.get("type") == "tool_use"
                            and block.get("name") == "StructuredOutput"
                        ):
                            structured = block.get("input")
                            break

            assert structured is not None, "no StructuredOutput tool use captured"
            envelope = AgentTurnEnvelope[Ping].model_validate(structured)
            assert envelope.outcome.kind == "success"
            assert isinstance(envelope.outcome.payload, Ping)
            assert envelope.outcome.payload.echoed  # non-empty
        finally:
            try:
                manager.stop(handle, timeout=5)
            except Exception:  # noqa: BLE001
                pass
            manager.destroy(handle)
    ```

  Pattern-match against existing integration tests in `agent-foundry/tests/agent_foundry/acp/` for fixture and teardown style; adjust imports if names differ.

- [ ] **Step 2: Run the test.** `cd agent-foundry && pdm test-integration tests/agent_foundry/integration/test_foundation_smoke.py`. Expected: PASS.
- [ ] **Step 3: On failure, halt Plan 2.** Investigate the base image build, `ContainerManager`, `ClaudeCodeAdapter`, or `to_claude_code_schema` before starting Phase F0. Do not proceed to later phases with a broken foundation.
- [ ] **Step 4: Commit.** `test(acp): add foundation smoke test against real Claude Code in container`.

---

## Phase F0 — Minimum viable executor

Phase F0 delivers a working `run_agent_in_container` with the minimum scope that still lets a product run a real `AgentAction` end-to-end. Intentionally out of scope for F0: responders, artifacts dir, container reuse, file-path markers, summary, lifecycle events, error/clarification/permission envelopes. Everything except happy-path success raises `NotImplementedError` with a pointer to the later phase that fills it in. Phases A–H then elaborate on, tighten, and extend F0 — they do not supersede it.

### Task F0.1: Minimal `AgentRunContext` + no-op `LifecycleWriter`

**Files:**
- `agent-foundry/src/agent_foundry/orchestration/__init__.py` (create — empty or minimal export)
- `agent-foundry/src/agent_foundry/orchestration/run_context.py` (new)
- `tests/agent_foundry/orchestration/__init__.py` (create if missing — empty)
- `tests/agent_foundry/orchestration/test_run_context_f0.py` (new)

**Task F0.1-T (tests):**

- [ ] **Step 1: Write `test_run_context_f0.py`.** Verbatim:

    ```python
    from __future__ import annotations

    import pytest
    from pydantic import ConfigDict

    from agent_foundry.orchestration.run_context import (
        AgentRunContext,
        NoOpLifecycleWriter,
    )


    def test_agent_run_context_has_required_f0_fields() -> None:
        ctx = AgentRunContext(
            run_id="run-1",
            container_registry=object(),
            lifecycle_writer=NoOpLifecycleWriter(),
            env={"CLAUDE_CODE_OAUTH_TOKEN": "tok"},
        )
        assert ctx.run_id == "run-1"
        assert ctx.env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok"


    def test_no_op_lifecycle_writer_accepts_append_and_discards() -> None:
        writer = NoOpLifecycleWriter()
        # Must not raise; must not persist anywhere visible.
        writer.append({"type": "anything", "payload": {"x": 1}})
        writer.append({"type": "other"})
        # No public read surface — the whole point is that it's a sink.


    def test_agent_run_context_env_is_required() -> None:
        with pytest.raises(Exception):
            AgentRunContext(  # type: ignore[call-arg]
                run_id="r",
                container_registry=object(),
                lifecycle_writer=NoOpLifecycleWriter(),
            )
    ```

- [ ] **Step 2: Run tests — expect failure** (module not yet created).

**Task F0.1-I (impl):**

- [ ] **Step 3: Implement `orchestration/run_context.py`.** Verbatim:

    ```python
    """Minimal AgentRunContext for Phase F0.

    Phase B (Task B.1) replaces this with the full context carrying
    artifacts_dir, responder_provider, cancel_event, and a real
    LifecycleWriter. F0 only needs enough context to stand up a
    container and run one turn.
    """
    from __future__ import annotations

    from typing import Any, Protocol

    from pydantic import BaseModel, ConfigDict


    class LifecycleWriter(Protocol):
        def append(self, event: dict[str, Any]) -> None: ...


    class NoOpLifecycleWriter:
        """Satisfies the LifecycleWriter protocol by discarding all events.

        Phase B Task B.2 introduces the real append-only jsonl writer.
        """

        def append(self, event: dict[str, Any]) -> None:  # noqa: D401
            return None


    class AgentRunContext(BaseModel):
        """Minimum-viable run context for the F0 executor.

        Fields:
          - run_id: unique identifier for this run
          - container_registry: AgentContainerRegistry (duck-typed in F0)
          - lifecycle_writer: any object satisfying LifecycleWriter protocol
          - env: container env dict (must include CLAUDE_CODE_OAUTH_TOKEN)
        """

        model_config = ConfigDict(arbitrary_types_allowed=True)

        run_id: str
        container_registry: Any
        lifecycle_writer: Any
        env: dict[str, str]
    ```

- [ ] **Step 4: Run tests — expect pass.**
- [ ] **Step 5: Commit.** `feat(orchestration): add minimal AgentRunContext and NoOpLifecycleWriter (F0)`.

### Task F0.2: Env builder

**Files:**
- `agent-foundry/src/agent_foundry/orchestration/env.py` (new)
- `tests/agent_foundry/orchestration/test_env_f0.py` (new)

Modeled loosely on Archipelago's `docker_worker/env.py` — compose the agent-specific env vars the entrypoint expects (`CLAUDE_CODE_OAUTH_TOKEN`, `ACP_ROLE_INSTRUCTIONS_PATH`) plus caller-supplied extras into a single dict.

**Task F0.2-T (tests):**

- [ ] **Step 1: Write `test_env_f0.py`.** Verbatim:

    ```python
    from __future__ import annotations

    from unittest.mock import MagicMock

    from agent_foundry.orchestration.env import build_container_env


    def test_build_container_env_includes_required_keys() -> None:
        primitive = MagicMock()
        env = build_container_env(
            primitive,
            oauth_token="tok-abc",
            role_instructions_path="/home/claude/role-instructions.md",
        )
        assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok-abc"
        assert env["ACP_ROLE_INSTRUCTIONS_PATH"] == "/home/claude/role-instructions.md"


    def test_build_container_env_merges_extra() -> None:
        primitive = MagicMock()
        env = build_container_env(
            primitive,
            oauth_token="t",
            role_instructions_path="/r",
            extra={"FOO": "bar", "BAZ": "1"},
        )
        assert env["FOO"] == "bar"
        assert env["BAZ"] == "1"


    def test_extra_cannot_silently_override_required_keys() -> None:
        primitive = MagicMock()
        env = build_container_env(
            primitive,
            oauth_token="real",
            role_instructions_path="/r",
            extra={"CLAUDE_CODE_OAUTH_TOKEN": "fake"},
        )
        # Required keys win over extra.
        assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "real"
    ```

- [ ] **Step 2: Run tests — expect failure.**

**Task F0.2-I (impl):**

- [ ] **Step 3: Implement `orchestration/env.py`.** Verbatim:

    ```python
    """Container env composition for the F0 executor.

    Lifted loosely from Archipelago's docker_worker/env.py composition
    pattern: caller-supplied extras merge first, then required agent
    env vars overwrite to guarantee they win.
    """
    from __future__ import annotations

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from agent_foundry.primitives.models import AgentAction


    def build_container_env(
        primitive: "AgentAction",
        *,
        oauth_token: str,
        role_instructions_path: str,
        extra: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Compose the env dict passed to ContainerManager.create_container.

        The required agent keys (CLAUDE_CODE_OAUTH_TOKEN,
        ACP_ROLE_INSTRUCTIONS_PATH) always win over ``extra``; callers use
        ``extra`` for optional additions (REPO_URL, GIT_USER_NAME, etc.).
        """
        env: dict[str, str] = {}
        if extra:
            env.update(extra)
        env["CLAUDE_CODE_OAUTH_TOKEN"] = oauth_token
        env["ACP_ROLE_INSTRUCTIONS_PATH"] = role_instructions_path
        return env
    ```

- [ ] **Step 4: Run tests — expect pass.**
- [ ] **Step 5: Commit.** `feat(orchestration): add container env builder (F0)`.

### Task F0.3: Minimal `AgentContainerRegistry` (new-container-per-invocation mode)

**Files:**
- `agent-foundry/src/agent_foundry/orchestration/registry.py` (new — F0 surface only)
- `tests/agent_foundry/orchestration/fakes.py` (new — F0 shape)
- `tests/agent_foundry/orchestration/test_registry_f0.py` (new)

Only the new-container-per-invocation path ships in F0. Phase B Task B.4 extends this with reuse-policy-aware `get_or_create`.

**Task F0.3-T (tests):**

- [ ] **Step 1: Write `tests/agent_foundry/orchestration/fakes.py` (F0 shape).** Verbatim:

    ```python
    """Test fakes for the orchestration layer (F0 shape).

    Phase B.4 and F.3 extend FakeContainerManager and add FakeContainer
    features (exec_run scripting, put_archive round-trip, etc.). F0
    only needs create/start/write_file/destroy.
    """
    from __future__ import annotations

    from dataclasses import dataclass, field
    from typing import Any


    @dataclass
    class FakeContainerHandle:
        container_id: str
        workspace_path: str = "/workspace"
        status: str = "created"
        files: dict[str, str] = field(default_factory=dict)
        env: dict[str, str] = field(default_factory=dict)


    class FakeContainerManager:
        """F0 shape: create_container / start / write_file_to_container /
        destroy. Phase B.4 and F.3 extend.
        """

        def __init__(self) -> None:
            self.handles: list[FakeContainerHandle] = []
            self._next_id = 0

        def create_container(
            self,
            image: str | None = None,
            workspace_volume: str = "",
            constraints: Any = None,
            extra_env: dict[str, str] | None = None,
        ) -> FakeContainerHandle:
            self._next_id += 1
            h = FakeContainerHandle(
                container_id=f"fake-{self._next_id}",
                env=dict(extra_env or {}),
            )
            self.handles.append(h)
            return h

        def start(self, handle: FakeContainerHandle) -> None:
            handle.status = "running"

        def write_file_to_container(
            self, handle: FakeContainerHandle, path: str, content: str
        ) -> None:
            handle.files[path] = content

        def destroy(self, handle: FakeContainerHandle) -> None:
            handle.status = "destroyed"

        def stop(self, handle: FakeContainerHandle, timeout: int = 10) -> None:
            handle.status = "stopped"
    ```

- [ ] **Step 2: Write `test_registry_f0.py`.** Verbatim:

    ```python
    from __future__ import annotations

    import asyncio
    from unittest.mock import MagicMock

    import pytest

    from agent_foundry.orchestration.registry import AgentContainerRegistry

    from .fakes import FakeContainerManager


    @pytest.mark.asyncio
    async def test_create_for_invocation_writes_instructions_and_starts() -> None:
        fake_mgr = FakeContainerManager()
        registry = AgentContainerRegistry(
            manager=fake_mgr,
            base_image_tag="agent-foundry-base:test",
            workspace_volume="vol-1",
        )
        primitive = MagicMock()
        live = await registry.create_for_invocation(
            primitive,
            oauth_token="tok",
            instructions_text="# agent role\nBe precise.",
        )
        assert live.handle.status == "running"
        assert live.handle.env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok"
        assert live.handle.env["ACP_ROLE_INSTRUCTIONS_PATH"]
        written_path = live.handle.env["ACP_ROLE_INSTRUCTIONS_PATH"]
        assert live.handle.files[written_path] == "# agent role\nBe precise."


    @pytest.mark.asyncio
    async def test_destroy_marks_handle_destroyed() -> None:
        fake_mgr = FakeContainerManager()
        registry = AgentContainerRegistry(
            manager=fake_mgr,
            base_image_tag="agent-foundry-base:test",
            workspace_volume="vol-2",
        )
        primitive = MagicMock()
        live = await registry.create_for_invocation(
            primitive, oauth_token="t", instructions_text="x"
        )
        await registry.destroy(live)
        assert live.handle.status == "destroyed"
    ```

- [ ] **Step 3: Run tests — expect failure.**

**Task F0.3-I (impl):**

- [ ] **Step 4: Implement `orchestration/registry.py` (F0 surface).** Verbatim:

    ```python
    """Minimal AgentContainerRegistry (F0).

    F0 mode: every create_for_invocation creates a brand-new container,
    writes the instruction file, starts it, and returns a LiveContainer.
    Phase B Task B.4 extends with reuse-policy-aware get_or_create.
    """
    from __future__ import annotations

    import asyncio
    from dataclasses import dataclass
    from typing import Any

    from agent_foundry.orchestration.env import build_container_env

    ROLE_INSTRUCTIONS_PATH = "/home/claude/role-instructions.md"


    @dataclass
    class LiveContainer:
        handle: Any
        manager: Any
        session_id: str | None = None


    class AgentContainerRegistry:
        """F0 registry — no reuse, no keying, no session recording.

        Phase B.4 replaces create_for_invocation with a policy-aware
        get_or_create and adds record_session_id / shutdown_all.
        """

        def __init__(
            self,
            *,
            manager: Any,
            base_image_tag: str,
            workspace_volume: str,
        ) -> None:
            self._manager = manager
            self._base_image_tag = base_image_tag
            self._workspace_volume = workspace_volume

        async def create_for_invocation(
            self,
            primitive: Any,
            *,
            oauth_token: str,
            instructions_text: str,
        ) -> LiveContainer:
            env = build_container_env(
                primitive,
                oauth_token=oauth_token,
                role_instructions_path=ROLE_INSTRUCTIONS_PATH,
            )
            handle = await asyncio.to_thread(
                self._manager.create_container,
                image=self._base_image_tag,
                workspace_volume=self._workspace_volume,
                extra_env=env,
            )
            await asyncio.to_thread(
                self._manager.write_file_to_container,
                handle,
                ROLE_INSTRUCTIONS_PATH,
                instructions_text,
            )
            await asyncio.to_thread(self._manager.start, handle)
            return LiveContainer(handle=handle, manager=self._manager)

        async def destroy(self, live: LiveContainer) -> None:
            try:
                await asyncio.to_thread(self._manager.stop, live.handle, 5)
            except Exception:  # noqa: BLE001
                pass
            await asyncio.to_thread(self._manager.destroy, live.handle)
    ```

- [ ] **Step 5: Run tests — expect pass.**
- [ ] **Step 6: Commit.** `feat(orchestration): minimal container registry with new-per-invocation mode (F0)`.

### Task F0.4: Minimal `run_agent_in_container`

**Files:**
- `agent-foundry/src/agent_foundry/orchestration/container_executor.py` (new — F0 surface)
- `agent-foundry/src/agent_foundry/acp/agent_runner.py` (modify — re-export)
- `tests/agent_foundry/orchestration/test_container_executor_f0.py` (new)

**Task F0.4-T (tests):**

- [ ] **Step 1: Extend `tests/agent_foundry/orchestration/fakes.py`** with a scripted adapter:

    ```python
    # Append to tests/agent_foundry/orchestration/fakes.py

    from typing import Any


    class FakeClaudeCodeAdapter:
        """Scripted adapter returning canned envelope payloads per turn.

        F0 only uses run_turn once per invocation and only supports
        success envelopes. F.3's inner-loop tests extend this fake.
        """

        def __init__(self, *, canned_structured_output: dict[str, Any]) -> None:
            self._canned = canned_structured_output
            self.calls: list[dict[str, Any]] = []

        async def run_turn(
            self,
            *,
            prompt: str,
            json_schema: dict[str, Any],
            resume_session_id: str | None = None,
        ) -> dict[str, Any]:
            self.calls.append(
                {"prompt": prompt, "schema": json_schema, "resume": resume_session_id}
            )
            return self._canned
    ```

- [ ] **Step 2: Write `test_container_executor_f0.py`.** Verbatim:

    ```python
    from __future__ import annotations

    from typing import Any
    from unittest.mock import MagicMock

    import pytest
    from pydantic import BaseModel

    from agent_foundry.orchestration import container_executor
    from agent_foundry.orchestration.container_executor import run_agent_in_container
    from agent_foundry.orchestration.registry import AgentContainerRegistry
    from agent_foundry.orchestration.run_context import (
        AgentRunContext,
        NoOpLifecycleWriter,
    )
    from agent_foundry.primitives.models import (
        AgentAction,
        ContainerReusePolicy,
    )

    from .fakes import FakeClaudeCodeAdapter, FakeContainerManager


    class InputModel(BaseModel):
        task: str


    class OutputModel(BaseModel):
        answer: str


    def _make_primitive() -> AgentAction[InputModel, OutputModel]:
        return AgentAction[InputModel, OutputModel](
            prompt_builder=lambda s: f"do: {s.task}",
            instructions_provider=lambda: "Be precise.",
            executor=run_agent_in_container,
            reuse_policy=ContainerReusePolicy.REUSE_NEW_SESSION,
        )


    @pytest.fixture
    def patch_adapter(monkeypatch) -> list[FakeClaudeCodeAdapter]:
        holder: list[FakeClaudeCodeAdapter] = []

        def factory(*a: Any, **kw: Any) -> FakeClaudeCodeAdapter:
            adapter = FakeClaudeCodeAdapter(
                canned_structured_output={
                    "outcome": {
                        "kind": "success",
                        "payload": {"answer": "42"},
                    }
                },
            )
            holder.append(adapter)
            return adapter

        monkeypatch.setattr(container_executor, "build_adapter", factory)
        return holder


    @pytest.mark.asyncio
    async def test_run_agent_in_container_happy_path(patch_adapter) -> None:
        fake_mgr = FakeContainerManager()
        registry = AgentContainerRegistry(
            manager=fake_mgr,
            base_image_tag="agent-foundry-base:test",
            workspace_volume="vol-f0",
        )
        ctx = AgentRunContext(
            run_id="run-f0",
            container_registry=registry,
            lifecycle_writer=NoOpLifecycleWriter(),
            env={"CLAUDE_CODE_OAUTH_TOKEN": "tok"},
        )
        primitive = _make_primitive()
        result = await run_agent_in_container(
            primitive=primitive, prompt="go", run_ctx=ctx
        )
        assert isinstance(result, OutputModel)
        assert result.answer == "42"
        # Container was created and destroyed.
        assert fake_mgr.handles[0].status == "destroyed"


    @pytest.mark.asyncio
    async def test_run_agent_in_container_non_success_raises_not_implemented(
        monkeypatch,
    ) -> None:
        # Adapter returns a failure envelope; F0 must reject it.
        from agent_foundry.orchestration import container_executor as ce

        def factory(*a: Any, **kw: Any) -> FakeClaudeCodeAdapter:
            return FakeClaudeCodeAdapter(
                canned_structured_output={
                    "outcome": {"kind": "failed", "reason": "nope"}
                },
            )
        monkeypatch.setattr(ce, "build_adapter", factory)

        fake_mgr = FakeContainerManager()
        registry = AgentContainerRegistry(
            manager=fake_mgr,
            base_image_tag="x",
            workspace_volume="v",
        )
        ctx = AgentRunContext(
            run_id="r",
            container_registry=registry,
            lifecycle_writer=NoOpLifecycleWriter(),
            env={"CLAUDE_CODE_OAUTH_TOKEN": "t"},
        )
        primitive = _make_primitive()
        with pytest.raises(NotImplementedError, match="Phase F.3"):
            await run_agent_in_container(
                primitive=primitive, prompt="go", run_ctx=ctx
            )
        assert fake_mgr.handles[0].status == "destroyed"  # finally ran
    ```

- [ ] **Step 3: Run tests — expect failure.**

**Task F0.4-I (impl):**

- [ ] **Step 4: Implement `orchestration/container_executor.py` (F0).** Verbatim:

    ```python
    """Minimum viable run_agent_in_container (Phase F0).

    One turn, success-only, no reuse, no responders, no artifacts.
    Phases F.1–F.4 replace this with the full inner-loop executor.
    """
    from __future__ import annotations

    from typing import Any, get_args

    from pydantic import BaseModel

    from agent_foundry.acp.agent_turn_envelope import AgentTurnEnvelope
    from agent_foundry.acp.schema_tools import to_claude_code_schema
    from agent_foundry.orchestration.registry import LiveContainer
    from agent_foundry.orchestration.run_context import AgentRunContext
    from agent_foundry.primitives.models import AgentAction


    def build_adapter(live: LiveContainer) -> Any:
        """Construct the real claude-code driver bound to a container.

        F0 stub — the production driver (`ExecRunDriver`) lands in
        Phase F.3 in `orchestration/claude_cmd.py` and wraps
        `handle._container.exec_run`. Tests monkeypatch this symbol.
        """
        raise NotImplementedError(
            "Production driver wiring lands in Phase F.3 as "
            "orchestration.claude_cmd.ExecRunDriver; F0 tests must "
            "monkeypatch container_executor.build_adapter."
        )


    def _output_type(primitive: AgentAction) -> type[BaseModel]:
        args = get_args(type(primitive).__pydantic_generic_metadata__["args"] or ())
        # Fallback — primitives/models.py exposes get_type_args helper
        from agent_foundry.primitives.models import get_type_args
        _i, o = get_type_args(primitive)
        return o


    async def run_agent_in_container(
        *,
        primitive: AgentAction,
        prompt: str,
        run_ctx: AgentRunContext,
    ) -> BaseModel:
        """F0 executor: single turn, success-only, no reuse.

        1. Build AgentTurnEnvelope[O] schema.
        2. Get instructions via primitive.instructions_provider().
        3. Create a fresh container via run_ctx.container_registry.
        4. Run one turn via the adapter.
        5. Validate success payload against O and return.
        6. Destroy the container in finally.
        """
        output_type = _output_type(primitive)
        envelope_type = AgentTurnEnvelope[output_type]  # type: ignore[valid-type]
        schema = to_claude_code_schema(envelope_type)
        instructions_text = primitive.instructions_provider()

        oauth_token = run_ctx.env["CLAUDE_CODE_OAUTH_TOKEN"]
        registry = run_ctx.container_registry
        live = await registry.create_for_invocation(
            primitive,
            oauth_token=oauth_token,
            instructions_text=instructions_text,
        )
        try:
            adapter = build_adapter(live)
            raw = await adapter.run_turn(
                prompt=prompt,
                json_schema=schema,
                resume_session_id=None,
            )
            envelope = envelope_type.model_validate(raw)
            outcome = envelope.outcome
            kind = getattr(outcome, "kind", None)
            if kind == "success" or (
                hasattr(outcome, "payload") and kind in (None, "success")
            ):
                payload = outcome.payload
                return output_type.model_validate(
                    payload if not isinstance(payload, BaseModel) else payload.model_dump()
                )
            raise NotImplementedError(
                "F0 handles success only; clarification / permission / "
                "failure outcomes land in Phase F.3."
            )
        finally:
            await registry.destroy(live)
    ```

- [ ] **Step 5: Modify `acp/agent_runner.py`** to re-export (replace Plan 1's stub):

    ```python
    """Re-export of the container executor (F0 onward).

    Plan 1 shipped this as a NotImplementedError stub. Phase F0 replaces
    it with the real minimum-viable executor from
    orchestration.container_executor. Phase F.4 (later) is now a no-op
    reconfirmation rather than the first wiring point.
    """
    from agent_foundry.orchestration.container_executor import run_agent_in_container

    __all__ = ["run_agent_in_container"]
    ```

- [ ] **Step 6: Run tests — expect pass.**
- [ ] **Step 7: Commit.** `feat(orchestration): minimum viable container executor (F0)`.

### Task F0.5: Integration test — real Claude Code via `AgentAction`

**Files:**
- `agent-foundry/tests/agent_foundry/integration/test_f0_agent_action_end_to_end.py` (new)

Single end-to-end verification for F0. No T/I split.

- [ ] **Step 1: Write `test_f0_agent_action_end_to_end.py`.** Verbatim:

    ```python
    """F0 end-to-end: build a real AgentAction, construct the context
    manually (no run_primitive_plan wiring yet — that's Phase G.2), and
    drive run_agent_in_container against real Claude Code in a real
    container.
    """
    from __future__ import annotations

    import asyncio
    import os
    import uuid

    import pytest
    from pydantic import BaseModel

    from agent_foundry.orchestration.container_executor import run_agent_in_container
    from agent_foundry.orchestration.registry import AgentContainerRegistry
    from agent_foundry.orchestration.run_context import (
        AgentRunContext,
        NoOpLifecycleWriter,
    )
    from agent_foundry.primitives.models import AgentAction, ContainerReusePolicy


    class AnalysisInput(BaseModel):
        topic: str


    class AnalysisOutput(BaseModel):
        headline: str


    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_f0_end_to_end_real_claude_code() -> None:
        oauth_token = os.environ["CLAUDE_CODE_OAUTH_TOKEN"]

        try:
            import docker
            client = docker.from_env()
            client.ping()
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"docker daemon unavailable: {e}")

        from agent_foundry.acp.container import ContainerManager

        base_image = os.environ.get("ACP_BASE_IMAGE", "agent-foundry-base:latest")
        workspace_volume = f"f0-e2e-{uuid.uuid4().hex[:8]}"
        manager = ContainerManager(client=client, default_image=base_image)
        registry = AgentContainerRegistry(
            manager=manager,
            base_image_tag=base_image,
            workspace_volume=workspace_volume,
        )
        ctx = AgentRunContext(
            run_id=f"run-{uuid.uuid4().hex[:8]}",
            container_registry=registry,
            lifecycle_writer=NoOpLifecycleWriter(),
            env={"CLAUDE_CODE_OAUTH_TOKEN": oauth_token},
        )

        primitive = AgentAction[AnalysisInput, AnalysisOutput](
            prompt_builder=lambda s: f"Write a one-line headline about {s.topic}.",
            instructions_provider=lambda: (
                "You are a headline writer. Return structured output with a "
                "single `headline` field. Be concise."
            ),
            executor=run_agent_in_container,
            reuse_policy=ContainerReusePolicy.REUSE_NEW_SESSION,
        )

        result = await run_agent_in_container(
            primitive=primitive,
            prompt=primitive.prompt_builder(AnalysisInput(topic="cats")),
            run_ctx=ctx,
        )
        assert isinstance(result, AnalysisOutput)
        assert result.headline.strip()
    ```

- [ ] **Step 2: Run the test.** `cd agent-foundry && pdm test-integration tests/agent_foundry/integration/test_f0_agent_action_end_to_end.py`. Expected: PASS.
- [ ] **Step 3: On failure, halt** and investigate the F0.1–F0.4 implementations before starting Phase A.
- [ ] **Step 4: Commit.** `feat(orchestration): minimum viable container executor`.

---

## Phase A — Tighten Plan 1's primitive surface

Phase A is mechanical cleanup of Plan 1's shipped model based on brainstorm decisions 4, 6, and 10. It is a pre-requisite for every subsequent phase but touches only the models module.

### Task A.1: Drop `ContainerReusePolicy.NEW_EACH_TIME`; make `reuse_policy` required

**Files:**
- `agent-foundry/src/agent_foundry/primitives/models.py`
- `tests/agent_foundry/primitives/test_agent_action_model.py`

- [ ] **Step 1: Update tests to fail against the new contract.** In `test_agent_action_model.py`, delete every `NEW_EACH_TIME` reference. Add:
    ```python
    def test_reuse_policy_is_required():
        with pytest.raises(ValidationError, match="reuse_policy"):
            AgentAction[InputModel, OutputModel](
                prompt_builder=lambda s: "go",
                instructions_provider=lambda: "be good",
                executor=lambda **kw: OutputModel(),
            )

    def test_container_reuse_policy_has_exactly_two_members():
        assert set(ContainerReusePolicy) == {
            ContainerReusePolicy.REUSE_RESUME,
            ContainerReusePolicy.REUSE_NEW_SESSION,
        }
    ```
- [ ] **Step 2: Run unit tests — expect failures.** `cd agent-foundry && pdm test-unit tests/agent_foundry/primitives/test_agent_action_model.py`.
- [ ] **Step 3: Update `primitives/models.py`.** Remove `NEW_EACH_TIME = "new_each_time"` from the `ContainerReusePolicy` enum. Change `reuse_policy: ContainerReusePolicy = ContainerReusePolicy.NEW_EACH_TIME` to `reuse_policy: ContainerReusePolicy` (no default). Update the enum docstring accordingly.
- [ ] **Step 4: Run unit tests — expect pass.**
- [ ] **Step 5: Verify downstream.** `pdm test-unit` (full unit suite) to catch any callers relying on the default. Fix callers (if any) by declaring the policy explicitly.
- [ ] **Step 6: Typecheck.** `pdm run typecheck`.
- [ ] **Step 7: Commit.** `refactor(primitives): drop NEW_EACH_TIME and require reuse_policy`.

### Task A.2: Remove `FileCollectionChannel`, `StructuredOutputChannel`, `ResponseChannel`, `AgentAction.response_channel`

**Files:**
- `agent-foundry/src/agent_foundry/primitives/models.py`
- `agent-foundry/src/agent_foundry/primitives/__init__.py`
- `tests/agent_foundry/primitives/test_agent_action_model.py`

- [ ] **Step 1: Update tests.** Delete every channel-related test case in `test_agent_action_model.py`. Add:
    ```python
    def test_agent_action_has_no_response_channel():
        assert "response_channel" not in AgentAction.model_fields
    ```
- [ ] **Step 2: Run — expect failures.**
- [ ] **Step 3: Delete from `primitives/models.py`:**
    - `class ResponseChannelKind(StrEnum)` and its two members
    - `class StructuredOutputChannel(BaseModel)`
    - `class FileCollectionChannel(BaseModel)`
    - `ResponseChannel = Annotated[...]`
    - `AgentAction.response_channel: ResponseChannel` field
    - The `StructuredOutputChannel.model_rebuild()` and `FileCollectionChannel.model_rebuild()` calls at module bottom
    - The `from enum import StrEnum` import if no other uses remain (keep `Literal` if still used; otherwise remove)
- [ ] **Step 4: Update `primitives/__init__.py`.** Remove any exports of `StructuredOutputChannel`, `FileCollectionChannel`, `ResponseChannel`, `ResponseChannelKind` from the `__all__` list.
- [ ] **Step 5: Run — expect pass.**
- [ ] **Step 6: Commit.** `refactor(primitives): remove response channel surface — structured output only`.

### Task A.3: Evolve `FunctionAction.function` signature to accept `AgentRunContext`

**Files:**
- `agent-foundry/src/agent_foundry/primitives/models.py`
- `tests/agent_foundry/primitives/test_function_action_signature.py` (new)

**Note:** `AgentRunContext` does not exist yet (Phase B introduces it). For this task, loosen the type to `Callable[..., BaseModel]` with a docstring stating the intended contract `function(state: I, run_ctx: "AgentRunContext") -> O`. Phase B Task B.1 Step 5 will tighten the annotation to `Callable[[I, "AgentRunContext"], O]` via a forward reference and `model_rebuild` finalizer.

- [ ] **Step 1: Write the test.**
    ```python
    def test_function_action_accepts_two_arg_callable():
        def fn(state: InputModel, ctx) -> OutputModel:
            return OutputModel()
        action = FunctionAction[InputModel, OutputModel](function=fn)
        assert action.function is fn

    def test_function_action_still_accepts_one_arg_callable_back_compat():
        # Back-compat: Plan 2 keeps the compiler tolerant of 1-arg callables
        # during migration (see compiler arity-probe in G.1).
        action = FunctionAction[InputModel, OutputModel](function=lambda s: OutputModel())
        assert callable(action.function)
    ```
- [ ] **Step 2: Run — expect failure** (`function: Callable[[I], O]` rejects two-arg lambda at construct time because Pydantic v2 validates callable arity on some paths — verify actual failure; if Pydantic doesn't enforce arity, the test still passes and Step 3 is a docs-only change. In that case, delete the failing test variant and keep the doc comment only).
- [ ] **Step 3: Modify `FunctionAction.function`** from `Callable[[I], O]` to `Callable[..., BaseModel]` with the contract docstring:
    ```python
    class FunctionAction[I: BaseModel, O: BaseModel](Primitive[I, O]):
        """..."""
        function: Callable[..., BaseModel]
        """Contract: ``function(state: I, run_ctx: AgentRunContext) -> O``.

        Single-argument callables ``function(state: I) -> O`` are accepted
        during Plan 2 migration but deprecated — the compiler's arity probe
        calls them without a run_ctx and logs a deprecation warning.
        Will be tightened to ``Callable[[I, "AgentRunContext"], O]`` once
        Phase B lands (Task B.1 Step 5).
        """
    ```
- [ ] **Step 4: Run — expect pass.**
- [ ] **Step 5: Commit.** `refactor(primitives): evolve FunctionAction.function signature for run context`.

---

## Phase B — Run context, registry, and artifacts

Phase B builds the skeletal infrastructure the executor will stand on. No Docker interaction yet.

### Task B.1: `AgentRunContext`

**Files:**
- `agent-foundry/src/agent_foundry/orchestration/__init__.py` (new — bare init)
- `agent-foundry/src/agent_foundry/orchestration/run_context.py` (new)
- `tests/agent_foundry/orchestration/__init__.py` (new — empty)
- `tests/agent_foundry/orchestration/test_run_context.py` (new)

**Shape:**

```python
# run_context.py
from __future__ import annotations

import asyncio
import contextvars
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from agent_foundry.orchestration.lifecycle_writer import LifecycleWriter
    from agent_foundry.orchestration.registry import AgentContainerRegistry
    from agent_foundry.responders.protocol import ResponderProvider


class AgentRunContext(BaseModel):
    """Run-scoped dependencies passed to every primitive's user-supplied callable.

    One instance per `run_primitive_plan` invocation. Carries everything an
    executor, function action, or compiled node wrapper needs to interact with
    run-scoped infrastructure (container pool, responder, artifacts, cancel).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    run_id: str = Field(min_length=1)
    artifacts_dir: Path
    container_registry: "AgentContainerRegistry"
    responder_provider: "ResponderProvider"
    lifecycle_writer: "LifecycleWriter"
    cancel_event: asyncio.Event


# Module-level ContextVar so the compiler can thread run_ctx to node functions
# without mutating compiled StateGraph state. The compiler sets this inside
# run_primitive_plan before graph.ainvoke and resets it in `finally`.
current_run_context: contextvars.ContextVar[AgentRunContext | None] = (
    contextvars.ContextVar("agent_foundry.current_run_context", default=None)
)


def require_current_run_context() -> AgentRunContext:
    ctx = current_run_context.get()
    if ctx is None:
        raise RuntimeError(
            "No AgentRunContext set — this function must be called inside "
            "run_primitive_plan (see agent_foundry.compiler.run_primitive_plan)."
        )
    return ctx
```

- [ ] **Step 1: Write tests.**
    - Construction with all fields present succeeds; `model_dump_json()` round-trips (the async.Event + registry + writer fields will appear as `arbitrary_types_allowed` pseudo-values — use `model_dump(mode="python")` with round-trip skipped for those three fields and compare primitives).
    - `run_id=""` raises `ValidationError`.
    - `frozen=True`: `ctx.run_id = "x"` raises `ValidationError`. Mutation of contents (`ctx.cancel_event.set()`) succeeds — pin this.
    - `cancel_event.is_set()` is `False` immediately after construction.
    - `current_run_context.get() is None` by default; `current_run_context.set(ctx)` makes `require_current_run_context()` return `ctx`; `require_current_run_context()` after reset raises `RuntimeError`.
- [ ] **Step 2: Run — expect failure.**
- [ ] **Step 3: Create the module and `__init__.py` exports** (`__init__.py` contents: `from .run_context import AgentRunContext, current_run_context, require_current_run_context` plus `__all__`).
- [ ] **Step 4: Run — expect pass.**
- [ ] **Step 5: Tighten `FunctionAction.function` annotation** in `primitives/models.py` to `Callable[[Any, "AgentRunContext"], BaseModel]` using a `TYPE_CHECKING` import. Add a finalizer in `primitives/__init__.py` (or a new `primitives/_finalize.py` imported from `__init__.py`) that does:
    ```python
    from agent_foundry.orchestration.run_context import AgentRunContext
    from agent_foundry.primitives.models import FunctionAction
    FunctionAction.model_rebuild(_types_namespace={"AgentRunContext": AgentRunContext})
    ```
    This must run after `orchestration` is importable, so use a late import in the primitives package `__init__`. Add a test that `FunctionAction.model_fields["function"]` annotation resolves without errors.
- [ ] **Step 6: Commit.** `feat(orchestration): add AgentRunContext and thread through FunctionAction`.

### Task B.2: `LifecycleWriter`

**Files:**
- `agent-foundry/src/agent_foundry/orchestration/lifecycle_writer.py` (new)
- `tests/agent_foundry/orchestration/test_lifecycle_writer.py` (new)

**Shape:**

```python
# lifecycle_writer.py
from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class LifecycleWriter:
    """Append-only JSONL writer for run lifecycle events.

    Auto-stamps every record with ``ts`` (ISO 8601 UTC) and ``run_id``.
    Thread-safe and safe to call from async contexts. Writes are flushed
    per record so a crashed process still leaves a readable partial log.
    """

    def __init__(self, run_id: str, path: Path) -> None:
        self._run_id = run_id
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        # Open in append mode so concurrent writers do not truncate.
        self._fh = path.open("a", encoding="utf-8")
        self._lock = threading.Lock()
        self._closed = False

    def append(self, event: dict[str, Any]) -> None:
        """Append a single record. Auto-stamps ts and run_id; caller-supplied
        keys win if they collide (rare — intentional for replay tooling)."""
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "run_id": self._run_id,
            **event,
        }
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        with self._lock:
            if self._closed:
                raise RuntimeError("LifecycleWriter is closed")
            self._fh.write(line)
            self._fh.flush()

    # Public alias intended for FunctionAction callables so product code
    # can emit domain events without importing the `append` name (which
    # is a common word in product code).
    def append_run_event(self, event: dict[str, Any]) -> None:
        self.append(event)

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._fh.close()
                self._closed = True
```

- [ ] **Step 1: Write tests.**
    - Basic append: `write.append({"type": "test", "foo": 1})` produces exactly one line that parses as JSON and contains `ts`, `run_id`, `type`, `foo`.
    - Concurrency: spawn 20 threads each appending one record; read the file; assert 20 valid JSON lines with unique payload markers (pass the thread index).
    - Flush-per-append: write from one handle, read via a separate `open()` handle; see the record immediately.
    - Durability: write 3 records; truncate the file at an exact byte offset mid-line; read; the first N-1 lines are still valid JSON (line-based recovery).
    - `close()` then `append` raises `RuntimeError`.
    - Empty `event={}` still produces a valid line with just `ts`, `run_id`.
- [ ] **Step 2: Run — expect failure.**
- [ ] **Step 3: Implement** as shown above.
- [ ] **Step 4: Run — expect pass.**
- [ ] **Step 5: Commit.** `feat(orchestration): add LifecycleWriter for run-scoped jsonl`.

### Task B.3: Artifacts directory bootstrap + `inspect-workspace.sh`

**Files:**
- `agent-foundry/src/agent_foundry/orchestration/artifacts.py` (new)
- `tests/agent_foundry/orchestration/test_artifacts.py` (new)

**API:**

```python
# artifacts.py
from __future__ import annotations

import stat
from datetime import UTC, datetime
from pathlib import Path


_INSPECT_SCRIPT_TEMPLATE = """\
#!/bin/bash
# Auto-generated on {iso_timestamp}
# Inspect the workspace volume for run {run_id}.
# The volume is retained after the run so this script works as long as
# the volume has not been pruned manually.
set -euo pipefail
docker run --rm -it \\
  -v "{workspace_volume}:/workspace" \\
  --workdir /workspace \\
  "{base_image_tag}" \\
  bash
"""


def bootstrap_run_artifacts(
    *, artifacts_dir: Path, run_id: str, workspace_volume: str, base_image_tag: str
) -> Path:
    """Create <artifacts_dir>/<run_id>/, write inspect-workspace.sh.

    Returns the run directory path. Raises FileExistsError on collision.
    """
    run_dir = artifacts_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    write_inspect_workspace_script(
        run_dir=run_dir,
        run_id=run_id,
        workspace_volume=workspace_volume,
        base_image_tag=base_image_tag,
    )
    return run_dir


def write_inspect_workspace_script(
    *, run_dir: Path, run_id: str, workspace_volume: str, base_image_tag: str
) -> Path:
    script = _INSPECT_SCRIPT_TEMPLATE.format(
        iso_timestamp=datetime.now(UTC).isoformat(),
        run_id=run_id,
        workspace_volume=workspace_volume,
        base_image_tag=base_image_tag,
    )
    script_path = run_dir / "inspect-workspace.sh"
    script_path.write_text(script, encoding="utf-8")
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return script_path


def agent_turn_dir(run_dir: Path, agent_name: str, turn: int) -> Path:
    """Return (creating if needed) <run_dir>/<agent_name>/turns/<turn>/."""
    p = run_dir / agent_name / "turns" / str(turn)
    p.mkdir(parents=True, exist_ok=True)
    (p / "collected_files").mkdir(parents=True, exist_ok=True)
    return p


def agent_log_path(run_dir: Path, agent_name: str) -> Path:
    """Return <run_dir>/<agent_name>/container.log (directory is created)."""
    (run_dir / agent_name).mkdir(parents=True, exist_ok=True)
    return run_dir / agent_name / "container.log"
```

- [ ] **Step 1: Write tests.**
    - `bootstrap_run_artifacts` creates the run dir and the script.
    - Second call with the same `run_id` raises `FileExistsError`.
    - Script contents: starts with `#!/bin/bash`, contains the exact workspace volume and image tag strings, contains the run id.
    - Executable bit: `script_path.stat().st_mode & 0o111 != 0`.
    - `agent_turn_dir` creates nested dirs and a `collected_files/` sub.
    - `agent_log_path` returns a path whose parent exists but whose file does not (caller appends to it).
- [ ] **Step 2: Run — expect failure.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run — expect pass.**
- [ ] **Step 5: Commit.** `feat(orchestration): bootstrap run artifacts directory`.

### Task B.4: `AgentContainerRegistry`

**Files:**
- `agent-foundry/src/agent_foundry/orchestration/registry.py` (new)
- `tests/agent_foundry/orchestration/test_registry.py` (new)
- `tests/agent_foundry/orchestration/fakes.py` (new — created here, extended in F.2)

**Shape:**

```python
# registry.py
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_foundry.acp.container import ContainerHandle, ContainerManager
from agent_foundry.orchestration.lifecycle_events import LifecycleEvent
from agent_foundry.orchestration.lifecycle_writer import LifecycleWriter
from agent_foundry.primitives.models import AgentAction

logger = logging.getLogger(__name__)


@dataclass
class LiveContainer:
    """One container bound to one AgentAction for the duration of one run."""

    primitive_id: int  # id(primitive) — identity-keyed
    agent_name: str
    manager: ContainerManager
    handle: ContainerHandle
    session_id: str | None = None  # claude --resume target; None until first turn completes
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class AgentContainerRegistry:
    """One-container-per-AgentAction-per-run pool.

    Keyed by ``id(primitive)`` (Python object identity) — the primitive is the
    stable reference throughout the run because the PrimitivePlan is immutable
    during execution. Creation is lazy (first call to ``get_or_create``).
    ``shutdown_all`` is idempotent and tolerates per-container destroy failures.
    """

    def __init__(
        self,
        *,
        workspace_volume: str,
        base_image_tag: str,
        docker_client_factory: "Callable[[], Any] | None" = None,
    ) -> None:
        self._workspace_volume = workspace_volume
        self._base_image_tag = base_image_tag
        self._containers: dict[int, LiveContainer] = {}
        self._lock = asyncio.Lock()
        self._shut_down = False
        # docker_client_factory is injectable for tests; default imports
        # `docker` lazily so tests without docker installed still pass.
        self._docker_client_factory = docker_client_factory

    async def get_or_create(
        self,
        primitive: AgentAction,
        *,
        lifecycle_writer: LifecycleWriter,
        agent_name: str,
    ) -> LiveContainer:
        pid = id(primitive)
        async with self._lock:
            if self._shut_down:
                raise RuntimeError("Registry is shut down")
            live = self._containers.get(pid)
            if live is not None:
                return live
            manager = await asyncio.to_thread(self._build_manager, primitive)
            handle = await asyncio.to_thread(
                manager.create_container,
                self._base_image_tag,
                self._workspace_volume,
                None,
                self._extra_env_for(primitive),
            )
            await asyncio.to_thread(manager.start, handle)
            live = LiveContainer(
                primitive_id=pid,
                agent_name=agent_name,
                manager=manager,
                handle=handle,
            )
            self._containers[pid] = live
            lifecycle_writer.append(
                {
                    "type": LifecycleEvent.AGENT_CONTAINER_STARTED,
                    "agent_name": agent_name,
                    "container_id": handle.container_id,
                }
            )
            return live

    def record_session_id(self, primitive: AgentAction, session_id: str) -> None:
        live = self._containers.get(id(primitive))
        if live is not None:
            live.session_id = session_id

    async def shutdown_all(self) -> None:
        async with self._lock:
            if self._shut_down:
                return
            self._shut_down = True
            targets = list(self._containers.values())
            self._containers.clear()

        for live in targets:
            try:
                await asyncio.to_thread(live.manager.destroy, live.handle)
            except Exception as exc:  # noqa: BLE001 — log and continue
                logger.warning(
                    "destroy failed for %s (%s): %s",
                    live.agent_name, live.handle.container_id, exc,
                )

    def _build_manager(self, primitive: AgentAction) -> ContainerManager:
        if self._docker_client_factory is not None:
            client = self._docker_client_factory()
        else:
            import docker  # local import so tests without docker still import
            client = docker.from_env()
        return ContainerManager(client=client, default_image=self._base_image_tag)

    def _extra_env_for(self, primitive: AgentAction) -> dict[str, str]:
        """Hook point — subclasses/extensions may pass primitive-specific env.

        Base impl returns an empty dict; the executor supplies instructions
        via `ACP_ROLE_INSTRUCTIONS_PATH` separately at turn time (Plan 2
        injects instructions once at container-start time via this hook in
        Task F.3).
        """
        return {}
```

**Fakes (to create in this task for use here + F.2):**

```python
# tests/agent_foundry/orchestration/fakes.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_foundry.acp.container import ContainerHandle, ContainerManager


@dataclass
class FakeContainer:
    container_id: str
    started: bool = False
    destroyed: bool = False
    files: dict[str, bytes] = field(default_factory=dict)

    # The ContainerManager code reaches into handle._container to call
    # .start() / .stop() / .remove() / .exec_run() / .get_archive() /
    # .put_archive(). We expose these as methods.
    def start(self) -> None: self.started = True
    def reload(self) -> None: ...
    def stop(self, timeout: int = 10) -> None: self.started = False
    def remove(self, v: bool = False) -> None: self.destroyed = True
    def exec_run(self, cmd: str) -> tuple[int, bytes]: return (0, b"")
    # Archive ops sufficient for read_file_from_container/write_file_to_container:
    def get_archive(self, path: str): ...  # tests that use files implement via monkeypatch
    def put_archive(self, path: str, data): ...


@dataclass
class FakeDockerClient:
    containers: "FakeContainers" = field(default_factory=lambda: FakeContainers())


class FakeContainers:
    def __init__(self) -> None:
        self._created: list[FakeContainer] = []

    def create(self, image: str, **kwargs: Any) -> FakeContainer:
        c = FakeContainer(container_id=f"fake-{len(self._created)}")
        self._created.append(c)
        return c


def make_fake_registry(workspace_volume: str = "test-vol", image: str = "test:latest"):
    from agent_foundry.orchestration.registry import AgentContainerRegistry
    return AgentContainerRegistry(
        workspace_volume=workspace_volume,
        base_image_tag=image,
        docker_client_factory=lambda: FakeDockerClient(),
    )
```

- [ ] **Step 1: Write tests.**
    - Lazy creation: `get_or_create(primA)` returns a `LiveContainer`; the fake docker client has exactly 1 container.
    - Identity keying: two distinct `AgentAction` instances A and B → two containers; `get_or_create(primA)` twice returns the same instance; `get_or_create(primB)` returns a different instance.
    - `record_session_id(primA, "sess-1")` updates `live.session_id`; on unknown primitive it's a no-op.
    - `shutdown_all` destroys all containers; every underlying `FakeContainer.destroyed is True`.
    - `shutdown_all` after `shutdown_all` is a no-op (no exception).
    - If one destroy raises, the others still succeed: monkeypatch one manager's `.destroy` to raise; shut down; assert the other container still destroyed.
    - Lifecycle event is emitted on first creation with `type == AGENT_CONTAINER_STARTED`.
- [ ] **Step 2: Run — expect failure.**
- [ ] **Step 3: Implement** per the spec above.
- [ ] **Step 4: Run — expect pass.**
- [ ] **Step 5: Commit.** `feat(orchestration): add AgentContainerRegistry`.

### Task B.5: Lifecycle event constants

**Files:**
- `agent-foundry/src/agent_foundry/orchestration/lifecycle_events.py` (new)
- `tests/agent_foundry/orchestration/test_lifecycle_events.py` (new)

```python
from enum import StrEnum


class LifecycleEvent(StrEnum):
    """Stable wire constants for lifecycle.jsonl event "type" fields.

    Downstream tooling (summary renderer, future domain renderers, CI
    introspection) branches on these values. Per project convention, use
    a StrEnum so LSP findReferences works across producers and consumers.
    """

    RUN_STARTED = "run_started"
    RUN_ENDED = "run_ended"
    AGENT_CONTAINER_STARTED = "agent_container_started"
    AGENT_INVOCATION_STARTED = "agent_invocation_started"
    AGENT_INVOCATION_COMPLETED = "agent_invocation_completed"
    AGENT_INVOCATION_FAILED = "agent_invocation_failed"
    TURN_STARTED = "turn_started"
    TURN_COMPLETED = "turn_completed"
    RESPONDER_REQUESTED = "responder_requested"
    RESPONDER_ANSWERED = "responder_answered"
    FUNCTION_ACTION_STARTED = "function_action_started"
    FUNCTION_ACTION_COMPLETED = "function_action_completed"
    DOMAIN = "domain"  # product-defined events routed through append_run_event
```

- [ ] **Step 1: Write test asserting the set of members** (so reviewers notice when the vocabulary changes).
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Commit.** `feat(orchestration): add LifecycleEvent enum`.

### Task B.6: Summary renderer

**Files:**
- `agent-foundry/src/agent_foundry/orchestration/summary.py` (new)
- `tests/agent_foundry/orchestration/test_summary.py` (new)

**API:** `def render_summary(run_dir: Path) -> None` — reads `lifecycle.jsonl`, writes `summary.txt`.

Summary content (generic):

```
Run {run_id} — started {start}, ended {end} ({duration})

{agent_name:<12} {n_invocations:>4} invocations  {n_success:>3} success  {n_failure:>3} failure  avg {avg_ms:>6.0f}ms

Artifacts:
  container logs: ./{agent}/container.log, ...
  workspace:      ./inspect-workspace.sh
```

Aggregation rules:
- For each agent observed in events, count `AGENT_INVOCATION_COMPLETED` (success) and `AGENT_INVOCATION_FAILED` (failure). Total invocations = sum of the two.
- `avg_ms` comes from the difference between paired `AGENT_INVOCATION_STARTED.ts` and `AGENT_INVOCATION_COMPLETED.ts` / `AGENT_INVOCATION_FAILED.ts` records (match by `agent_name` + `invocation` field, falling back to a FIFO queue per agent if the invocation field is absent).
- If no `RUN_ENDED` record is present: render everything below a first line `"(incomplete — no RUN_ENDED recorded)"` header.
- If `lifecycle.jsonl` is empty or missing: write `"Run (unknown) — no events recorded\n"`.

- [ ] **Step 1: Write tests with a known jsonl fixture.**
    - Complete run fixture: `RUN_STARTED`, two agents each with one invocation started+completed, `RUN_ENDED`. Summary contains correct stats.
    - Partial fixture: `RUN_STARTED` + one invocation started, no completion, no `RUN_ENDED`. `(incomplete ...)` marker present; in-flight invocation counted as 0 success 0 failure with an `avg_ms` of `-` or `n/a`.
    - Empty file: summary is the "no events" header.
    - Missing file: same as empty.
- [ ] **Step 2: Run — expect failure.**
- [ ] **Step 3: Implement.** Parse line-by-line (tolerate malformed lines by skipping with a warning log), aggregate by agent, format with f-strings. Write via `Path.write_text`.
- [ ] **Step 4: Run — expect pass.**
- [ ] **Step 5: Commit.** `feat(orchestration): add generic run summary renderer`.

---

## Phase C — Responders

Phase C builds the interactive-continuation machinery. No container interaction yet.

### Task C.1: Request/response models

**Files:**
- `agent-foundry/src/agent_foundry/responders/__init__.py` (new)
- `agent-foundry/src/agent_foundry/responders/models.py` (new)
- `tests/agent_foundry/responders/__init__.py` (new — empty)
- `tests/agent_foundry/responders/test_responder_protocol.py` (new)

**Shape:**

```python
# responders/models.py
from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from agent_foundry.acp.agent_turn_envelope import (
    ClarificationOutcome,
    PermissionOutcome,
)


class ResponderKind(StrEnum):
    CLARIFICATION = "clarification"
    PERMISSION = "permission"


class ClarificationRequest(BaseModel):
    kind: Literal[ResponderKind.CLARIFICATION] = ResponderKind.CLARIFICATION
    question: str = Field(min_length=1)
    options: list[str] = Field(default_factory=list)
    agent_name: str = Field(min_length=1)
    invocation: int = Field(ge=0)
    turn: int = Field(ge=0)


class PermissionRequest(BaseModel):
    kind: Literal[ResponderKind.PERMISSION] = ResponderKind.PERMISSION
    action_summary: str = Field(min_length=1)
    risk_level: str = Field(min_length=1)
    why_needed: str = Field(min_length=1)
    agent_name: str = Field(min_length=1)
    invocation: int = Field(ge=0)
    turn: int = Field(ge=0)


ResponderRequest = Annotated[
    ClarificationRequest | PermissionRequest,
    Field(discriminator="kind"),
]


class ResponderResponse(BaseModel):
    answer: str = Field(description="Free-form answer text, or 'allow'/'deny' for permission")


class ResponderContext(BaseModel):
    model_config = ConfigDict(frozen=True)
    run_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    agent_name: str = Field(min_length=1)
    invocation: int = Field(ge=0)
    turn: int = Field(ge=0)


def build_request_from_outcome(
    outcome: ClarificationOutcome | PermissionOutcome,
    *,
    agent_name: str,
    invocation: int,
    turn: int,
) -> ClarificationRequest | PermissionRequest:
    if isinstance(outcome, ClarificationOutcome):
        return ClarificationRequest(
            question=outcome.question,
            options=list(outcome.options),
            agent_name=agent_name,
            invocation=invocation,
            turn=turn,
        )
    return PermissionRequest(
        action_summary=outcome.action,
        risk_level=outcome.risk_level,
        why_needed=outcome.why_needed,
        agent_name=agent_name,
        invocation=invocation,
        turn=turn,
    )
```

- [ ] **Step 1: Write tests.**
    - Discriminator routing: construct a `ResponderRequest` TypeAdapter; validating a clarification-shaped dict produces `ClarificationRequest`; permission-shaped → `PermissionRequest`; unknown `kind` → `ValidationError`.
    - Serialization round-trip: `model_dump()` → `model_validate` returns an equal instance for both variants.
    - Field validation: empty `question`, empty `agent_name`, negative `invocation`/`turn` all raise.
    - `build_request_from_outcome` on a `ClarificationOutcome(question="q", options=["a","b"])` → `ClarificationRequest(question="q", options=["a","b"], ...)`.
    - `build_request_from_outcome` on a `PermissionOutcome(action="write", risk_level="medium", why_needed="x")` → `PermissionRequest(action_summary="write", risk_level="medium", why_needed="x", ...)`.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Commit.** `feat(responders): add responder request/response models`.

### Task C.2: `Responder` protocol and `ResponderProvider`

**Files:**
- `agent-foundry/src/agent_foundry/responders/protocol.py` (new)
- `tests/agent_foundry/responders/test_responder_protocol.py` (extend)

```python
# responders/protocol.py
from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from agent_foundry.responders.models import (
    ResponderContext,
    ResponderRequest,
    ResponderResponse,
)


@runtime_checkable
class Responder(Protocol):
    async def respond(
        self, request: ResponderRequest, context: ResponderContext
    ) -> ResponderResponse: ...


ResponderProvider = Callable[[], Responder]


def static_provider(responder: Responder) -> ResponderProvider:
    """Return a provider that always resolves to the given responder."""
    return lambda: responder
```

- [ ] **Step 1: Write tests.**
    - A fake responder class implementing `respond` satisfies `isinstance(obj, Responder)` via `runtime_checkable`.
    - `static_provider(responder)()` returns the same instance on every call.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Commit.** `feat(responders): add Responder protocol and provider`.

### Task C.3: `StdinResponder`

**Files:**
- `agent-foundry/src/agent_foundry/responders/stdin.py` (new)
- `tests/agent_foundry/responders/test_stdin_responder.py` (new)

**Prompt format:**

```
[clarification · queue 2] reviewer#2 (turn 4)
Question:
  Should I rebase onto main or merge?
Options:
  [1] rebase
  [2] merge
> _
```

For permission:

```
[permission · queue 1] planner#1 (turn 2)
Action:
  write /etc/hosts
Risk:
  high
Why needed:
  inject test hostname
Reply with 'allow' or 'deny':
> _
```

**Behavior:**
- Internal `asyncio.Lock` serializes concurrent `respond()` calls.
- While the lock is held, the number of waiters is tracked in a counter (`self._waiting`) incremented before `async with self._lock` and decremented after. The rendered prompt header includes `· queue N` when `N > 0`.
- Stdin read is done via `anyio.to_thread.run_sync(input)` to stay non-blocking in async contexts.

```python
# responders/stdin.py
from __future__ import annotations

import asyncio
import sys
from typing import TextIO

import anyio.to_thread

from agent_foundry.responders.models import (
    ClarificationRequest,
    PermissionRequest,
    ResponderContext,
    ResponderRequest,
    ResponderResponse,
)


class StdinResponder:
    def __init__(self, *, stream_in: TextIO | None = None, stream_out: TextIO | None = None) -> None:
        self._in = stream_in or sys.stdin
        self._out = stream_out or sys.stdout
        self._lock = asyncio.Lock()
        self._waiting = 0

    async def respond(
        self, request: ResponderRequest, context: ResponderContext
    ) -> ResponderResponse:
        self._waiting += 1
        try:
            async with self._lock:
                queue_ahead = self._waiting - 1
                prompt = self._format(request, context, queue_ahead=queue_ahead)
                self._out.write(prompt)
                self._out.flush()
                answer = await anyio.to_thread.run_sync(self._read_line)
                return ResponderResponse(answer=answer.rstrip("\n"))
        finally:
            self._waiting -= 1

    def _read_line(self) -> str:
        line = self._in.readline()
        if line == "":
            # stdin closed — surface a clear error
            raise EOFError("stdin closed while waiting for responder input")
        return line

    def _format(
        self,
        request: ResponderRequest,
        context: ResponderContext,
        *,
        queue_ahead: int,
    ) -> str:
        header_suffix = f" · queue {queue_ahead}" if queue_ahead > 0 else ""
        if isinstance(request, ClarificationRequest):
            lines = [
                f"[clarification{header_suffix}] {request.agent_name}#{request.invocation} "
                f"(turn {request.turn})",
                "Question:",
                f"  {request.question}",
            ]
            if request.options:
                lines.append("Options:")
                for i, opt in enumerate(request.options, start=1):
                    lines.append(f"  [{i}] {opt}")
            lines.append("> ")
            return "\n".join(lines)
        assert isinstance(request, PermissionRequest)
        return "\n".join(
            [
                f"[permission{header_suffix}] {request.agent_name}#{request.invocation} "
                f"(turn {request.turn})",
                "Action:",
                f"  {request.action_summary}",
                "Risk:",
                f"  {request.risk_level}",
                "Why needed:",
                f"  {request.why_needed}",
                "Reply with 'allow' or 'deny':",
                "> ",
            ]
        )
```

- [ ] **Step 1: Write tests.**
    - Happy path: pass `stream_in=io.StringIO("rebase\n")`, `stream_out=io.StringIO()`; call `respond` on a clarification request; `answer == "rebase"`; the `stream_out` buffer contains `"clarification"`, the question, and `"> "`.
    - Permission request: same pattern with `"allow\n"`; output contains `"Reply with 'allow' or 'deny':"`.
    - Queue depth: construct two `StringIO` pipes that block until closed (use a custom `BlockingStringIO` helper in tests); call `respond` twice in `asyncio.gather`; assert the second prompt's header contains `"queue 1"`.
    - EOF: `stream_in=io.StringIO("")` → `EOFError`.
    - Concurrency fairness: 5 concurrent calls; each gets its own turn; `answer` values match the order of the lines written to the fake stdin.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Commit.** `feat(responders): add StdinResponder with concurrency serialization`.

---

## Phase D — `AgentFilePath` marker and schema extension

Phase D introduces the annotated file-path marker and the JSON-schema extension that propagates it to the adapter. No container interaction yet; the adapter verification hook lands in Phase E.

### Task D.1: `AgentFilePath` marker

**Files:**
- `agent-foundry/src/agent_foundry/models/__init__.py` (new — empty + exports)
- `agent-foundry/src/agent_foundry/models/markers.py` (new)
- `tests/agent_foundry/models/__init__.py` (new — empty)
- `tests/agent_foundry/models/test_agent_file_path_marker.py` (new)

```python
# models/markers.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from pydantic import GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema


PLATFORM_DEFAULT_MAX_FILE_BYTES: Final[int] = 10_000_000


@dataclass(frozen=True)
class AgentFilePath:
    """Annotated metadata marker for fields that contain agent-written file paths.

    Example:

        class ReviewerOutput(BaseModel):
            review_path: Annotated[str, AgentFilePath()]
            transcript_path: Annotated[str, AgentFilePath(max_size_bytes=50_000_000)]

    Platform behavior:
      - The adapter walks the JSON schema for every ``x-agent-file-path`` node
        after each structured output turn and os.stats each declared path.
      - If the path is missing or oversized, the adapter issues one ``--resume``
        correction turn.
      - The host-side executor copies each declared file out of the container
        into ``<run-dir>/<agent_name>/turns/<n>/collected_files/``.
    """

    max_size_bytes: int = PLATFORM_DEFAULT_MAX_FILE_BYTES

    def __get_pydantic_json_schema__(
        self, core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        schema = handler(core_schema)
        schema["x-agent-file-path"] = {"max_size_bytes": self.max_size_bytes}
        return schema
```

- [ ] **Step 1: Write tests.**
    - `class M(BaseModel): p: Annotated[str, AgentFilePath()]` → `M.model_json_schema()["properties"]["p"]["x-agent-file-path"] == {"max_size_bytes": 10_000_000}`.
    - Custom `max_size_bytes=50_000_000` propagates.
    - `list[Annotated[str, AgentFilePath()]]` propagates at the array `items` level.
    - Nested: `class Inner: path: Annotated[str, AgentFilePath()]` within `class Outer: inner: Inner` → after `to_claude_code_schema` (inlining), the `x-agent-file-path` appears on the inlined inner property.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Commit.** `feat(models): add AgentFilePath annotated marker`.

### Task D.2: Schema walker

**Files:**
- `agent-foundry/src/agent_foundry/models/markers.py` (extend)
- `tests/agent_foundry/models/test_agent_file_path_marker.py` (extend)

```python
@dataclass(frozen=True)
class FilePathFieldSpec:
    """Located during schema walking — the JSON pointer path + size limit."""

    json_pointer: str  # RFC 6901 style: "/review_path", "/items/*/path"
    max_size_bytes: int


def walk_file_path_fields(schema: dict[str, Any]) -> list[FilePathFieldSpec]:
    """Walk an inlined JSON schema; collect every field carrying x-agent-file-path.

    Handles nested objects (``properties``), arrays (``items``), and ``oneOf``/
    ``anyOf`` unions (recursed into each branch; the same pointer appears once
    per variant in the output — the adapter deduplicates at extraction time).
    Ignores ``$defs`` / ``$ref`` — the schema is expected to be already inlined
    by ``to_claude_code_schema``.
    """


def extract_paths(
    output: dict[str, Any], specs: list[FilePathFieldSpec]
) -> list[tuple[str, int]]:
    """Resolve each spec's pointer against an instance; return (path, max) tuples.

    Missing optional nodes are silently skipped. Wildcard segments (``*``)
    iterate arrays. Non-string terminal values raise ValueError.
    """
```

- [ ] **Step 1: Write tests.**
    - Flat: `{"properties": {"p": {"type": "string", "x-agent-file-path": {"max_size_bytes": 100}}}}` → `[FilePathFieldSpec("/p", 100)]`.
    - Nested object: pointer `/outer/inner_path`.
    - Array of paths: `{"properties": {"paths": {"type": "array", "items": {"type": "string", "x-agent-file-path": {...}}}}}` → `[FilePathFieldSpec("/paths/*", ...)]`.
    - OneOf discriminated union with the same field in two variants: both variants carry the same pointer; the returned list may contain duplicates; extraction dedupes.
    - `extract_paths` on `{"p": "/workspace/a.txt"}` with `[FilePathFieldSpec("/p", 100)]` → `[("/workspace/a.txt", 100)]`.
    - Wildcard: `{"paths": ["a", "b"]}` with `/paths/*` → `[("a", ...), ("b", ...)]`.
    - Missing optional: `{}` with `/p` spec → `[]` (not an error).
- [ ] **Step 2: Implement.** Recursive walker over `properties` / `items` / `oneOf` / `anyOf` / `allOf`; accumulate pointers. Extraction: split the pointer on `/`; iterate arrays at `*`.
- [ ] **Step 3: Commit.** `feat(models): add schema walker for AgentFilePath markers`.

### Task D.3: `to_claude_code_schema` marker preservation regression test

**Files:**
- `tests/agent_foundry/acp/test_schema_tools_marker_preserved.py` (new)
- (Possibly) `agent-foundry/src/agent_foundry/acp/schema_tools.py` (modify only if the regression test fails — the current walker preserves unknown keys, so no change is expected).

- [ ] **Step 1: Write the test.** Define a nested Pydantic model with an `AgentFilePath`-marked field. Call `to_claude_code_schema(Model)`. Walk the returned dict, assert that `x-agent-file-path` still appears on the exact property.
- [ ] **Step 2: Run.** Expected to pass without source changes because `_inline` preserves every key except `discriminator` and `$defs`.
- [ ] **Step 3: If it fails**, extend `_inline` to explicitly whitelist `x-` extension keys rather than blacklisting two keys. Re-run.
- [ ] **Step 4: Commit.** `test(acp): pin x-agent-file-path survival through to_claude_code_schema`.

---

## Phase E — Host-side file-path verification and bounded retry

Phase E adds `AgentFilePath` verification to the host-side executor. Per the Architecture note, the executor drives `claude` via `docker exec` from the host, parses stream-json from `exec_run`'s stdout, and — on successful structured output — verifies every `AgentFilePath`-marked path exists in the container (via `ContainerManager.read_file_from_container`) and is within its declared size limit. If any violation is found, the executor issues **one bounded** correction `--resume` turn via a second `docker exec` call; if the retry still has violations, it raises `AgentFailedError`. The in-container adapter (`ClaudeCodeAdapter`) is **not modified** by Plan 2.

### Task E.1: Extract `file_path_specs` in the executor's turn call

**Files:**
- `agent-foundry/src/agent_foundry/orchestration/container_executor.py` (modify)
- `tests/agent_foundry/orchestration/test_file_path_verification.py` (new)

The executor builds the JSON schema for `AgentTurnEnvelope[O]` once per invocation. At the same time it calls `walk_file_path_fields(schema)` once to obtain `list[FilePathFieldSpec]`. These specs are captured in closure and used after every turn in the inner loop (E.2) to verify paths on `success` envelopes.

**Task E.1-T (tests):**

- [ ] **Step 1: Create `tests/agent_foundry/orchestration/test_file_path_verification.py`.** Verbatim:

    ```python
    """Host-side AgentFilePath verification tests."""
    from __future__ import annotations

    from typing import Annotated

    import pytest
    from pydantic import BaseModel

    from agent_foundry.acp.agent_turn_envelope import AgentTurnEnvelope
    from agent_foundry.acp.schema_tools import to_claude_code_schema
    from agent_foundry.models.markers import AgentFilePath, walk_file_path_fields


    class OutputWithPath(BaseModel):
        report_path: Annotated[str, AgentFilePath()]
        summary: str


    class OutputNoPath(BaseModel):
        summary: str


    class TestExecutorSpecExtraction:
        """The executor walks the schema exactly once per invocation."""

        def test_executor_extracts_specs_from_schema(self) -> None:
            schema = to_claude_code_schema(AgentTurnEnvelope[OutputWithPath])
            specs = walk_file_path_fields(schema)
            paths = {s.json_pointer for s in specs}
            assert any("report_path" in p for p in paths)

        def test_executor_finds_no_specs_when_no_marker(self) -> None:
            schema = to_claude_code_schema(AgentTurnEnvelope[OutputNoPath])
            specs = walk_file_path_fields(schema)
            assert specs == []
    ```

- [ ] **Step 2: Run.** Expected: pass once D.1/D.2 have landed (marker + walker already written).
- [ ] **Step 3: Commit.** `test(orchestration): pin AgentFilePath spec extraction from envelope schema`.

**Task E.1-I (impl):**

- [ ] **Step 4: Verify gate.** Confirm `git diff HEAD~1 HEAD -- 'tests/**'` is empty before editing impl.
- [ ] **Step 5: Modify `orchestration/container_executor.py`** to compute `specs` once per invocation alongside the schema (inside the main entry point — placed next to the existing `schema = to_claude_code_schema(envelope_type)` line added in F.3):

    ```python
    # inside run_agent_in_container, once per invocation:
    schema = to_claude_code_schema(envelope_type)
    file_path_specs = walk_file_path_fields(schema)
    ```

  No other logic changes in E.1; the specs are consumed in E.2.

- [ ] **Step 6: Run tests — expect pass.**
- [ ] **Step 7: Commit.** `feat(orchestration): capture AgentFilePath specs per invocation`.

### Task E.2: Host-side verification with bounded `--resume` retry

**Files:**
- `agent-foundry/src/agent_foundry/orchestration/container_executor.py` (extend — add `_verify_file_paths` helper and wire into the inner loop)
- `tests/agent_foundry/orchestration/test_file_path_verification.py` (extend)

**Behavior:** inside the inner turn loop, after a turn returns a `success` envelope and before routing the success outcome to the caller:

1. `pairs = extract_paths(success_envelope.outcome.payload.model_dump(), file_path_specs)`.
2. For each `(path, max_size)`:
    - Read the file via `ContainerManager.read_file_from_container(live.handle, path)`. The method returns `None` if missing.
    - If `None` → append `{"path": path, "reason": "missing"}` to `violations`.
    - Else if `len(content.encode("utf-8")) > max_size` → append `{"path": path, "reason": "oversized", "size": ..., "limit": max_size}`.
3. If `violations` is empty → success envelope is returned; executor proceeds to any snapshotting.
4. Else, if this is the first verification attempt for this turn: issue exactly **one** correction `--resume` turn. Build the correction prompt, call the same `_run_one_turn(...)` helper that F.3 uses but with `session_id=success_envelope.agent_session_id` and the correction prompt. Re-verify after the retry.
5. If retry still has violations (or the retry itself does not produce a success envelope) → raise `AgentFailedError(reason=f"file_path_verification_failed: {violations}", agent_name=..., invocation=...)`.

**Correction prompt template:**

```
You declared these files in your structured output but they are missing or oversized:
{bullets}

Please write them correctly (or reduce their size), then emit the structured output again.
```

`{bullets}` is one line per violation — `- {path}: {reason}` (with size/limit appended when oversized).

**Task E.2-T (tests):**

- [ ] **Step 1: Extend `test_file_path_verification.py`** with a `FakeContainerManager` whose `read_file_from_container` returns scripted responses per path, and a scripted `exec_run` stream (from F.2) that returns a success envelope pointing to the declared path(s). Write the following tests:

    ```python
    # Append to test_file_path_verification.py

    import json
    from typing import Any

    from agent_foundry.orchestration import container_executor as ce
    from agent_foundry.orchestration.errors import AgentFailedError
    from agent_foundry.orchestration.registry import AgentContainerRegistry
    from agent_foundry.orchestration.run_context import (
        AgentRunContext,
        NoOpLifecycleWriter,
    )
    from agent_foundry.primitives.models import AgentAction, ContainerReusePolicy

    from .fakes import FakeContainerManager


    def _success_envelope(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "outcome": {"kind": "success", "payload": payload},
            "agent_session_id": "sess-1",
        }


    def _make_primitive_with_path() -> AgentAction:
        return AgentAction[BaseModel, OutputWithPath](
            prompt_builder=lambda s: "go",
            instructions_provider=lambda: "",
            executor=ce.run_agent_in_container,
            reuse_policy=ContainerReusePolicy.REUSE_NEW_SESSION,
        )


    class TestVerificationHappyPath:
        """Declared files exist and are within size — no retry."""

        @pytest.mark.asyncio
        async def test_happy_path_no_retry(self, monkeypatch) -> None:
            fake_mgr = FakeContainerManager(
                file_contents={"/workspace/report.md": "hello"},
            )
            registry = AgentContainerRegistry(
                manager=fake_mgr, base_image_tag="x", workspace_volume="v"
            )
            ctx = AgentRunContext(
                run_id="r",
                container_registry=registry,
                lifecycle_writer=NoOpLifecycleWriter(),
                env={"CLAUDE_CODE_OAUTH_TOKEN": "t"},
            )
            fake_mgr.script_turn(
                _success_envelope(
                    {"report_path": "/workspace/report.md", "summary": "ok"}
                )
            )
            primitive = _make_primitive_with_path()
            result = await ce.run_agent_in_container(
                primitive=primitive, prompt="go", run_ctx=ctx
            )
            assert isinstance(result, OutputWithPath)
            assert fake_mgr.turns_scripted_remaining() == 0  # only one turn


    class TestVerificationMissingFileRetryRecovers:
        """Missing file triggers one retry; retry writes the file; success."""

        @pytest.mark.asyncio
        async def test_missing_then_ok(self, monkeypatch) -> None:
            fake_mgr = FakeContainerManager(
                # First read returns None; second call returns content
                file_contents_sequence={
                    "/workspace/report.md": [None, "content"],
                },
            )
            registry = AgentContainerRegistry(
                manager=fake_mgr, base_image_tag="x", workspace_volume="v"
            )
            ctx = AgentRunContext(
                run_id="r",
                container_registry=registry,
                lifecycle_writer=NoOpLifecycleWriter(),
                env={"CLAUDE_CODE_OAUTH_TOKEN": "t"},
            )
            # Two turns scripted: first success pointing at missing file,
            # then success on retry with the file now present.
            fake_mgr.script_turn(
                _success_envelope(
                    {"report_path": "/workspace/report.md", "summary": "a"}
                )
            )
            fake_mgr.script_turn(
                _success_envelope(
                    {"report_path": "/workspace/report.md", "summary": "b"}
                )
            )
            primitive = _make_primitive_with_path()
            result = await ce.run_agent_in_container(
                primitive=primitive, prompt="go", run_ctx=ctx
            )
            assert result.summary == "b"


    class TestVerificationOversizedFileRetryRecovers:
        """Oversized file triggers retry; retry shrinks; success."""

        @pytest.mark.asyncio
        async def test_oversized_then_ok(self) -> None:
            big = "x" * 20_000_000  # 20MB > 10MB default
            small = "x" * 100
            fake_mgr = FakeContainerManager(
                file_contents_sequence={
                    "/workspace/report.md": [big, small],
                },
            )
            registry = AgentContainerRegistry(
                manager=fake_mgr, base_image_tag="x", workspace_volume="v"
            )
            ctx = AgentRunContext(
                run_id="r",
                container_registry=registry,
                lifecycle_writer=NoOpLifecycleWriter(),
                env={"CLAUDE_CODE_OAUTH_TOKEN": "t"},
            )
            fake_mgr.script_turn(
                _success_envelope(
                    {"report_path": "/workspace/report.md", "summary": "a"}
                )
            )
            fake_mgr.script_turn(
                _success_envelope(
                    {"report_path": "/workspace/report.md", "summary": "b"}
                )
            )
            primitive = _make_primitive_with_path()
            result = await ce.run_agent_in_container(
                primitive=primitive, prompt="go", run_ctx=ctx
            )
            assert result.summary == "b"


    class TestVerificationRetryStillFails:
        """Missing file, retry still missing → AgentFailedError."""

        @pytest.mark.asyncio
        async def test_retry_still_missing_raises(self) -> None:
            fake_mgr = FakeContainerManager(
                file_contents={"/workspace/report.md": None},  # always missing
            )
            registry = AgentContainerRegistry(
                manager=fake_mgr, base_image_tag="x", workspace_volume="v"
            )
            ctx = AgentRunContext(
                run_id="r",
                container_registry=registry,
                lifecycle_writer=NoOpLifecycleWriter(),
                env={"CLAUDE_CODE_OAUTH_TOKEN": "t"},
            )
            fake_mgr.script_turn(
                _success_envelope(
                    {"report_path": "/workspace/report.md", "summary": "a"}
                )
            )
            fake_mgr.script_turn(
                _success_envelope(
                    {"report_path": "/workspace/report.md", "summary": "b"}
                )
            )
            primitive = _make_primitive_with_path()
            with pytest.raises(AgentFailedError, match="file_path_verification_failed"):
                await ce.run_agent_in_container(
                    primitive=primitive, prompt="go", run_ctx=ctx
                )


    class TestVerificationNonSuccessEnvelopeSkipped:
        """Non-success envelopes have no payload to verify."""

        @pytest.mark.asyncio
        async def test_failure_envelope_not_verified(self) -> None:
            fake_mgr = FakeContainerManager(file_contents={})
            registry = AgentContainerRegistry(
                manager=fake_mgr, base_image_tag="x", workspace_volume="v"
            )
            ctx = AgentRunContext(
                run_id="r",
                container_registry=registry,
                lifecycle_writer=NoOpLifecycleWriter(),
                env={"CLAUDE_CODE_OAUTH_TOKEN": "t"},
            )
            fake_mgr.script_turn(
                {"outcome": {"kind": "failed", "reason": "nope"}, "agent_session_id": None}
            )
            primitive = _make_primitive_with_path()
            with pytest.raises(AgentFailedError, match="nope"):
                await ce.run_agent_in_container(
                    primitive=primitive, prompt="go", run_ctx=ctx
                )
            # read_file_from_container was never called because no success payload
            assert fake_mgr.read_file_calls == []
    ```

- [ ] **Step 2: Run tests — expect failure** (verification logic not yet in place).
- [ ] **Step 3: Commit.** `test(orchestration): pin host-side AgentFilePath verification and bounded retry`.

**Task E.2-I (impl):**

- [ ] **Step 4: Verify gate:** `git diff HEAD~1 HEAD -- 'tests/**'` empty.
- [ ] **Step 5: Extend `orchestration/container_executor.py`** with the verification helper and wire it into the inner loop's success branch. Key sketch (integrated into the existing F.3 inner loop):

    ```python
    def _verify_file_paths(
        *,
        payload_dict: dict[str, Any],
        specs: list[FilePathFieldSpec],
        manager: ContainerManager,
        handle: ContainerHandle,
    ) -> list[dict[str, Any]]:
        violations: list[dict[str, Any]] = []
        for path, max_size in extract_paths(payload_dict, specs):
            content = manager.read_file_from_container(handle, path)
            if content is None:
                violations.append({"path": path, "reason": "missing"})
                continue
            size = len(content.encode("utf-8"))
            if size > max_size:
                violations.append(
                    {"path": path, "reason": "oversized", "size": size, "limit": max_size}
                )
        return violations


    def _format_correction(violations: list[dict[str, Any]]) -> str:
        bullets = "\n".join(
            f"- {v['path']}: {v['reason']}"
            + (f" ({v['size']} > {v['limit']})" if v["reason"] == "oversized" else "")
            for v in violations
        )
        return (
            "You declared these files in your structured output but they "
            "are missing or oversized:\n"
            f"{bullets}\n\n"
            "Please write them correctly (or reduce their size), then "
            "emit the structured output again."
        )


    # Inside the inner turn loop, after a success envelope:
    #   violations = _verify_file_paths(payload_dict=..., specs=file_path_specs, manager=manager, handle=live.handle)
    #   if not violations:
    #       return validated_payload
    #   # retry once
    #   retry_envelope, _ = await _run_one_turn(
    #       prompt=_format_correction(violations),
    #       session_id=success_envelope.agent_session_id,
    #       manager=manager,
    #       handle=live.handle,
    #       schema=schema,
    #   )
    #   if retry_envelope.outcome.kind != "success":
    #       raise AgentFailedError(reason=f"file_path_verification_failed: {violations}", ...)
    #   retry_violations = _verify_file_paths(payload_dict=retry_envelope.outcome.payload.model_dump(), ...)
    #   if retry_violations:
    #       raise AgentFailedError(reason=f"file_path_verification_failed: {retry_violations}", ...)
    #   return output_type.model_validate(retry_envelope.outcome.payload.model_dump())
    ```

- [ ] **Step 6: Run tests — expect pass.**
- [ ] **Step 7: Commit.** `feat(orchestration): host-side AgentFilePath verification with bounded --resume retry`.

---

## Phase F — Container executor (the headline deliverable)

Phase F replaces the Plan 1 stub. This is the largest task in the plan and the one that ties everything together.

### Task F.1: `AgentFailedError`

**Files:**
- `agent-foundry/src/agent_foundry/orchestration/errors.py` (new)
- `tests/agent_foundry/orchestration/test_errors.py` (new)

```python
class AgentFailedError(RuntimeError):
    """An agent invocation terminated without producing a valid output.

    Raised when:
      - the envelope reports kind=failed
      - the responder raises any exception
      - file-path verification exhausts its one retry
      - the schema-validated output fails Pydantic validation against O
      - cancel_event is set between turns
      - any other non-recoverable error in the turn loop
    """

    def __init__(self, reason: str, *, agent_name: str, invocation: int) -> None:
        super().__init__(reason)
        self.reason = reason
        self.agent_name = agent_name
        self.invocation = invocation
```

- [ ] **Step 1: Write tests.** Construction; fields accessible; `str(err) == reason`; `err.agent_name`, `err.invocation` preserved.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Commit.** `feat(orchestration): add AgentFailedError`.

### Task F.2: Fake harness extension

**Files:**
- `tests/agent_foundry/orchestration/fakes.py` (extend from B.4)

Add:

```python
@dataclass
class ScriptedTurn:
    """One entry in a FakeClaudeCodeDriver's script."""
    envelope: AgentTurnEnvelope  # what the driver should emit this turn
    expects_prompt_contains: str | None = None  # optional prompt assertion
    session_id_after: str = "sess-fake"  # session id to expose after this turn
    files_to_write: dict[str, bytes] = field(default_factory=dict)
    """When the envelope is a success with AgentFilePath fields, the driver
    writes these files into the (fake) container workspace so the adapter's
    verification hook sees them."""


class FakeClaudeCodeDriver:
    """Scriptable stand-in for ExecRunDriver.

    Production uses `orchestration.claude_cmd.ExecRunDriver`, which
    shells out to `handle._container.exec_run(build_claude_cmd(...))`
    and parses stream-json. For unit tests we bypass Docker entirely:
    this driver is injected in place of the production driver via the
    module-level `set_driver_factory` seam documented in F.3.
    """

    def __init__(self, script: list[ScriptedTurn]) -> None:
        self._script = list(script)
        self._turn = 0
        self._session_id: str | None = None

    async def run_turn(
        self, *, prompt: str, resume_session_id: str | None
    ) -> tuple[AgentTurnEnvelope, str]:
        if self._turn >= len(self._script):
            raise AssertionError("FakeClaudeCodeDriver exhausted")
        entry = self._script[self._turn]
        self._turn += 1
        if entry.expects_prompt_contains is not None:
            assert entry.expects_prompt_contains in prompt
        self._session_id = entry.session_id_after
        return entry.envelope, self._session_id


class FakeResponder:
    def __init__(self, answers: list[str]) -> None:
        self._answers = list(answers)
        self._idx = 0
        self.calls: list[tuple[Any, Any]] = []

    async def respond(self, request, context):
        self.calls.append((request, context))
        from agent_foundry.responders.models import ResponderResponse
        ans = self._answers[self._idx]
        self._idx += 1
        return ResponderResponse(answer=ans)


def build_fake_run_context(tmp_path, *, run_id="test-run-001"):
    """One-stop constructor for AgentRunContext in tests."""
    from agent_foundry.orchestration.artifacts import bootstrap_run_artifacts
    from agent_foundry.orchestration.lifecycle_writer import LifecycleWriter
    from agent_foundry.orchestration.run_context import AgentRunContext
    from agent_foundry.responders.protocol import static_provider
    import asyncio

    run_dir = bootstrap_run_artifacts(
        artifacts_dir=tmp_path, run_id=run_id,
        workspace_volume="test-vol", base_image_tag="test:latest",
    )
    lifecycle = LifecycleWriter(run_id=run_id, path=run_dir / "lifecycle.jsonl")
    registry = make_fake_registry()
    responder = FakeResponder(answers=[])
    return AgentRunContext(
        run_id=run_id,
        artifacts_dir=run_dir,
        container_registry=registry,
        responder_provider=static_provider(responder),
        lifecycle_writer=lifecycle,
        cancel_event=asyncio.Event(),
    ), responder, registry
```

- [ ] **Step 1: Build and test the fakes.** Script a single success turn; script clarification→answer→success; script a failed envelope. Assert the driver advances turn-by-turn and exhausts cleanly.
- [ ] **Step 2: Commit.** `test(orchestration): add FakeClaudeCodeDriver and related fakes`.

### Task F.3: Inner turn loop

**Files:**
- `agent-foundry/src/agent_foundry/orchestration/container_executor.py` (extend from F0.4)
- `agent-foundry/src/agent_foundry/orchestration/claude_cmd.py` (extend from F0.4 — add the production stream-json driver)
- `tests/agent_foundry/orchestration/test_container_executor.py` (new)

**Seam for tests:** the container executor looks up its "driver" through a module-level hook:

```python
# container_executor.py (excerpt)
_DEFAULT_DRIVER_FACTORY: Callable[[LiveContainer, dict[str, Any]], "Driver"] | None = None


def set_driver_factory(factory: Callable[[LiveContainer, dict[str, Any]], "Driver"] | None) -> None:
    """Test hook — replace the production exec_run-backed driver with a fake.

    Production default (None) uses `orchestration/claude_cmd.py`'s
    `ExecRunDriver` which invokes `handle._container.exec_run(...)`
    per turn and parses the stream-json output host-side.
    """
    global _DEFAULT_DRIVER_FACTORY
    _DEFAULT_DRIVER_FACTORY = factory


class Driver(Protocol):
    async def run_turn(
        self, *, prompt: str, resume_session_id: str | None
    ) -> tuple[AgentTurnEnvelope, str | None]:
        """Returns (envelope, session_id).

        session_id is the Claude Code session id parsed from the
        first SystemInitEvent in the stream-json output; `None` only
        if the stream never emitted a SystemInitEvent (a hard error).
        """
```

Tests call `set_driver_factory(lambda live, schema: fake_driver)` before invoking the executor, and reset to `None` in teardown. The production factory returns an `ExecRunDriver(live, schema)` whose `run_turn` shells out to `handle._container.exec_run(build_claude_cmd(...), stream=True)` and parses line-by-line.

**Public entry:**

```python
async def run_agent_in_container(
    *,
    primitive: AgentAction,
    prompt: str,
    run_ctx: AgentRunContext,
) -> BaseModel:
    """Execute one invocation of an AgentAction in its (possibly reused) container.

    Lifecycle:
      1. Acquire/create the container via run_ctx.container_registry.
      2. Build the JSON schema for AgentTurnEnvelope[O] via to_claude_code_schema.
      3. Start the turn loop. First turn uses `prompt`; subsequent turns in the loop
         use responder answers.
      4. For each turn:
           a. run_ctx.cancel_event.is_set() → raise AgentFailedError("cancelled")
           b. Invoke driver.run_turn(prompt, resume_session_id).
           c. Snapshot prompt/envelope to artifacts dir.
           d. Match envelope outcome:
              - SuccessOutcome(payload):
                  Validate payload type == primitive's O.
                  Snapshot files declared by AgentFilePath specs.
                  Emit turn_completed + agent_invocation_completed events.
                  Record session id on the LiveContainer.
                  Return payload.
              - ClarificationOutcome / PermissionOutcome:
                  req = build_request_from_outcome(outcome, ...).
                  ctx = ResponderContext(run_id, uuid4(), agent_name, invocation, turn).
                  responder = run_ctx.responder_provider()
                  Emit responder_requested event.
                  try: response = await responder.respond(req, ctx)
                  except Exception as e: raise AgentFailedError(f"responder failed: {e}")
                  Emit responder_answered event.
                  prompt = response.answer
                  resume_session_id = current_session_id
                  Loop.
              - FailureOutcome(reason):
                  Emit agent_invocation_failed.
                  raise AgentFailedError(reason).
      5. On any unhandled exception, emit agent_invocation_failed and re-raise
         (wrapping in AgentFailedError if not already).

    Safety bound: max 20 responder loops per invocation. Exceeding this raises
    AgentFailedError("responder loop exceeded max iterations").
    """
```

**Reuse policy dispatch:**

Before each invocation (not each turn within):

- `REUSE_RESUME` + `LiveContainer.session_id is not None` → `resume_session_id = session_id`.
- `REUSE_RESUME` + `session_id is None` → `resume_session_id = None`; record the session id after the first turn captures one.
- `REUSE_NEW_SESSION` → `resume_session_id = None` for every new invocation.

Within the same invocation, every clarification/permission continuation uses the *current-turn* session id regardless of policy.

**File snapshotting on success:**

```python
for declared_path, _max in extract_paths(payload.model_dump(), specs):
    turn_dir = agent_turn_dir(run_ctx.artifacts_dir, agent_name, turn_number)
    target = turn_dir / "collected_files" / Path(declared_path).name
    ok = await asyncio.to_thread(
        live.manager.copy_from_container, live.handle, declared_path, target
    )
    if not ok:
        # Non-fatal — the adapter's verification should have caught missing
        # files. Log and continue.
        logger.warning("failed to snapshot %s from container %s", declared_path, live.handle.container_id)
```

**Transport — host-driven `docker exec` per turn:**

Per the Architecture note, Plan 2 does not run a Python adapter process inside the container and does not use a WebSocket server between host and container. Each turn within an invocation is a fresh `claude` CLI process invoked via `handle._container.exec_run(...)` inside the long-running container. The session is threaded through `claude --resume <session-id>`.

The production driver lives in `agent_foundry/orchestration/claude_cmd.py`:

```python
# orchestration/claude_cmd.py (production ExecRunDriver)
import json
from typing import Any

from agent_foundry.acp.agent_turn_envelope import AgentTurnEnvelope
from agent_foundry.acp.claude_code_events import (
    STRUCTURED_OUTPUT_TOOL_NAME,
    AssistantEvent,
    SystemInitEvent,
    parse_stream_event,
)
from agent_foundry.orchestration.registry import LiveContainer


def build_claude_cmd(
    prompt: str,
    *,
    session_id: str | None = None,
    skip_permissions: bool = False,
    json_schema: dict[str, Any] | None = None,
) -> list[str]:
    """Host-side port of acp/adapters/claude_code.py::_build_claude_cmd.

    Identical argv; lives in orchestration/ so the new executor does
    not depend on the in-container adapter module.
    """
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose"]
    if session_id:
        cmd.extend(["--resume", session_id])
    if skip_permissions:
        cmd.append("--dangerously-skip-permissions")
    if json_schema is not None:
        cmd.extend(["--json-schema", json.dumps(json_schema)])
    return cmd


class ExecRunDriver:
    """Production driver: invoke claude via docker exec_run and parse stream-json."""

    def __init__(self, live: LiveContainer, json_schema: dict[str, Any]) -> None:
        self._live = live
        self._schema = json_schema

    async def run_turn(
        self, *, prompt: str, resume_session_id: str | None
    ) -> tuple[AgentTurnEnvelope, str | None]:
        cmd = build_claude_cmd(
            prompt, session_id=resume_session_id, json_schema=self._schema
        )
        # exec_run with stream=True returns a generator of chunks on stdout.
        # asyncio.to_thread wraps the synchronous iteration.
        captured_session_id: str | None = None
        structured_output: dict[str, Any] | None = None
        for line in await asyncio.to_thread(self._iter_exec_lines, cmd):
            event = parse_stream_event(line)
            if isinstance(event, SystemInitEvent):
                captured_session_id = event.session_id
            elif isinstance(event, AssistantEvent):
                for block in event.blocks:
                    if getattr(block, "tool_name", None) == STRUCTURED_OUTPUT_TOOL_NAME:
                        structured_output = block.tool_input
        if structured_output is None:
            # cold-start retry / missing-structured-output retry logic lives here;
            # see Phase F.3 test matrix below.
            ...
        envelope = AgentTurnEnvelope.model_validate(structured_output)
        return envelope, captured_session_id

    def _iter_exec_lines(self, cmd: list[str]):
        exec_result = self._live.handle._container.exec_run(
            cmd, stream=True, demux=False
        )
        # exec_result.output yields bytes chunks; split by newline.
        buf = b""
        for chunk in exec_result.output:
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if line.strip():
                    yield line.decode("utf-8")
```

Retry behavior (missing structured output, cold-start per anthropics/claude-code#23265, refusal / max_tokens stop-reason handling) is ported host-side from `acp/adapters/claude_code.py` into this driver. Each retry is a fresh `exec_run` of `claude --resume <session_id> -p <correction>`.

**Instructions path handling:** the registry writes `primitive.instructions_provider()` via `ContainerManager.write_file_to_container(handle, "/home/claude/role-instructions.md", text)` *after* `create_container(...)` and *before* `start(handle)`. `ACP_ROLE_INSTRUCTIONS_PATH` is set in the container env at create time so `entrypoint.sh`'s existing block (lines 46–51) appends the file onto `/home/claude/.claude/CLAUDE.md` on first boot. This is already implemented in Task F0.3; F.3 inherits it unchanged.

- [ ] **Step 1: Write tests.** Drive with `FakeClaudeCodeDriver` + `FakeContainerManager`:
    - Happy path, structured output only: `SuccessOutcome` envelope returns validated `O`.
    - Clarification round-trip: first envelope is `ClarificationOutcome`; `FakeResponder(answers=["rebase"])` provides answer; second envelope is `SuccessOutcome`; result is validated `O`.
    - Permission round-trip: analogous with `PermissionOutcome` + `FakeResponder(answers=["allow"])`.
    - `FailureOutcome`: `AgentFailedError(reason=...)` raised; `agent_invocation_failed` event written to `lifecycle.jsonl`.
    - Responder raises `TimeoutError`: `AgentFailedError` with `reason` containing `"responder failed"` and the original exception's message.
    - `cancel_event.set()` before next turn: `AgentFailedError("cancelled")` raised.
    - `REUSE_RESUME`: second invocation of the same `AgentAction` passes the session id captured after the first. Driver's `expects_prompt_contains` on the second call is the new prompt; driver records the `resume_session_id` arg; test asserts `resume_session_id == "sess-fake"` (from first invocation).
    - `REUSE_NEW_SESSION`: second invocation passes `resume_session_id=None` even though the first captured a session.
    - Pydantic validation failure on envelope payload: construct a driver that emits a `SuccessOutcome[WrongType]`; executor raises `AgentFailedError` with reason containing `"payload validation failed"`.
    - File snapshotting: a `SuccessOutcome` whose payload includes an `AgentFilePath` field with value `/workspace/out.txt`; the fake registry is pre-seeded with that file's contents; after execution, `<run_dir>/<agent_name>/turns/1/collected_files/out.txt` exists with the expected bytes.
    - Max responder loops: script 25 consecutive clarifications; executor raises `AgentFailedError("responder loop exceeded max iterations")` on the 21st turn.
    - **Session-id capture (per the resolved ambiguity):** the fake driver's `run_turn` returns `(envelope, "sess-abc")` on the first call. After the first turn, `live.session_id == "sess-abc"` — recorded regardless of envelope outcome. The `FakeContainerManager`'s scripted `exec_run` (or the fake driver directly) must expose this so tests can assert on it.
- [ ] **Step 2: Implement** the executor, the `ExecRunDriver` in `orchestration/claude_cmd.py`, and the registry adjustments. The driver's real `exec_run` path is **not** unit-tested in F.3 — only the driver abstraction is. The `exec_run` path gets an integration test in H.1.
- [ ] **Step 3: Commit.** `feat(orchestration): implement container executor inner turn loop`.

### Task F.4: Replace the Plan 1 stub

**Files:**
- `agent-foundry/src/agent_foundry/acp/agent_runner.py` (modify)
- `tests/agent_foundry/acp/test_agent_runner.py` (modify or create)

- [ ] **Step 1: Update tests.** The old stub test asserted `NotImplementedError`. Delete the assertion and replace with:
    ```python
    def test_run_agent_in_container_is_real_executor():
        from agent_foundry.acp.agent_runner import run_agent_in_container
        from agent_foundry.orchestration.container_executor import (
            run_agent_in_container as real_impl,
        )
        assert run_agent_in_container is real_impl
    ```
- [ ] **Step 2: Update `acp/agent_runner.py`.** Replace the stub body with:
    ```python
    """Re-export of the real container executor (see orchestration.container_executor).

    This module exists to preserve the import path used by Plan 1's compiler.
    """
    from agent_foundry.orchestration.container_executor import run_agent_in_container

    __all__ = ["run_agent_in_container"]
    ```
- [ ] **Step 3: Run all unit tests** across the repo.
- [ ] **Step 4: Commit.** `feat(acp): replace run_agent_in_container stub with real executor`.

---

## Phase G — Compiler + runner integration

### Task G.1: Thread `run_ctx` through the compiler

**Files:**
- `agent-foundry/src/agent_foundry/compiler/primitive_compiler.py`
- `tests/agent_foundry/compiler/test_agent_action_compiler.py`

The Plan 1 compiler builds `AgentAction`'s node without `run_ctx`. Plan 2 injects it via the `current_run_context` `ContextVar` defined in B.1. The compilation functions do not carry run_ctx explicitly; the *node functions* read it from the ContextVar at invocation time.

**Change to `_compile_agent_action`:**

```python
from agent_foundry.orchestration.run_context import require_current_run_context

def _compile_agent_action(graph, action, prefix, gate_ids):
    node_id = prefix
    input_type, output_type = get_type_args(action)
    prompt_builder = action.prompt_builder
    executor = action.executor

    async def node_fn(state: dict[str, Any]) -> dict[str, Any]:
        _validate_boundary(state, input_type, node_id)
        model_input = input_type.model_validate(state)
        prompt = prompt_builder(model_input)
        run_ctx = require_current_run_context()
        result = await executor(primitive=action, prompt=prompt, run_ctx=run_ctx)
        if not isinstance(result, output_type):
            raise PrimitiveCompilationError(
                f"AgentAction {node_id}: executor returned {type(result).__name__}, "
                f"expected {output_type.__name__}",
                primitive_type=node_id,
            )
        return result.model_dump()

    graph.add_node(node_id, node_fn)
    return (node_id, node_id)
```

**Change to `_compile_function_action`:**

```python
def _compile_function_action(graph, action, prefix, gate_ids):
    node_id = prefix
    input_type, _ = get_type_args(action)
    fn = action.function
    sig_params = list(inspect.signature(fn).parameters)
    arity = len(sig_params)

    def node_fn(state: dict[str, Any]) -> dict[str, Any]:
        if arity == 0:
            result = fn()
        elif arity == 1:
            _validate_boundary(state, input_type, node_id)
            result = fn(input_type.model_validate(state))
        else:  # 2 or more: pass (state_model, run_ctx)
            _validate_boundary(state, input_type, node_id)
            run_ctx = require_current_run_context()
            result = fn(input_type.model_validate(state), run_ctx)
        return result.model_dump()

    graph.add_node(node_id, node_fn)
    return (node_id, node_id)
```

**Async-node caveat:** LangGraph's `StateGraph.add_node` accepts both sync and async callables; async nodes are awaited when the graph is invoked via `ainvoke`. The existing compiler mixes sync and async nodes because only `_compile_agent_action` becomes async. The existing `run_primitive_plan_sync` calls `graph.invoke`; the new async `run_primitive_plan` calls `graph.ainvoke`. Sync wrappers around the new async executor are not allowed — async node → async graph → async caller.

**Impact on other compiler functions:** `_compile_sequence`, `_compile_conditional`, `_compile_loop`, `_compile_retry` call `compiled_sub.invoke(...)` which is sync. If any step inside a sequence is an `AgentAction`, its node is async; LangGraph requires `compiled_sub.ainvoke` in that case. Task G.1 Step 4 below addresses this.

- [ ] **Step 1: Update tests.** Every node test now (a) sets `current_run_context.set(run_ctx_stub)` before invoking the node fn, (b) asserts `executor` is called with `run_ctx=<the ctx>`, (c) asserts `FunctionAction` arity-2 callable receives `(state_model, ctx)`, arity-1 receives only `(state_model,)`, arity-0 receives nothing. Add a test that `current_run_context` unset raises the expected `RuntimeError`.
- [ ] **Step 2: Modify the compiler per the code above.**
- [ ] **Step 3: Widen sub-compilers to `async def`** — convert the inner node fns in `_compile_sequence` / `_compile_conditional` / `_compile_loop` / `_compile_retry` to `async def`, and replace `compiled_sub.invoke(...)` with `await compiled_sub.ainvoke(...)`. If a sub-plan has only sync primitives, `ainvoke` still works (LangGraph handles sync nodes in an async graph). Update tests that currently call `.invoke` on compiled sequences to use `await compiled.ainvoke(...)` with `pytest.mark.asyncio`.
- [ ] **Step 4: Run full unit suite — expect green.**
- [ ] **Step 5: Commit.** `feat(compiler): thread AgentRunContext through primitive compilation via ContextVar`.

### Task G.2: Extend `run_primitive_plan`

**Files:**
- `agent-foundry/src/agent_foundry/compiler/primitive_compiler.py` (extend — add async entry point and a sync wrapper)
- `agent-foundry/src/agent_foundry/compiler/__init__.py` (export)
- `tests/agent_foundry/compiler/test_run_primitive_plan.py` (new)

**New signatures:**

```python
async def run_primitive_plan(
    plan: PrimitivePlan,
    *,
    initial_state: BaseModel | None = None,
    artifacts_dir: Path,
    workspace_volume: str,
    base_image_tag: str,
    responder_provider: ResponderProvider,
    run_id: str | None = None,
) -> BaseModel:
    """Compile and execute a primitive plan end-to-end.

    Builds AgentRunContext, installs signal handlers, runs the compiled
    graph, writes summary.txt in finally. Returns the final state as an
    instance of the root primitive's output type.
    """


def run_primitive_plan_sync(
    plan: PrimitivePlan,
    initial_state: BaseModel | None = None,
    config: dict[str, Any] | None = None,
) -> BaseModel:
    """Legacy sync entry point.

    Compiles and invokes the plan synchronously; runs AgentActions are
    rejected with a clear error — products executing AgentActions must
    use the async `run_primitive_plan`.
    """
    if _plan_contains_agent_action(plan):
        raise RuntimeError(
            "run_primitive_plan_sync cannot execute plans containing AgentAction. "
            "Use `await run_primitive_plan(plan, ...)` instead."
        )
    # Existing sync implementation, unchanged
    ...
```

**Body outline of the async entry:**

```python
async def run_primitive_plan(...) -> BaseModel:
    run_id = run_id or _new_run_id()
    run_dir = bootstrap_run_artifacts(
        artifacts_dir=artifacts_dir,
        run_id=run_id,
        workspace_volume=workspace_volume,
        base_image_tag=base_image_tag,
    )
    lifecycle = LifecycleWriter(run_id=run_id, path=run_dir / "lifecycle.jsonl")
    lifecycle.append({"type": LifecycleEvent.RUN_STARTED})
    registry = AgentContainerRegistry(
        workspace_volume=workspace_volume, base_image_tag=base_image_tag,
    )
    cancel = asyncio.Event()
    run_ctx = AgentRunContext(
        run_id=run_id,
        artifacts_dir=run_dir,
        container_registry=registry,
        responder_provider=responder_provider,
        lifecycle_writer=lifecycle,
        cancel_event=cancel,
    )
    token = current_run_context.set(run_ctx)
    signal_handlers_installed = _install_signal_handlers(cancel)
    try:
        graph = compile_primitive(plan)
        input_dict = initial_state.model_dump() if initial_state else {}
        result_dict = await graph.ainvoke(input_dict)
        _, root_out = get_type_args(plan.root)
        return root_out.model_validate(result_dict)
    finally:
        try:
            await registry.shutdown_all()
        finally:
            lifecycle.append({"type": LifecycleEvent.RUN_ENDED})
            lifecycle.close()
            render_summary(run_dir)
            if signal_handlers_installed:
                _remove_signal_handlers()
            current_run_context.reset(token)


def _new_run_id() -> str:
    import uuid
    from datetime import UTC, datetime
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    return f"{ts}-{uuid.uuid4().hex[:8]}"


def _install_signal_handlers(cancel: asyncio.Event) -> bool:
    """Register SIGINT/SIGTERM handlers that set cancel. Returns True if installed.

    Returns False (no-op) when not in the main thread or when no running loop
    is available (pytest in a sub-thread, etc.).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False
    import threading
    if threading.current_thread() is not threading.main_thread():
        return False
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, cancel.set)
        except (NotImplementedError, RuntimeError):
            # Windows or certain embedded runtimes
            return False
    return True
```

- [ ] **Step 1: Write tests** (using `FakeClaudeCodeDriver` via `set_driver_factory`):
    - End-to-end happy path: a `Sequence` of one `AgentAction` returning `OutputModel(x=1)` and one `FunctionAction` that multiplies `x` by 2; final state has `x == 2`; `<run_dir>/lifecycle.jsonl` contains `RUN_STARTED`, `AGENT_INVOCATION_*`, `FUNCTION_ACTION_*`, `RUN_ENDED`; `summary.txt` exists.
    - Cancellation: spawn the plan as a task; set `cancel_event` from the outside after the first agent turn; the plan raises `AgentFailedError("cancelled")`; `summary.txt` still written; no orphan containers (fake registry reports `destroyed=True`).
    - Exception mid-run: `FakeClaudeCodeDriver` scripts a `FailureOutcome`; the outer call raises `AgentFailedError`; teardown still happens; `summary.txt` written.
    - Explicit `run_id="foo"` honored — artifacts under `<artifacts_dir>/foo/`.
    - Implicit `run_id` is unique across two consecutive calls.
    - `run_primitive_plan_sync(plan_with_agent_action)` raises `RuntimeError("run_primitive_plan_sync cannot execute ...")`.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Run — expect pass.**
- [ ] **Step 4: Commit.** `feat(compiler): run_primitive_plan builds run context, handles signals, writes artifacts`.

---

## Phase H — Integration verification

### Task H.1: End-to-end integration test with a real container + scripted claude

**Files:**
- `agent-foundry/tests/agent_foundry/integration/__init__.py` (new — empty)
- `agent-foundry/tests/agent_foundry/integration/test_plan2_end_to_end.py` (new)

This test spins up a real Docker container with the Agent Foundry base image, replacing the `claude` binary inside the image with a scripted shell shim that echoes a canned structured-output stream. The host-side executor drives the container via `handle._container.exec_run(build_claude_cmd(...), stream=True)` per turn; the full loop exercises Docker, `ContainerManager`, `ExecRunDriver`, the container executor, the responder, and the summary renderer.

Gate: `pytest.mark.integration` + `docker.from_env().ping()` — skip with reason if Docker is not available.

Setup (see `conftest.py` in the integration directory):
- A canned base image built from `Dockerfile.base` with a scripted `claude` binary at `/home/claude/.local/bin/claude` that reads its `-p` prompt and emits prescribed `stream-json` lines.
- Two scripted scenarios: a clarification→answer→success path and a pure-success path. Both can be stored as JSON fixtures under `tests/agent_foundry/integration/fixtures/`.

Plan:
- `Sequence[StateA, StateC]` of `[AgentAction[StateA, StateB], FunctionAction[StateB, StateC]]`.
- `AgentAction` output model has one `Annotated[str, AgentFilePath()]` field and one plain string field; `reuse_policy=REUSE_RESUME`.
- `FunctionAction` records a domain event via `run_ctx.lifecycle_writer.append_run_event`.
- Scripted `claude`: one `clarification_needed` envelope → answer `"go ahead"` → `success` envelope with a valid file path + summary.
- Scripted stdin (via a `StringIO` injected into `StdinResponder`): pipes the clarification answer.

Assertions:
- Final state has the expected fields.
- `artifacts_dir/<run-id>/lifecycle.jsonl` contains the expected sequence: `RUN_STARTED`, `AGENT_CONTAINER_STARTED`, `AGENT_INVOCATION_STARTED`, `TURN_STARTED`, `RESPONDER_REQUESTED`, `RESPONDER_ANSWERED`, `TURN_STARTED`, `TURN_COMPLETED`, `AGENT_INVOCATION_COMPLETED`, `FUNCTION_ACTION_STARTED`, `DOMAIN`, `FUNCTION_ACTION_COMPLETED`, `RUN_ENDED`.
- `artifacts_dir/<run-id>/<agent_name>/turns/0/` has `prompt.txt`, `envelope.json`, `output.json`, `collected_files/` populated.
- `artifacts_dir/<run-id>/inspect-workspace.sh` is executable and contains the volume name.
- `artifacts_dir/<run-id>/summary.txt` renders counts correctly.
- No orphan Docker containers: after `run_primitive_plan` returns, `docker.from_env().containers.list(filters={"ancestor": base_image_tag})` is empty.

- [ ] **Step 1: Write the test harness** (shim, fixtures, scenario JSON).
- [ ] **Step 2: Write the test.**
- [ ] **Step 3: Make it pass.** If any gap is found, fix the underlying module and add a unit test pinning the behavior.
- [ ] **Step 4: Commit.** `test(orchestration): end-to-end Plan 2 integration`.

### Task H.2: Type checks and lint

- [ ] `pdm run typecheck` in agent-foundry — clean.
- [ ] `pdm run lint` in agent-foundry — clean.
- [ ] `pdm test-all` in agent-foundry — all unit + (docker-gated) integration tests pass or skip cleanly.
- [ ] `pdm test-all` in archipelago — unchanged, still passing (Plan 2 does not touch Archipelago).

---

## Anticipated challenges

These are known risk points. Each lists a concrete mitigation; several flag ambiguities that were **not** locked during the brainstorm and must be revisited before or during implementation.

- **`AgentRunContext` forward-reference in `FunctionAction`.** `FunctionAction` lives in `primitives.models`; `AgentRunContext` lives in `orchestration.run_context`. A direct import creates a cycle. Use `TYPE_CHECKING` + `model_rebuild` with a `_types_namespace` finalizer in `primitives/__init__.py`. The pattern is already used elsewhere in Agent Foundry (per the primitive's existing `model_rebuild` calls), so extending it is low-risk.

- **JSON-schema-extra preservation in `to_claude_code_schema`.** The flattener in `acp/schema_tools.py` (CS6.5) strips `$defs`/`$ref` and `discriminator`. `x-agent-file-path` extensions must survive flattening. Task D.3 verifies this; the current implementation uses a blacklist that preserves unknown keys, so the test is expected to pass without source changes. If it doesn't, extend `_inline` to explicitly whitelist `x-*` extension keys.

- **Claude Code session-id capture.** The existing adapter already captures `event.session_id` from `SystemInitEvent` (see `claude_code.py` around line 315) and exposes it on `TurnResult.agent_session_id`. Plan 2's driver abstraction threads this through. No new event parsing needed.

- **Signal handlers and pytest.** `signal.signal()` called from a non-main thread raises. `_install_signal_handlers` guards with a `threading.current_thread() is main_thread()` check and returns `False` when uninstallable. Tests drive `cancel_event.set()` directly instead of sending signals.

- **`asyncio.Event` on a frozen Pydantic model.** `ConfigDict(frozen=True)` prevents attribute reassignment but not mutation of mutable values — `cancel_event.set()` remains valid. Task B.1 Step 1 pins this.

- **LangGraph sync/async node mixing.** Turning `_compile_agent_action`'s node async forces every enclosing compiler (sequence, conditional, loop, retry) to use `ainvoke` instead of `invoke` on its compiled sub-graph. Task G.1 Step 3 addresses this. All existing compiler tests that called `.invoke` on compiled sub-plans must be updated to `await .ainvoke`.

- **`FakeContainerManager` fidelity — RESOLVED.** The fake lives at the `ContainerManager` public-method boundary (the same methods in `agent_foundry/acp/container.py`: `create_container`, `start`, `stop`, `destroy`, `write_file_to_container`, `copy_from_container`, `read_file_from_container`, plus a scripted `exec_run` pass-through via `handle._container.exec_run`). It is defined in `tests/agent_foundry/orchestration/fakes.py` at its minimum F0 shape (Task F0.3); Phase B.4 extends it with reuse-policy keying and Phase F.3 extends it with scripted `exec_run` stream output. Tests do **not** fake below the `ContainerManager` boundary — the `docker` SDK is never mocked directly.

- **Architectural simplification: host-driven `docker exec` (not WebSocket) — RESOLVED.** Plan 2's executor drives `claude` from the host via `handle._container.exec_run(build_claude_cmd(...), stream=True)` for every turn (first and subsequent). No Python adapter process runs inside the container; no WebSocket server runs on the host. Stream-json output is read from exec's stdout and parsed by the existing transport-agnostic typed models in `acp/claude_code_events.py`. `claude --resume <session-id>` threads the session across turns. All retry logic (missing structured output, cold-start, refusal/max_tokens, `AgentFilePath` verification) runs host-side. Implications: (a) The in-container `ClaudeCodeAdapter`, the WS server in `acp/session.py`, and `AdapterBase`/`TurnResult` in `acp/adapter.py` are **not used** by Plan 2's new executor — they remain intact for legacy `docker_worker/` agents until CS11. (b) Plan 2 ports `_build_claude_cmd` into `orchestration/claude_cmd.py`. (c) `AgentFilePath` verification moves host-side (Phase E). (d) Production driver is `ExecRunDriver` in `orchestration/claude_cmd.py` (see F.3). Callers use `handle._container.exec_run` directly as the codebase already does in `validate_image`.

- **Session-id capture — RESOLVED.** `ClaudeCodeAdapter.run_turn` already parses the first `system` stream-json event (typed as `SystemInitEvent`) and extracts `event.session_id`; the existing `TurnResult` exposes it on `TurnResult.agent_session_id`. Plan 2's F.3 driver returns this value from its async `run_turn`; the executor records it on `LiveContainer.session_id` after the first turn that exposes a session id, regardless of outcome (matches adapter behavior — the `SystemInitEvent` arrives before any outcome event). An acceptance criterion is added to Task F.3: "the fake driver's `run_turn` returns `(envelope, session_id)`, and after the first turn `live.session_id` equals the captured id."

- **Instruction injection timing — RESOLVED.** The registry writes the instruction file via `ContainerManager.write_file_to_container(handle, ROLE_INSTRUCTIONS_PATH, text)` *after* `create_container(...)` and *before* `start(handle)`. The Docker SDK's `put_archive` (wrapped internally by `write_file_to_container`) accepts a created-but-not-yet-started container, so the file is on disk before `entrypoint.sh` runs. The entrypoint then appends that file onto `/home/claude/.claude/CLAUDE.md` via its existing `ACP_ROLE_INSTRUCTIONS_PATH` block (`entrypoint.sh` lines 46–51). No second per-run volume is needed.

- **Container env injection — RESOLVED.** Env is composed once at create time via `build_container_env(primitive, oauth_token=..., role_instructions_path=..., extra=...)` (Task F0.2) and passed to `ContainerManager.create_container(extra_env=...)`. Docker env is immutable post-create, which is fine because everything the container needs at boot (OAuth token, instructions path, optional repo URL) is known at create time. No WS-port env is required, because Plan 2's transport is `docker exec`-based rather than WS-based (see the multi-turn transport resolution above). Task B.4 no longer needs an `extra_env_resolver` callable; it composes env at create time via `build_container_env` directly.

- **20-turn responder loop cap is a platform default, not a brainstorm decision.** Added as a safety net to prevent infinite clarify-forever loops. If a product legitimately needs more, they can raise a follow-up to make it per-primitive; for Plan 2 the cap is hard-coded.

- **Cross-plan ordering.** This plan modifies Plan 1's `AgentAction` model (Phase A). If Plan 1 is already consumed by in-flight work (Plan 3 or Plan 4 branches), coordinate timing — Phase A lands first, then other work rebases.

---

## Verification checklist

After all tasks:

- [ ] **Phase 0 gate — `tests/agent_foundry/integration/test_foundation_smoke.py` passes** against real Claude Code. This is the foundational substrate check; it must pass before anything else is meaningful.
- [ ] **H.1 gate — `tests/agent_foundry/integration/test_plan2_end_to_end.py` passes** against real Claude Code. Drives the full Plan 2 stack; subsumes F0 integration coverage. (The F0 integration test `test_f0_agent_action_end_to_end.py` was deleted when H.1 landed; F0 unit tests still pin the minimum-viable scope.)
- [ ] `pdm run test-unit` passes in agent-foundry.
- [ ] `pdm run test-integration` passes (or skips with no-docker reason) in agent-foundry.
- [ ] `pdm run test-all` passes in archipelago (no regression — Archipelago is untouched).
- [ ] `pdm run typecheck` clean in both repos.
- [ ] `pdm run lint` clean in both repos.
- [ ] Manual smoke test: run a minimal plan containing one `AgentAction` against real Claude Code (requires a real Anthropic key and a real workspace volume). Inspect `<artifacts_dir>/<run-id>/`; confirm layout, `summary.txt` is readable, `inspect-workspace.sh` opens a shell into the volume, `lifecycle.jsonl` captures the expected events.

---

## Out of scope — explicit deferrals

The following are deliberately not in Plan 2. Each has a known home.

- **Escalation bridge** (`EscalationRequired` → LangGraph interrupt). Deferred until a concrete driving use case (e.g., Slack responder with timeouts).
- **Per-`AgentAction` responder overrides.** Current injection is per-system. Add when a real asymmetric requirement appears.
- **Commit-aware progress tracking** (`progress.jsonl` parsing, `PatchInfo`, `CommitEvidence`). CS8 scope.
- **Agent implementations** (Planner, Reviewer, Dispatcher, Integrator). CS7 Plan 4.
- **`CommitAction` / `SubmitPRAction` `FunctionAction`s.** CS7 Plan 4.
- **Instruction files for the four agents.** CS7 Plan 4.
- **`lessons-learned` skill move + base `CLAUDE.md` rewrite.** CS7 Plan 3.
- **Archipelago domain-level `summary.txt` renderer.** CS9 Task 4 (added to roadmap during the Plan 2 brainstorm).
- **Run artifacts retention/pruning.** Future change set.
- **Alternative execution strategies (SDK/API).** CS10.5.
- **`docker_worker/` deletion.** CS11.
- **Text-marker protocol removal.** CS11.
- **`ARCHIPELAGO_UPDATE_AVAILABLE` CI replacement.** CS11.

---

## Build deviations from the plan

The following adjustments were made during execution and landed on the branch. Each is aligned with the plan's final intent; this section records what diverged so future readers aren't confused by plan-vs-code mismatches.

### Design and primitive-model changes

1. **`AgentAction.name` required field added.** Plan 1 originally stated "no `name` field — composition is by direct Python object reference." That decision predated per-agent artifact directories and per-agent lifecycle events. Plan 2's `name: str = Field(min_length=1)` is a **diagnostic label only** (artifact directory naming, lifecycle event payloads, log prefixes) — it is *not* used for composition, lookup, or system-definition wiring. `AgentContainerRegistry` remains keyed by `id(primitive)`. Commit `c39e607`.
2. **`AgentRunContext` field defaults added.** B.1 specified `artifacts_dir`, `responder_provider`, `cancel_event` as required fields. They ship with defaults (ephemeral tmp via `tempfile.mkdtemp` for `artifacts_dir`; `None` for `responder_provider`; `asyncio.Event()` factory for `cancel_event`) so F0 call sites continue to work without the full Plan 2 wiring. Production code (`run_primitive_plan`) always supplies explicit values.
3. **Anti-gaming T/I-split contract dropped.** An early plan draft included a "Tests must commit RED, implementation commits GREEN, diff gate between them" contract. This proved incompatible with the pre-commit hook (which blocks RED commits) and was not retained in the final plan document. Phase F0 onward used role-scoped `-T`/`-I` subagents with merged commits; scope separation held at dispatch time even without the commit boundary.

### Transport and infrastructure changes

4. **`ACP_HOST_DRIVEN=1` env var + entrypoint mode.** The base ACP image's `entrypoint.sh` grew an `ACP_HOST_DRIVEN=1` branch that idles the container with `exec tail -f /dev/null` so the host-driven `docker exec` executor has something to exec into. `build_container_env` in `orchestration/env.py` always sets this env var. Not in the original plan; required to make the docker-exec transport work end-to-end. Phase 0.
5. **`CLAUDE.md` existence check in entrypoint.** The entrypoint's debug `cat /home/claude/.claude/CLAUDE.md` call was unguarded and crashed via `set -e` when the file was absent. Added a guard: if the file is absent, emit a clear `ERROR` message to stderr and `exit 1` (fail loudly, matching "safe-by-default" principle). Phase 0.
6. **Container readiness via Docker `HEALTHCHECK` (replaced the original fixed sleep).** The entrypoint runs 1–2+ seconds of setup (plugin install, role-instructions append, lockdown, product-init hook) before reaching the idle `tail -f /dev/null` state. `exec_run` calls during that window silently race against the setup: if they land before role-instructions have been appended onto `/home/claude/.claude/CLAUDE.md`, Claude Code starts without its role definition — a silent correctness bug, not just flakiness. An earlier build used a fixed 2-second `time.sleep(2)` + `handle.reload()` after `manager.start()`; that was unsafe on slow networks / loaded CI. The final fix uses the Docker-native mechanism: `Dockerfile.base` declares `HEALTHCHECK --interval=1s --timeout=3s --start-period=60s --retries=3 CMD test -f /tmp/.container-ready`; the entrypoint touches `/tmp/.container-ready` as its final step before `exec tail -f /dev/null`; `AgentContainerRegistry._wait_until_healthy` polls `container.attrs["State"]["Health"]["Status"]` every 250ms (90s timeout) and returns on `healthy`, raises on `unhealthy`/timeout. Test fakes (no real `_container` / no health attrs) are no-ops. Registry constructor grew a `wait_for_health: bool` param (+ `health_wait_timeout_seconds: float`, default 90s). `run_primitive_plan` sets `wait_for_health=True` when a real OAuth token is present. Phase 0's smoke test uses the same health-poll pattern inline. Commits: `c39e607` (initial 2s sleep landed via H.1) → `5cec83a` (replaced with HEALTHCHECK before Plan 2 completion).
7. **`pytest-asyncio` added as dev dep** with `asyncio_mode = "strict"`. Required by `@pytest.mark.asyncio` markers introduced from Phase B onward. Not called out in the plan.
8. **Per-turn artifact writes added to executor.** Plan 2's artifact layout section listed `<agent>/turns/<n>/prompt.txt`, `envelope.json`, `output.json`, but no specific task added the write logic. H.1 added it in `container_executor.py` (try/except wrapped, non-fatal on failure).
9. **`FUNCTION_ACTION_STARTED/COMPLETED/FAILED` event emission added to compiler.** The event enum listed these in B.5 but no specific task wired their emission. H.1 added it in `_compile_function_action` when a run context is active.

### Driver and protocol changes

10. **Driver contract is `(prompt, resume_session_id) -> (envelope, session_id)`.** An earlier draft of F.3 had `(prompt, json_schema=, resume_session_id=)`. The schema is computed once per invocation and closed over by the driver factory, not passed per-turn. F0.4 used the old shape; F.3 migrated F0 tests to the new shape.
11. **`run_primitive_plan` became async; sync preserved as `run_primitive_plan_sync`.** G.2 added the async entry point. The sync version emits `DeprecationWarning`. Some pre-existing `test_primitive_compiler.py` call sites import the sync version via alias to avoid a ~40-line sweep; those will migrate naturally as their behavior changes.
12. **`ClaudeCodeAdapter` and WS server remain intact** for legacy `docker_worker/` agents. Plan 2's new executor uses host-driven `docker exec` (ported `_build_claude_cmd` from adapter into `orchestration/claude_cmd.py` — though that module's `ExecRunDriver` stub is still optional; H.1 used an in-test adapter shim). CS11 cleanup retires the adapter/WS path.

### Phase H changes

13. **F0 integration test deleted.** `test_f0_agent_action_end_to_end.py` was removed when H.1 landed: H.1's integration test subsumes F0's coverage (same substrate requirements, strictly larger scope). F0 unit tests (`test_run_context_f0`, `test_env_f0`, `test_registry_f0`, `test_container_executor_f0`) continue to pin the minimum-viable F0 scope.

### Summary of changes to the AgentAction surface

For quick reference — the final `AgentAction` model differs from the original Plan 1 shape as follows:

| Field | Plan 1 | Plan 2 |
|---|---|---|
| `name` | (not present) | Required `str`, non-empty (diagnostic label) |
| `prompt_builder` | Required | Required |
| `instructions_provider` | Required | Required |
| `response_channel` | Required (`StructuredOutputChannel` or `FileCollectionChannel`) | **Removed** — always structured output |
| `executor` | Required | Required |
| `timeout_seconds` | Default 3600 | Default 3600 |
| `skip_permissions` | Default False | Default False |
| `visible_dirs` | Default `[]` | Default `[]` |
| `writable_dirs` | Default `[]` | Default `[]` |
| `reuse_policy` | Optional, default `NEW_EACH_TIME` | **Required**, no default; two variants (`REUSE_RESUME`, `REUSE_NEW_SESSION`) |
