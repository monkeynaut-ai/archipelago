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

from pathlib import Path

from agent_foundry.orchestration.container_executor import run_agent_in_container
from agent_foundry.primitives.models import AgentAction, ContainerReusePolicy
from archetype.templating import resolve

from archipelago.agents.models import ChangeSetPlannerInput, ChangeSetPlannerOutput
from archipelago.config import CHANGE_SET_PLANNER_MODEL
from archipelago.constants import GID_DOCUMENTS
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
        design_document_path=state.design_document_path,
        FeatureDefinition=FeatureDefinition,
        ChangeSetsDocument=ChangeSetsDocument,
    )


change_set_planner = AgentAction[ChangeSetPlannerInput, ChangeSetPlannerOutput](
    name="change_set_planner",
    prompt_builder=change_set_planner_prompt_builder,
    instructions_provider=change_set_planner_instructions_provider,
    executor=run_agent_in_container,  # type: ignore[arg-type]
    reuse_policy=ContainerReusePolicy.REUSE_NEW_SESSION,
    timeout_seconds=1800,
    gids=[GID_DOCUMENTS],
    skip_permissions=True,
    model=CHANGE_SET_PLANNER_MODEL,
)
