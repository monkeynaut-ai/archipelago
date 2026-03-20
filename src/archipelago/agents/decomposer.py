"""Decomposer handler — parses job_definition into global context and commit slices."""

from typing import Any

from agent_foundry.registry.spec import RoleSpec

from archipelago.models import JobDefinition


class DecomposerHandler:
    def __init__(self, spec: RoleSpec) -> None:
        self.spec = spec

    def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        return decomposer_handler(state)


def decomposer_handler(state: dict[str, Any]) -> dict[str, Any]:
    """Parse job_definition into global_context and commit_slices."""
    raw = state.get("job_definition")
    if not raw:
        raise ValueError("job_definition is required")

    job = JobDefinition(**raw) if isinstance(raw, dict) else JobDefinition.model_validate(raw)

    return {
        **state,
        "global_context": {
            "objective": job.objective,
            "constraints": job.constraints,
        },
        "commit_slices": [c.model_dump() for c in job.commits],
        "current_index": 0,
    }
