from __future__ import annotations

from archipelago.agents.design_review.operator_resolver import operator_intervention_fn
from archipelago.systems.pipeline import design, operator_resolver


def test_resolver_wired_onto_loop() -> None:
    assert design.on_max_attempts_resolver is operator_resolver


def test_resolver_uses_intervention_fn() -> None:
    assert operator_resolver.function is operator_intervention_fn
