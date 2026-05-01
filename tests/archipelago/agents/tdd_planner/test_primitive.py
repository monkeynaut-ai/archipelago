"""Tests for the TDDPlanner AgentAction primitive config."""

from __future__ import annotations

from agent_foundry.orchestration.container_executor import run_agent_in_container
from agent_foundry.primitives.models import AgentAction, ContainerReusePolicy

from archipelago.agents.tdd_planner.primitive import tdd_planner
from archipelago.constants import GID_DOCUMENTS


class TestTDDPlannerPrimitiveConfig:
    def test_given_tdd_planner_when_inspected_then_is_agent_action(self):
        assert isinstance(tdd_planner, AgentAction)

    def test_given_tdd_planner_when_inspected_then_name_is_tdd_planner(self):
        assert tdd_planner.name == "tdd_planner"

    def test_given_tdd_planner_when_inspected_then_executor_is_run_agent_in_container(self):
        assert tdd_planner.executor is run_agent_in_container

    def test_given_tdd_planner_when_inspected_then_reuse_policy_is_new_session(self):
        assert tdd_planner.reuse_policy is ContainerReusePolicy.REUSE_NEW_SESSION

    def test_given_tdd_planner_when_inspected_then_timeout_is_30_minutes(self):
        assert tdd_planner.timeout_seconds == 1800

    def test_given_tdd_planner_when_inspected_then_gids_are_documents_writer(self):
        assert tdd_planner.gids == [GID_DOCUMENTS]
