"""Tests for Designer input/output/slice models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from archipelago.actions import WorkspaceHandle
from archipelago.agents.designer.models import (
    DesignerInput,
    DesignerOutput,
)


def _sample_handle() -> WorkspaceHandle:
    return WorkspaceHandle(
        volume_name="v",
        root="/workspace",
        documents_path="/workspace/documents",
        codebase_path="/workspace/codebase",
        feature_definition_path="/workspace/documents/feature_definition.md",
        codebase_source_ref="main",
        codebase_resolved_sha="a" * 40,
    )


class TestDesignerInput:
    def test_given_handle_and_feature_when_constructed_then_fields_populated(
        self, minimal_feature_definition
    ):
        state = DesignerInput(
            workspace_handle=_sample_handle(),
            feature_definition=minimal_feature_definition,
        )
        assert state.workspace_handle.root == "/workspace"
        assert state.feature_definition.title == "Demo Feature"

    def test_given_missing_workspace_handle_when_constructed_then_validation_error(
        self, minimal_feature_definition
    ):
        with pytest.raises(ValidationError):
            DesignerInput(feature_definition=minimal_feature_definition)  # type: ignore[call-arg]


class TestDesignerOutput:
    def test_given_path_when_constructed_then_stored_as_string(self):
        out = DesignerOutput(design_document="/workspace/documents/design.md")
        assert out.design_document == "/workspace/documents/design.md"

    def test_given_json_schema_when_generated_then_design_document_carries_agent_file_path_marker(
        self,
    ):
        schema = DesignerOutput.model_json_schema()
        path_schema = schema["properties"]["design_document"]
        assert "x-agent-file-path" in path_schema
