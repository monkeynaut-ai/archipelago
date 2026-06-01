from __future__ import annotations

from collections.abc import Callable

from agent_foundry.primitives import DispositionKind, RetryExhaustionReason

from archipelago.agents.design_review.operator_resolver import (
    resolve_operator_intervention,
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
from archipelago.systems.pipeline import DesignReviewState


def _scripted(answers: list[str]) -> Callable[[str], str]:
    it = iter(answers)

    def _prompt(_message: str) -> str:
        return next(it)

    return _prompt


def _exhausted_state() -> DesignReviewState:
    correctness = CorrectnessVerdict(
        dimension_scores={d: DimensionScore.MEETS_BAR for d in CorrectnessDimension}
        | {CorrectnessDimension.REQUIREMENT_COVERAGE: DimensionScore.INADEQUATE},
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
    verdict = DesignReviewVerdict(
        correctness=correctness, quality=quality, passed=False, attempt_number=3
    )
    return DesignReviewState.model_construct(
        design_document_path="/workspace/documents/design.md",
        design_review_verdict=verdict,
        design_review_history=[verdict, verdict, verdict],
        exhaustion_reason=RetryExhaustionReason.CONDITION_NOT_MET,
    )


def test_accept_disposition() -> None:
    result = resolve_operator_intervention(
        _exhausted_state(), prompt=_scripted(["accept"]), out=lambda _m: None
    )
    assert result.disposition.kind is DispositionKind.ACCEPT
    assert result.operator_guidance is None


def test_abort_disposition_carries_reason() -> None:
    result = resolve_operator_intervention(
        _exhausted_state(),
        prompt=_scripted(["abort", "blocked on infra"]),
        out=lambda _m: None,
    )
    assert result.disposition.kind is DispositionKind.ABORT
    assert result.disposition.reason == "blocked on infra"


def test_retry_disposition_carries_guidance() -> None:
    result = resolve_operator_intervention(
        _exhausted_state(),
        prompt=_scripted(["retry", "use a queue instead of polling"]),
        out=lambda _m: None,
    )
    assert result.disposition.kind is DispositionKind.RETRY
    assert result.operator_guidance == "use a queue instead of polling"


def test_invalid_choice_reprompts() -> None:
    result = resolve_operator_intervention(
        _exhausted_state(), prompt=_scripted(["maybe", "accept"]), out=lambda _m: None
    )
    assert result.disposition.kind is DispositionKind.ACCEPT


def test_blank_guidance_reprompts() -> None:
    result = resolve_operator_intervention(
        _exhausted_state(),
        prompt=_scripted(["retry", "   ", "real guidance"]),
        out=lambda _m: None,
    )
    assert result.operator_guidance == "real guidance"
