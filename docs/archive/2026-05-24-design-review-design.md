# Design Review (Designer → Review → Retry → Operator Gate)

## Problem Statement

Today the full working-session pipeline runs Designer before the change-set planner. The Designer agent produces a `DesignDocument` and an investigation summary, and the pipeline then passes the design directly to downstream consumers, starting with the change-set planner. There is no review step between Designer and those consumers.

This means design defects — missed acceptance criteria, violated constraints, weak cohesion, leaky abstractions — survive into downstream stages, where the cost of correcting them grows. By the time a TDD planner has consumed a flawed design and produced an implementation task, fixing the original design defect requires unwinding the planner's work too. The fix needs to happen at the design boundary, while the Designer can still iterate cheaply on its own output.

The goal of this work is to insert a review step immediately after the Designer that judges the design against (a) the feature definition it was meant to satisfy and (b) engineering quality principles, and that can route the design back to the Designer for revision when the review fails. After a bounded number of failed attempts, an operator is invited to override the verdict or terminate the working session.

## Approved Approach

Insert a design-review step into the full working-session pipeline immediately after Designer and before the change-set planner, composed of:

- **Two `AICall` reviewers** (no container; in-process structured-output inference) — one for correctness against the feature definition, one for engineering quality against a fixed rubric.
- **An aggregator `FunctionAction`** that combines both verdicts into a single `DesignReviewVerdict` and computes its `passed` flag.
- **A `Retry` primitive** wrapping `[designer, load-design-into-state, correctness-review, quality-review, aggregator]` with `max_attempts=3` and `until=lambda s: s.design_review_verdict.passed`. The Designer is inside the retry body so every Designer invocation is followed by review.
- **A post-Retry `Conditional`** that routes to a `GateAction` when the verdict still hasn't passed after three attempts.
- **A `GateAction`** that displays the full review history and lets a human operator choose `APPROVE` (proceed downstream with the latest design) or `ABORT` (terminate the working session).

This is the minimum sufficient shape: no new primitives are needed (`AICall`, `Retry`, `Conditional`, `GateAction`, `FunctionAction` all exist in Agent Foundry), and no new container surface is needed (the reviewers are in-process inference calls; the existing `read_markdown` action handles the bridge from container artifacts to in-process state).

## Architecture

### Pipeline Composition

```
Sequence[
  workspace_bootstrap,
  Retry(
    max_attempts = 3,
    until        = lambda s: s.design_review_verdict.passed,
    body = Sequence[
      designer,                        # existing AgentAction, REUSE_NEW_SESSION
      load_design_into_state,          # FunctionAction → DesignDocument in state
      load_investigation_into_state,   # FunctionAction → investigation_summary_text in state
      design_correctness_review,       # AICall (custom executor) → correctness_verdict in state
      design_quality_review,           # AICall (custom executor) → quality_verdict in state
      aggregate_design_verdict,        # FunctionAction → DesignReviewVerdict, appends to history
    ],
  ),
  Conditional(
    condition   = lambda s: not s.design_review_verdict.passed,   # gate fires only on failure
    then_branch = Sequence[
      render_operator_payload,         # FunctionAction → Markdown payload in state
      operator_gate,                   # GateAction → OperatorDecision in state
      apply_operator_decision,         # FunctionAction → terminal "proceed" or "aborted" state
    ],
    # else_branch omitted (defaults to no-op) — passed design proceeds to downstream consumers.
  ),
]
```

### New Components

**`load_design_into_state` (FunctionAction)**
- Reads: `state.workspace_handle`, `state.design_document_path`
- Writes: `state.design_document` (`DesignDocument`)
- Uses the existing `archipelago.actions.workspace_io.read_markdown` helper.

**`load_investigation_into_state` (FunctionAction)**
- Reads: `state.workspace_handle`, `state.investigation_summary_path`
- Writes: `state.investigation_summary_text` (`str` — raw markdown)
- Uses `archipelago.actions.workspace_ops.read_file` directly. The investigation summary is freeform Designer output with no canonical schema, so loading it as raw text avoids inventing a Pydantic model just to round-trip text the reviewer reads in full anyway. The quality reviewer's prompt formats it as a fenced code block.

**`design_correctness_review` (AICall)**
- Input: `feature_definition` + `design_document`. (No codebase context; correctness is a traceability exercise against the spec.)
- Output: `CorrectnessReviewOutput`, whose single field writes `state.correctness_verdict`.
- `executor`: `_correctness_executor` (see below) — wraps `invoke_ai_call` with transient-failure handling.
- Registered with the `agent_foundry.evals` registry so it can be evaluated independently.

**`design_quality_review` (AICall)**
- Input: `design_document` + `investigation_summary_text`. (The investigation summary is Designer's captured codebase context; reusing it grounds quality judgments in the same context the design was made against without a second codebase read.)
- Output: `QualityReviewOutput`, whose single field writes `state.quality_verdict`.
- `executor`: `_quality_executor` (analogous to the correctness executor).
- Registered for independent eval.
- Accepted v1 limitation: because the quality reviewer uses Designer-produced context rather than independently inspecting the codebase, it may miss quality issues caused by an incomplete Designer investigation. Revisit if real runs show repeated blind spots.

**`_correctness_executor` and `_quality_executor` (AICall executor wrappers)**

Each wraps `agent_foundry.ai_models.execute.invoke.invoke_ai_call` with a try/except for the bounded set of transient inference failures:

- `anthropic.APIConnectionError` — network failure (DNS/TCP/TLS)
- `anthropic.APITimeoutError` — request timeout
- `anthropic.RateLimitError` — 429 after SDK-internal retries exhausted
- `anthropic.APIStatusError` — 5xx variants
- `RuntimeError` raised by `AnthropicProvider` when the response contains no `tool_use` block (model ignored the tool-use directive)
- `pydantic.ValidationError` — provider's tool-input value didn't satisfy the verdict schema (including our own `@model_validator`s such as the INADEQUATE-with-no-finding rule)

On any of these: the executor builds a placeholder verdict of the appropriate type (`CorrectnessVerdict` or `QualityVerdict`) with every dimension scored `INADEQUATE`, one synthesized must-fix finding per dimension whose `description` carries the exception type and message and whose `suggested_resolution` is "Retry the design pass; this may be a transient provider error," and `reviewer_notes` recording that the verdict was synthesized in lieu of a real reviewer response. It then wraps that verdict in the reviewer output model so Agent Foundry writes the intended named state slot (`correctness_verdict` or `quality_verdict`) rather than flattening verdict internals into shared state.

On any other exception (`AuthenticationError`, `PermissionDeniedError`, `BadRequestError`, errors from the AICall's instruction/prompt resolver callables, or any unanticipated exception class): the executor lets the exception propagate. These represent system-config or programmer errors and should not be silently swallowed.

The placeholder verdict satisfies the `CorrectnessVerdict`/`QualityVerdict` validators (every INADEQUATE dimension has a citing finding, every dimension is scored), so it can be aggregated normally. The aggregator computes `passed=False`, the Retry condition stays False, and the loop advances to the next attempt. If all three attempts hit transient failures, the operator gate fires with three `INADEQUATE` verdicts whose `reviewer_notes` make clear the failure was infrastructure rather than design quality — an operator can `ABORT` without burning a real review cycle on transient errors.

Parameter names follow the `AICall.executor` contract: `async def _correctness_executor(*, primitive: AICall, model_input: DesignReviewInput) -> CorrectnessReviewOutput`. Both reviewers' executors share the same wrapping logic but return different output wrapper types — extract a generic helper if the duplication grates.

**`aggregate_design_verdict` (FunctionAction)**
- Input: `state.correctness_verdict`, `state.quality_verdict`, `state.design_review_history`.
- Output: `state.design_review_verdict` (with `passed` and `attempt_number` set), `state.design_review_history` with the new verdict appended.
- `passed = (every correctness dimension is not INADEQUATE) and (every quality dimension is not INADEQUATE) and (no must-fix findings in either verdict)`.
- Emits a `step_completed` lifecycle event with the verdict payload so artifacts capture per-attempt review state.

**`render_operator_payload` (FunctionAction)**
- Input: `state.workspace_handle`, `state.feature_definition`, `state.design_document`, `state.design_review_history`.
- Output: `state.operator_prompt` — a rendered Markdown string for the gate to display, containing: the design document path + excerpt, the latest verdict's must-fix findings and dimension scores from both reviewers, a per-attempt history summary, and the feature definition path + excerpt (constraints + scope boundaries + acceptance criteria).

**`operator_gate` (GateAction)**
- `interaction = "human_stdin"`.
- `prompt_key = "operator_prompt"`.
- Parses stdin response into `OperatorDecision`. On parse failure, re-prompts.

**`apply_operator_decision` (FunctionAction)**
- Input: `state.operator_decision`.
- Output: a terminal state field indicating whether downstream pipeline stages should proceed (`APPROVE`) or whether the working session should end (`ABORT`).
- Planning note: verify Agent Foundry's actual terminal-control mechanism for `ABORT`. A state field alone may not stop a surrounding `Sequence`; the implementation plan must determine whether `ABORT` should raise a controlled terminal exception, route downstream stages through a `Conditional`, or use the Guided Retry / gate runtime's terminal transition support.

## Data Flow

```
FeatureDefinition + CodebaseSource
  │
  ▼
workspace_bootstrap ──▶ WorkspaceHandle
  │
  ▼
[Retry attempt N]
  ├─ Designer ──▶ DesignerOutput (paths to design + investigation files in /workspace/documents)
  ├─ load_design_into_state          ──▶ DesignDocument (parsed)
  ├─ load_investigation_into_state   ──▶ investigation_summary_text (raw markdown str)
  ├─ design_correctness_review (AICall) ──▶ correctness_verdict
  ├─ design_quality_review     (AICall) ──▶ quality_verdict
  └─ aggregate_design_verdict        ──▶ DesignReviewVerdict (+ appended to history)
       │
       └─ Retry.until evaluates verdict.passed
             ├─ True  → exit Retry
             └─ False → next attempt (up to 3 total)

[Post-Retry Conditional]
  ├─ verdict.passed → noop, downstream pipeline continues
  └─ !verdict.passed
       ├─ render_operator_payload ──▶ operator_prompt (Markdown)
       ├─ operator_gate           ──▶ OperatorDecision
       └─ apply_operator_decision ──▶ proceed | aborted
```

**Designer's retry-context behavior:** Designer's `prompt_builder` reads `state.design_review_verdict` (the last attempt's verdict, populated from the previous Retry iteration). When present, the prompt instructs Designer to read its prior design from disk (`state.design_document_path`) and revise it in light of the supplied must-fix findings and `INADEQUATE` dimension scores. When absent (first attempt), the prompt is the existing first-pass brief.

Designer remains `REUSE_NEW_SESSION`. The container persists for the duration of the design pipeline; the volume holds the prior design across sessions; each session starts fresh agent context with explicit inputs.

## Data Model Additions

All new types are Pydantic `BaseModel`s. Enumerated values use `StrEnum` per the project's data-model conventions; no `Literal`.

### Enums

```python
class DimensionScore(StrEnum):
    MEETS_BAR = "meets_bar"
    NEEDS_IMPROVEMENT = "needs_improvement"
    INADEQUATE = "inadequate"

class CorrectnessDimension(StrEnum):
    REQUIREMENT_COVERAGE = "requirement_coverage"
    INTERFACE_FIDELITY = "interface_fidelity"
    SCOPE_DISCIPLINE = "scope_discipline"
    CONSTRAINT_ADHERENCE = "constraint_adherence"

class QualityDimension(StrEnum):
    COHESION = "cohesion"
    MODULARITY = "modularity"
    ABSTRACTION_QUALITY = "abstraction_quality"

class OperatorDecisionKind(StrEnum):
    APPROVE = "approve"
    ABORT = "abort"
```

### Findings & Verdicts

```python
class CorrectnessMustFixFinding(BaseModel):
    description: str
    suggested_resolution: str
    dimension: CorrectnessDimension

class QualityMustFixFinding(BaseModel):
    description: str
    suggested_resolution: str
    dimension: QualityDimension

class CorrectnessVerdict(BaseModel):
    dimension_scores: dict[CorrectnessDimension, DimensionScore]
    must_fix_findings: list[CorrectnessMustFixFinding]
    reviewer_notes: str

    @model_validator(mode="after")
    def _all_dimensions_scored(self) -> Self:
        missing = set(CorrectnessDimension) - set(self.dimension_scores)
        if missing:
            raise ValueError(
                f"Every CorrectnessDimension must be scored. "
                f"Missing: {sorted(d.value for d in missing)}"
            )
        return self

    @model_validator(mode="after")
    def _inadequate_dims_have_findings(self) -> Self:
        inadequate = {
            d for d, s in self.dimension_scores.items()
            if s == DimensionScore.INADEQUATE
        }
        cited = {f.dimension for f in self.must_fix_findings}
        missing = inadequate - cited
        if missing:
            raise ValueError(
                f"Dimensions scored INADEQUATE must each have at least one "
                f"must_fix finding citing them. Missing: "
                f"{sorted(d.value for d in missing)}"
            )
        return self

class QualityVerdict(BaseModel):
    dimension_scores: dict[QualityDimension, DimensionScore]
    must_fix_findings: list[QualityMustFixFinding]
    reviewer_notes: str

    @model_validator(mode="after")
    def _all_dimensions_scored(self) -> Self:
        missing = set(QualityDimension) - set(self.dimension_scores)
        if missing:
            raise ValueError(
                f"Every QualityDimension must be scored. "
                f"Missing: {sorted(d.value for d in missing)}"
            )
        return self

    @model_validator(mode="after")
    def _inadequate_dims_have_findings(self) -> Self:
        inadequate = {
            d for d, s in self.dimension_scores.items()
            if s == DimensionScore.INADEQUATE
        }
        cited = {f.dimension for f in self.must_fix_findings}
        missing = inadequate - cited
        if missing:
            raise ValueError(
                f"Dimensions scored INADEQUATE must each have at least one "
                f"must_fix finding citing them. Missing: "
                f"{sorted(d.value for d in missing)}"
            )
        return self
```

### Reviewer Outputs

`AICall` outputs are merged into Agent Foundry state by their output model's field names. The reviewers therefore return wrapper output models instead of returning `CorrectnessVerdict` or `QualityVerdict` directly; this prevents their shared internal field names (`dimension_scores`, `must_fix_findings`, `reviewer_notes`) from colliding in flat pipeline state.

```python
class CorrectnessReviewOutput(BaseModel):
    correctness_verdict: CorrectnessVerdict

class QualityReviewOutput(BaseModel):
    quality_verdict: QualityVerdict
```

### Aggregated Verdict

```python
class DesignReviewVerdict(BaseModel):
    correctness: CorrectnessVerdict
    quality: QualityVerdict
    passed: bool                   # set by the aggregator
    attempt_number: int            # 1, 2, or 3
```

Consumers that want a flat finding view concatenate at the call site:

```python
all_findings = (
    verdict.correctness.must_fix_findings
    + verdict.quality.must_fix_findings
)
```

`passed` is a stored field set by `aggregate_design_verdict`, not a Pydantic computed field — keeping the threshold policy in one function makes it easy to tune later (e.g., if `NEEDS_IMPROVEMENT` should block, edit one function rather than the model).

### Operator Decision

```python
class OperatorDecision(BaseModel):
    kind: OperatorDecisionKind
    comment: str | None = None
```

### Pipeline State Additions

`DesignPipelineState` grows the following fields:

```python
# new fields on DesignPipelineState
design_document: DesignDocument | None = None
investigation_summary_text: str | None = None
correctness_verdict: CorrectnessVerdict | None = None
quality_verdict: QualityVerdict | None = None
design_review_verdict: DesignReviewVerdict | None = None
design_review_history: list[DesignReviewVerdict] = []
operator_prompt: str | None = None
operator_decision: OperatorDecision | None = None
```

## Error Handling

Three explicit failure modes, organised by which step raises:

1. **Reviewer `AICall` raises a transient inference exception.** The custom executor (`_correctness_executor` / `_quality_executor`, see *New Components* above) catches the bounded set of transient failures and returns a synthesized `INADEQUATE`-everywhere placeholder verdict. From `Retry`'s perspective the AICall completed successfully and produced output; the aggregator combines the placeholder into a `DesignReviewVerdict` with `passed=False`; the Retry loop advances to the next attempt. If all three attempts hit transient failures, the operator gate fires with the per-attempt verdicts in `design_review_history`, each carrying the underlying exception details in `reviewer_notes`. The `Retry` itself uses the default `RetryExceptionPolicy.PROPAGATE` — exception handling is entirely the executor's responsibility, not the loop's.

2. **Reviewer `AICall` raises an unrecoverable exception** (`AuthenticationError`, `PermissionDeniedError`, `BadRequestError`, or any error class outside the executor's catch list). The executor lets the exception propagate. The `Retry` propagates it further (no `RetryExceptionPolicy.CATCH_AND_CONTINUE` for this pipeline). The pipeline aborts. This is the right behavior — these failures represent system-config or programmer bugs that retrying would only mask.

3. **Other body steps raise.** Same as case 2: the exception propagates and the pipeline aborts.
   - `load_design_into_state` / `load_investigation_into_state`: workspace volume gone, file missing, design file fails to parse as `DesignDocument`. The pipeline cannot review content the system cannot read.
   - `designer` (`AgentAction`): container crash, OOM, agent timeout. Operator restarts the working session. (Accepted v1 limitation — see *Open / Deferred*.)
   - `aggregator` (`FunctionAction`): code bug. Should fail loudly.

4. **Operator response doesn't parse as `OperatorDecision`** (malformed input, unknown action). `operator_gate` re-prompts. No retry counter; the operator is trusted to eventually produce a parseable response.

## Test Strategy

TDD throughout. Unit and integration tests written before implementation.

- **Aggregator unit tests** — all combinations of (must-fix non-empty, all-MEETS_BAR, any INADEQUATE) across both verdicts → expected `passed` boolean.
- **Verdict validator tests** — partial dimension coverage rejected, INADEQUATE without matching finding rejected, NEEDS_IMPROVEMENT without finding accepted, INADEQUATE with matching finding accepted.
- **Retry-body integration test with fake AICall executor** — canned `CorrectnessReviewOutput`/`QualityReviewOutput` sequences exercise: pass on attempt 1, pass on attempt 2, pass on attempt 3, exhaust attempts.
- **Operator gate integration test** — scripted stdin responder feeds `APPROVE` and `ABORT` cases; `apply_operator_decision` produces the right terminal state.
- **AICall executor failure-mode test** — for each exception class in the catch list, the executor returns a synthesized `INADEQUATE` verdict wrapped in the appropriate reviewer output model; the verdict satisfies the verdict validators; the aggregator combines it into `passed=False`; the Retry advances. For an out-of-catch-list exception (e.g., `AuthenticationError`), the executor propagates and the pipeline aborts.
- **`read_markdown` failure-mode test** — using the existing fault-injection seam, simulate volume read failure; pipeline raises.
- **Real-LLM end-to-end** — too expensive/flaky for CI; covered manually before merge against the existing fixture feature definition.

## Concerns Checklist

Walked through `jig.config.md`'s checklist:

| Concern | Verdict | Notes |
|---|---|---|
| i18n | N/A | No user-facing strings. |
| analytics | N/A | Internal pipeline. |
| feature-flags | N/A | Single switch; no per-feature flags. |
| migrations | N/A | New state fields, no schema migration. |
| caching | N/A | |
| webhooks | N/A | |
| event-publishing | Yes (implicit) | Aggregator emits `step_completed` with verdict payload; lifecycle event capture verified by test. |
| security-auth | N/A | |
| responsive | N/A | |
| error-handling | Yes | See **Error Handling** section above. |
| security | Light | AICall sends `FeatureDefinition` + `DesignDocument` + the raw investigation-summary markdown to the LLM provider over the provider API. Accepted v1 risk: the investigation summary could contain codebase excerpts, secrets, or other sensitive values if Designer included them verbatim. No redaction or secret scanning is added in v1; rely on existing product/provider data-handling controls and revisit if real-world runs surface leakage. Not a blocker. |
| test-strategy | Yes | See **Test Strategy** section above. |

## Rationale (Key Design Decisions)

### Why two `AICall`s instead of one

Two distinct evaluation frames pull on different muscles: correctness traces the design against the feature definition's positive specs (acceptance criteria, interfaces) and negative specs (scope boundaries, constraints); quality judges the design against engineering rubrics (cohesion, modularity, abstractions). A single prompt that tries to apply both rubrics surfaces obvious issues in each and skims subtle ones — attention is finite per token, and rubric sprawl dilutes focus.

**The dominant driver, though, is independent improvement loops.** Two AICalls become two independently-registered eval targets. The correctness prompt can be iterated against a fixture set of "designs that miss requirements" without disturbing the quality reviewer's eval results, and vice versa. With a combined call, every prompt change risks regressing the other dimension — which slows down the feedback loop that actually drives "eventually better designs." Split-by-cohesion preserves the per-dimension regression test surface; combined doesn't. This is the long-game argument and probably the strongest single reason for the split.

A combined reviewer can catch one class of issue the split version misses: joint failures where a design is technically correct only because it adopts a brittle abstraction. In practice this is rare, and the must-fix loop catches the symptoms on the next round once they surface. Not a strong enough counter to flip the decision.

### Why categorical scoring instead of numeric

LLM scoring on a numeric 1–5 scale drifts run-to-run for the same content; the model isn't well-calibrated across runs and threshold gating becomes noisy. A three-tier categorical scale (`MEETS_BAR` / `NEEDS_IMPROVEMENT` / `INADEQUATE`) has much tighter inter-run agreement because the model is making a coarser distinction. The pass/fail gate becomes deterministic instead of noisy.

The categorical scale also forces specificity: a `NEEDS_IMPROVEMENT` rating without enumerated reasoning (in `reviewer_notes` or a must-fix finding) is operationally meaningless; the validator and the prompt push the reviewer toward concrete content. A "3 out of 5" with no explanation is just a number.

### Why constraint adherence is its own correctness dimension

The feature definition splits its specs into positive (acceptance criteria, interfaces) and negative (scope boundaries, constraints). A design can satisfy every acceptance criterion while violating a constraint — the two are independent. Without a dedicated dimension, the reviewer has no incentive to systematically check each constraint, and there's no signal in the verdict that constraints were considered. Treating constraint violations as automatic must-fix findings (rather than as a scored dimension) loses that checklist signal — the reviewer doesn't have to explicitly affirm "I looked at every constraint."

### Why `NEEDS_IMPROVEMENT` doesn't block pass

Every design has rough edges. Gating on `MEETS_BAR` across every dimension means the loop rarely terminates in three attempts on non-trivial features, which collapses the design-review step into an operator-escalation step. `INADEQUATE` is the structural-failure bar that genuinely blocks. `NEEDS_IMPROVEMENT` signals are still visible to the operator on escalation via `reviewer_notes` and the verdict history; they're just not loop blockers.

### Why Designer is inside the Retry body

The alternative is to keep the first Designer invocation outside the loop and put only the review + revision inside. That requires special-casing the first attempt and complicates the state shape (the verdict has to be `None` somewhere in the diagram). Putting Designer inside the body makes every attempt symmetric: invoke Designer, review, aggregate. The `prompt_builder` reads `state.design_review_verdict` to know whether this is a first pass (verdict absent) or a revision (verdict present); no special-casing in the pipeline shape.

### Why custom `AICall.executor` wrappers but not `RetryExceptionPolicy.CATCH_AND_CONTINUE`

Agent Foundry now offers two complementary capabilities for failure tolerance: a configurable `AICall.executor` (which lets a wrapper translate transient inference exceptions into structured fallback verdicts) and `Retry.exception_policy = RetryExceptionPolicy.CATCH_AND_CONTINUE` (which makes the Retry loop tolerate any exception raised during an attempt). Using both would maximize resilience, but it would also tolerate exceptions from steps this design wants to fail fast on — `load_design_into_state` / `load_investigation_into_state` (workspace I/O bugs the operator must see), the `aggregator` (programmer bug), and the `designer` container (catastrophic enough that automatic retry of a 10–20 minute step on infra hiccups is the wrong default for v1). `Retry` therefore stays on the default `PROPAGATE` policy; the AICall executors handle the failure class — transient inference errors — that is actually worth tolerating in this pipeline.

If real-world runs surface designer container crashes frequently enough to motivate retry, swapping `Retry.exception_policy` to `RetryExceptionPolicy.CATCH_AND_CONTINUE` is a one-field change. Until then, the loud-fail behavior on non-AICall exceptions is preserved.

### Why two reviewers are sequenced, not parallel

Agent Foundry has no parallel-composition primitive today. The two AICalls are written with **disjoint state reads and writes** (`correctness_verdict` and `quality_verdict` are separate fields; neither reads the other's output), so when a `Parallel[I, O]` primitive ships, swapping `Sequence[correctness, quality]` for `Parallel[correctness, quality]` is a constructor-name change with no other code edits. The extra latency in the interim (one AICall instead of two in parallel, ~30s) is dwarfed by Designer's container time.

## Open / Deferred

### Operator `GUIDE` action — deferred to v2

The operator gate currently exposes only `APPROVE` and `ABORT`. A third option — `GUIDE`, where the operator writes their own findings and the system runs Designer once more with those findings, then re-reviews — is genuinely valuable (it gives the operator a path between "rubber-stamp" and "throw away an hour of agent work") but requires an Agent Foundry capability that doesn't exist today: re-entering an exhausted retry with an external participant's verdict in place of the automated one. That platform work is captured in its own feature definition: `agent-foundry/docs/archipelago/2026-05-24-operator-guided-retry-feature-def.md`. v1 ships without `GUIDE`; v2 enables it once the platform feature lands.

### Parallel composition for sibling reviewers — deferred

The two reviewers are sequenced because Agent Foundry has no `Parallel` primitive. The state-write shape of the two `AICall`s is already disjoint so the eventual swap is mechanical. No work item filed against this directly; tracked as a known optimization.

### Designer container failure on retry — accepted v1 limitation

A `designer` container crash (Docker daemon hiccup, OOM kill, mid-run timeout) propagates and aborts the pipeline. The operator restarts the working session, losing any agent work from prior attempts in the loop. The platform capability that would make this survivable — `Retry.exception_policy = RetryExceptionPolicy.CATCH_AND_CONTINUE` — has landed (see `agent-foundry/docs/plans/failure-resilience-retry-aicall.md`), but the design opts not to use it (see *Why custom `AICall.executor` wrappers but not `RetryExceptionPolicy.CATCH_AND_CONTINUE`* in *Rationale*). Reconsider this choice if container failures become frequent enough in real-world runs to justify auto-retry of a 10–20 minute step.

### Relationship to commit review

A separate Reviewer concept exists in `job-add-review.md` (the umbrella job-add-review proposal): a reviewer agent that judges change-set commits with must-fix-before-PR vs can-defer findings. That reviewer reviews **commits**; this one reviews a **design document**. They share the "review → loop on failure → escalate to operator" pattern but operate on different artifacts at different lifecycle points. Naming chosen to keep them distinct: this work introduces `DesignReviewVerdict`, `CorrectnessVerdict`, `QualityVerdict`; the commit-review work would introduce its own verdict types.

## References

- `docs/archipelago-vision.md` — canonical project frame and the "harness competing tensions" decomposition principle.
- `job-add-review.md` — the umbrella review proposal in which this design-review work is one component.
- `agent-foundry/docs/archipelago/2026-05-24-operator-guided-retry-feature-def.md` — the platform feature def that unblocks the `GUIDE` operator action in v2.
- `src/archipelago/systems/pipeline.py` — current full working-session pipeline composition this design extends.
- `src/archipelago/agents/designer/primitive.py` — Designer `AgentAction` declaration, unchanged in shape but its prompt builder will read the new `design_review_verdict` state.
- `src/archipelago/actions/workspace_io.py` — `read_markdown` helper used by the new load-into-state `FunctionAction`s.
- `agent_foundry/primitives/ai_call.py` — `AICall` primitive (used here for the first time in Archipelago; `executor` field consumed by the reviewer wrappers).
- `agent_foundry/primitives/models.py` — `Retry`, `Conditional`, `GateAction`, `FunctionAction` primitives (composed here; `Retry` stays on default `PROPAGATE` policy).
- `agent_foundry/ai_models/execute/invoke.py` — `invoke_ai_call` is the function the reviewer executors wrap with their try/except logic.
- `agent_foundry/docs/plans/failure-resilience-retry-aicall.md` — implementation plan for the platform capabilities (`AICall.executor`, `Retry.exception_policy`, `on_exhaustion`) that landed in commit `c2928a4`. This design consumes the `AICall.executor` field; the other two are available but unused here.
