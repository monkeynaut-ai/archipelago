"""Tests for PrCreatorInput and PrCreatorOutput models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from archipelago.actions import WorkspaceHandle
from archipelago.agents.models import PrCreatorInput, PrCreatorOutput
from archipelago.constants import (
    FEATURE_DEFINITION_FILENAME,
    WORKSPACE_CODEBASE_PATH,
    WORKSPACE_DOCUMENTS_PATH,
    WORKSPACE_ROOT,
)
from archipelago.models import CodebaseSource


def _handle() -> WorkspaceHandle:
    return WorkspaceHandle(
        volume_name="ws",
        root=WORKSPACE_ROOT,
        documents_path=WORKSPACE_DOCUMENTS_PATH,
        codebase_path=WORKSPACE_CODEBASE_PATH,
        feature_definition_path=f"{WORKSPACE_DOCUMENTS_PATH}/{FEATURE_DEFINITION_FILENAME}",
        codebase_source_ref="main",
        codebase_resolved_sha="a" * 40,
    )


class TestPrCreatorInput:
    def test_given_required_fields_when_constructed_then_fields_populated(
        self, minimal_feature_definition
    ):
        state = PrCreatorInput(
            workspace_handle=_handle(),
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(repo_url="https://github.com/org/repo.git", ref="main"),
        )
        assert state.feature_definition is minimal_feature_definition
        assert state.codebase_source.ref == "main"
        assert state.workspace_handle.root == WORKSPACE_ROOT

    def test_given_no_design_document_when_constructed_then_defaults_to_none(
        self, minimal_feature_definition
    ):
        state = PrCreatorInput(
            workspace_handle=_handle(),
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(repo_url="u", ref="r"),
        )
        assert state.design_document_path is None

    def test_given_design_document_path_when_constructed_then_preserved(
        self, minimal_feature_definition
    ):
        state = PrCreatorInput(
            workspace_handle=_handle(),
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(repo_url="u", ref="r"),
            design_document_path=f"{WORKSPACE_DOCUMENTS_PATH}/design.md",
        )
        assert state.design_document_path == f"{WORKSPACE_DOCUMENTS_PATH}/design.md"

    def test_given_missing_workspace_handle_when_constructed_then_validation_error(
        self, minimal_feature_definition
    ):
        with pytest.raises(ValidationError):
            PrCreatorInput(  # type: ignore[call-arg]
                feature_definition=minimal_feature_definition,
                codebase_source=CodebaseSource(repo_url="u", ref="r"),
            )


class TestPrCreatorOutput:
    def test_given_no_args_when_constructed_then_pr_url_is_none(self):
        out = PrCreatorOutput()
        assert out.pr_url is None

    def test_given_pr_url_when_constructed_then_preserved(self):
        out = PrCreatorOutput(pr_url="https://github.com/org/repo/pull/42")
        assert out.pr_url == "https://github.com/org/repo/pull/42"
