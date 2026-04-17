"""SoftwareReviewer agent — reviews code changes against quality criteria."""

import json
import time
from typing import Any

import structlog
from pydantic import ValidationError

from archipelago.agents.io_models import SoftwareReviewerOutput
from archipelago.docker_worker.env import build_agent_env
from archipelago.docker_worker.lifecycle import (
    DockerLifecycle,
    DockerLifecycleProtocol,
    LifecycleResult,
)
from archipelago.docker_worker.models import WorkerConstraints
from archipelago.models import AgentWorkerResult, CodeReview, CurrentTask
from archipelago.types import CommitHash, WorkSpace

logger = structlog.get_logger(__name__)


def _review_output_path(commit_hash: str) -> str:
    """Generate a unique review output path based on the commit hash."""
    return f"/workspace/review-{commit_hash}.json"


def _build_prompt(
    task: CurrentTask, commit_hash: str, review_path: str, prompt_preamble: list[str]
) -> str:
    """Build a prompt for the software reviewer role."""
    parts = list(prompt_preamble) if prompt_preamble else ["Review the following changes:"]

    if task.objective:
        parts.append(f"Objective: {task.objective}")
    if task.title:
        parts.append(f"Title: {task.title}")
    parts.append(f"Commit hash: {commit_hash}")
    parts.append(f"Review output path: {review_path}")

    return "\n".join(parts)


def _map_output(
    lifecycle_result: LifecycleResult,
    workspace_volume: str,
    review_output_path: str,
) -> SoftwareReviewerOutput:
    """Map lifecycle result to typed output, parsing the review JSON file."""
    status = "completed" if lifecycle_result.exit_code == 0 else "failed"

    review_data = None
    if status == "completed" and review_output_path in lifecycle_result.collected_files:
        raw_content = lifecycle_result.collected_files[review_output_path]
        try:
            parsed = json.loads(raw_content)
            review = CodeReview.model_validate(parsed)
            review_data = review.model_dump()
            logger.debug("review_parsed", review=review_data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error("review_parse_failed", path=review_output_path, error=str(e))
            status = "failed"

    return SoftwareReviewerOutput(
        worker_result=AgentWorkerResult(
            result_summary=f"Software reviewer {status}",
            status=status,
            output_lines=lifecycle_result.output_lines,
            review=review_data,
        ),
        workspace_volume=workspace_volume,
    )


class SoftwareReviewer:
    """Agent that reviews code using a Docker container with Claude Code."""

    def __init__(
        self,
        spec: Any = None,
        *,
        lifecycle: DockerLifecycleProtocol | None = None,
        prompt_preamble: list[str] | None = None,
        role_instructions_path: str | None = None,
        workspace_readonly_dirs: list[str] | None = None,
        workspace_hidden_dirs: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self.spec = spec
        self.lifecycle = lifecycle or DockerLifecycle()
        self.prompt_preamble = prompt_preamble or []
        self.role_instructions_path = role_instructions_path
        self.workspace_readonly_dirs = workspace_readonly_dirs or []
        self.workspace_hidden_dirs = workspace_hidden_dirs or []

    def __call__(
        self,
        current_task: CurrentTask,
        commit_hash: CommitHash,
        workspace_volume: WorkSpace | None = None,
        worker_constraints: dict[str, Any] | None = None,
    ) -> SoftwareReviewerOutput:
        structlog.contextvars.bind_contextvars(agent="software_reviewer")
        review_path = _review_output_path(commit_hash)
        prompt = _build_prompt(current_task, commit_hash, review_path, self.prompt_preamble)

        existing_volume = workspace_volume
        workspace_volume = existing_volume or f"archipelago-{int(time.time())}"
        constraints = WorkerConstraints(**(worker_constraints or {}))

        config = {
            "workspace_readonly_dirs": self.workspace_readonly_dirs,
            "workspace_hidden_dirs": self.workspace_hidden_dirs,
            "role_instructions_path": self.role_instructions_path,
        }
        extra_env = build_agent_env(current_task, config, existing_volume)

        result = self.lifecycle.execute(
            prompt=prompt,
            workspace_volume=workspace_volume,
            extra_env=extra_env,
            constraints=constraints,
            timeout_seconds=constraints.timeout_seconds,
            connection_timeout_seconds=constraints.connection_timeout_seconds,
            auto_approve_low_risk=constraints.network_policy != "none",
            collect_files=[review_path],
        )

        return _map_output(result, workspace_volume, review_path)
