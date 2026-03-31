"""Evaluator handler — determines whether a commit slice is complete.

Stub implementation: always passes. Will be replaced with an LLM-based
evaluator that can route to any node in the kernel subgraph.
"""

from typing import Any

from archipelago.agents.io_models import EvaluatorOutput
from archipelago.models import AgentWorkerResult


class EvaluatorHandler:
    def __init__(self, spec: Any = None, **kwargs: Any) -> None:
        self.spec = spec

    def __call__(
        self,
        current_task: Any = None,
        worker_result: AgentWorkerResult | dict[str, Any] | None = None,
    ) -> EvaluatorOutput:
        return EvaluatorOutput(commit_passed=True)


def evaluator_handler(
    state: dict[str, Any], node_config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Legacy dict-based evaluator for backward compatibility."""
    return {**state, "commit_passed": True}
