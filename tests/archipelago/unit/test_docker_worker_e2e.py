"""Docker worker end-to-end pipeline tests with stub handlers."""

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


def _stub_docker_worker(state: dict[str, Any]) -> dict[str, Any]:
    return {
        **state,
        "worker_result": {
            "result_summary": "Feature completed",
            "workspace_ref": "ws-test",
            "patches": [
                {
                    "pr_id": "pr-1",
                    "branch_name": "feat/t",
                    "files_changed": ["f.py"],
                    "diff_summary": "diff",
                },
            ],
            "evidence": [
                {
                    "commit_id": "abc",
                    "pr_id": "pr-1",
                    "test_commands_run": ["pytest"],
                    "test_output": "ok",
                    "tests_passed": 5,
                    "tests_failed": 0,
                    "all_green": True,
                },
            ],
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
def plan():
    plan_data = json.loads(PLAN_PATH.read_text())
    return GraphWiringPlan(**plan_data)


@pytest.fixture
def final_state(registry, plan):
    graph = compile_plan(plan, registry, handler_registry=STUB_HANDLERS)
    job_def = {"objective": "Build a test product", "repo_url": "https://github.com/org/repo", "commits": [{"title": "c1"}]}
    return graph.invoke({"job_definition": job_def})


class TestEndToEnd:
    def test_given_valid_input_when_pipeline_runs_then_commit_passed(self, final_state):
        assert final_state["commit_passed"] is True

    def test_given_valid_input_when_pipeline_runs_then_all_commits_dispatched(self, final_state):
        assert final_state["has_more_commits"] is False
