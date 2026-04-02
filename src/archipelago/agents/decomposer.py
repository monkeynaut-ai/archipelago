"""Decomposer handler — parses job_specification into global context and commit slices."""

from typing import Any

from dotenv.main import logger

from archipelago.agents.io_models import DecomposerOutput
from archipelago.models import JobSpecification


class DecomposerHandler:
    def __init__(self, spec: Any = None, **kwargs: Any) -> None:
        self.spec = spec

    def __call__(self, job_specification: dict[str, Any]) -> DecomposerOutput:
        logger.info("job specification: ", job_specification)
        job = (
            JobSpecification(**job_specification)
            if isinstance(job_specification, dict)
            else JobSpecification.model_validate(job_specification)
        )
        return DecomposerOutput(
            objective=job.objective,
            repo_url=job.repo_url,
            repo_ref=job.repo_ref,
            constraints=job.constraints,
            commit_slices=[c.model_dump() for c in job.change_sets],
            current_index=0,
        )


def decomposer_handler(
    state: dict[str, Any], node_config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Legacy dict-based decomposer for backward compatibility."""
    raw = state.get("job_specification")
    if not raw:
        raise ValueError("job_specification is required")

    job = JobSpecification(**raw) if isinstance(raw, dict) else JobSpecification.model_validate(raw)

    return {
        **state,
        "objective": job.objective,
        "repo_url": job.repo_url,
        "repo_ref": job.repo_ref,
        "constraints": job.constraints,
        "commit_slices": [c.model_dump() for c in job.change_sets],
        "current_index": 0,
    }
