"""Archipelago end-to-end pipeline tests with stub handlers and tracing."""

from pathlib import Path
from typing import Any

import pytest

from agent_foundry.compiler.compiler import compile_plan
from agent_foundry.observability.tracer import ExecutionTracer
from agent_foundry.planner.wiring_plan import GraphWiringPlan

PLAN_PATH = (
    Path(__file__).parent.parent.parent.parent / "src" / "archipelago" / "archipelago_system.json"
)


# ── Stub handlers that produce valid artifacts without LLM calls ──


def _stub_docker_worker(state: dict[str, Any]) -> dict[str, Any]:
    return {
        **state,
        "worker_result": {
            "result_summary": "Feature completed",
            "workspace_ref": "ws-test",
            "patches": [],
            "evidence": [],
            "status": "completed",
        },
    }


STUB_HANDLERS = {
    "write_unit_tests_from_spec": _stub_docker_worker,
    "code_implement_from_tests": _stub_docker_worker,
}


@pytest.fixture
def plan():
    import json

    plan_data = json.loads(PLAN_PATH.read_text())
    return GraphWiringPlan(**plan_data)


@pytest.fixture
def final_state(registry, plan):
    graph = compile_plan(plan, registry, handler_registry=STUB_HANDLERS)
    return graph.invoke({"job_definition": "Build a test product"})


class TestEndToEnd:
    def test_given_valid_input_when_pipeline_runs_then_final_state_has_worker_result(
        self, final_state
    ):
        assert "worker_result" in final_state
        assert final_state["worker_result"]["status"] == "completed"

    def test_given_pipeline_with_tracer_when_run_then_2_spans_exported(self, registry, plan):
        tracer = ExecutionTracer()
        node_caps = {n.id: n.role for n in plan.nodes}

        def _make_traced_handler(node_id, original):
            def handler(state):
                span = tracer.start_span(node_id, node_caps[node_id])
                result = original(state)
                tracer.end_span(span, "ok")
                return result

            return handler

        traced_handlers = {
            cap: _make_traced_handler(nid, STUB_HANDLERS[cap]) for nid, cap in node_caps.items()
        }

        graph = compile_plan(plan, registry, handler_registry=traced_handlers)
        graph.invoke({"job_definition": "Build a test product"})

        spans = tracer.export()
        assert len(spans) == 2

    def test_given_pipeline_with_tracer_when_run_then_all_spans_have_ok_status(
        self, registry, plan
    ):
        tracer = ExecutionTracer()
        node_caps = {n.id: n.role for n in plan.nodes}

        def _make_traced_handler(node_id, original):
            def handler(state):
                span = tracer.start_span(node_id, node_caps[node_id])
                result = original(state)
                tracer.end_span(span, "ok")
                return result

            return handler

        traced_handlers = {
            cap: _make_traced_handler(nid, STUB_HANDLERS[cap]) for nid, cap in node_caps.items()
        }

        graph = compile_plan(plan, registry, handler_registry=traced_handlers)
        graph.invoke({"job_definition": "Build a test product"})

        spans = tracer.export()
        for span in spans:
            assert span["status"] == "ok"
