"""Tester AgentAction declaration."""

from __future__ import annotations

from pathlib import Path

from agent_foundry.agents.lifecycle import ContainerConfig
from agent_foundry.orchestration.container_executor import run_agent_in_container
from agent_foundry.primitives.models import AgentAction, ContainerReusePolicy
from archetype.templating import resolve

from archipelago.agents.models import TesterInput, TesterOutput
from archipelago.config import TESTER_MODEL
from archipelago.constants import GID_DOCUMENTS, GID_TESTS
from archipelago.models import TDDPlan

_TEMPLATE_PATH = Path(__file__).parent / "instructions_template.md"


def tester_prompt_builder(state: TesterInput) -> str:
    return (
        f"The workspace is mounted at {state.workspace_handle.root}. "
        "Follow your instructions to write the failing tests."
    )


def tester_instructions_provider(state: TesterInput) -> str:
    template_text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return resolve(
        template_text,
        feature=state.feature_definition,
        design_document_path=state.design_document_path,
        current_change_set=state.current_change_set,
        tdd_plan_path=state.tdd_plan_path,
        TDDPlan=TDDPlan,
    )


tester = AgentAction[TesterInput, TesterOutput](
    name="tester",
    prompt_builder=tester_prompt_builder,
    instructions_provider=tester_instructions_provider,
    executor=run_agent_in_container,  # type: ignore[arg-type]
    reuse_policy=ContainerReusePolicy.REUSE_NEW_SESSION,
    timeout_seconds=1800,
    gids=[GID_DOCUMENTS, GID_TESTS],
    skip_permissions=True,
    model=TESTER_MODEL,
    container_config=ContainerConfig(mem_limit_mb=3072),
    cwd="/workspace/codebase",
)
