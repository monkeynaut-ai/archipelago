"""Tests for the ChangeSetPlanner AgentAction primitive config."""

from __future__ import annotations

from archipelago.agents.change_set_planner.primitive import change_set_planner
from archipelago.constants import GID_DOCUMENTS


class TestChangeSetPlannerPrimitiveConfig:
    def test_given_change_set_planner_when_inspected_then_name_is_change_set_planner(self):
        assert change_set_planner.name == "change_set_planner"

    def test_given_change_set_planner_when_inspected_then_gids_are_documents_writer(self):
        assert change_set_planner.gids == [GID_DOCUMENTS]
