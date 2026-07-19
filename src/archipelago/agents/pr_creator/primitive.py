"""PR Creator AgentAction declaration."""

from __future__ import annotations

from pathlib import Path

from agent_foundry.constructs import AgentAction, ContainerReusePolicy
from agent_foundry.orchestration import run_agent_in_container
from archetype.templating import resolve

from archipelago.agents._container import agent_container_config
from archipelago.agents.models import PrCreatorInput, PrCreatorOutput
from archipelago.config import PR_CREATOR_MODEL
from archipelago.constants import GID_CODEBASE, GID_DOCUMENTS

_TEMPLATE_PATH = Path(__file__).parent / "instructions_template.md"


def pr_creator_prompt_builder(state: PrCreatorInput) -> str:
    return (
        f"The workspace is mounted at {state.workspace_handle.root}. "
        "Follow your instructions to push the feature branch and open a pull request."
    )


def pr_creator_instructions_provider(state: PrCreatorInput) -> str:
    template_text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return resolve(
        template_text,
        feature=state.feature_definition,
        codebase_source=state.codebase_source,
        workspace_handle=state.workspace_handle,
        design_document_path=state.design_document_path,
    )


pr_creator = AgentAction[PrCreatorInput, PrCreatorOutput](
    name="pr_creator",
    prompt_builder=pr_creator_prompt_builder,
    instructions_provider=pr_creator_instructions_provider,
    executor=run_agent_in_container,  # type: ignore[arg-type]
    reuse_policy=ContainerReusePolicy.REUSE_NEW_SESSION,
    timeout_seconds=1800,
    gids=[GID_DOCUMENTS, GID_CODEBASE],
    skip_permissions=True,
    model=PR_CREATOR_MODEL,
    container_config=agent_container_config(mem_limit_mb=6144),
    cwd="/workspace/codebase",
)
