"""Designer agent state models.

Input: workspace handle (paths, volume, ref/SHA) + parsed
FeatureDefinition (inlined into instructions via Jinja).

Output: a single envelope pointing at the design document's path in
the workspace. `Annotated[str, AgentFilePath()]` causes the container
executor's file-verification machinery to check existence + size bounds
when the agent emits success.
"""

from __future__ import annotations

from typing import Annotated

from agent_foundry.models.markers import AgentFilePath
from pydantic import BaseModel, ConfigDict

from archipelago.actions import WorkspaceHandle
from archipelago.models import FeatureDefinition


class DesignerInput(BaseModel):
    # Explicit extra="ignore" — the compiler passes the full pipeline
    # state; extra fields must be dropped.
    model_config = ConfigDict(extra="ignore")

    workspace_handle: WorkspaceHandle
    feature_definition: FeatureDefinition


class DesignerOutput(BaseModel):
    design_document: Annotated[str, AgentFilePath()]
