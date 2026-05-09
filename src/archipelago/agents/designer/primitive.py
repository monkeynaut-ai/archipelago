"""Designer AgentAction declaration.

Container config per design §6.1:
- /workspace visible (codebase read-only + documents writable via chmod).
- Only /workspace/documents/ writable.
- REUSE_NEW_SESSION reuse policy.
- 30-minute timeout (declaration only — not enforced by the
  orchestrator in Phase 2; Designer can run longer in practice).
"""

from __future__ import annotations

from pathlib import Path

from agent_foundry.orchestration.container_executor import run_agent_in_container
from agent_foundry.primitives.models import AgentAction, ContainerReusePolicy
from archetype.templating import resolve

from archipelago.agents.models import DesignerInput, DesignerOutput
from archipelago.config import DESIGNER_EFFORT, DESIGNER_MODEL
from archipelago.constants import GID_DOCUMENTS
from archipelago.models import DesignDocument, FeatureDefinition

_TEMPLATE_PATH = Path(__file__).parent / "instructions_template.md"


def designer_prompt_builder(state: DesignerInput) -> str:
    return (
        f"The workspace is mounted at {state.workspace_handle.root}. "
        f"Follow your instructions to produce the design document."
    )


def designer_instructions_provider(state: DesignerInput) -> str:
    template_text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return resolve(
        template_text,
        feature=state.feature_definition,
        workspace_handle=state.workspace_handle,
        FeatureDefinition=FeatureDefinition,
        DesignDocument=DesignDocument,
    )


designer = AgentAction[DesignerInput, DesignerOutput](
    name="designer",
    prompt_builder=designer_prompt_builder,
    instructions_provider=designer_instructions_provider,
    executor=run_agent_in_container,  # type: ignore[arg-type]  # agent-foundry's executor returns BaseModel; the AgentFilePath marker narrows at runtime.
    reuse_policy=ContainerReusePolicy.REUSE_NEW_SESSION,
    timeout_seconds=1800,
    gids=[GID_DOCUMENTS],
    skip_permissions=True,
    model=DESIGNER_MODEL,
    effort=DESIGNER_EFFORT,
)
