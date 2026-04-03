"""Archipelago checkpoint/resume — compilation tests."""

import json
from pathlib import Path
from typing import Any

import pytest
from agent_foundry.compiler.compiler import compile_plan
from agent_foundry.planner.wiring_plan import GraphWiringPlan

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
            "workspace_ref": "/workspace",
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


def _stub_decomposer(state, node_config=None):
    raw = state["job_specification"]
    return {
        **state,
        "objective": raw["objective"],
        "repo_url": raw.get("repo_url", ""),
        "repo_ref": raw.get("repo_ref", "main"),
        "constraints": raw.get("constraints", []),
        "commit_slices": raw.get("change_sets", []),
        "current_index": 0,
    }


def _stub_dispatcher(state, node_config=None):
    slices = state.get("commit_slices", [])
    idx = state.get("current_index", 0)
    if idx >= len(slices):
        return {**state, "has_more_commits": False}
    return {
        **state,
        "current_task": {
            "objective": state.get("objective", ""),
            "repo_url": state.get("repo_url", ""),
            "repo_ref": state.get("repo_ref", "main"),
            "constraints": state.get("constraints", []),
            **slices[idx],
        },
        "current_index": idx + 1,
        "has_more_commits": True,
    }


STUB_HANDLERS = {
    "decompose_job_specification": _stub_decomposer,
    "dispatch_commit": _stub_dispatcher,
    "evaluate_commit": lambda state, node_config=None: {**state, "commit_passed": True},
    "write_unit_tests_from_spec": _stub_docker_worker,
    "code_implement_from_tests": _stub_docker_worker,
    "software_review": _stub_software_review,
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
    def test_given_pipeline_when_invoked_then_produces_result(self, registry, base_plan_data):
        plan = GraphWiringPlan(**base_plan_data)
        graph = compile_plan(plan, registry, handler_registry=STUB_HANDLERS)
        job_def = {
            "objective": "test",
            "repo_url": "https://github.com/org/repo",
            "change_sets": [{"title": "c1"}],
        }
        result = graph.invoke({"job_specification": job_def})
        assert result["has_more_commits"] is False
        assert result["commit_passed"] is True
