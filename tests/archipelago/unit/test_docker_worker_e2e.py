"""Docker worker end-to-end pipeline tests with stub handlers."""

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from agent_foundry.compiler.compiler import compile_plan
from agent_foundry.observability.tracer import ExecutionTracer
from agent_foundry.planner.wiring_plan import GraphWiringPlan
from agent_foundry.registry.spec import load_role_spec

PRODUCT_ROLES_DIR = Path(__file__).parent.parent.parent.parent / "src" / "archipelago" / "roles"

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
    return graph.invoke({"job_definition": "Build a test product"})


class TestEndToEnd:
    def test_given_valid_input_when_pipeline_runs_then_final_state_has_worker_result(
        self, final_state
    ):
        assert "worker_result" in final_state
        assert final_state["worker_result"]["status"] == "completed"

    def test_given_valid_input_when_pipeline_runs_then_worker_result_validates(self, final_state):
        spec = load_role_spec(PRODUCT_ROLES_DIR / "coding_implement_feature_from_spec.yaml")
        jsonschema.validate(final_state["worker_result"], spec.outputs_schema)

    def test_given_pipeline_with_tracer_when_run_then_docker_worker_span_emitted(
        self, registry, plan
    ):
        tracer = ExecutionTracer()
        node_caps = {n.id: n.role for n in plan.nodes}

        def _make_traced(node_id, original):
            def handler(state):
                span = tracer.start_span(node_id, node_caps[node_id])
                result = original(state)
                tracer.end_span(span, "ok")
                return result

            return handler

        traced = {cap: _make_traced(nid, STUB_HANDLERS[cap]) for nid, cap in node_caps.items()}
        graph = compile_plan(plan, registry, handler_registry=traced)
        graph.invoke({"job_definition": "test"})

        spans = tracer.export()
        worker_spans = [
            s
            for s in spans
            if s["role"] in ("write_unit_tests_from_spec", "code_implement_from_tests")
        ]
        assert len(worker_spans) == 2
        assert all(s["status"] == "ok" for s in worker_spans)

    def test_given_pipeline_with_tracer_when_run_then_all_2_spans_emitted(self, registry, plan):
        tracer = ExecutionTracer()
        node_caps = {n.id: n.role for n in plan.nodes}

        def _make_traced(node_id, original):
            def handler(state):
                span = tracer.start_span(node_id, node_caps[node_id])
                result = original(state)
                tracer.end_span(span, "ok")
                return result

            return handler

        traced = {cap: _make_traced(nid, STUB_HANDLERS[cap]) for nid, cap in node_caps.items()}
        graph = compile_plan(plan, registry, handler_registry=traced)
        graph.invoke({"job_definition": "test"})

        assert len(tracer.export()) == 2
