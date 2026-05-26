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
