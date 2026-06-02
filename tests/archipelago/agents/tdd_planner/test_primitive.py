"""Tests for the TDDPlanner AgentAction primitive config."""

from __future__ import annotations

from archipelago.agents.tdd_planner.primitive import tdd_planner
from archipelago.constants import GID_DOCUMENTS


class TestTDDPlannerPrimitiveConfig:
    def test_given_tdd_planner_when_inspected_then_name_is_tdd_planner(self):
        assert tdd_planner.name == "tdd_planner"

    def test_given_tdd_planner_when_inspected_then_gids_are_documents_writer(self):
        assert tdd_planner.gids == [GID_DOCUMENTS]
