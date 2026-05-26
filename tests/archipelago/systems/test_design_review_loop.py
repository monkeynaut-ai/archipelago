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
                description="d",
                suggested_resolution="r",
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
            correctness=_passing_correctness(),
            quality=_quality(),
            passed=True,
            attempt_number=1,
        )
    )
    assert _design_review_passed(state) is True
    assert (
        _design_review_passed(DesignReviewState.model_construct(design_review_verdict=None))
        is False
    )


def test_exhaustion_raises_with_history() -> None:
    from agent_foundry.primitives.retry_types import RetryExhaustion, RetryExhaustionReason

    history = [
        DesignReviewVerdict(
            correctness=_failing_correctness(),
            quality=_quality(),
            passed=False,
            attempt_number=i + 1,
        )
        for i in range(3)
    ]
    last = DesignReviewState.model_construct(
        design_review_verdict=history[-1], design_review_history=history
    )
    exhaustion = RetryExhaustion.model_construct(
        max_attempts=3,
        reason=RetryExhaustionReason.CONDITION_NOT_MET,
        attempt_failures=[],
        last_state=last,
    )
    with pytest.raises(DesignReviewNotApprovedError) as ei:
        _design_review_exhausted(exhaustion)
    assert "3" in str(ei.value)
