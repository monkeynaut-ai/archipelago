"""write_task_context — per-task context injection FunctionAction.

Runs once per inner-loop iteration before tester and implementer.
Writes `/workspace/documents/current-task.md` to the workspace volume
so each tester/implementer invocation knows exactly which change set,
TDD plan, and task it is responsible for — regardless of what is baked
into its CLAUDE.md at container startup.

Also logs the task name for operator visibility (absorbing log_tdd_plan_task).
"""

from __future__ import annotations

import docker
from agent_foundry.primitives.models import FunctionAction
from pydantic import BaseModel

from archipelago.actions import workspace_ops as _ops
from archipelago.actions.workspace_bootstrap import WorkspaceHandle
from archipelago.models import ChangeSetRef, Task


class WriteTaskContextInput(BaseModel):
    current_task: Task
    current_change_set: ChangeSetRef
    tdd_plan_path: str
    workspace_handle: WorkspaceHandle


class WriteTaskContextOutput(BaseModel):
    pass


def write_task_context_fn(state: WriteTaskContextInput) -> WriteTaskContextOutput:
    print(
        f"[task] {state.current_task.title} ({state.current_task.slug})",
        flush=True,
    )
    content = (
        f"# Current Task\n\n"
        f"**Change set:** {state.current_change_set.title}\n"
        f"**TDD plan:** {state.tdd_plan_path}\n"
        f"**Task:** {state.current_task.title}\n"
    )
    _ops.write_file(
        docker.from_env(),
        volume_name=state.workspace_handle.volume_name,
        path=state.workspace_handle.current_task_path,
        content=content,
    )
    return WriteTaskContextOutput()


write_task_context = FunctionAction[WriteTaskContextInput, WriteTaskContextOutput](
    function=write_task_context_fn,
)
