"""Archipelago end-to-end pipeline tests with stub handlers."""

from pathlib import Path
from typing import Any

import pytest
from agent_foundry.compiler.compiler import compile_plan
from agent_foundry.planner.wiring_plan import GraphWiringPlan

from archipelago.agents.decomposer import decomposer_handler
from archipelago.agents.dispatcher import dispatcher_handler
from archipelago.agents.evaluator import evaluator_handler

PLAN_PATH = (
    Path(__file__).parent.parent.parent.parent / "src" / "archipelago" / "archipelago_system.json"
)


def _stub_docker_worker(
    state: dict[str, Any], node_config: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        **state,
        "worker_result": {
            "result_summary": "completed",
            "workspace_ref": "ws-test",
            "patches": [],
            "evidence": [],
            "status": "completed",
        },
        "workspace_volume": state.get("workspace_volume", "archipelago-stub"),
        "commit_hash": "stubhash123",
    }


def _stub_software_review(
    state: dict[str, Any], node_config: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        **state,
        "worker_result": {
            "scope": {"paths": []},
            "summary": {"overall_rating": "good", "strengths": [], "primary_concerns": []},
            "findings": [],
        },
        "workspace_volume": state.get("workspace_volume", "archipelago-stub"),
    }


STUB_HANDLERS = {
    "decompose_job_specification": decomposer_handler,
    "dispatch_commit": dispatcher_handler,
    "evaluate_commit": evaluator_handler,
    "write_unit_tests_from_spec": _stub_docker_worker,
    "code_implement_from_tests": _stub_docker_worker,
    "software_review": _stub_software_review,
}


def _job_specification(num_change_sets: int = 2) -> dict:
    return {
        "objective": "Add user authentication",
        "repo_url": "https://github.com/org/repo",
        "constraints": ["Must use OAuth2"],
        "change_sets": [
            {"title": f"commit-{i}", "test_focus": f"tests-{i}"} for i in range(num_change_sets)
        ],
    }


@pytest.fixture
def plan():
    import json

    plan_data = json.loads(PLAN_PATH.read_text())
    return GraphWiringPlan(**plan_data)


class TestEndToEnd:
    def test_given_2_change_sets_when_pipeline_runs_then_all_change_sets_processed(
        self, registry, plan
    ):
        graph = compile_plan(plan, registry, handler_registry=STUB_HANDLERS)
        result = graph.invoke({"job_specification": _job_specification(2)})
        assert result["current_index"] == 2
        assert result["has_more_commits"] is False

    def test_given_3_change_sets_when_pipeline_runs_then_all_3_dispatched(self, registry, plan):
        graph = compile_plan(plan, registry, handler_registry=STUB_HANDLERS)
        result = graph.invoke({"job_specification": _job_specification(3)})
        assert result["current_index"] == 3
        assert result["has_more_commits"] is False

    def test_given_1_change_set_when_pipeline_runs_then_commit_passed_in_result(
        self, registry, plan
    ):
        graph = compile_plan(plan, registry, handler_registry=STUB_HANDLERS)
        result = graph.invoke({"job_specification": _job_specification(1)})
        assert result["commit_passed"] is True

    def test_given_pipeline_runs_then_job_fields_preserved(self, registry, plan):
        graph = compile_plan(plan, registry, handler_registry=STUB_HANDLERS)
        result = graph.invoke({"job_specification": _job_specification(1)})
        assert result["objective"] == "Add user authentication"
        assert result["constraints"] == ["Must use OAuth2"]
