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
    DesignReviewVerdict,
    DimensionScore,
    QualityDimension,
    QualityVerdict,
)


def _correctness(
    *,
    all_score: DimensionScore = DimensionScore.MEETS_BAR,
    findings: list[CorrectnessMustFixFinding] | None = None,
) -> CorrectnessVerdict:
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
                description="d",
                suggested_resolution="r",
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
    scores = {d: DimensionScore.MEETS_BAR for d in CorrectnessDimension}
    correctness = CorrectnessVerdict(
        dimension_scores=scores,
        must_fix_findings=[
            CorrectnessMustFixFinding(
                description="d",
                suggested_resolution="r",
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
        rt.artifacts_dir.return_value = None
        aggregate_design_verdict_fn(
            AggregateDesignVerdictInput(
                correctness_verdict=_correctness(),
                quality_verdict=_quality(),
                design_review_history=[],
            )
        )
    rt.emit.assert_called_once()
    assert rt.emit.call_args.args[0] == "step_completed"


def test_writes_per_attempt_verdict_artifact(tmp_path) -> None:
    with patch("archipelago.actions.aggregate_design_verdict.runtime") as rt:
        rt.artifacts_dir.return_value = tmp_path
        aggregate_design_verdict_fn(
            AggregateDesignVerdictInput(
                correctness_verdict=_correctness(),
                quality_verdict=_quality(),
                design_review_history=[],
            )
        )
    artifact = tmp_path / "design-review" / "attempt-1.json"
    assert artifact.exists()
    written = DesignReviewVerdict.model_validate_json(artifact.read_text())
    assert written.attempt_number == 1
    assert written.passed is True


def test_artifact_filename_tracks_attempt_number(tmp_path) -> None:
    with patch("archipelago.actions.aggregate_design_verdict.runtime") as rt:
        rt.artifacts_dir.return_value = tmp_path
        first = aggregate_design_verdict_fn(
            AggregateDesignVerdictInput(
                correctness_verdict=_correctness(),
                quality_verdict=_quality(),
                design_review_history=[],
            )
        )
        aggregate_design_verdict_fn(
            AggregateDesignVerdictInput(
                correctness_verdict=_correctness(),
                quality_verdict=_quality(),
                design_review_history=first.design_review_history,
            )
        )
    assert (tmp_path / "design-review" / "attempt-1.json").exists()
    assert (tmp_path / "design-review" / "attempt-2.json").exists()


def test_no_artifacts_dir_is_noop(tmp_path) -> None:
    with patch("archipelago.actions.aggregate_design_verdict.runtime") as rt:
        rt.artifacts_dir.return_value = None
        aggregate_design_verdict_fn(
            AggregateDesignVerdictInput(
                correctness_verdict=_correctness(),
                quality_verdict=_quality(),
                design_review_history=[],
            )
        )
    assert list(tmp_path.iterdir()) == []
