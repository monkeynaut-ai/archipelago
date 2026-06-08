"""TDDPlanner AgentAction declaration.

Cluster C (verify + execute rigor). Reasoning agent — eventual
candidate for API/SDK execution per the Stage 2 roadmap; uses
container execution for now.
"""

from __future__ import annotations

from pathlib import Path

from agent_foundry.agents.lifecycle import ContainerConfig
from agent_foundry.orchestration.container_executor import run_agent_in_container
from agent_foundry.primitives.models import AgentAction, ContainerReusePolicy
from archetype.templating import resolve

from archipelago.agents.models import TDDPlannerInput, TDDPlannerOutput
from archipelago.config import TDD_PLANNER_MODEL
from archipelago.constants import GID_DOCUMENTS
from archipelago.models import FeatureDefinition, TDDPlan

_TEMPLATE_PATH = Path(__file__).parent / "instructions_template.md"


def tdd_planner_prompt_builder(state: TDDPlannerInput) -> str:
    return (
        f"The workspace is mounted at {state.workspace_handle.root}. "
        f"Plan TDD steps for change set "
        f"'{state.current_change_set.heading}'."
    )


def tdd_planner_instructions_provider(state: TDDPlannerInput) -> str:
    template_text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return resolve(
        template_text,
        feature=state.feature_definition,
        workspace_handle=state.workspace_handle,
        design_document_path=state.design_document_path,
        current_change_set=state.current_change_set,
        change_set_workspace_path=state.change_set_workspace_path,
        tdd_plan_path=state.tdd_plan_path,
        FeatureDefinition=FeatureDefinition,
        TDDPlan=TDDPlan,
    )


tdd_planner = AgentAction[TDDPlannerInput, TDDPlannerOutput](
    name="tdd_planner",
    prompt_builder=tdd_planner_prompt_builder,
    instructions_provider=tdd_planner_instructions_provider,
    executor=run_agent_in_container,  # type: ignore[arg-type]
    reuse_policy=ContainerReusePolicy.REUSE_NEW_SESSION,
    timeout_seconds=1800,
    gids=[GID_DOCUMENTS],
    skip_permissions=True,
    model=TDD_PLANNER_MODEL,
    container_config=ContainerConfig(mem_limit_mb=3072),
    cwd="/workspace/codebase",
)
