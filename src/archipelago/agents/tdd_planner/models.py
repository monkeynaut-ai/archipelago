"""TDDPlanner state models.

Input: workspace handle + the upstream `design_document` path (flat
field from Designer's output) + the current change set (bound by the
outer Loop's item_key) + paths into the per-CS subdirectory
(computed by prepare_change_set_workspace and threaded as state).

Output: a single `steps_document` path — also flat, merged into
accumulated state for downstream consumers.
"""

from __future__ import annotations

from typing import Annotated

from agent_foundry.models.markers import AgentFilePath
from pydantic import BaseModel

from archipelago.actions import WorkspaceHandle
from archipelago.models import ChangeSetRef, FeatureDefinition


class TDDPlannerInput(BaseModel):
    workspace_handle: WorkspaceHandle
    design_document: str
    feature_definition: FeatureDefinition
    current_change_set: ChangeSetRef
    change_set_workspace_path: str
    steps_document_path: str


class TDDPlannerOutput(BaseModel):
    steps_document: Annotated[str, AgentFilePath()]
