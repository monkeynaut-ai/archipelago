"""Designer AgentAction declaration.

Container config per design §6.1:
- /workspace visible (codebase read-only + documents writable via chmod).
- Only /workspace/documents/ writable.
- REUSE_NEW_SESSION reuse policy.
- 30-minute timeout (declaration only — not enforced by the
  orchestrator in Phase 2; Designer can run longer in practice).
"""

from __future__ import annotations

from agent_foundry.orchestration.container_executor import run_agent_in_container
from agent_foundry.primitives.models import AgentAction, ContainerReusePolicy

from archipelago.agents.designer.callables import (
    designer_instructions_provider,
    designer_prompt_builder,
)
from archipelago.agents.models import DesignerInput, DesignerOutput
from archipelago.constants import GID_DOCUMENTS

designer = AgentAction[DesignerInput, DesignerOutput](
    name="designer",
    prompt_builder=designer_prompt_builder,
    instructions_provider=designer_instructions_provider,
    executor=run_agent_in_container,  # type: ignore[arg-type]  # agent-foundry's executor returns BaseModel; the AgentFilePath marker narrows at runtime.
    reuse_policy=ContainerReusePolicy.REUSE_NEW_SESSION,
    timeout_seconds=1800,
    gids=[GID_DOCUMENTS],
    skip_permissions=True,
)
