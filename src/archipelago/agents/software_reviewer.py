"""SoftwareReviewer agent — reviews code changes against quality criteria."""

from typing import Any

from archipelago.docker_worker.env import build_agent_env
from archipelago.docker_worker.lifecycle import (
    DockerLifecycle,
    DockerLifecycleProtocol,
    LifecycleResult,
)
from archipelago.docker_worker.models import WorkerConstraints
from archipelago.models import CurrentTask


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
    lifecycle_result: LifecycleResult, state: dict[str, Any], workspace_volume: str
) -> dict[str, Any]:
    """Map lifecycle result to state updates."""
    status = "completed" if lifecycle_result.exit_code == 0 else "failed"
    worker_result = {
        "result_summary": f"Software reviewer {status}",
        "status": status,
        "output_lines": lifecycle_result.output_lines,
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
        node_config = node_config or {}
        task = CurrentTask(**state["current_task"])
        commit_hash = state["commit_hash"]
        prompt = _build_prompt(task, commit_hash, node_config)

        existing_volume = state.get("workspace_volume")
        workspace_volume = existing_volume or "archipelago-scratch"
        constraints = WorkerConstraints(**state.get("worker_constraints", {}))
        extra_env = build_agent_env(task, node_config, existing_volume)

        result = self.lifecycle.execute(
            prompt=prompt,
            workspace_volume=workspace_volume,
            extra_env=extra_env,
            constraints=constraints,
            timeout_seconds=constraints.timeout_seconds,
            connection_timeout_seconds=constraints.connection_timeout_seconds,
            auto_approve_low_risk=constraints.network_policy != "none",
        )

        return _map_output(result, state, workspace_volume)
