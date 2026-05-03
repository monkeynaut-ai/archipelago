"""Stdout logging FunctionActions for the topography skeleton.

Transient: these print the current change-set / task name so an operator
can see pipeline progression. They retire when Run Summary lands and
structured run-event emission replaces stdout logging.
"""

from __future__ import annotations

from agent_foundry.primitives.models import FunctionAction
from pydantic import BaseModel

from archipelago.models import ChangeSetRef, Task


class LogChangeSetNameInput(BaseModel):
    current_change_set: ChangeSetRef


class LogChangeSetNameOutput(BaseModel):
    pass


def log_change_set_name_fn(state: LogChangeSetNameInput) -> LogChangeSetNameOutput:
    print(
        f"[change set] {state.current_change_set.title} ({state.current_change_set.slug})",
        flush=True,
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
    print(
        f"[task] {state.current_task.title} ({state.current_task.slug})",
        flush=True,
    )
    return LogTddPlanTaskOutput()


log_tdd_plan_task = FunctionAction[LogTddPlanTaskInput, LogTddPlanTaskOutput](
    function=log_tdd_plan_task_fn
)
