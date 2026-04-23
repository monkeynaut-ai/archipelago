"""Tests for workspace-bootstrap state models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from archipelago.actions.workspace_bootstrap import (
    BootstrapInput,
    BootstrapOutput,
    WorkspaceHandle,
)
from archipelago.models import CodebaseSource


def _sample_handle() -> WorkspaceHandle:
    return WorkspaceHandle(
        volume_name="archipelago-ws-demo-1000000000000000000",
        root="/workspace",
        documents_path="/workspace/documents",
        codebase_path="/workspace/codebase",
        feature_definition_path="/workspace/documents/feature_definition.md",
        codebase_source_ref="main",
        codebase_resolved_sha="a" * 40,
    )


class TestWorkspaceHandle:
    def test_given_all_fields_when_constructed_then_fields_populated(self):
        handle = _sample_handle()
        assert handle.root == "/workspace"
        assert handle.codebase_resolved_sha == "a" * 40

    def test_given_missing_volume_name_when_constructed_then_validation_error(self):
        with pytest.raises(ValidationError):
            WorkspaceHandle(
                root="/workspace",
                documents_path="/workspace/documents",
                codebase_path="/workspace/codebase",
                feature_definition_path="/workspace/documents/feature_definition.md",
                codebase_source_ref="main",
                codebase_resolved_sha="a" * 40,
            )  # type: ignore[call-arg]


class TestBootstrapInputOutput:
    def test_given_all_fields_when_bootstrap_input_then_fields_populated(
        self, minimal_feature_definition
    ):
        state = BootstrapInput(
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(
                repo_url="https://github.com/730alchemy/agent-foundry.git",
                ref="main",
            ),
            volume_name="archipelago-ws-demo-1000000000000000000",
        )
        assert state.feature_definition is minimal_feature_definition
        assert state.volume_name.startswith("archipelago-ws-")

    def test_given_missing_volume_name_when_bootstrap_input_then_validation_error(
        self, minimal_feature_definition
    ):
        with pytest.raises(ValidationError):
            BootstrapInput(
                feature_definition=minimal_feature_definition,
                codebase_source=CodebaseSource(repo_url="u", ref="r"),
            )  # type: ignore[call-arg]

    def test_given_handle_when_bootstrap_output_then_handle_preserved(self):
        handle = _sample_handle()
        out = BootstrapOutput(workspace_handle=handle)
        assert out.workspace_handle is handle
