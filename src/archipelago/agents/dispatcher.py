"""Dispatcher handler — iterates over commit slices, merging global context."""

from typing import Any

from agent_foundry.registry.spec import RoleSpec


class DispatcherHandler:
    def __init__(self, spec: RoleSpec) -> None:
        self.spec = spec

    def __call__(self, state: dict[str, Any], node_config: dict[str, Any] | None = None) -> dict[str, Any]:
        return dispatcher_handler(state, node_config or {})


def dispatcher_handler(state: dict[str, Any], node_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Advance to the next commit slice, merging job-level fields with commit data."""
    commit_slices = state.get("commit_slices", [])
    current_index = state.get("current_index", 0)

    if current_index >= len(commit_slices):
        return {**state, "has_more_commits": False}

    current_slice = commit_slices[current_index]

    current_commit = {
        "objective": state.get("objective", ""),
        "repo_url": state.get("repo_url", ""),
        "repo_ref": state.get("repo_ref", "main"),
        "constraints": state.get("constraints", []),
        **current_slice,
    }

    return {
        **state,
        "current_commit": current_commit,
        "current_index": current_index + 1,
        "has_more_commits": True,
    }
