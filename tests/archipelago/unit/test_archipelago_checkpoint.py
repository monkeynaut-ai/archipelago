"""Archipelago checkpoint/resume — compilation, breakpoint pause, and resume tests."""

import json
from pathlib import Path
from typing import Any

import pytest

from agent_foundry.compiler.compiler import compile_plan
from agent_foundry.planner.wiring_plan import GraphWiringPlan

PLAN_PATH = (
    Path(__file__).parent.parent.parent.parent / "src" / "archipelago" / "archipelago_system.json"
)


# ── Stub handlers ──

_execution_log: list[str] = []


def _make_logging_handler(node_id: str, state_updates: dict[str, Any]):
    def handler(state: dict[str, Any]) -> dict[str, Any]:
        _execution_log.append(node_id)
        return {**state, **state_updates}

    return handler


STUB_HANDLERS = {
    "write_unit_tests_from_spec": _make_logging_handler(
        "unit_test_writer",
        {
            "worker_result": {
                "result_summary": "Tests written",
                "workspace_ref": "/workspace",
                "patches": [],
                "evidence": [],
                "status": "completed",
            },
            "workspace_volume": "archipelago-test",
        },
    ),
    "code_implement_from_tests": _make_logging_handler(
        "code_writer",
        {
            "worker_result": {
                "result_summary": "Code implemented",
                "workspace_ref": "/workspace",
                "patches": [],
                "evidence": [],
                "status": "completed",
            },
        },
    ),
}


@pytest.fixture
def base_plan_data():
    return json.loads(PLAN_PATH.read_text())


@pytest.fixture(autouse=True)
def clear_execution_log():
    _execution_log.clear()


# ── Commit 1: Checkpoint compilation tests ──


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


# ── Commit 2: Execution tests ──


class TestPipelineExecution:
    def test_given_pipeline_when_invoked_then_both_nodes_execute(
        self, registry, base_plan_data
    ):
        plan = GraphWiringPlan(**base_plan_data)
        graph = compile_plan(plan, registry, handler_registry=STUB_HANDLERS)
        graph.invoke({"job_definition": "test"})

        assert "unit_test_writer" in _execution_log
        assert "code_writer" in _execution_log

    def test_given_pipeline_when_invoked_then_worker_result_present(
        self, registry, base_plan_data
    ):
        plan = GraphWiringPlan(**base_plan_data)
        graph = compile_plan(plan, registry, handler_registry=STUB_HANDLERS)
        result = graph.invoke({"job_definition": "test"})

        assert "worker_result" in result
        assert result["worker_result"]["status"] == "completed"
