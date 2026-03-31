"""Decomposer handler — parses job_definition into global context and commit slices."""

from typing import Any

from archipelago.agents.io_models import DecomposerOutput
from archipelago.models import JobDefinition


class DecomposerHandler:
    def __init__(self, spec: Any = None, **kwargs: Any) -> None:
        self.spec = spec

    def __call__(self, job_definition: dict[str, Any]) -> DecomposerOutput:
        job = (
            JobDefinition(**job_definition)
            if isinstance(job_definition, dict)
            else JobDefinition.model_validate(job_definition)
        )
        return DecomposerOutput(
            objective=job.objective,
            repo_url=job.repo_url,
            repo_ref=job.repo_ref,
            constraints=job.constraints,
            commit_slices=[c.model_dump() for c in job.commits],
            current_index=0,
        )


def decomposer_handler(
    state: dict[str, Any], node_config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Legacy dict-based decomposer for backward compatibility."""
    raw = state.get("job_definition")
    if not raw:
        raise ValueError("job_definition is required")

    job = JobDefinition(**raw) if isinstance(raw, dict) else JobDefinition.model_validate(raw)

    return {
        **state,
        "objective": job.objective,
        "repo_url": job.repo_url,
        "repo_ref": job.repo_ref,
        "constraints": job.constraints,
        "commit_slices": [c.model_dump() for c in job.commits],
        "current_index": 0,
    }
