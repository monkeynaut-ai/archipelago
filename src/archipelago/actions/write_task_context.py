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
import structlog
from agent_foundry.constructs import FunctionAction
from archetype.markdown import render_markdown
from pydantic import BaseModel

from archipelago.actions import workspace_ops as _ops
from archipelago.actions.workspace_bootstrap import WorkspaceHandle
from archipelago.models import (
    ChangeSetContext,
    ChangeSetRef,
    CurrentTaskDocument,
    CurrentTaskFrontmatter,
    Task,
)

_log = structlog.get_logger(__name__)


class WriteTaskContextInput(BaseModel):
    current_task: Task
    current_change_set: ChangeSetRef
    tdd_plan_path: str
    workspace_handle: WorkspaceHandle


class WriteTaskContextOutput(BaseModel):
    pass


def write_task_context_fn(state: WriteTaskContextInput) -> WriteTaskContextOutput:
    _log.info(
        "task",
        title=state.current_task.heading,
        slug=state.current_task.slug,
    )
    document = CurrentTaskDocument(
        frontmatter=CurrentTaskFrontmatter(
            change_set_slug=state.current_change_set.slug,
            task_slug=state.current_task.slug,
            tdd_plan_path=state.tdd_plan_path,
        ),
        change_set=ChangeSetContext(
            heading=state.current_change_set.heading,
            purpose=state.current_change_set.purpose,
            acceptance_criteria=state.current_change_set.acceptance_criteria,
        ),
        task=state.current_task,
    )
    _ops.write_file(
        docker.from_env(),
        volume_name=state.workspace_handle.volume_name,
        path=state.workspace_handle.current_task_path,
        content=render_markdown(document),
    )
    return WriteTaskContextOutput()


write_task_context = FunctionAction[WriteTaskContextInput, WriteTaskContextOutput](
    function=write_task_context_fn,
)
