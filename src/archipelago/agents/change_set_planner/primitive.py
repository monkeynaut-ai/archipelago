"""ChangeSetPlanner AgentAction declaration.

Container config mirrors Designer:
- /workspace visible.
- /workspace/documents writable.
- REUSE_NEW_SESSION reuse policy.
- 30-minute timeout (declaration only).

Cluster B (slice + order). Reasoning agent — eventual candidate for
API/SDK execution per the Stage 2 roadmap; uses container execution
for now.
"""

from __future__ import annotations

from agent_foundry.orchestration.container_executor import run_agent_in_container
from agent_foundry.primitives.models import AgentAction, ContainerReusePolicy

from archipelago.agents.change_set_planner.callables import (
    change_set_planner_instructions_provider,
    change_set_planner_prompt_builder,
)
from archipelago.agents.change_set_planner.models import (
    ChangeSetPlannerInput,
    ChangeSetPlannerOutput,
)

change_set_planner = AgentAction[ChangeSetPlannerInput, ChangeSetPlannerOutput](
    name="change_set_planner",
    prompt_builder=change_set_planner_prompt_builder,
    instructions_provider=change_set_planner_instructions_provider,
    executor=run_agent_in_container,  # type: ignore[arg-type]
    reuse_policy=ContainerReusePolicy.REUSE_NEW_SESSION,
    timeout_seconds=1800,
    visible_dirs=["/workspace"],
    writable_dirs=["/workspace/documents"],
    skip_permissions=True,
)
