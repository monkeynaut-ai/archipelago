"""Stdout logging FunctionActions for the topography skeleton.

Transient: these print the current change-set / step name so an operator
can see pipeline progression. They retire when Run Summary lands and
structured run-event emission replaces stdout logging.
"""

from __future__ import annotations

from agent_foundry.primitives.models import FunctionAction
from pydantic import BaseModel

from archipelago.models import ChangeSetRef, StepRef


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


class LogChangeSetStepNameInput(BaseModel):
    current_step: StepRef


class LogChangeSetStepNameOutput(BaseModel):
    pass


def log_change_set_step_name_fn(
    state: LogChangeSetStepNameInput,
) -> LogChangeSetStepNameOutput:
    print(
        f"[step] {state.current_step.title} ({state.current_step.slug})",
        flush=True,
    )
    return LogChangeSetStepNameOutput()


log_change_set_step_name = FunctionAction[LogChangeSetStepNameInput, LogChangeSetStepNameOutput](
    function=log_change_set_step_name_fn
)
