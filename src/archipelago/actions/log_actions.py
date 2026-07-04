"""Logging FunctionActions for the topography skeleton.

Transient: these log the current change-set / task name so an operator
can see pipeline progression. They retire when Run Summary lands and
structured run-event emission replaces this logging.
"""

from __future__ import annotations

import structlog
from agent_foundry.constructs import FunctionAction
from pydantic import BaseModel

from archipelago.models import ChangeSetRef, Task

_log = structlog.get_logger(__name__)


class LogChangeSetNameInput(BaseModel):
    current_change_set: ChangeSetRef


class LogChangeSetNameOutput(BaseModel):
    pass


def log_change_set_name_fn(state: LogChangeSetNameInput) -> LogChangeSetNameOutput:
    _log.info(
        "change_set",
        title=state.current_change_set.heading,
        slug=state.current_change_set.slug,
    )
    return LogChangeSetNameOutput()


log_change_set_name = FunctionAction[LogChangeSetNameInput, LogChangeSetNameOutput](
    function=log_change_set_name_fn,
)


class LogTddPlanTaskInput(BaseModel):
    current_task: Task


class LogTddPlanTaskOutput(BaseModel):
    pass


def log_tdd_plan_task_fn(
    state: LogTddPlanTaskInput,
) -> LogTddPlanTaskOutput:
    _log.info(
        "task",
        title=state.current_task.heading,
        slug=state.current_task.slug,
    )
    return LogTddPlanTaskOutput()


log_tdd_plan_task = FunctionAction[LogTddPlanTaskInput, LogTddPlanTaskOutput](
    function=log_tdd_plan_task_fn
)
