from __future__ import annotations

from unittest.mock import patch

from archipelago.actions.load_review_inputs import (
    LoadDesignInput,
    LoadInvestigationInput,
    load_design_into_state_fn,
    load_investigation_into_state_fn,
)
from archipelago.actions.workspace_bootstrap import WorkspaceHandle
from archipelago.constants import FEATURE_DEFINITION_FILENAME, WORKSPACE_DOCUMENTS_PATH
from archipelago.models.design_document import DesignDocument, DesignDocumentFrontmatter


def _handle() -> WorkspaceHandle:
    return WorkspaceHandle.model_construct(volume_name="vol-x", root="/workspace")


def _minimal_design_document() -> DesignDocument:
    return DesignDocument(
        frontmatter=DesignDocumentFrontmatter(
            feature_slug="demo",
            feature_name="Demo Feature",
            feature_definition_path=f"{WORKSPACE_DOCUMENTS_PATH}/{FEATURE_DEFINITION_FILENAME}",
            codebase_ref="main",
            codebase_resolved_sha="a" * 40,
            generated_at="2026-04-21T12:00:00Z",
        ),
        title="Demo Feature",
        summary="One-paragraph framing.",
        current_state_context="Relevant existing state.",
        components="Component A, Component B.",
        architecture="How they interact.",
        acceptance_criteria="Refined AC.",
        test_strategy="Test approach.",
        risks_and_open_items="Open risks.",
        resolved_assumptions="Dispositions.",
    )


def test_load_design_parses_via_read_markdown() -> None:
    fake_doc = _minimal_design_document()
    with patch("archipelago.actions.load_review_inputs.read_markdown", return_value=fake_doc) as rm:
        out = load_design_into_state_fn(
            LoadDesignInput(workspace_handle=_handle(), design_document_path="/workspace/d.md")
        )
    rm.assert_called_once()
    assert rm.call_args.args[1] == "/workspace/d.md"
    assert out.design_document is fake_doc


def test_load_investigation_reads_raw_text() -> None:
    with patch(
        "archipelago.actions.load_review_inputs.read_workspace_file",
        return_value="# investigation\nbody",
    ) as rf:
        out = load_investigation_into_state_fn(
            LoadInvestigationInput(
                workspace_handle=_handle(), investigation_summary_path="/workspace/i.md"
            )
        )
    rf.assert_called_once()
    assert rf.call_args.args[1] == "/workspace/i.md"
    assert out.investigation_summary_text == "# investigation\nbody"
