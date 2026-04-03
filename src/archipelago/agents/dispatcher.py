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
