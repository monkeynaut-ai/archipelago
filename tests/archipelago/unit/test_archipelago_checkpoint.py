"""Archipelago checkpoint/resume — compilation tests."""

import json
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


def _stub_docker_worker(state: dict[str, Any], node_config: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        **state,
        "worker_result": {
            "result_summary": "completed",
            "workspace_ref": "/workspace",
            "patches": [],
            "evidence": [],
            "status": "completed",
        },
    }


STUB_HANDLERS = {
    "decompose_job_definition": decomposer_handler,
    "dispatch_commit": dispatcher_handler,
    "evaluate_commit": evaluator_handler,
    "write_unit_tests_from_spec": _stub_docker_worker,
    "code_implement_from_tests": _stub_docker_worker,
}


@pytest.fixture
def base_plan_data():
    return json.loads(PLAN_PATH.read_text())


class TestCheckpointCompilation:
    def test_given_plan_with_persistence_when_compiled_then_graph_has_checkpointer(
        self, registry, base_plan_data
    ):
        base_plan_data["persistence"] = {"backend": "memory", "thread_id": "test-1"}
        plan = GraphWiringPlan(**base_plan_data)
        graph = compile_plan(plan, registry, handler_registry=STUB_HANDLERS)
        assert graph.checkpointer is not None

    def test_given_plan_without_persistence_when_compiled_then_no_checkpointer(
        self, registry, base_plan_data
    ):
        plan = GraphWiringPlan(**base_plan_data)
        graph = compile_plan(plan, registry, handler_registry=STUB_HANDLERS)
        assert graph.checkpointer is None


class TestPipelineExecution:
    def test_given_pipeline_when_invoked_then_produces_result(
        self, registry, base_plan_data
    ):
        plan = GraphWiringPlan(**base_plan_data)
        graph = compile_plan(plan, registry, handler_registry=STUB_HANDLERS)
        job_def = {"objective": "test", "repo_url": "https://github.com/org/repo", "commits": [{"title": "c1"}]}
        result = graph.invoke({"job_definition": job_def})
        assert result["has_more_commits"] is False
        assert result["commit_passed"] is True
