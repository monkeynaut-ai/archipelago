from __future__ import annotations

from agent_foundry.primitives.models import Sequence

from archipelago.systems.pipeline import (
    DesignReviewState,
    design,
    design_review,
)


def test_intermediate_fields_isolated_from_loop_state() -> None:
    for field in (
        "design_document",
        "investigation_summary_text",
        "correctness_verdict",
        "quality_verdict",
    ):
        assert field not in DesignReviewState.model_fields


def test_body_is_designer_then_design_review() -> None:
    body = design.body
    assert isinstance(body, Sequence)
    assert len(body.steps) == 2
    assert body.steps[1] is design_review


def test_design_review_has_five_steps() -> None:
    assert isinstance(design_review, Sequence)
    assert len(design_review.steps) == 5
