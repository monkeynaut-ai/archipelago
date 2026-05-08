"""Tests for the pr_creator AgentAction primitive config."""

from __future__ import annotations

from agent_foundry.orchestration.container_executor import run_agent_in_container
from agent_foundry.primitives.models import AgentAction, ContainerReusePolicy

from archipelago.agents.pr_creator.primitive import (
    pr_creator,
    pr_creator_instructions_provider,
    pr_creator_prompt_builder,
)
from archipelago.constants import GID_CODEBASE, GID_DOCUMENTS


class TestPrCreatorPrimitiveConfig:
    def test_given_pr_creator_when_inspected_then_is_agent_action(self):
        assert isinstance(pr_creator, AgentAction)

    def test_given_pr_creator_when_inspected_then_name_is_pr_creator(self):
        assert pr_creator.name == "pr_creator"

    def test_given_pr_creator_when_inspected_then_callables_wired(self):
        assert pr_creator.prompt_builder is pr_creator_prompt_builder
        assert pr_creator.instructions_provider is pr_creator_instructions_provider

    def test_given_pr_creator_when_inspected_then_executor_is_run_agent_in_container(self):
        assert pr_creator.executor is run_agent_in_container

    def test_given_pr_creator_when_inspected_then_gids_include_documents_and_codebase(self):
        assert GID_DOCUMENTS in pr_creator.gids
        assert GID_CODEBASE in pr_creator.gids

    def test_given_pr_creator_when_inspected_then_reuse_policy_is_new_session(self):
        assert pr_creator.reuse_policy is ContainerReusePolicy.REUSE_NEW_SESSION

    def test_given_pr_creator_when_inspected_then_timeout_is_30_minutes(self):
        assert pr_creator.timeout_seconds == 1800

    def test_given_pr_creator_when_inspected_then_skip_permissions_is_true(self):
        assert pr_creator.skip_permissions is True


class TestPrCreatorPromptBuilder:
    def test_given_state_when_prompt_builder_then_returns_non_empty_string(
        self, minimal_feature_definition
    ):
        from archipelago.actions import WorkspaceHandle
        from archipelago.agents.models import PrCreatorInput
        from archipelago.constants import (
            FEATURE_DEFINITION_FILENAME,
            WORKSPACE_CODEBASE_PATH,
            WORKSPACE_DOCUMENTS_PATH,
            WORKSPACE_ROOT,
        )
        from archipelago.models import CodebaseSource

        state = PrCreatorInput(
            workspace_handle=WorkspaceHandle(
                volume_name="ws",
                root=WORKSPACE_ROOT,
                documents_path=WORKSPACE_DOCUMENTS_PATH,
                codebase_path=WORKSPACE_CODEBASE_PATH,
                feature_definition_path=f"{WORKSPACE_DOCUMENTS_PATH}/{FEATURE_DEFINITION_FILENAME}",
                codebase_source_ref="main",
                codebase_resolved_sha="a" * 40,
            ),
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(repo_url="https://github.com/org/repo.git", ref="main"),
        )
        result = pr_creator_prompt_builder(state)
        assert isinstance(result, str)
        assert len(result) > 0
