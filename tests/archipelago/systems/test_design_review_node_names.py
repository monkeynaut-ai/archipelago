"""Design-review leaf primitives carry meaningful names so lifecycle.jsonl
labels them by name instead of positional node_id (e.g. design_correctness_review
rather than root_step_2_body_step_3)."""

from __future__ import annotations

from archipelago.actions.aggregate_design_verdict import aggregate_design_verdict
from archipelago.actions.load_review_inputs import (
    load_design_into_state,
    load_investigation_into_state,
)
from archipelago.agents.design_review import (
    design_correctness_review,
    design_quality_review,
)


def test_reviewer_ai_calls_are_named() -> None:
    assert design_correctness_review.name == "design_correctness_review"
    assert design_quality_review.name == "design_quality_review"


def test_review_function_actions_are_named() -> None:
    assert aggregate_design_verdict.name == "aggregate_design_verdict"
    assert load_design_into_state.name == "load_design_into_state"
    assert load_investigation_into_state.name == "load_investigation_into_state"
