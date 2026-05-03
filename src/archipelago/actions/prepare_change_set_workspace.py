"""prepare_change_set_workspace — outer-loop preamble FunctionAction.

Runs once per outer-loop iteration before TDD Planner. Creates the
per-change-set subdirectory under `/workspace/documents/change-sets/`
and threads its path (and the steps document path inside it) into
state via Pydantic output, so downstream steps (TDD Planner and the
inner-loop body) consume them as typed input rather than reconstructing
paths from convention.
"""

from __future__ import annotations

import docker
from agent_foundry.primitives.models import FunctionAction
from pydantic import BaseModel

from archipelago.actions import workspace_ops as _ops
from archipelago.actions.workspace_bootstrap import WorkspaceHandle
from archipelago.models import ChangeSetRef


class PrepareChangeSetWorkspaceInput(BaseModel):
    workspace_handle: WorkspaceHandle
    current_change_set: ChangeSetRef


class PrepareChangeSetWorkspaceOutput(BaseModel):
    change_set_workspace_path: str
    steps_document_path: str


def prepare_change_set_workspace_fn(
    state: PrepareChangeSetWorkspaceInput,
) -> PrepareChangeSetWorkspaceOutput:
    client = docker.from_env()
    cs_path = _ops.make_change_set_subdir(
        client,
        volume_name=state.workspace_handle.volume_name,
        slug=state.current_change_set.slug,
        parent_dir=state.workspace_handle.change_sets_dir,
    )
    return PrepareChangeSetWorkspaceOutput(
        change_set_workspace_path=cs_path,
        steps_document_path=f"{cs_path}/steps.md",
    )


prepare_change_set_workspace = FunctionAction[
    PrepareChangeSetWorkspaceInput, PrepareChangeSetWorkspaceOutput
](function=prepare_change_set_workspace_fn)
