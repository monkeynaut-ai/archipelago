"""SoftwareReviewer agent — reviews code changes against quality criteria."""

import json
import time
from typing import Any

import structlog
from pydantic import ValidationError

from archipelago.docker_worker.env import build_agent_env
from archipelago.docker_worker.lifecycle import (
    DockerLifecycle,
    DockerLifecycleProtocol,
    LifecycleResult,
)
from archipelago.docker_worker.models import WorkerConstraints
from archipelago.models import CodeReview, CurrentTask

logger = structlog.get_logger(__name__)

DEFAULT_REVIEW_OUTPUT_PATH = "/workspace/review.json"


def _build_prompt(task: CurrentTask, commit_hash: str, node_config: dict[str, Any]) -> str:
    """Build a prompt for the software reviewer role."""
    preamble = node_config.get("prompt_preamble", [])
    parts = list(preamble) if preamble else ["Review the following changes:"]

    if task.objective:
        parts.append(f"Objective: {task.objective}")
    if task.title:
        parts.append(f"Title: {task.title}")
    parts.append(f"Commit hash: {commit_hash}")

    return "\n".join(parts)


def _map_output(
    lifecycle_result: LifecycleResult,
    state: dict[str, Any],
    workspace_volume: str,
    review_output_path: str,
) -> dict[str, Any]:
    """Map lifecycle result to state updates, parsing the review JSON file."""
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

    worker_result = {
        "result_summary": f"Software reviewer {status}",
        "status": status,
        "output_lines": lifecycle_result.output_lines,
        "review": review_data,
    }
    return {
        **state,
        "worker_result": worker_result,
        "workspace_volume": workspace_volume,
    }


class SoftwareReviewer:
    """Agent that reviews code using a Docker container with Claude Code."""

    def __init__(
        self, spec: Any = None, *, lifecycle: DockerLifecycleProtocol | None = None
    ) -> None:
        self.spec = spec
        self.lifecycle = lifecycle or DockerLifecycle()

    def __call__(
        self, state: dict[str, Any], node_config: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        structlog.contextvars.bind_contextvars(agent="software_reviewer")
        node_config = node_config or {}
        task = CurrentTask(**state["current_task"])
        commit_hash = state["commit_hash"]
        prompt = _build_prompt(task, commit_hash, node_config)

        existing_volume = state.get("workspace_volume")
        workspace_volume = existing_volume or f"archipelago-{int(time.time())}"
        constraints = WorkerConstraints(**state.get("worker_constraints", {}))
        extra_env = build_agent_env(task, node_config, existing_volume)
        review_output_path = node_config.get("review_output_path", DEFAULT_REVIEW_OUTPUT_PATH)

        result = self.lifecycle.execute(
            prompt=prompt,
            workspace_volume=workspace_volume,
            extra_env=extra_env,
            constraints=constraints,
            timeout_seconds=constraints.timeout_seconds,
            connection_timeout_seconds=constraints.connection_timeout_seconds,
            auto_approve_low_risk=constraints.network_policy != "none",
            collect_files=[review_output_path],
        )

        return _map_output(result, state, workspace_volume, review_output_path)
