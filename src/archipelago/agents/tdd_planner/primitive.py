"""TDDPlanner AgentAction declaration.

Cluster C (verify + execute rigor). Reasoning agent — eventual
candidate for API/SDK execution per the Stage 2 roadmap; uses
container execution for now.
"""

from __future__ import annotations

from agent_foundry.orchestration.container_executor import run_agent_in_container
from agent_foundry.primitives.models import AgentAction, ContainerReusePolicy

from archipelago.agents.tdd_planner.callables import (
    tdd_planner_instructions_provider,
    tdd_planner_prompt_builder,
)
from archipelago.agents.tdd_planner.models import TDDPlannerInput, TDDPlannerOutput

tdd_planner = AgentAction[TDDPlannerInput, TDDPlannerOutput](
    name="tdd_planner",
    prompt_builder=tdd_planner_prompt_builder,
    instructions_provider=tdd_planner_instructions_provider,
    executor=run_agent_in_container,  # type: ignore[arg-type]
    reuse_policy=ContainerReusePolicy.REUSE_NEW_SESSION,
    timeout_seconds=1800,
    visible_dirs=["/workspace"],
    writable_dirs=["/workspace/documents"],
    skip_permissions=True,
)
