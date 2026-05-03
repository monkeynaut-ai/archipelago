"""Tests for DesignDocument."""

from __future__ import annotations

import pytest
from archetype.markdown import render_instance, template_fields, validate_markdown
from pydantic import ValidationError

from archipelago.constants import WORKSPACE_DOCUMENTS_PATH
from archipelago.models.design_document import (
    DesignDocument,
    DesignDocumentFrontmatter,
)


def _minimal_design_document() -> DesignDocument:
    return DesignDocument(
        frontmatter=DesignDocumentFrontmatter(
            feature_slug="demo",
            feature_name="Demo Feature",
            feature_definition_path=f"{WORKSPACE_DOCUMENTS_PATH}/feature_definition.md",
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


class TestDesignDocumentFrontmatter:
    def test_given_all_fields_when_constructed_then_fields_populated(self):
        fm = DesignDocumentFrontmatter(
            feature_slug="x",
            feature_name="X",
            feature_definition_path="/p",
            codebase_ref="main",
            codebase_resolved_sha="a" * 40,
            generated_at="ts",
        )
        assert fm.feature_slug == "x"
        assert fm.codebase_resolved_sha == "a" * 40

    def test_given_missing_generated_at_when_constructed_then_validation_error(self):
        with pytest.raises(ValidationError):
            DesignDocumentFrontmatter(
                feature_slug="x",
                feature_name="X",
                feature_definition_path="/p",
                codebase_ref="main",
                codebase_resolved_sha="a" * 40,
            )  # type: ignore[call-arg]


class TestDesignDocumentConstruction:
    def test_given_all_sections_when_constructed_then_no_error(self):
        dd = _minimal_design_document()
        assert dd.title == "Demo Feature"
        assert dd.summary == "One-paragraph framing."

    def test_given_missing_architecture_when_constructed_then_validation_error(self):
        with pytest.raises(ValidationError):
            DesignDocument(
                frontmatter=DesignDocumentFrontmatter(
                    feature_slug="x",
                    feature_name="X",
                    feature_definition_path="/p",
                    codebase_ref="main",
                    codebase_resolved_sha="a" * 40,
                    generated_at="ts",
                ),
                title="X",
                summary="s",
                current_state_context="c",
                components="c",
                acceptance_criteria="ac",
                test_strategy="t",
                risks_and_open_items="r",
                resolved_assumptions="a",
            )  # type: ignore[call-arg]


class TestDesignDocumentTemplateFields:
    def test_given_design_document_when_template_fields_then_eight_entries(self):
        fields = template_fields(DesignDocument)
        assert len(fields) == 8

    def test_given_design_document_when_template_fields_then_headings_match(self):
        fields = template_fields(DesignDocument)
        assert [f.heading for f in fields] == [
            "Summary",
            "Current State Context",
            "Components",
            "Architecture",
            "Acceptance Criteria",
            "Test Strategy",
            "Risks And Open Items",
            "Resolved Assumptions",
        ]


class TestDesignDocumentTitleTextTemplate:
    def test_given_instance_when_rendered_then_h1_uses_design_for_prefix(self):
        dd = _minimal_design_document()
        rendered = render_instance(dd)
        assert "# Design for Demo Feature" in rendered


class TestDesignDocumentRoundTrip:
    def test_given_instance_when_rendered_and_parsed_then_semantically_equal(self):
        dd = _minimal_design_document()
        rendered = render_instance(dd)
        reparsed = validate_markdown(rendered, DesignDocument)
        assert reparsed == dd

    def test_given_instance_when_rendered_then_all_frontmatter_fields_present(self):
        dd = _minimal_design_document()
        rendered = render_instance(dd)
        for key in [
            "feature_slug:",
            "feature_name:",
            "feature_definition_path:",
            "codebase_ref:",
            "codebase_resolved_sha:",
            "generated_at:",
        ]:
            assert key in rendered, f"missing frontmatter key {key!r}"
