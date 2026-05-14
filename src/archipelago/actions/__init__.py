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
    log_change_set_name,
)
from archipelago.actions.prepare_change_set_workspace import (
    PrepareChangeSetWorkspaceInput,
    PrepareChangeSetWorkspaceOutput,
    prepare_change_set_workspace,
)
from archipelago.actions.setup_python_workspace import (
    SetupPythonWorkspaceInput,
    SetupPythonWorkspaceOutput,
    setup_python_workspace,
)
from archipelago.actions.workspace_bootstrap import (
    BootstrapInput,
    BootstrapOutput,
    WorkspaceHandle,
    workspace_bootstrap,
)
from archipelago.actions.workspace_io import read_markdown
from archipelago.actions.write_task_context import (
    WriteTaskContextInput,
    WriteTaskContextOutput,
    write_task_context,
)

__all__ = [
    "BootstrapInput",
    "BootstrapOutput",
    "LogChangeSetNameInput",
    "LogChangeSetNameOutput",
    "PrepareChangeSetWorkspaceInput",
    "PrepareChangeSetWorkspaceOutput",
    "SetupPythonWorkspaceInput",
    "SetupPythonWorkspaceOutput",
    "WorkspaceHandle",
    "WriteTaskContextInput",
    "WriteTaskContextOutput",
    "log_change_set_name",
    "prepare_change_set_workspace",
    "read_markdown",
    "setup_python_workspace",
    "workspace_bootstrap",
    "workspace_io",
    "workspace_ops",
    "write_task_context",
]
