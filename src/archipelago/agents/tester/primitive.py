"""Tester AgentAction declaration."""

from __future__ import annotations

from pathlib import Path

from agent_foundry.orchestration.container_executor import run_agent_in_container
from agent_foundry.primitives.models import AgentAction, ContainerReusePolicy
from archetype.templating import resolve

from archipelago.agents.models import TesterInput, TesterOutput
from archipelago.constants import GID_DOCUMENTS
from archipelago.models import FeatureDefinition

_TEMPLATE_PATH = Path(__file__).parent / "instructions_template.md"


def tester_prompt_builder(state: TesterInput) -> str:
    return (
        f"The workspace is mounted at {state.workspace_handle.root}. "
        f"Run the test suite for change set '{state.current_change_set.title}' "
        f"following the steps in {state.steps_document_path}."
    )


def tester_instructions_provider(state: TesterInput) -> str:
    template_text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return resolve(
        template_text,
        feature=state.feature_definition,
        workspace_handle=state.workspace_handle,
        current_change_set=state.current_change_set,
        change_set_workspace_path=state.change_set_workspace_path,
        steps_document_path=state.steps_document_path,
        FeatureDefinition=FeatureDefinition,
    )


tester = AgentAction[TesterInput, TesterOutput](
    name="tester",
    prompt_builder=tester_prompt_builder,
    instructions_provider=tester_instructions_provider,
    executor=run_agent_in_container,  # type: ignore[arg-type]
    reuse_policy=ContainerReusePolicy.REUSE_NEW_SESSION,
    timeout_seconds=1800,
    gids=[GID_DOCUMENTS],
    skip_permissions=True,
)
