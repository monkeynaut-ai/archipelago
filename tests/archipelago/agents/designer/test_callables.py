"""Tests for Designer prompt_builder and instructions_provider."""

from __future__ import annotations

from pathlib import Path

from archetype.markdown import template_fields
from archetype.templating import resolve

from archipelago.actions import WorkspaceHandle
from archipelago.agents.designer.callables import (
    designer_instructions_provider,
    designer_prompt_builder,
)
from archipelago.agents.designer.models import DesignerInput
from archipelago.constants import (
    FEATURE_DEFINITION_FILENAME,
    WORKSPACE_CODEBASE_PATH,
    WORKSPACE_DOCUMENTS_PATH,
    WORKSPACE_ROOT,
)
from archipelago.models import DesignDocument, FeatureDefinition


def _state(minimal_feature_definition) -> DesignerInput:
    return DesignerInput(
        workspace_handle=WorkspaceHandle(
            volume_name="v",
            root=WORKSPACE_ROOT,
            documents_path=WORKSPACE_DOCUMENTS_PATH,
            codebase_path=WORKSPACE_CODEBASE_PATH,
            feature_definition_path=f"{WORKSPACE_DOCUMENTS_PATH}/{FEATURE_DEFINITION_FILENAME}",
            codebase_source_ref="main",
            codebase_resolved_sha="a" * 40,
        ),
        feature_definition=minimal_feature_definition,
    )


class TestDesignerPromptBuilder:
    def test_given_state_when_prompt_builder_then_returns_non_empty_string(
        self, minimal_feature_definition
    ):
        result = designer_prompt_builder(_state(minimal_feature_definition))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_given_state_when_prompt_builder_then_mentions_workspace_root(
        self, minimal_feature_definition
    ):
        result = designer_prompt_builder(_state(minimal_feature_definition))
        assert WORKSPACE_ROOT in result

    def test_given_state_when_prompt_builder_then_references_instructions_or_design(
        self, minimal_feature_definition
    ):
        result = designer_prompt_builder(_state(minimal_feature_definition))
        assert "instructions" in result.lower() or "design" in result.lower()


class TestDesignerInstructionsProvider:
    def test_given_state_when_instructions_provider_then_matches_manual_resolve(
        self, minimal_feature_definition
    ):
        state = _state(minimal_feature_definition)
        result = designer_instructions_provider(state)

        template_path = (
            Path(__file__).resolve().parents[4]
            / "src"
            / "archipelago"
            / "agents"
            / "designer"
            / "instructions_template.md"
        )
        expected = resolve(
            template_path.read_text(encoding="utf-8"),
            feature=state.feature_definition,
            workspace_handle=state.workspace_handle,
            FeatureDefinition=FeatureDefinition,
            DesignDocument=DesignDocument,
        )
        assert result == expected

    def test_given_state_when_instructions_provider_then_contains_structural_markers(
        self, minimal_feature_definition
    ):
        state = _state(minimal_feature_definition)
        result = designer_instructions_provider(state)
        for field in template_fields(FeatureDefinition):
            assert field.heading in result
        for field in template_fields(DesignDocument):
            assert f"## {field.heading}" in result
