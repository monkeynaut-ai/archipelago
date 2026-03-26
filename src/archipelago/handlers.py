"""Archipelago handler registry."""

from typing import Any

from archipelago.agents.code_writer import CodeWriter
from archipelago.agents.decomposer import decomposer_handler
from archipelago.agents.dispatcher import dispatcher_handler
from archipelago.agents.evaluator import evaluator_handler
from archipelago.agents.software_reviewer import SoftwareReviewer
from archipelago.agents.unit_test_writer import UnitTestWriter

ARCHIPELAGO_HANDLERS: dict[str, Any] = {
    "decompose_job_definition": decomposer_handler,
    "dispatch_commit": dispatcher_handler,
    "evaluate_commit": evaluator_handler,
    "write_unit_tests_from_spec": UnitTestWriter(),
    "code_implement_from_tests": CodeWriter(),
    "software_review": SoftwareReviewer(),
}
