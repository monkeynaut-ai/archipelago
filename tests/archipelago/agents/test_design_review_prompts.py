from __future__ import annotations

from archipelago.agents.design_review.prompts import correctness_prompt, quality_prompt
from archipelago.constants import FEATURE_DEFINITION_FILENAME, WORKSPACE_DOCUMENTS_PATH
from archipelago.models.design_document import DesignDocument, DesignDocumentFrontmatter
from archipelago.models.design_review import DesignReviewInput


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


def test_prompts_render_real_documents(minimal_feature_definition) -> None:
    state = DesignReviewInput(
        feature_definition=minimal_feature_definition,
        design_document=_minimal_design_document(),
        investigation_summary_text="codebase notes",
    )
    c = correctness_prompt(state)
    q = quality_prompt(state)
    assert "# Feature Definition" in c
    assert "# Design Document" in c
    assert "# Investigation Summary" in q
    assert "codebase notes" in q
