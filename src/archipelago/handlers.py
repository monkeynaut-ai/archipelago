"""Archipelago handler registry."""

from typing import Any

from archipelago.docker_worker.handler import docker_worker_handler

ARCHIPELAGO_HANDLERS: dict[str, Any] = {
    "write_unit_tests_from_spec": docker_worker_handler,
    "code_implement_from_tests": docker_worker_handler,
}
