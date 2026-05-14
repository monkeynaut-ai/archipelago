"""Public API surface for archipelago.actions."""

from __future__ import annotations

from agent_foundry.primitives.models import FunctionAction

import archipelago.actions as actions_pkg
from archipelago.actions.workspace_bootstrap import (
    bootstrap_fn,
    workspace_bootstrap,
)


class TestWorkspaceBootstrapPrimitive:
    def test_given_workspace_bootstrap_when_inspected_then_is_function_action(self):
        assert isinstance(workspace_bootstrap, FunctionAction)

    def test_given_workspace_bootstrap_when_inspected_then_function_is_bootstrap_fn(self):
        assert workspace_bootstrap.function is bootstrap_fn

    def test_given_workspace_bootstrap_function_return_type_is_bootstrap_output(self):
        assert workspace_bootstrap.function.__annotations__["return"] == "BootstrapOutput"


class TestPublicAPI:
    def test_given_actions_package_when_imported_then_all_matches_expected(self):
        assert set(actions_pkg.__all__) == {
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
        }

    def test_given_all_names_when_accessed_then_importable(self):
        for name in actions_pkg.__all__:
            assert hasattr(actions_pkg, name)
