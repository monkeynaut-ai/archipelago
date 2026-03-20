"""Archipelago pipeline plan — parsing, validation, and planner integration tests."""

import json
from pathlib import Path

import pytest

from agent_foundry.planner.validators import validate_plan
from agent_foundry.planner.wiring_plan import GraphWiringPlan

PLAN_PATH = (
    Path(__file__).parent.parent.parent.parent / "src" / "archipelago" / "archipelago_system.json"
)


@pytest.fixture
def plan_data():
    return json.loads(PLAN_PATH.read_text())


@pytest.fixture
def plan(plan_data):
    return GraphWiringPlan(**plan_data)


# ── Commit 1: Parse tests ──


class TestParsePlan:
    def test_given_pipeline_json_when_parsed_then_goal_is_archipelago_pipeline(self, plan):
        assert plan.goal == "archipelago-pipeline"

    def test_given_pipeline_json_when_parsed_then_has_3_nodes(self, plan):
        assert len(plan.nodes) == 3

    def test_given_pipeline_json_when_parsed_then_has_3_edges(self, plan):
        assert len(plan.edges) == 3

    def test_given_pipeline_json_when_parsed_then_entry_point_is_decomposer(self, plan):
        assert plan.entry_point == "decomposer"

    def test_given_pipeline_json_when_parsed_then_breakpoints_are_empty(self, plan):
        assert plan.breakpoints == []

    def test_given_pipeline_json_when_parsed_then_kernel_node_is_subgraph(self, plan):
        kernel = next(n for n in plan.nodes if n.id == "kernel")
        assert kernel.subgraph is not None
        assert kernel.state_mapping is not None

    def test_given_pipeline_json_when_parsed_then_kernel_subgraph_has_3_nodes(self, plan):
        kernel = next(n for n in plan.nodes if n.id == "kernel")
        assert len(kernel.subgraph.nodes) == 3

    def test_given_pipeline_json_when_round_tripped_then_no_field_loss(self, plan_data):
        plan = GraphWiringPlan(**plan_data)
        dumped = json.loads(plan.model_dump_json())
        reconstructed = GraphWiringPlan(**dumped)
        assert reconstructed == plan


# ── Commit 2: Validation tests ──


class TestValidatePlan:
    def test_given_pipeline_plan_and_full_registry_when_validated_then_no_errors(
        self, plan, registry
    ):
        validate_plan(plan, registry)

    def test_given_pipeline_plan_when_duplicate_check_runs_then_no_duplicate_ids(self, plan):
        node_ids = [n.id for n in plan.nodes]
        assert len(node_ids) == len(set(node_ids))

    def test_given_pipeline_plan_when_dangling_edge_check_runs_then_no_dangles(self, plan):
        node_ids = {n.id for n in plan.nodes}
        for edge in plan.edges:
            assert edge.source in node_ids, f"Dangling source: {edge.source}"
            assert edge.target in node_ids, f"Dangling target: {edge.target}"
