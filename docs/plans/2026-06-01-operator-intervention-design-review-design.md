# Operator Intervention for Design-Review Exhaustion (Option A)

**Date:** 2026-06-01
**Status:** Approved design — ready for `plan`

## Problem statement

Archipelago's design-review `Retry` loop (`systems/pipeline.py:227`) runs the
designer + reviewers up to `max_attempts=3`. When the loop exhausts without
`_design_review_passed` returning true, it is fail-closed: with no
`on_max_attempts_resolver` configured, Agent Foundry raises `RetryAborted` and
the whole run dies.

We need a human operator to intervene at exhaustion and choose one of three
actions:

- **abort** the run,
- **accept** the current design and continue downstream, or
- **retry with guidance** — supply instructions to the designer on how to
  resolve the outstanding design issues.

## Approved approach

Use Agent Foundry's existing resolver seat (`Retry.on_max_attempts_resolver`)
with a **synchronous `FunctionAction` that interacts with the operator over
stdin/stdout** (Option A). This works entirely inside the current single,
blocking `asyncio.run` execution — no checkpointer, no pause/resume loop, no
runner changes.

The operator's three choices map 1:1 onto `DispositionKind`:

| Operator choice | Disposition | Effect |
|---|---|---|
| abort | `ABORT(reason)` | raises `RetryAborted` — run terminates |
| accept | `ACCEPT` | resolver's merged state flows downstream |
| retry with guidance | `RETRY` | body re-enters once with guidance injected |

### Why Option A (not GateAction / Option B)

`GateAction` is built on graph-level `interrupt_before` + checkpointer: it pauses
the run by *exiting* the invocation, requiring an external resume cycle the
runner does not implement today (`run_primitive_plan` does a single `ainvoke`
with no `thread_id`). That is the resumable / absent-operator path and is
tracked separately:

- Agent Foundry #66 — runner support for GateAction interrupt + resume (Option B)
- Agent Foundry #67 — let `FunctionAction` consult a `Responder` (async)

For present needs — one blocking run, operator present at the terminal — a sync
`FunctionAction` reading stdin is sufficient. It deliberately bypasses the
`Responder` abstraction; #67 is the future cleanup.

### RETRY semantics

A framework `RETRY` re-enters the body **exactly once**, then re-evaluates
`until`:

- if the guided attempt now passes → run continues downstream automatically;
- if it still fails → control returns to the operator resolver.

`resolver_max_reentries` is left at the framework default (50).

## Component breakdown

### 1. State additions — `DesignReviewState` (`systems/pipeline.py`)

- `disposition: ResolverDisposition | None = None` — the resolver output
  contract the compiler reads to route ACCEPT/ABORT/RETRY.
- `operator_guidance: str | None = None` — operator instructions carried into
  the guided re-attempt.

Both default to `None`, so the body Sequence's eager scope-in validation is
unaffected.

### 2. `DesignerInput` addition (`agents/models.py`)

- `operator_guidance: str | None = None` — projected from `DesignReviewState` by
  field-name matching so the designer can read it.

### 3. Designer prompt (`agents/designer/primitive.py`)

`designer_prompt_builder`: when `operator_guidance` is set, include it as a
prioritized "operator guidance" section alongside the existing must-fix
findings. Guidance steers; findings remain the concrete defect list.

### 4. Operator resolver (`agents/design_review/operator_resolver.py`, new)

A sync `FunctionAction[DesignReviewState, DesignReviewState]`:

1. Print an exhaustion summary: attempt count, the latest verdict's must-fix
   findings + INADEQUATE dimensions, and the `exhaustion_reason` metadata.
2. Prompt `[abort / accept / retry]`; re-prompt on invalid input.
3. Branch:
   - **abort** → prompt for a reason → return state with
     `disposition = ResolverDisposition(kind=ABORT, reason=...)`.
   - **accept** → return state with `disposition = ResolverDisposition(kind=ACCEPT)`.
   - **retry** → prompt for guidance text → return state with
     `disposition = ResolverDisposition(kind=RETRY)` and `operator_guidance` set.

Input is read via an injected callable parameter defaulting to `input`, so tests
inject a scripted responder rather than monkeypatching global stdin.

### 5. Wiring (`systems/pipeline.py`)

Set `design_review_loop.on_max_attempts_resolver = operator_resolver`.

### 6. CLI (`scripts/run_full_pipeline.py`)

Catch `RetryAborted`, print its `reason`, and exit non-zero cleanly — so an
operator abort reads as a terminal outcome, not a crash traceback.

## Data flow

```
design_review_loop (max_attempts=3)
  └─ exhausted without passing
       └─ operator_resolver  ── reads exhaustion_reason + latest verdict
            ├─ ABORT  → RetryAborted(reason) → CLI prints reason, non-zero exit
            ├─ ACCEPT → merged state (non-passing verdict) flows downstream
            └─ RETRY  → body once with operator_guidance
                          ├─ passes → downstream
                          └─ fails  → back to operator_resolver
```

On ACCEPT the verdict remains non-passing — it only gated the loop. The
`design_document_path` is real (a prior designer run wrote it), so the
downstream change-sets boundary receives a valid path.

## Error handling

- Invalid operator input → re-prompt, no crash.
- ABORT → `RetryAborted(reason)` caught at the CLI for a clean terminal message.
- Resolver disposition is recorded in the Agent Foundry lifecycle stream
  (`RESOLVER_DISPOSITION`) — no new event work in Archipelago.

## Test strategy (TDD)

- Resolver unit tests with an injected input callable: each of abort / accept /
  retry produces the correct `ResolverDisposition`; retry sets
  `operator_guidance`; invalid-then-valid input re-prompts.
- `designer_prompt_builder` includes operator guidance when present and omits the
  section when absent.
- Wiring test: `design_review_loop.on_max_attempts_resolver is operator_resolver`.
- Full gate (`pdm test-all`) before commit.

## Concerns checklist

| Concern | Disposition |
|---|---|
| i18n, analytics, feature-flags, caching, webhooks, security-auth, responsive | N/A |
| migrations | N/A — new fields are optional with defaults; backward compatible |
| event-publishing | N/A — disposition lifecycle event emitted by Agent Foundry |
| error-handling | **Yes** — invalid-input re-prompt, `RetryAborted` CLI catch, reason propagation |
| security | Trivial — local operator stdin, trusted input; guidance becomes designer prompt text |
| test-strategy | **Yes** — TDD unit tests above |

## Open / deferred

- Absent-operator / resumable intervention via `GateAction` → Agent Foundry #66.
- Responder-based resolver (drop direct stdin) → Agent Foundry #67.
- Clean run-termination signal so ABORT is a non-error terminal outcome →
  deferred in Agent Foundry.
