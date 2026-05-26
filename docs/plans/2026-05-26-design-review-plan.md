# Design Review Implementation Plan

> **Design:** docs/plans/2026-05-24-design-review-design.md
> **For agents:** Use team-dev (parallel) or sdd (sequential) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Insert a design-review step into the working-session pipeline immediately after Designer — two in-process `AICall` reviewers (correctness + quality), an aggregator, wrapped in a `Retry(max_attempts=3)` that re-runs Designer-and-review until the design passes; on exhaustion the pipeline aborts loudly.

**Architecture:** A `Retry[DesignReviewState, DesignReviewState]` replaces the bare `designer` step in `full_pipeline`. Its body is a `Sequence` of `[designer, load_design_into_state, load_investigation_into_state, design_correctness_review, design_quality_review, aggregate_design_verdict]`. `Retry.until` checks `design_review_verdict.passed`; `Retry.on_exhaustion` raises `DesignReviewNotApprovedError` carrying the per-attempt history. Reviewers are `AICall`s with custom executors that translate transient inference failures into `INADEQUATE`-everywhere placeholder verdicts so the loop advances rather than crashing.

**Tech Stack:** Python 3.14, Pydantic v2, PDM. Agent Foundry primitives (`AICall`, `Retry`, `FunctionAction`, `Sequence`) from the sibling `agent-foundry` repo.

---

## Divergences From the Design Doc (read first)

The design doc was written against an earlier topology. Two adaptations apply throughout this plan:

1. **No `DesignPipelineState`.** It was removed in commit `39c50dd`. The real integration target is the flat `FullPipelineState` in `src/archipelago/systems/pipeline.py`. New durable fields are added there; transient per-attempt fields live in a new `DesignReviewState` scoped to the `Retry`.

2. **Operator gate deferred to v2** (user decision, 2026-05-26). The `GateAction`/`Conditional`/`render_operator_payload`/`operator_gate`/`apply_operator_decision` components and the `OperatorDecision`/`OperatorDecisionKind` types are **out of scope**. Rationale: `GateAction` is not wired for resume in Agent Foundry today (`run_primitive_plan` calls `graph.ainvoke` once with no `thread_id` and no interrupt-resume loop — `runner.py:193`). Instead, exhaustion is handled by `Retry.on_exhaustion`, which raises a domain exception and aborts the pipeline. Human override becomes a follow-up once gate runtime lands.

3. **No transient-failure executor; reviewers fail loud** (user decision, 2026-05-26). The design's `_correctness_executor`/`_quality_executor` wrappers translated transient inference errors into `INADEQUATE`-everywhere placeholder verdicts. Their only payoff was letting the *operator gate* escalate after three transient failures — and the gate is deferred. Worse, honoring the catch-list (`anthropic.APITimeoutError`, …) would require importing `anthropic` into archipelago, which violates the provider-abstraction boundary (agent-foundry currently leaks raw SDK exceptions — `providers.py` has no exception hierarchy to catch instead). So v1 drops the custom executors entirely: the reviewer `AICall`s use the default invoke path, and any inference error propagates and aborts the pipeline loudly — the same loud-failure stance as `on_exhaustion`. Resilience returns in v2 alongside the gate, at which point agent-foundry should expose a `TransientInferenceError`/`PermanentInferenceError` hierarchy. The `OperatorDecision`/eval-registry coupling and the executor-failure-mode tests are removed.

Everything else (two split reviewers, categorical scoring, validators, Designer-inside-Retry) is implemented as designed.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/archipelago/models/design_review.py` | Create | Enums, findings, `CorrectnessVerdict`/`QualityVerdict` (+ validators), reviewer output wrappers, `DesignReviewVerdict`, `DesignReviewInput` |
| `src/archipelago/models/__init__.py` | Modify | Re-export the new design-review types |
| `src/archipelago/actions/load_review_inputs.py` | Create | `load_design_into_state` + `load_investigation_into_state` FunctionActions |
| `src/archipelago/actions/aggregate_design_verdict.py` | Create | `aggregate_design_verdict` FunctionAction (passed logic, history append, lifecycle event) |
| `src/archipelago/actions/workspace_io.py` | Modify | Add `read_workspace_file` raw-text passthrough used by `load_investigation_into_state` |
| `src/archipelago/actions/__init__.py` | Modify | Re-export new actions |
| `src/archipelago/agents/design_review/__init__.py` | Create | Package exports for the two reviewers |
| `src/archipelago/agents/design_review/prompts.py` | Create | Instruction + prompt builders for correctness and quality reviewers |
| `src/archipelago/agents/design_review/reviewers.py` | Create | `design_correctness_review` / `design_quality_review` `AICall`s (default invoke path, no custom executor) |
| `src/archipelago/agents/models.py` | Modify | Widen `DesignerInput` with `design_review_verdict` + `design_document_path` |
| `src/archipelago/agents/designer/primitive.py` | Modify | `designer_prompt_builder` branches on `design_review_verdict` (revision vs first pass) |
| `src/archipelago/config.py` | Modify | Add `DESIGN_REVIEW_MODEL` |
| `src/archipelago/systems/pipeline.py` | Modify | `DesignReviewState`, new `FullPipelineState` fields, wire `Retry` into `full_pipeline`, `on_exhaustion` raiser + `DesignReviewNotApprovedError` |
| `tests/archipelago/models/test_design_review.py` | Create | Verdict validator + aggregator-input model tests |
| `tests/archipelago/actions/test_load_review_inputs.py` | Create | Load-into-state actions (mocked workspace I/O) |
| `tests/archipelago/actions/test_aggregate_design_verdict.py` | Create | Aggregator passed-logic + history + lifecycle event |
| `tests/archipelago/agents/test_design_review_prompts.py` | Create | Reviewer prompt builders render real docs without error (`render_instance`) |
| `tests/archipelago/agents/test_designer_prompt.py` | Create | Designer prompt first-pass vs revision branch (incl. None-path guard) |
| `tests/archipelago/systems/test_design_review_loop.py` | Create | Retry predicate + on_exhaustion raise; full-pipeline compile smoke |

---

## Conventions

- **Commits:** Conventional Commits — `type(scope): message`. `jig.config.md` sets `require-ticket-reference: true`; there is no ticket, so reference the design doc in a footer: `Refs: docs/plans/2026-05-24-design-review-design.md`. `co-author: true` — the pre-commit hook / tooling appends the co-author trailer.
- **TDD:** Every code task is red-green-refactor. Follow the `tdd` skill. Run `pdm test-unit` for unit tasks; the final wiring task runs `pdm test-all`.
- **Data model rules (CLAUDE.md):** `StrEnum` for branched values (no `Literal`), every boundary type a `BaseModel`.
- **Pre-commit hook runs unit tests on every commit.** Each task's commit will only succeed if its tests pass.

---

## Task 1: Design-review data models

**Files:**
- Create: `src/archipelago/models/design_review.py`
- Modify: `src/archipelago/models/__init__.py`
- Test: `tests/archipelago/models/test_design_review.py`

**Dependencies:** none

- [ ] **Step 1: Write the failing tests**

```python
# tests/archipelago/models/test_design_review.py
from __future__ import annotations

import pytest
from pydantic import ValidationError

from archipelago.models.design_review import (
    CorrectnessDimension,
    CorrectnessMustFixFinding,
    CorrectnessVerdict,
    DimensionScore,
    QualityDimension,
    QualityMustFixFinding,
    QualityVerdict,
)


def _all_meets_correctness() -> dict[CorrectnessDimension, DimensionScore]:
    return {d: DimensionScore.MEETS_BAR for d in CorrectnessDimension}


def test_correctness_verdict_accepts_full_meets_bar() -> None:
    v = CorrectnessVerdict(
        dimension_scores=_all_meets_correctness(),
        must_fix_findings=[],
        reviewer_notes="ok",
    )
    assert v.dimension_scores[CorrectnessDimension.SCOPE_DISCIPLINE] == DimensionScore.MEETS_BAR


def test_correctness_verdict_rejects_partial_dimension_coverage() -> None:
    scores = _all_meets_correctness()
    del scores[CorrectnessDimension.CONSTRAINT_ADHERENCE]
    with pytest.raises(ValidationError, match="must be scored"):
        CorrectnessVerdict(dimension_scores=scores, must_fix_findings=[], reviewer_notes="x")


def test_correctness_verdict_rejects_inadequate_without_finding() -> None:
    scores = _all_meets_correctness()
    scores[CorrectnessDimension.REQUIREMENT_COVERAGE] = DimensionScore.INADEQUATE
    with pytest.raises(ValidationError, match="must each have at least one"):
        CorrectnessVerdict(dimension_scores=scores, must_fix_findings=[], reviewer_notes="x")


def test_correctness_verdict_accepts_inadequate_with_matching_finding() -> None:
    scores = _all_meets_correctness()
    scores[CorrectnessDimension.REQUIREMENT_COVERAGE] = DimensionScore.INADEQUATE
    v = CorrectnessVerdict(
        dimension_scores=scores,
        must_fix_findings=[
            CorrectnessMustFixFinding(
                description="AC-3 unaddressed",
                suggested_resolution="cover AC-3",
                dimension=CorrectnessDimension.REQUIREMENT_COVERAGE,
            )
        ],
        reviewer_notes="x",
    )
    assert len(v.must_fix_findings) == 1


def test_correctness_verdict_accepts_needs_improvement_without_finding() -> None:
    scores = _all_meets_correctness()
    scores[CorrectnessDimension.INTERFACE_FIDELITY] = DimensionScore.NEEDS_IMPROVEMENT
    v = CorrectnessVerdict(dimension_scores=scores, must_fix_findings=[], reviewer_notes="x")
    assert v.must_fix_findings == []


def test_quality_verdict_rejects_inadequate_without_finding() -> None:
    scores = {d: DimensionScore.MEETS_BAR for d in QualityDimension}
    scores[QualityDimension.COHESION] = DimensionScore.INADEQUATE
    with pytest.raises(ValidationError, match="must each have at least one"):
        QualityVerdict(dimension_scores=scores, must_fix_findings=[], reviewer_notes="x")


def test_quality_verdict_accepts_inadequate_with_matching_finding() -> None:
    scores = {d: DimensionScore.MEETS_BAR for d in QualityDimension}
    scores[QualityDimension.MODULARITY] = DimensionScore.INADEQUATE
    v = QualityVerdict(
        dimension_scores=scores,
        must_fix_findings=[
            QualityMustFixFinding(
                description="god object",
                suggested_resolution="split",
                dimension=QualityDimension.MODULARITY,
            )
        ],
        reviewer_notes="x",
    )
    assert v.dimension_scores[QualityDimension.MODULARITY] == DimensionScore.INADEQUATE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/archipelago/models/test_design_review.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'archipelago.models.design_review'`

- [ ] **Step 3: Write the model module**

```python
# src/archipelago/models/design_review.py
"""Design-review boundary types: categorical verdicts from the two
in-process reviewers and the aggregated verdict the Retry loop gates on.

The reviewer AICalls return the wrapper output models (one verdict field
each) so their shared internal field names don't collide when Agent
Foundry merges AICall output flat into pipeline state.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, model_validator

from archipelago.models.design_document import DesignDocument
from archipelago.models.feature_definition import FeatureDefinition


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
            d for d, s in self.dimension_scores.items() if s == DimensionScore.INADEQUATE
        }
        cited = {f.dimension for f in self.must_fix_findings}
        missing = inadequate - cited
        if missing:
            raise ValueError(
                f"Dimensions scored INADEQUATE must each have at least one "
                f"must_fix finding citing them. Missing: {sorted(d.value for d in missing)}"
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
            d for d, s in self.dimension_scores.items() if s == DimensionScore.INADEQUATE
        }
        cited = {f.dimension for f in self.must_fix_findings}
        missing = inadequate - cited
        if missing:
            raise ValueError(
                f"Dimensions scored INADEQUATE must each have at least one "
                f"must_fix finding citing them. Missing: {sorted(d.value for d in missing)}"
            )
        return self


class CorrectnessReviewOutput(BaseModel):
    correctness_verdict: CorrectnessVerdict


class QualityReviewOutput(BaseModel):
    quality_verdict: QualityVerdict


class DesignReviewVerdict(BaseModel):
    correctness: CorrectnessVerdict
    quality: QualityVerdict
    passed: bool
    attempt_number: int


class DesignReviewInput(BaseModel):
    """Projected slice the reviewer AICalls read from loop state.

    Correctness reads feature_definition + design_document; quality reads
    design_document + investigation_summary_text. Both reviewers share this
    input type and the compiler projects the fields each prompt builder uses.
    """

    feature_definition: FeatureDefinition
    design_document: DesignDocument
    investigation_summary_text: str
```

- [ ] **Step 4: Re-export from the models package**

Add to `src/archipelago/models/__init__.py` imports block:

```python
from archipelago.models.design_review import (
    CorrectnessDimension,
    CorrectnessMustFixFinding,
    CorrectnessReviewOutput,
    CorrectnessVerdict,
    DesignReviewInput,
    DesignReviewVerdict,
    DimensionScore,
    QualityDimension,
    QualityMustFixFinding,
    QualityReviewOutput,
    QualityVerdict,
)
```

And add these names to `__all__` (alphabetically): `"CorrectnessDimension"`, `"CorrectnessMustFixFinding"`, `"CorrectnessReviewOutput"`, `"CorrectnessVerdict"`, `"DesignReviewInput"`, `"DesignReviewVerdict"`, `"DimensionScore"`, `"QualityDimension"`, `"QualityMustFixFinding"`, `"QualityReviewOutput"`, `"QualityVerdict"`.

- [ ] **Step 5: Run test to verify it passes**

Run: `pdm run pytest tests/archipelago/models/test_design_review.py`
Expected: PASS (8 passed)

- [ ] **Step 6: Commit**

```bash
git add src/archipelago/models/design_review.py src/archipelago/models/__init__.py tests/archipelago/models/test_design_review.py
git commit -m "feat(models): add design-review verdict types

Refs: docs/plans/2026-05-24-design-review-design.md"
```

---

## Task 2: Aggregator FunctionAction

**Files:**
- Create: `src/archipelago/actions/aggregate_design_verdict.py`
- Modify: `src/archipelago/actions/__init__.py`
- Test: `tests/archipelago/actions/test_aggregate_design_verdict.py`

**Dependencies:** Task 1

The aggregator computes `passed`, sets `attempt_number` (1-based: `len(history) + 1`), appends the new verdict to history, and emits a `step_completed` lifecycle event. `passed = (no correctness dimension is INADEQUATE) and (no quality dimension is INADEQUATE) and (no must-fix findings in either verdict)`. A `NEEDS_IMPROVEMENT` *score* does not block by itself — but a `must_fix_finding` always blocks, regardless of which dimension's score it cites (the name says must-fix). The validator permits findings on non-INADEQUATE dimensions; the aggregator treats any such finding as a blocker. This matches the design doc's stated rule.

- [ ] **Step 1: Write the failing tests**

```python
# tests/archipelago/actions/test_aggregate_design_verdict.py
from __future__ import annotations

from unittest.mock import patch

from archipelago.actions.aggregate_design_verdict import (
    AggregateDesignVerdictInput,
    aggregate_design_verdict_fn,
)
from archipelago.models.design_review import (
    CorrectnessDimension,
    CorrectnessMustFixFinding,
    CorrectnessVerdict,
    DimensionScore,
    QualityDimension,
    QualityVerdict,
)


def _correctness(*, all_score: DimensionScore = DimensionScore.MEETS_BAR,
                 findings: list[CorrectnessMustFixFinding] | None = None) -> CorrectnessVerdict:
    return CorrectnessVerdict(
        dimension_scores={d: all_score for d in CorrectnessDimension},
        must_fix_findings=findings or [],
        reviewer_notes="n",
    )


def _quality(*, all_score: DimensionScore = DimensionScore.MEETS_BAR) -> QualityVerdict:
    return QualityVerdict(
        dimension_scores={d: all_score for d in QualityDimension},
        must_fix_findings=[],
        reviewer_notes="n",
    )


def test_all_meets_bar_passes() -> None:
    out = aggregate_design_verdict_fn(
        AggregateDesignVerdictInput(
            correctness_verdict=_correctness(),
            quality_verdict=_quality(),
            design_review_history=[],
        )
    )
    assert out.design_review_verdict.passed is True
    assert out.design_review_verdict.attempt_number == 1
    assert len(out.design_review_history) == 1


def test_needs_improvement_still_passes() -> None:
    out = aggregate_design_verdict_fn(
        AggregateDesignVerdictInput(
            correctness_verdict=_correctness(all_score=DimensionScore.NEEDS_IMPROVEMENT),
            quality_verdict=_quality(all_score=DimensionScore.NEEDS_IMPROVEMENT),
            design_review_history=[],
        )
    )
    assert out.design_review_verdict.passed is True


def test_inadequate_dimension_blocks() -> None:
    scores = {d: DimensionScore.MEETS_BAR for d in CorrectnessDimension}
    scores[CorrectnessDimension.SCOPE_DISCIPLINE] = DimensionScore.INADEQUATE
    correctness = CorrectnessVerdict(
        dimension_scores=scores,
        must_fix_findings=[
            CorrectnessMustFixFinding(
                description="d", suggested_resolution="r",
                dimension=CorrectnessDimension.SCOPE_DISCIPLINE,
            )
        ],
        reviewer_notes="n",
    )
    out = aggregate_design_verdict_fn(
        AggregateDesignVerdictInput(
            correctness_verdict=correctness,
            quality_verdict=_quality(),
            design_review_history=[],
        )
    )
    assert out.design_review_verdict.passed is False


def test_must_fix_finding_with_meets_bar_still_blocks() -> None:
    # A finding can exist on a NEEDS_IMPROVEMENT dimension; any finding blocks.
    scores = {d: DimensionScore.MEETS_BAR for d in CorrectnessDimension}
    scores[CorrectnessDimension.INTERFACE_FIDELITY] = DimensionScore.NEEDS_IMPROVEMENT
    correctness = CorrectnessVerdict(
        dimension_scores=scores,
        must_fix_findings=[
            CorrectnessMustFixFinding(
                description="d", suggested_resolution="r",
                dimension=CorrectnessDimension.INTERFACE_FIDELITY,
            )
        ],
        reviewer_notes="n",
    )
    out = aggregate_design_verdict_fn(
        AggregateDesignVerdictInput(
            correctness_verdict=correctness,
            quality_verdict=_quality(),
            design_review_history=[],
        )
    )
    assert out.design_review_verdict.passed is False


def test_attempt_number_increments_with_history() -> None:
    first = aggregate_design_verdict_fn(
        AggregateDesignVerdictInput(
            correctness_verdict=_correctness(),
            quality_verdict=_quality(),
            design_review_history=[],
        )
    )
    second = aggregate_design_verdict_fn(
        AggregateDesignVerdictInput(
            correctness_verdict=_correctness(),
            quality_verdict=_quality(),
            design_review_history=first.design_review_history,
        )
    )
    assert second.design_review_verdict.attempt_number == 2
    assert len(second.design_review_history) == 2


def test_emits_step_completed_event() -> None:
    with patch("archipelago.actions.aggregate_design_verdict.runtime") as rt:
        aggregate_design_verdict_fn(
            AggregateDesignVerdictInput(
                correctness_verdict=_correctness(),
                quality_verdict=_quality(),
                design_review_history=[],
            )
        )
    rt.emit.assert_called_once()
    assert rt.emit.call_args.args[0] == "step_completed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/archipelago/actions/test_aggregate_design_verdict.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'archipelago.actions.aggregate_design_verdict'`

- [ ] **Step 3: Write the aggregator**

```python
# src/archipelago/actions/aggregate_design_verdict.py
"""Combine the correctness and quality verdicts into a single gated
DesignReviewVerdict and append it to the per-attempt history.

`passed` lives in one function (not a Pydantic computed field) so the
threshold policy is tunable in one place — e.g. if NEEDS_IMPROVEMENT
should ever block, edit here, not the model.
"""

from __future__ import annotations

from agent_foundry import runtime
from agent_foundry.primitives.models import FunctionAction
from pydantic import BaseModel

from archipelago.models.design_review import (
    CorrectnessVerdict,
    DesignReviewVerdict,
    DimensionScore,
    QualityVerdict,
)


class AggregateDesignVerdictInput(BaseModel):
    correctness_verdict: CorrectnessVerdict
    quality_verdict: QualityVerdict
    design_review_history: list[DesignReviewVerdict] = []


class AggregateDesignVerdictOutput(BaseModel):
    design_review_verdict: DesignReviewVerdict
    design_review_history: list[DesignReviewVerdict]


def _passed(correctness: CorrectnessVerdict, quality: QualityVerdict) -> bool:
    no_inadequate = all(
        s != DimensionScore.INADEQUATE
        for s in (*correctness.dimension_scores.values(), *quality.dimension_scores.values())
    )
    no_findings = not correctness.must_fix_findings and not quality.must_fix_findings
    return no_inadequate and no_findings


def aggregate_design_verdict_fn(
    state: AggregateDesignVerdictInput,
) -> AggregateDesignVerdictOutput:
    verdict = DesignReviewVerdict(
        correctness=state.correctness_verdict,
        quality=state.quality_verdict,
        passed=_passed(state.correctness_verdict, state.quality_verdict),
        attempt_number=len(state.design_review_history) + 1,
    )
    history = [*state.design_review_history, verdict]
    runtime.emit(
        "step_completed",
        step="aggregate_design_verdict",
        passed=verdict.passed,
        attempt_number=verdict.attempt_number,
    )
    return AggregateDesignVerdictOutput(
        design_review_verdict=verdict,
        design_review_history=history,
    )


aggregate_design_verdict = FunctionAction[
    AggregateDesignVerdictInput, AggregateDesignVerdictOutput
](function=aggregate_design_verdict_fn)
```

- [ ] **Step 4: Re-export from the actions package**

Add to `src/archipelago/actions/__init__.py` imports:

```python
from archipelago.actions.aggregate_design_verdict import (
    AggregateDesignVerdictInput,
    AggregateDesignVerdictOutput,
    aggregate_design_verdict,
)
```

Add to `__all__`: `"AggregateDesignVerdictInput"`, `"AggregateDesignVerdictOutput"`, `"aggregate_design_verdict"`.

- [ ] **Step 5: Run test to verify it passes**

Run: `pdm run pytest tests/archipelago/actions/test_aggregate_design_verdict.py`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit**

```bash
git add src/archipelago/actions/aggregate_design_verdict.py src/archipelago/actions/__init__.py tests/archipelago/actions/test_aggregate_design_verdict.py
git commit -m "feat(actions): aggregate correctness+quality into gated verdict

Refs: docs/plans/2026-05-24-design-review-design.md"
```

---

## Task 3: Load-into-state FunctionActions

**Files:**
- Create: `src/archipelago/actions/load_review_inputs.py`
- Modify: `src/archipelago/actions/workspace_io.py`, `src/archipelago/actions/__init__.py`
- Test: `tests/archipelago/actions/test_load_review_inputs.py`

**Dependencies:** Task 1

`load_design_into_state` parses the design markdown into a `DesignDocument` via the existing `read_markdown`. `load_investigation_into_state` reads the investigation summary as raw text via a new `read_workspace_file` passthrough in `workspace_io` (the existing `read_markdown` validates against a model; the investigation summary has no canonical schema, so we read it as a plain string). The name is `read_workspace_file` — "from the workspace volume, unparsed" — to convey the volume-read mechanism and contrast with `read_markdown`, and to avoid colliding with the lower-level `workspace_ops.read_file` (different signature: `client`, `volume_name`, `path`). Modeling the investigation summary so this helper can be dropped is deferred — see `docs/engineering/design-investigation-type.md`.

- [ ] **Step 1: Add `read_workspace_file` passthrough to `workspace_io.py`**

Append to `src/archipelago/actions/workspace_io.py`:

```python
def read_workspace_file(workspace_handle: WorkspaceHandle, path: str) -> str:
    """Read a file from the workspace volume as raw UTF-8 text.

    The freeform-text counterpart to `read_markdown`: no model validation,
    for content (like the Designer investigation summary) that has no
    canonical document schema.
    """
    client = docker.from_env()
    return workspace_ops.read_file(
        client,
        volume_name=workspace_handle.volume_name,
        path=path,
    )
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/archipelago/actions/test_load_review_inputs.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

from archipelago.actions.load_review_inputs import (
    LoadDesignInput,
    LoadInvestigationInput,
    load_design_into_state_fn,
    load_investigation_into_state_fn,
)
from archipelago.actions.workspace_bootstrap import WorkspaceHandle


def _handle() -> WorkspaceHandle:
    return WorkspaceHandle(volume_name="vol-x", root="/workspace")


def test_load_design_parses_via_read_markdown() -> None:
    fake_doc = MagicMock(name="DesignDocument")
    with patch(
        "archipelago.actions.load_review_inputs.read_markdown", return_value=fake_doc
    ) as rm:
        out = load_design_into_state_fn(
            LoadDesignInput(workspace_handle=_handle(), design_document_path="/workspace/d.md")
        )
    rm.assert_called_once()
    assert rm.call_args.args[1] == "/workspace/d.md"
    assert out.design_document is fake_doc


def test_load_investigation_reads_raw_text() -> None:
    with patch(
        "archipelago.actions.load_review_inputs.read_workspace_file", return_value="# investigation\nbody"
    ) as rf:
        out = load_investigation_into_state_fn(
            LoadInvestigationInput(
                workspace_handle=_handle(), investigation_summary_path="/workspace/i.md"
            )
        )
    rf.assert_called_once()
    assert rf.call_args.args[1] == "/workspace/i.md"
    assert out.investigation_summary_text == "# investigation\nbody"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pdm run pytest tests/archipelago/actions/test_load_review_inputs.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'archipelago.actions.load_review_inputs'`

- [ ] **Step 4: Write the load actions**

```python
# src/archipelago/actions/load_review_inputs.py
"""Bridge Designer's on-disk artifacts into in-process review state.

Designer writes the design document and investigation summary as files in
the workspace volume. These two FunctionActions load them into typed state
slots the reviewers read: the design parsed as a DesignDocument, the
investigation summary as raw markdown text.
"""

from __future__ import annotations

from agent_foundry.primitives.models import FunctionAction
from pydantic import BaseModel

from archipelago.actions.workspace_bootstrap import WorkspaceHandle
from archipelago.actions.workspace_io import read_markdown, read_workspace_file
from archipelago.models.design_document import DesignDocument


class LoadDesignInput(BaseModel):
    workspace_handle: WorkspaceHandle
    design_document_path: str


class LoadDesignOutput(BaseModel):
    design_document: DesignDocument


def load_design_into_state_fn(state: LoadDesignInput) -> LoadDesignOutput:
    doc = read_markdown(state.workspace_handle, state.design_document_path, DesignDocument)
    return LoadDesignOutput(design_document=doc)


load_design_into_state = FunctionAction[LoadDesignInput, LoadDesignOutput](
    function=load_design_into_state_fn,
)


class LoadInvestigationInput(BaseModel):
    workspace_handle: WorkspaceHandle
    investigation_summary_path: str


class LoadInvestigationOutput(BaseModel):
    investigation_summary_text: str


def load_investigation_into_state_fn(state: LoadInvestigationInput) -> LoadInvestigationOutput:
    text = read_workspace_file(state.workspace_handle, state.investigation_summary_path)
    return LoadInvestigationOutput(investigation_summary_text=text)


load_investigation_into_state = FunctionAction[LoadInvestigationInput, LoadInvestigationOutput](
    function=load_investigation_into_state_fn,
)
```

- [ ] **Step 5: Re-export**

Add to `src/archipelago/actions/__init__.py` imports:

```python
from archipelago.actions.load_review_inputs import (
    LoadDesignInput,
    LoadDesignOutput,
    LoadInvestigationInput,
    LoadInvestigationOutput,
    load_design_into_state,
    load_investigation_into_state,
)
from archipelago.actions.workspace_io import read_markdown, read_workspace_file
```

(Replace the existing `from archipelago.actions.workspace_io import read_markdown` line with the combined import above.) Add to `__all__`: `"LoadDesignInput"`, `"LoadDesignOutput"`, `"LoadInvestigationInput"`, `"LoadInvestigationOutput"`, `"load_design_into_state"`, `"load_investigation_into_state"`, `"read_workspace_file"`.

- [ ] **Step 6: Run test to verify it passes**

Run: `pdm run pytest tests/archipelago/actions/test_load_review_inputs.py`
Expected: PASS (2 passed)

- [ ] **Step 7: Commit**

```bash
git add src/archipelago/actions/load_review_inputs.py src/archipelago/actions/workspace_io.py src/archipelago/actions/__init__.py tests/archipelago/actions/test_load_review_inputs.py
git commit -m "feat(actions): load design + investigation into review state

Refs: docs/plans/2026-05-24-design-review-design.md"
```

---

## Task 4: Reviewer AICalls (default invoke path)

**Files:**
- Modify: `src/archipelago/config.py`
- Create: `src/archipelago/agents/design_review/__init__.py`, `src/archipelago/agents/design_review/prompts.py`, `src/archipelago/agents/design_review/reviewers.py`
- Test: `tests/archipelago/agents/test_design_review_prompts.py`

**Dependencies:** Task 1

Each reviewer is a plain `AICall[DesignReviewInput, <Output>]` with **no custom executor** — it uses the default `invoke_ai_call` path. Per Divergence #3, v1 has no transient-failure translation: any inference error propagates and aborts the pipeline loudly. This keeps `anthropic` out of archipelago (the provider-abstraction boundary), and the only behavior to unit-test here is that the prompt builders render real documents without error. The reviewers' wiring is exercised at compile time in Task 6.

- [ ] **Step 1: Add model config**

Add to `src/archipelago/config.py`:

```python
from agent_foundry.ai_models.model import Model

DESIGN_REVIEW_MODEL = Model.CLAUDE_SONNET_4_6
```

(Place the `Model` import next to the existing `from agent_foundry.primitives import ...` import; keep the existing `ClaudeModel`/`ClaudeEffort` line. `Model.CLAUDE_SONNET_4_6` is a `ModelEntry` — the type `AICall.model` expects — distinct from the `ClaudeModel` StrEnum used for container `AgentAction`s.)

- [ ] **Step 2: Write the failing test**

```python
# tests/archipelago/agents/test_design_review_prompts.py
from __future__ import annotations

from archipelago.agents.design_review.prompts import (
    correctness_prompt,
    quality_prompt,
)
from archipelago.models.design_review import DesignReviewInput


def test_prompts_render_real_documents(sample_feature_definition, sample_design_document) -> None:
    # sample_feature_definition / sample_design_document come from the existing
    # test fixtures used elsewhere in the suite (see tests/archipelago/conftest.py
    # or the models tests). If no shared fixture exists, build minimal valid
    # instances here. The point: the prompt builders must call the real markdown
    # serializer without raising AttributeError.
    state = DesignReviewInput(
        feature_definition=sample_feature_definition,
        design_document=sample_design_document,
        investigation_summary_text="codebase notes",
    )
    c = correctness_prompt(state)
    q = quality_prompt(state)
    assert "# Feature Definition" in c
    assert "# Design Document" in c
    assert "# Investigation Summary" in q
    assert "codebase notes" in q
```

> **Implementer note:** locate an existing fixture that yields a valid `FeatureDefinition` and `DesignDocument` (the models tests and `read_markdown` tests build these). If none is reusable, construct minimal valid instances inline. The test's job is to catch a wrong serializer call (see Step 4).

- [ ] **Step 3: Run test to verify it fails**

Run: `pdm run pytest tests/archipelago/agents/test_design_review_prompts.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'archipelago.agents.design_review'`

- [ ] **Step 4: Write the prompts module**

`FeatureDefinition`/`DesignDocument` are `MarkdownDocument` subclasses; they have **no `.render()` method**. Serialize them with the module-level `render_instance` from `archetype.markdown` (the same helper `workspace_bootstrap.py:199` uses to write documents to the volume).

```python
# src/archipelago/agents/design_review/prompts.py
"""Instruction + prompt builders for the two design reviewers.

Correctness traces the design against the feature definition (positive
specs: acceptance criteria, interfaces; negative specs: scope boundaries,
constraints). Quality judges the design against engineering rubrics using
the Designer-captured investigation summary as codebase context.
"""

from __future__ import annotations

from archetype.markdown import render_instance

from archipelago.models.design_review import DesignReviewInput

_CORRECTNESS_INSTRUCTIONS = """\
You review a software design document for CORRECTNESS against a feature \
definition. Score each dimension MEETS_BAR, NEEDS_IMPROVEMENT, or INADEQUATE:

- requirement_coverage: every acceptance criterion is addressed by the design.
- interface_fidelity: declared interfaces match what the feature requires.
- scope_discipline: the design stays within the feature's scope boundaries.
- constraint_adherence: the design honors every stated constraint.

Any dimension you score INADEQUATE MUST have at least one must_fix finding \
citing that dimension. Put concrete, enumerated reasoning in reviewer_notes; \
a score without reasoning is meaningless.
"""

_QUALITY_INSTRUCTIONS = """\
You review a software design document for ENGINEERING QUALITY. Score each \
dimension MEETS_BAR, NEEDS_IMPROVEMENT, or INADEQUATE:

- cohesion: each unit has one clear responsibility.
- modularity: clean boundaries, low coupling between units.
- abstraction_quality: abstractions are at the right level, not leaky.

Use the supplied investigation summary as the codebase context the design \
was made against. Any dimension you score INADEQUATE MUST have at least one \
must_fix finding citing that dimension. Put concrete reasoning in reviewer_notes.
"""


def correctness_instructions(_state: DesignReviewInput) -> str:
    return _CORRECTNESS_INSTRUCTIONS


def correctness_prompt(state: DesignReviewInput) -> str:
    return (
        "# Feature Definition\n\n"
        f"{render_instance(state.feature_definition)}\n\n"
        "# Design Document\n\n"
        f"{render_instance(state.design_document)}\n"
    )


def quality_instructions(_state: DesignReviewInput) -> str:
    return _QUALITY_INSTRUCTIONS


def quality_prompt(state: DesignReviewInput) -> str:
    return (
        "# Design Document\n\n"
        f"{render_instance(state.design_document)}\n\n"
        "# Investigation Summary (codebase context)\n\n"
        "```\n"
        f"{state.investigation_summary_text}\n"
        "```\n"
    )
```

- [ ] **Step 5: Write the reviewers module**

```python
# src/archipelago/agents/design_review/reviewers.py
"""The two design-review AICalls.

Plain AICalls on the default invoke path — no custom executor. v1 has no
transient-failure translation (Divergence #3): any inference error propagates
and aborts the pipeline, the same loud-failure stance as on_exhaustion. This
also keeps the anthropic SDK out of archipelago — there is nothing here to
catch provider exceptions, so there is no reason to import them.
"""

from __future__ import annotations

from agent_foundry.ai_models.inference import InferenceParameters
from agent_foundry.primitives.ai_call import AICall, ModelInput

from archipelago.agents.design_review.prompts import (
    correctness_instructions,
    correctness_prompt,
    quality_instructions,
    quality_prompt,
)
from archipelago.config import DESIGN_REVIEW_MODEL
from archipelago.models.design_review import (
    CorrectnessReviewOutput,
    DesignReviewInput,
    QualityReviewOutput,
)

_REVIEW_PARAMETERS = InferenceParameters(temperature=0.0, max_tokens=8_000)


design_correctness_review = AICall[DesignReviewInput, CorrectnessReviewOutput](
    model_input=ModelInput[DesignReviewInput](
        instructions=correctness_instructions,
        prompt=correctness_prompt,
    ),
    model=DESIGN_REVIEW_MODEL,
    parameters=_REVIEW_PARAMETERS,
    timeout_seconds=120,
)

design_quality_review = AICall[DesignReviewInput, QualityReviewOutput](
    model_input=ModelInput[DesignReviewInput](
        instructions=quality_instructions,
        prompt=quality_prompt,
    ),
    model=DESIGN_REVIEW_MODEL,
    parameters=_REVIEW_PARAMETERS,
    timeout_seconds=120,
)
```

- [ ] **Step 6: Write the package `__init__`**

```python
# src/archipelago/agents/design_review/__init__.py
from __future__ import annotations

from archipelago.agents.design_review.reviewers import (
    design_correctness_review,
    design_quality_review,
)

__all__ = [
    "design_correctness_review",
    "design_quality_review",
]
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pdm run pytest tests/archipelago/agents/test_design_review_prompts.py`
Expected: PASS (1 passed)

- [ ] **Step 8: Commit**

```bash
git add src/archipelago/config.py src/archipelago/agents/design_review/ tests/archipelago/agents/test_design_review_prompts.py
git commit -m "feat(agents): add correctness and quality design reviewers

Refs: docs/plans/2026-05-24-design-review-design.md"
```

---

## Task 5: Designer revision prompt

**Files:**
- Modify: `src/archipelago/agents/models.py`, `src/archipelago/agents/designer/primitive.py`
- Test: `tests/archipelago/agents/test_designer_prompt.py`

**Dependencies:** Task 1

`DesignerInput` gains `design_review_verdict` and `design_document_path` (both optional). `designer_prompt_builder` branches: when a verdict is present (a revision pass), it instructs Designer to read its prior design from disk and revise against the must-fix findings; when absent (first pass), it returns the existing brief.

- [ ] **Step 1: Write the failing tests**

```python
# tests/archipelago/agents/test_designer_prompt.py
from __future__ import annotations

import pytest

from archipelago.actions.workspace_bootstrap import WorkspaceHandle
from archipelago.agents.designer.primitive import designer_prompt_builder
from archipelago.agents.models import DesignerInput
from archipelago.models.design_review import (
    CorrectnessDimension,
    CorrectnessMustFixFinding,
    CorrectnessVerdict,
    DesignReviewVerdict,
    DimensionScore,
    QualityDimension,
    QualityVerdict,
)


def _handle() -> WorkspaceHandle:
    return WorkspaceHandle(volume_name="v", root="/workspace")


def _input(**kw) -> DesignerInput:
    base = dict(
        workspace_handle=_handle(),
        feature_definition=None,  # prompt builder does not read it
    )
    base.update(kw)
    return DesignerInput.model_construct(**base)


def _failing_verdict() -> DesignReviewVerdict:
    scores = {d: DimensionScore.MEETS_BAR for d in CorrectnessDimension}
    scores[CorrectnessDimension.REQUIREMENT_COVERAGE] = DimensionScore.INADEQUATE
    correctness = CorrectnessVerdict(
        dimension_scores=scores,
        must_fix_findings=[
            CorrectnessMustFixFinding(
                description="AC-2 missing",
                suggested_resolution="add AC-2 handling",
                dimension=CorrectnessDimension.REQUIREMENT_COVERAGE,
            )
        ],
        reviewer_notes="n",
    )
    quality = QualityVerdict(
        dimension_scores={d: DimensionScore.MEETS_BAR for d in QualityDimension},
        must_fix_findings=[],
        reviewer_notes="n",
    )
    return DesignReviewVerdict(
        correctness=correctness, quality=quality, passed=False, attempt_number=1
    )


def test_first_pass_prompt_has_no_revision_language() -> None:
    prompt = designer_prompt_builder(_input(design_review_verdict=None))
    assert "/workspace" in prompt
    assert "revise" not in prompt.lower()


def test_revision_prompt_references_prior_design_and_findings() -> None:
    prompt = designer_prompt_builder(
        _input(
            design_review_verdict=_failing_verdict(),
            design_document_path="/workspace/documents/design.md",
        )
    )
    assert "/workspace/documents/design.md" in prompt
    assert "AC-2 missing" in prompt
    assert "revise" in prompt.lower()


def test_revision_without_path_raises() -> None:
    # A verdict present but no design_document_path is an impossible state
    # (a revision pass always follows a prior Designer run that wrote the path).
    # The builder must fail loudly rather than emit "...prior design at None...".
    with pytest.raises(AssertionError):
        designer_prompt_builder(
            _input(design_review_verdict=_failing_verdict(), design_document_path=None)
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/archipelago/agents/test_designer_prompt.py`
Expected: FAIL with `AttributeError`/`ValidationError` on the unknown `design_review_verdict` field (or assertion failure on revision language).

- [ ] **Step 3: Widen `DesignerInput`**

In `src/archipelago/agents/models.py`, add the import and fields:

```python
from archipelago.models import (
    ChangeSetRef,
    CodebaseSource,
    DesignReviewVerdict,
    FeatureDefinition,
)
```

```python
class DesignerInput(AgentInputBase):
    feature_definition: FeatureDefinition
    # Present on revision passes (populated by the prior Retry iteration); None
    # on the first pass. Drives designer_prompt_builder's revise-vs-fresh branch.
    design_review_verdict: DesignReviewVerdict | None = None
    design_document_path: str | None = None
```

- [ ] **Step 4: Branch the prompt builder**

Replace `designer_prompt_builder` in `src/archipelago/agents/designer/primitive.py`:

```python
def designer_prompt_builder(state: DesignerInput) -> str:
    if state.design_review_verdict is None:
        return (
            f"The workspace is mounted at {state.workspace_handle.root}. "
            f"Follow your instructions to produce the design document."
        )

    verdict = state.design_review_verdict
    assert state.design_document_path is not None, (
        "design_document_path must be set on a revision pass (a verdict implies "
        "a prior Designer run wrote the design)."
    )
    findings = [*verdict.correctness.must_fix_findings, *verdict.quality.must_fix_findings]
    findings_text = "\n".join(
        f"- [{f.dimension.value}] {f.description} — {f.suggested_resolution}"
        for f in findings
    )
    inadequate = [
        d.value
        for scores in (verdict.correctness.dimension_scores, verdict.quality.dimension_scores)
        for d, s in scores.items()
        if s == DimensionScore.INADEQUATE
    ]
    return (
        f"The workspace is mounted at {state.workspace_handle.root}. "
        f"Your prior design at {state.design_document_path} did not pass review "
        f"(attempt {verdict.attempt_number}). Read it, then revise it in place to "
        f"resolve the following must-fix findings:\n\n{findings_text}\n\n"
        f"Dimensions scored INADEQUATE: {', '.join(inadequate)}. "
        f"Write the revised design document to the same path."
    )
```

Add the import at the top of the file:

```python
from archipelago.models.design_review import DesignReviewVerdict, DimensionScore
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pdm run pytest tests/archipelago/agents/test_designer_prompt.py`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add src/archipelago/agents/models.py src/archipelago/agents/designer/primitive.py tests/archipelago/agents/test_designer_prompt.py
git commit -m "feat(agents): designer prompt revises against review verdict

Refs: docs/plans/2026-05-24-design-review-design.md"
```

---

## Task 6: Wire the Retry loop into the pipeline

**Files:**
- Modify: `src/archipelago/systems/pipeline.py`
- Test: `tests/archipelago/systems/test_design_review_loop.py`

**Dependencies:** Tasks 1–5

Replaces the bare `designer` step in `full_pipeline` with a `Retry` whose body runs Designer + the two loads + the two reviewers + the aggregator. `until` checks `design_review_verdict.passed`. `on_exhaustion` raises `DesignReviewNotApprovedError` carrying the history, aborting the pipeline loudly.

**State shape:** A new `DesignReviewState` is the Retry's I/O type and the body Sequence's I/O type. `FullPipelineState` gains the durable fields so the Retry's outputs (especially `design_document_path`, needed by `change_set_planner` downstream) round-trip through the top-level scope.

- [ ] **Step 1: Write the failing unit tests**

These test the two pure helpers the Retry is wired with — `_design_review_passed` (the `until` predicate) and `_design_review_exhausted` (the `on_exhaustion` raiser) — with no Docker and no LLM. A full Retry-body run would need a Docker-backed Designer, so the body composition is verified instead by the compile smoke test in Step 5.

```python
# tests/archipelago/systems/test_design_review_loop.py
from __future__ import annotations

import pytest

from archipelago.models.design_review import (
    CorrectnessDimension,
    CorrectnessMustFixFinding,
    CorrectnessVerdict,
    DesignReviewVerdict,
    DimensionScore,
    QualityDimension,
    QualityVerdict,
)
from archipelago.systems.pipeline import (
    DesignReviewNotApprovedError,
    DesignReviewState,
    _design_review_exhausted,
    _design_review_passed,
)


def _passing_correctness() -> CorrectnessVerdict:
    return CorrectnessVerdict(
        dimension_scores={d: DimensionScore.MEETS_BAR for d in CorrectnessDimension},
        must_fix_findings=[],
        reviewer_notes="n",
    )


def _failing_correctness() -> CorrectnessVerdict:
    scores = {d: DimensionScore.MEETS_BAR for d in CorrectnessDimension}
    scores[CorrectnessDimension.SCOPE_DISCIPLINE] = DimensionScore.INADEQUATE
    return CorrectnessVerdict(
        dimension_scores=scores,
        must_fix_findings=[
            CorrectnessMustFixFinding(
                description="d", suggested_resolution="r",
                dimension=CorrectnessDimension.SCOPE_DISCIPLINE,
            )
        ],
        reviewer_notes="n",
    )


def _quality() -> QualityVerdict:
    return QualityVerdict(
        dimension_scores={d: DimensionScore.MEETS_BAR for d in QualityDimension},
        must_fix_findings=[],
        reviewer_notes="n",
    )


def test_passed_predicate() -> None:
    state = DesignReviewState.model_construct(
        design_review_verdict=DesignReviewVerdict(
            correctness=_passing_correctness(), quality=_quality(),
            passed=True, attempt_number=1,
        )
    )
    assert _design_review_passed(state) is True
    assert _design_review_passed(DesignReviewState.model_construct(design_review_verdict=None)) is False


def test_exhaustion_raises_with_history() -> None:
    from agent_foundry.primitives.retry_types import RetryExhaustion, RetryExhaustionReason

    history = [
        DesignReviewVerdict(
            correctness=_failing_correctness(), quality=_quality(),
            passed=False, attempt_number=i + 1,
        )
        for i in range(3)
    ]
    last = DesignReviewState.model_construct(
        design_review_verdict=history[-1], design_review_history=history
    )
    exhaustion = RetryExhaustion(
        max_attempts=3,
        reason=RetryExhaustionReason.CONDITION_NOT_MET,
        attempt_failures=[],
        last_state=last,
    )
    with pytest.raises(DesignReviewNotApprovedError) as ei:
        _design_review_exhausted(exhaustion)
    assert "3" in str(ei.value)
```

> **Implementer note:** These two unit tests need no Docker. The full-pipeline composition (Retry body scoping, reviewer wiring) is verified by the compile smoke test in Step 5. A Docker-backed end-to-end run is part of Task 7's manual smoke.

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/archipelago/systems/test_design_review_loop.py`
Expected: FAIL with `ImportError: cannot import name 'DesignReviewState'` (and siblings) from `archipelago.systems.pipeline`.

- [ ] **Step 3: Add state model, predicates, exhaustion raiser, and wire the Retry**

In `src/archipelago/systems/pipeline.py`:

(a) Extend the imports. **Merge into the existing import statements — do not add duplicate `from archipelago.actions import (...)` / `from archipelago.models import (...)` blocks** (a second block of either trips the isort/ruff pre-commit hook). The existing `from agent_foundry.primitives.models import Loop, Sequence` line gains `Retry`; the existing `archipelago.actions` and `archipelago.models` blocks gain their new names; the two new module imports (`retry_types`, `agents.design_review`, `models.design_review`) are added.

```python
from agent_foundry.primitives.models import Loop, Retry, Sequence
from agent_foundry.primitives.retry_types import RetryExhaustion

from archipelago.actions import (
    WorkspaceHandle,
    aggregate_design_verdict,
    load_design_into_state,
    load_investigation_into_state,
    log_change_set_name,
    prepare_change_set_workspace,
    read_markdown,
    setup_python_workspace,
    workspace_bootstrap,
    write_task_context,
)
from archipelago.agents.design_review import (
    design_correctness_review,
    design_quality_review,
)
from archipelago.models import (
    ChangeSetRef,
    ChangeSetsDocument,
    CodebaseSource,
    DesignDocument,
    DesignReviewVerdict,
    FeatureDefinition,
    Task,
    TDDPlan,
)
from archipelago.models.design_review import CorrectnessVerdict, QualityVerdict
```

(b) Add the durable fields to `FullPipelineState` (after the Designer flat-output fields), and update its docstring. The existing docstring says `design_document` is one of "DesignerOutput's fields" — that is now inaccurate (`DesignerOutput` carries `design_document_path`, a string; the new `design_document` is the *parsed* `DesignDocument` populated by `load_design_into_state`). Reword the docstring so it distinguishes `design_document_path` (string path, from `DesignerOutput`, round-tripped through the Retry scope) from `design_document` (parsed object, new durable field).

```python
    # Design-review loop outputs (durable across the Retry boundary):
    design_document: DesignDocument | None = None
    investigation_summary_text: str | None = None
    correctness_verdict: CorrectnessVerdict | None = None
    quality_verdict: QualityVerdict | None = None
    design_review_verdict: DesignReviewVerdict | None = None
    design_review_history: list[DesignReviewVerdict] = []
```

(c) Add the Retry-scoped state type and helpers (after the loop `over` callables):

```python
class DesignReviewState(BaseModel):
    """Retry I/O + body Sequence I/O for the design-review loop.

    Carries Designer's inputs (feature_definition, workspace_handle), its
    on-disk outputs (the two paths), the in-process review inputs loaded from
    disk, the two reviewer verdicts, and the aggregated verdict + history the
    Retry condition gates on.

    `design_document_path` is typed Optional here — NOT because it is
    semantically optional, but because the body Sequence's `_scope_in`
    eagerly validates this model at body entry, before Designer has written
    the path on the first attempt; a required field would fail scope-in.
    Its requiredness is enforced downstream: `ChangeSetsLoopState.design_document_path`
    is a required `str`, so a None-valued exit from this loop aborts loudly at
    the change-sets boundary. And by construction the loop only exits
    successfully when `design_review_verdict.passed`, which requires a design
    that was loaded from this path — so a passing exit always carries a real
    path. The only None-exit is `on_exhaustion`, which raises.
    """

    feature_definition: FeatureDefinition
    workspace_handle: WorkspaceHandle
    design_document_path: str | None = None
    investigation_summary_path: str | None = None
    design_document: DesignDocument | None = None
    investigation_summary_text: str | None = None
    correctness_verdict: CorrectnessVerdict | None = None
    quality_verdict: QualityVerdict | None = None
    design_review_verdict: DesignReviewVerdict | None = None
    design_review_history: list[DesignReviewVerdict] = []


class DesignReviewNotApprovedError(RuntimeError):
    """Raised when the design-review Retry exhausts all attempts without the
    design passing. Carries the per-attempt verdict history for diagnosis."""

    def __init__(self, history: list[DesignReviewVerdict], max_attempts: int) -> None:
        self.history = history
        super().__init__(
            f"Design review did not pass after {max_attempts} attempts. "
            f"Final verdict attempt_number="
            f"{history[-1].attempt_number if history else 'unknown'}."
        )


def _design_review_passed(state: DesignReviewState) -> bool:
    return state.design_review_verdict is not None and state.design_review_verdict.passed


def _design_review_exhausted(exhaustion: RetryExhaustion[DesignReviewState]) -> DesignReviewState:
    raise DesignReviewNotApprovedError(
        history=exhaustion.last_state.design_review_history,
        max_attempts=exhaustion.max_attempts,
    )
```

(d) Build the Retry and substitute it for `designer` in `full_pipeline`:

```python
design_review_loop = Retry[DesignReviewState, DesignReviewState](
    max_attempts=3,
    until=_design_review_passed,
    on_exhaustion=_design_review_exhausted,
    body=Sequence[DesignReviewState, DesignReviewState](
        steps=[
            designer,
            load_design_into_state,
            load_investigation_into_state,
            design_correctness_review,
            design_quality_review,
            aggregate_design_verdict,
        ],
    ),
)
```

In `full_pipeline.steps`, replace the lone `designer,` entry with `design_review_loop,`:

```python
full_pipeline = Sequence[FullPipelineState, FullPipelineState](
    steps=[
        workspace_bootstrap,
        setup_python_workspace,
        design_review_loop,
        change_set_planner,
        Loop[ChangeSetsLoopState, ChangeSetsLoopState](
            # ... unchanged ...
        ),
        pr_creator,
    ],
)
```

Keep the `from archipelago.agents.designer import designer` import — `designer` is now referenced inside `design_review_loop` rather than directly in the top-level steps.

- [ ] **Step 4: Run the loop unit tests**

Run: `pdm run pytest tests/archipelago/systems/test_design_review_loop.py`
Expected: PASS (3 passed)

- [ ] **Step 5: Verify the full pipeline still compiles**

Run: `pdm run python -c "from agent_foundry.compiler.primitive_compiler import compile_runtime_plan; from agent_foundry.primitives.plan import PrimitivePlan; from archipelago.systems.pipeline import full_pipeline; compile_runtime_plan(PrimitivePlan(root=full_pipeline)); print('compiled')"`
Expected: prints `compiled` with no exception (validates the Retry/Sequence composition and state scoping wire up).

- [ ] **Step 6: Commit**

```bash
git add src/archipelago/systems/pipeline.py tests/archipelago/systems/test_design_review_loop.py
git commit -m "feat(systems): insert design-review retry loop after designer

Refs: docs/plans/2026-05-24-design-review-design.md"
```

---

## Task 7: Full-suite gate

**Dependencies:** Tasks 1–6

- [ ] **Step 1: Run the full test suite**

Run: `pdm test-all`
Expected: PASS. Integration tests that need a Docker daemon may SKIP (acceptable per CLAUDE.md); any FAIL is a blocker. If the real-LLM end-to-end reviewer check is gated behind a marker, it is excluded from CI and run manually before merge (see design Test Strategy).

- [ ] **Step 2: Manual real-LLM smoke (pre-merge, not committed)**

Per the design's Test Strategy, run the full working session once against the existing fixture feature definition with real inference and confirm: (a) a clean design passes on attempt 1; (b) a deliberately under-specified design triggers at least one revision attempt. This is manual verification, not an automated test.

---

## Self-Review Notes

- **Spec coverage:** Two split reviewers (Task 4), categorical scoring + validators (Task 1), aggregator passed-logic (Task 2), Designer-inside-Retry with revision prompt (Tasks 5–6), loud failure on exhaustion (Task 6). Deliberately omitted per the recorded Divergences: operator gate + `OperatorDecision` (#2), transient-failure executors + eval-registry coupling (#3).
- **Type consistency:** `DesignReviewInput`, `CorrectnessReviewOutput`/`QualityReviewOutput`, `CorrectnessVerdict`/`QualityVerdict`, `DesignReviewVerdict`, `DesignReviewState` names are used identically across tasks. Field names (`design_review_verdict`, `design_review_history`, `correctness_verdict`, `quality_verdict`, `design_document`, `investigation_summary_text`, `design_document_path`, `investigation_summary_path`) match across the state model, the actions, and the reviewers so the compiler's flat-merge scoping lines up. `DesignerOutput.design_document_path` (existing, `agents/models.py:24`) matches `DesignReviewState.design_document_path`, so the path carries across Retry iterations into the revision prompt.
- **`design_document_path` requiredness:** typed Optional inside `DesignReviewState` (platform constraint — eager `_scope_in` at body entry), enforced as required downstream at `ChangeSetsLoopState`; guaranteed non-None on any successful loop exit by construction. See the `DesignReviewState` docstring (Task 6, Step 3c).
- **Reviewer failure stance:** no custom executor; inference errors propagate and abort (Divergence #3). No `anthropic` import in archipelago.
- **Open items for the implementer to confirm at build time:**
  1. The exact `render_instance` import path in `prompts.py` — confirm `from archetype.markdown import render_instance` against the usage at `workspace_bootstrap.py:199`.
  2. `WorkspaceHandle` constructor field names (`volume_name`, `root`) used in tests — confirm against `workspace_bootstrap.py`.
  3. `agent_foundry.runtime.emit` signature (Task 2) — positional event-name + kwargs; confirm against `agent-foundry/src/agent_foundry/runtime`.
  4. A reusable `FeatureDefinition`/`DesignDocument` fixture for `test_design_review_prompts.py` (Task 4, Step 2) — locate one in the existing suite or build minimal valid instances inline.
```
