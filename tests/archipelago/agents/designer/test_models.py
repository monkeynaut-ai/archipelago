"""Tests for Designer input/output/slice models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from archipelago.actions import WorkspaceHandle
from archipelago.agents.models import DesignerInput, DesignerOutput
from archipelago.constants import (
    FEATURE_DEFINITION_FILENAME,
    WORKSPACE_CODEBASE_PATH,
    WORKSPACE_DOCUMENTS_PATH,
    WORKSPACE_ROOT,
)


def _sample_handle() -> WorkspaceHandle:
    return WorkspaceHandle(
        volume_name="v",
        root=WORKSPACE_ROOT,
        documents_path=WORKSPACE_DOCUMENTS_PATH,
        codebase_path=WORKSPACE_CODEBASE_PATH,
        feature_definition_path=f"{WORKSPACE_DOCUMENTS_PATH}/{FEATURE_DEFINITION_FILENAME}",
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
        assert state.workspace_handle.root == WORKSPACE_ROOT
        assert state.feature_definition.title == "Demo Feature"

    def test_given_missing_workspace_handle_when_constructed_then_validation_error(
        self, minimal_feature_definition
    ):
        with pytest.raises(ValidationError):
            DesignerInput(feature_definition=minimal_feature_definition)  # type: ignore[call-arg]


class TestDesignerOutput:
    def test_given_paths_when_constructed_then_stored_as_strings(self):
        out = DesignerOutput(
            investigation_summary=f"{WORKSPACE_DOCUMENTS_PATH}/investigation.md",
            design_document_path=f"{WORKSPACE_DOCUMENTS_PATH}/design.md",
        )
        assert out.investigation_summary == f"{WORKSPACE_DOCUMENTS_PATH}/investigation.md"
        assert out.design_document_path == f"{WORKSPACE_DOCUMENTS_PATH}/design.md"

    def test_given_missing_investigation_summary_when_constructed_then_validation_error(self):
        with pytest.raises(ValidationError):
            DesignerOutput(design_document_path=f"{WORKSPACE_DOCUMENTS_PATH}/design.md")  # type: ignore[call-arg]

    def test_given_missing_design_document_when_constructed_then_validation_error(self):
        with pytest.raises(ValidationError):
            DesignerOutput(  # type: ignore[call-arg]
                investigation_summary=f"{WORKSPACE_DOCUMENTS_PATH}/investigation.md",
            )

    def test_given_json_schema_when_generated_then_both_paths_carry_agent_file_path_marker(
        self,
    ):
        schema = DesignerOutput.model_json_schema()
        assert "x-agent-file-path" in schema["properties"]["design_document_path"]
        assert "x-agent-file-path" in schema["properties"]["investigation_summary"]
