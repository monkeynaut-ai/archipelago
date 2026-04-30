"""ChangeSetPlanner state models.

Input: workspace handle (for the target write path via the typed
`change_sets_document_path` property) + the upstream `design_document`
path (Designer's flat output field) + parsed feature definition (for
instruction-template injection).

Output: a single `change_sets_document` path — `Annotated[str,
AgentFilePath()]` triggers the container executor's existence check
on success. AgentAction outputs are merged flat into accumulated
state, so consumers downstream pick up `change_sets_document` as a
top-level field.
"""

from __future__ import annotations

from typing import Annotated

from agent_foundry.models.markers import AgentFilePath
from pydantic import BaseModel

from archipelago.actions import WorkspaceHandle
from archipelago.models import FeatureDefinition


class ChangeSetPlannerInput(BaseModel):
    workspace_handle: WorkspaceHandle
    design_document: str
    feature_definition: FeatureDefinition


class ChangeSetPlannerOutput(BaseModel):
    change_sets_document: Annotated[str, AgentFilePath()]
