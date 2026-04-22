"""Tests for the Designer instructions template.

Loads the bundled template, resolves it against the minimal fixture,
asserts structural and content markers are present.
"""

from __future__ import annotations

from pathlib import Path

from archetype.markdown import template_fields
from archetype.templating import resolve

from archipelago.models import DesignDocument, FeatureDefinition

TEMPLATE_PATH = (
    Path(__file__).resolve().parents[4]
    / "src"
    / "archipelago"
    / "agents"
    / "designer"
    / "instructions_template.md"
)


def _template_text() -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8")


class TestTemplateFile:
    def test_given_template_path_when_read_then_exists_and_non_empty(self):
        text = _template_text()
        assert len(text) > 500


class TestTemplateResolution:
    def test_given_template_when_resolved_then_no_exception(self, minimal_feature_definition):
        resolved = resolve(
            _template_text(),
            feature=minimal_feature_definition,
            FeatureDefinition=FeatureDefinition,
            DesignDocument=DesignDocument,
        )
        assert len(resolved) > 500

    def test_given_resolved_when_checked_then_contains_feature_definition_headings(
        self, minimal_feature_definition
    ):
        resolved = resolve(
            _template_text(),
            feature=minimal_feature_definition,
            FeatureDefinition=FeatureDefinition,
            DesignDocument=DesignDocument,
        )
        for field in template_fields(FeatureDefinition):
            assert field.heading in resolved, f"missing FeatureDefinition heading {field.heading!r}"

    def test_given_resolved_when_checked_then_contains_design_document_skeleton(
        self, minimal_feature_definition
    ):
        resolved = resolve(
            _template_text(),
            feature=minimal_feature_definition,
            FeatureDefinition=FeatureDefinition,
            DesignDocument=DesignDocument,
        )
        for field in template_fields(DesignDocument):
            assert f"## {field.heading}" in resolved, (
                f"missing DesignDocument section '## {field.heading}'"
            )

    def test_given_resolved_when_checked_then_inlines_feature_prose(
        self, minimal_feature_definition
    ):
        resolved = resolve(
            _template_text(),
            feature=minimal_feature_definition,
            FeatureDefinition=FeatureDefinition,
            DesignDocument=DesignDocument,
        )
        assert minimal_feature_definition.problem_statement in resolved
        assert minimal_feature_definition.feature_intent in resolved

    def test_given_resolved_when_checked_then_inlines_list_items(self, minimal_feature_definition):
        resolved = resolve(
            _template_text(),
            feature=minimal_feature_definition,
            FeatureDefinition=FeatureDefinition,
            DesignDocument=DesignDocument,
        )
        for item in minimal_feature_definition.desired_outcomes.user_outcomes.items:
            assert item in resolved
        for item in minimal_feature_definition.assumptions.items:
            assert item in resolved
        for item in minimal_feature_definition.acceptance_criteria.items:
            assert item in resolved

    def test_given_resolved_when_checked_then_mentions_workspace_paths(
        self, minimal_feature_definition
    ):
        resolved = resolve(
            _template_text(),
            feature=minimal_feature_definition,
            FeatureDefinition=FeatureDefinition,
            DesignDocument=DesignDocument,
        )
        assert "/workspace/documents/feature_definition.md" in resolved
        assert "/workspace/codebase/" in resolved
        assert "/workspace/documents/design.md" in resolved
