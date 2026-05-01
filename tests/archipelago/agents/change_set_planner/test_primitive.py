"""Tests for the ChangeSetPlanner AgentAction primitive config."""

from __future__ import annotations

from agent_foundry.orchestration.container_executor import run_agent_in_container
from agent_foundry.primitives.models import AgentAction, ContainerReusePolicy

from archipelago.agents.change_set_planner.primitive import change_set_planner
from archipelago.constants import GID_DOCUMENTS


class TestChangeSetPlannerPrimitiveConfig:
    def test_given_change_set_planner_when_inspected_then_is_agent_action(self):
        assert isinstance(change_set_planner, AgentAction)

    def test_given_change_set_planner_when_inspected_then_name_is_change_set_planner(self):
        assert change_set_planner.name == "change_set_planner"

    def test_given_change_set_planner_when_inspected_then_executor_is_run_agent_in_container(self):
        assert change_set_planner.executor is run_agent_in_container

    def test_given_change_set_planner_when_inspected_then_reuse_policy_is_new_session(self):
        assert change_set_planner.reuse_policy is ContainerReusePolicy.REUSE_NEW_SESSION

    def test_given_change_set_planner_when_inspected_then_timeout_is_30_minutes(self):
        assert change_set_planner.timeout_seconds == 1800

    def test_given_change_set_planner_when_inspected_then_gids_are_documents_writer(self):
        assert change_set_planner.gids == [GID_DOCUMENTS]
