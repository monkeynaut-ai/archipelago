"""CodeWriter agent — implements production code to satisfy tests."""

import time
from typing import Any

import structlog

from archipelago.agents.io_models import CodeWriterOutput
from archipelago.docker_worker.env import build_agent_env
from archipelago.docker_worker.lifecycle import (
    DockerLifecycle,
    DockerLifecycleProtocol,
    LifecycleResult,
)
from archipelago.docker_worker.models import WorkerConstraints
from archipelago.models import AgentWorkerResult, CurrentTask
from archipelago.types import WorkSpace


def _build_prompt(task: CurrentTask, prompt_preamble: list[str]) -> str:
    """Build a prompt for the code writer role."""
    parts = list(prompt_preamble) if prompt_preamble else ["Implement the following:"]

    if task.objective:
        parts.append(f"Objective: {task.objective}")
    if task.title:
        parts.append(f"Title: {task.title}")
    if task.acceptance_criteria:
        parts.append("Acceptance criteria:")
        for criterion in task.acceptance_criteria:
            parts.append(f"  - {criterion}")
    if task.implementation_focus:
        parts.append(f"Implementation focus: {task.implementation_focus}")
    if task.constraints:
        parts.append("Constraints:")
        for constraint in task.constraints:
            parts.append(f"  - {constraint}")

    return "\n".join(parts)


def _map_output(lifecycle_result: LifecycleResult, workspace_volume: str) -> CodeWriterOutput:
    """Map lifecycle result to typed output."""
    status = "completed" if lifecycle_result.exit_code == 0 else "failed"
    return CodeWriterOutput(
        worker_result=AgentWorkerResult(
            result_summary=f"Code writer {status}",
            status=status,
            output_lines=lifecycle_result.output_lines,
        ),
        workspace_volume=workspace_volume,
        commit_hash=lifecycle_result.commit_hash,
    )


class CodeWriter:
    """Agent that writes production code using a Docker container with Claude Code."""

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
        workspace_volume: WorkSpace | None = None,
        worker_constraints: dict[str, Any] | None = None,
    ) -> CodeWriterOutput:
        structlog.contextvars.bind_contextvars(agent="code_writer")
        prompt = _build_prompt(current_task, self.prompt_preamble)

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
        )

        return _map_output(result, workspace_volume)
