"""Tests for the Designer AgentAction primitive config."""

from __future__ import annotations

from agent_foundry.orchestration.container_executor import run_agent_in_container
from agent_foundry.primitives.models import AgentAction, ContainerReusePolicy

from archipelago.agents.designer.callables import (
    designer_instructions_provider,
    designer_prompt_builder,
)
from archipelago.agents.designer.primitive import designer


class TestDesignerPrimitiveConfig:
    def test_given_designer_when_inspected_then_is_agent_action(self):
        assert isinstance(designer, AgentAction)

    def test_given_designer_when_inspected_then_name_is_designer(self):
        assert designer.name == "designer"

    def test_given_designer_when_inspected_then_callables_wired(self):
        assert designer.prompt_builder is designer_prompt_builder
        assert designer.instructions_provider is designer_instructions_provider

    def test_given_designer_when_inspected_then_executor_is_run_agent_in_container(self):
        assert designer.executor is run_agent_in_container

    def test_given_designer_when_inspected_then_dir_policy_matches_design(self):
        assert designer.visible_dirs == ["/workspace"]
        assert designer.writable_dirs == ["/workspace/documents"]

    def test_given_designer_when_inspected_then_reuse_policy_is_new_session(self):
        assert designer.reuse_policy is ContainerReusePolicy.REUSE_NEW_SESSION

    def test_given_designer_when_inspected_then_timeout_is_30_minutes(self):
        assert designer.timeout_seconds == 1800

    def test_given_designer_when_inspected_then_skip_permissions_is_true(self):
        assert designer.skip_permissions is True
