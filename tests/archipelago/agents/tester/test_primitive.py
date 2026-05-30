"""Tests for the tester AgentAction primitive."""

from __future__ import annotations

from archipelago.actions import WorkspaceHandle
from archipelago.agents import models as agent_models
from archipelago.agents.tester import primitive as tester_primitive


def _input_with_documents_path(documents_path: str) -> agent_models.TesterInput:
    return agent_models.TesterInput(
        workspace_handle=WorkspaceHandle(
            volume_name="ws",
            root="/workspace",
            documents_path=documents_path,
            codebase_path="/workspace/codebase",
            feature_definition_path=f"{documents_path}/feature_definition.md",
            codebase_source_ref="main",
            codebase_resolved_sha="a" * 40,
        ),
    )


class TestTesterInstructionsProvider:
    def test_given_state_when_rendered_then_threads_paths_from_workspace_handle(self):
        state = _input_with_documents_path("/custom/docs")
        rendered = tester_primitive.tester_instructions_provider(state)
        assert "/custom/docs/current-task.md" in rendered
        assert "/custom/docs/design.md" in rendered

    def test_given_state_when_rendered_then_no_hardcoded_default_paths(self):
        state = _input_with_documents_path("/custom/docs")
        rendered = tester_primitive.tester_instructions_provider(state)
        assert "/workspace/documents/current-task.md" not in rendered
        assert "/workspace/documents/design.md" not in rendered
