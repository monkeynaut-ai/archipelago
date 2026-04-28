"""ChangeSetPlanner callables — prompt_builder and instructions_provider.

Mirrors the Designer pattern. The instruction template is loaded from
the bundled markdown file and resolved via archetype.templating.
"""

from __future__ import annotations

from pathlib import Path

from archetype.templating import resolve

from archipelago.agents.change_set_planner.models import ChangeSetPlannerInput
from archipelago.models import ChangeSetsDocument, FeatureDefinition

_TEMPLATE_PATH = Path(__file__).parent / "instructions_template.md"


def change_set_planner_prompt_builder(state: ChangeSetPlannerInput) -> str:
    return (
        f"The workspace is mounted at {state.workspace_handle.root}. "
        f"Follow your instructions to produce the change-sets document."
    )


def change_set_planner_instructions_provider(state: ChangeSetPlannerInput) -> str:
    template_text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return resolve(
        template_text,
        feature=state.feature_definition,
        workspace_handle=state.workspace_handle,
        design_document=state.design_document,
        FeatureDefinition=FeatureDefinition,
        ChangeSetsDocument=ChangeSetsDocument,
    )
