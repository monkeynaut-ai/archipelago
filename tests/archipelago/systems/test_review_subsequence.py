from __future__ import annotations

from agent_foundry.primitives.models import Sequence

from archipelago.systems.pipeline import (
    DesignReviewState,
    design_review_loop,
    review_subsequence,
)


def test_intermediate_fields_isolated_from_loop_state() -> None:
    for field in (
        "design_document",
        "investigation_summary_text",
        "correctness_verdict",
        "quality_verdict",
    ):
        assert field not in DesignReviewState.model_fields


def test_body_is_designer_then_review_subsequence() -> None:
    body = design_review_loop.body
    assert isinstance(body, Sequence)
    assert len(body.steps) == 2
    assert body.steps[1] is review_subsequence


def test_review_subsequence_has_five_steps() -> None:
    assert isinstance(review_subsequence, Sequence)
    assert len(review_subsequence.steps) == 5
