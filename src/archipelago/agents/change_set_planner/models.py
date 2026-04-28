"""ChangeSetPlanner state models.

Input: workspace handle (for the target write path via the typed
`change_sets_document_path` property) + designer output (for the
upstream design.md path) + parsed feature definition (for instruction-
template injection).

Output: an envelope pointing at the change-sets document path the
agent wrote. `Annotated[str, AgentFilePath()]` triggers the container
executor's existence check on success.
"""

from __future__ import annotations

from typing import Annotated

from agent_foundry.models.markers import AgentFilePath
from pydantic import BaseModel, ConfigDict

from archipelago.actions import WorkspaceHandle
from archipelago.agents.designer import DesignerOutput
from archipelago.models import FeatureDefinition


class ChangeSetPlannerInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    workspace_handle: WorkspaceHandle
    designer_output: DesignerOutput
    feature_definition: FeatureDefinition


class ChangeSetPlannerOutput(BaseModel):
    change_sets_document: Annotated[str, AgentFilePath()]
