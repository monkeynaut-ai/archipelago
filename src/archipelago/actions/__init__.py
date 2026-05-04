"""Archipelago function-action primitives.

The `workspace_ops` and `workspace_io` submodules are also re-exported
here so callers can `from archipelago.actions import workspace_io` (or
`workspace_ops`) without reaching past the package boundary. `workspace_ops`
exposes the Docker-level operations (read/write file in a volume, chmod,
clone, etc.); `workspace_io` exposes higher-level typed helpers like
`read_markdown` that build on `workspace_ops`.
"""

from __future__ import annotations

from archipelago.actions import workspace_io, workspace_ops
from archipelago.actions.log_actions import (
    LogChangeSetNameInput,
    LogChangeSetNameOutput,
    LogTddPlanTaskInput,
    LogTddPlanTaskOutput,
    log_change_set_name,
    log_tdd_plan_task,
)
from archipelago.actions.prepare_change_set_workspace import (
    PrepareChangeSetWorkspaceInput,
    PrepareChangeSetWorkspaceOutput,
    prepare_change_set_workspace,
)
from archipelago.actions.workspace_bootstrap import (
    BootstrapInput,
    BootstrapOutput,
    WorkspaceHandle,
    workspace_bootstrap,
)
from archipelago.actions.workspace_io import read_markdown

__all__ = [
    "BootstrapInput",
    "BootstrapOutput",
    "LogChangeSetNameInput",
    "LogChangeSetNameOutput",
    "LogTddPlanTaskInput",
    "LogTddPlanTaskOutput",
    "PrepareChangeSetWorkspaceInput",
    "PrepareChangeSetWorkspaceOutput",
    "WorkspaceHandle",
    "log_change_set_name",
    "log_tdd_plan_task",
    "prepare_change_set_workspace",
    "read_markdown",
    "workspace_bootstrap",
    "workspace_io",
    "workspace_ops",
]
