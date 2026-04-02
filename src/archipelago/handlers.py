"""Archipelago handler registry.

The docker-worker agents (UnitTestWriter, CodeWriter, SoftwareReviewer) are
typed agents — the compiler detects them via ``is_typed_agent`` and wraps
them with the connector.  Static config from ``NodeDef.config`` is injected
at construction time via ``resolve_typed_handler``.

The plain handlers (decomposer, dispatcher, evaluator) remain dict-based
legacy functions until the full pipeline is wired through the connector.
"""

from typing import Any

from archipelago.agents.code_writer import CodeWriter
from archipelago.agents.decomposer import decomposer_handler
from archipelago.agents.dispatcher import dispatcher_handler
from archipelago.agents.evaluator import evaluator_handler
from archipelago.agents.software_reviewer import SoftwareReviewer
from archipelago.agents.unit_test_writer import UnitTestWriter

ARCHIPELAGO_HANDLERS: dict[str, Any] = {
    "decompose_job_specification": decomposer_handler,
    "dispatch_commit": dispatcher_handler,
    "evaluate_commit": evaluator_handler,
    "write_unit_tests_from_spec": UnitTestWriter(),
    "code_implement_from_tests": CodeWriter(),
    "software_review": SoftwareReviewer(),
}
