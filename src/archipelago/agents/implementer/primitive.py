"""Implementer AgentAction declaration."""

from __future__ import annotations

from pathlib import Path

from agent_foundry.agents.lifecycle import ContainerConfig
from agent_foundry.constructs.models import AgentAction, ContainerReusePolicy
from agent_foundry.orchestration.container_executor import run_agent_in_container
from archetype.templating import resolve

from archipelago.agents.models import ImplementerInput, ImplementerOutput
from archipelago.config import IMPLEMENTER_MODEL
from archipelago.constants import GID_CODEBASE, GID_DOCUMENTS
from archipelago.models import TDDPlan

_TEMPLATE_PATH = Path(__file__).parent / "instructions_template.md"


def implementer_prompt_builder(state: ImplementerInput) -> str:
    return (
        f"The workspace is mounted at {state.workspace_handle.root}. "
        "Follow your instructions to implement the change set."
    )


def implementer_instructions_provider(state: ImplementerInput) -> str:
    template_text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return resolve(
        template_text,
        TDDPlan=TDDPlan,
        current_task_path=state.workspace_handle.current_task_path,
        design_document_path=state.workspace_handle.design_document_path,
    )


implementer = AgentAction[ImplementerInput, ImplementerOutput](
    name="implementer",
    prompt_builder=implementer_prompt_builder,
    instructions_provider=implementer_instructions_provider,
    executor=run_agent_in_container,  # type: ignore[arg-type]
    reuse_policy=ContainerReusePolicy.REUSE_NEW_SESSION,
    timeout_seconds=1800,
    gids=[GID_DOCUMENTS, GID_CODEBASE],
    skip_permissions=True,
    model=IMPLEMENTER_MODEL,
    container_config=ContainerConfig(mem_limit_mb=6144),
    cwd="/workspace/codebase",
)
