from __future__ import annotations

from archipelago.models.design_review import (
    CorrectnessDimension,
    CorrectnessVerdict,
    DesignReviewVerdict,
    DimensionScore,
    QualityDimension,
    QualityVerdict,
)
from archipelago.systems.pipeline import (
    DesignReviewState,
    _design_review_passed,
)


def _passing_correctness() -> CorrectnessVerdict:
    return CorrectnessVerdict(
        dimension_scores={d: DimensionScore.MEETS_BAR for d in CorrectnessDimension},
        must_fix_findings=[],
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
