"""Public API surface for archipelago.actions."""

from __future__ import annotations

import archipelago.actions as actions_pkg


class TestPublicAPI:
    def test_given_actions_package_when_imported_then_all_matches_expected(self):
        assert set(actions_pkg.__all__) == {
            "AggregateDesignVerdictInput",
            "AggregateDesignVerdictOutput",
            "aggregate_design_verdict",
            "BootstrapInput",
            "BootstrapOutput",
            "LoadDesignInput",
            "LoadDesignOutput",
            "LoadInvestigationInput",
            "LoadInvestigationOutput",
            "load_design_into_state",
            "load_investigation_into_state",
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
            "read_workspace_file",
            "setup_python_workspace",
            "workspace_bootstrap",
            "workspace_io",
            "workspace_ops",
            "write_task_context",
        }

    def test_given_all_names_when_accessed_then_importable(self):
        for name in actions_pkg.__all__:
            assert hasattr(actions_pkg, name)
