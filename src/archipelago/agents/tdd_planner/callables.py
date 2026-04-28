"""TDDPlanner callables — prompt_builder and instructions_provider."""

from __future__ import annotations

from pathlib import Path

from archetype.templating import resolve

from archipelago.agents.tdd_planner.models import TDDPlannerInput
from archipelago.models import FeatureDefinition, StepsDocument

_TEMPLATE_PATH = Path(__file__).parent / "instructions_template.md"


def tdd_planner_prompt_builder(state: TDDPlannerInput) -> str:
    return (
        f"The workspace is mounted at {state.workspace_handle.root}. "
        f"Plan TDD steps for change set "
        f"'{state.current_change_set.title}'."
    )


def tdd_planner_instructions_provider(state: TDDPlannerInput) -> str:
    template_text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return resolve(
        template_text,
        feature=state.feature_definition,
        workspace_handle=state.workspace_handle,
        designer_output=state.designer_output,
        current_change_set=state.current_change_set,
        change_set_workspace_path=state.change_set_workspace_path,
        steps_document_path=state.steps_document_path,
        FeatureDefinition=FeatureDefinition,
        StepsDocument=StepsDocument,
    )
