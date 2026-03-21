"""Evaluator handler — determines whether a commit slice is complete.

Stub implementation: always passes. Will be replaced with an LLM-based
evaluator that can route to any node in the kernel subgraph.
"""

from typing import Any

from agent_foundry.registry.spec import RoleSpec


class EvaluatorHandler:
    def __init__(self, spec: RoleSpec) -> None:
        self.spec = spec

    def __call__(self, state: dict[str, Any], node_config: dict[str, Any] | None = None) -> dict[str, Any]:
        return evaluator_handler(state, node_config or {})


def evaluator_handler(state: dict[str, Any], node_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Evaluate whether the current commit meets acceptance criteria."""
    return {**state, "commit_passed": True}
