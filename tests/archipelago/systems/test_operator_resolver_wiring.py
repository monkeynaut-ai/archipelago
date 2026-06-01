from __future__ import annotations

from archipelago.systems.pipeline import design, operator_resolver


def test_resolver_wired_onto_loop() -> None:
    assert design.on_max_attempts_resolver is operator_resolver
