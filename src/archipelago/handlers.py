"""Archipelago handler registry."""

from typing import Any

from archipelago.agents.decomposer import decomposer_handler
from archipelago.agents.dispatcher import dispatcher_handler
from archipelago.agents.evaluator import evaluator_handler
from archipelago.docker_worker.handler import docker_worker_handler

ARCHIPELAGO_HANDLERS: dict[str, Any] = {
    "decompose_job_definition": decomposer_handler,
    "dispatch_commit": dispatcher_handler,
    "evaluate_commit": evaluator_handler,
    "write_unit_tests_from_spec": docker_worker_handler,
    "code_implement_from_tests": docker_worker_handler,
}
