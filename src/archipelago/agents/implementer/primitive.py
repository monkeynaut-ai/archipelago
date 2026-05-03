"""Implementer AgentAction declaration."""

from __future__ import annotations

from pathlib import Path

from agent_foundry.orchestration.container_executor import run_agent_in_container
from agent_foundry.primitives.models import AgentAction, ContainerReusePolicy
from archetype.templating import resolve

from archipelago.agents.models import ImplementerInput, ImplementerOutput
from archipelago.constants import GID_DOCUMENTS
from archipelago.models import FeatureDefinition

_TEMPLATE_PATH = Path(__file__).parent / "instructions_template.md"


def implementer_prompt_builder(state: ImplementerInput) -> str:
    return (
        f"The workspace is mounted at {state.workspace_handle.root}. "
        f"Implement change set '{state.current_change_set.title}' "
        f"following the TDD steps in {state.steps_document_path}."
    )


def implementer_instructions_provider(state: ImplementerInput) -> str:
    template_text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return resolve(
        template_text,
        feature=state.feature_definition,
        workspace_handle=state.workspace_handle,
        design_document=state.design_document,
        current_change_set=state.current_change_set,
        change_set_workspace_path=state.change_set_workspace_path,
        steps_document_path=state.steps_document_path,
        FeatureDefinition=FeatureDefinition,
    )


implementer = AgentAction[ImplementerInput, ImplementerOutput](
    name="implementer",
    prompt_builder=implementer_prompt_builder,
    instructions_provider=implementer_instructions_provider,
    executor=run_agent_in_container,  # type: ignore[arg-type]
    reuse_policy=ContainerReusePolicy.REUSE_NEW_SESSION,
    timeout_seconds=1800,
    gids=[GID_DOCUMENTS],
    skip_permissions=True,
)
