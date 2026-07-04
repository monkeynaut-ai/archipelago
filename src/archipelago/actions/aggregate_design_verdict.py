"""Combine the correctness and quality verdicts into a single gated
DesignReviewVerdict and append it to the per-attempt history.

`passed` lives in one function (not a Pydantic computed field) so the
threshold policy is tunable in one place — e.g. if NEEDS_IMPROVEMENT
should ever block, edit here, not the model.
"""

from __future__ import annotations

from agent_foundry import runtime
from agent_foundry.constructs import FunctionAction
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


def _write_verdict_artifact(verdict: DesignReviewVerdict) -> None:
    """Persist the attempt's verdict as a per-attempt JSON artifact.

    The reviewers are plain AICalls on the default path, so they leave no
    record of their own; the aggregator already holds both verdicts, so it
    writes the durable record here. No-op outside a run (artifacts_dir None).
    """
    artifacts_dir = runtime.artifacts_dir()
    if artifacts_dir is None:
        return
    review_dir = artifacts_dir / "design-review"
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / f"attempt-{verdict.attempt_number}.json").write_text(
        verdict.model_dump_json(indent=2), encoding="utf-8"
    )


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
    _write_verdict_artifact(verdict)
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
](function=aggregate_design_verdict_fn, name="aggregate_design_verdict")
