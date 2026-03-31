"""Dispatcher handler — iterates over commit slices, merging global context."""

from typing import Any

from archipelago.agents.io_models import DispatcherOutput
from archipelago.models import CurrentTask
from archipelago.types import Objective, RepoRef, RepoUrl


class DispatcherHandler:
    def __init__(self, spec: Any = None, **kwargs: Any) -> None:
        self.spec = spec

    def __call__(
        self,
        commit_slices: list[dict[str, Any]],
        current_index: int,
        objective: Objective = "",
        repo_url: RepoUrl = "",
        repo_ref: RepoRef = "main",
        constraints: list[str] | None = None,
    ) -> DispatcherOutput:
        if current_index >= len(commit_slices):
            # Return a minimal output indicating no more commits
            return DispatcherOutput(
                current_task=CurrentTask(objective=objective, title=""),
                current_index=current_index,
                has_more_commits=False,
            )

        current_slice = commit_slices[current_index]
        current_task = CurrentTask(
            objective=objective,
            repo_url=repo_url,
            repo_ref=repo_ref,
            constraints=constraints or [],
            **current_slice,
        )

        return DispatcherOutput(
            current_task=current_task,
            current_index=current_index + 1,
            has_more_commits=True,
        )


def dispatcher_handler(
    state: dict[str, Any], node_config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Legacy dict-based dispatcher for backward compatibility."""
    commit_slices = state.get("commit_slices", [])
    current_index = state.get("current_index", 0)

    if current_index >= len(commit_slices):
        return {**state, "has_more_commits": False}

    current_slice = commit_slices[current_index]

    current_task = {
        "objective": state.get("objective", ""),
        "repo_url": state.get("repo_url", ""),
        "repo_ref": state.get("repo_ref", "main"),
        "constraints": state.get("constraints", []),
        **current_slice,
    }

    return {
        **state,
        "current_task": current_task,
        "current_index": current_index + 1,
        "has_more_commits": True,
    }
