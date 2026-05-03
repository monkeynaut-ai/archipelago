"""Agent state models for all Archipelago agents."""

from __future__ import annotations

from typing import Annotated

from agent_foundry.models.markers import AgentFilePath
from pydantic import BaseModel

from archipelago.actions import WorkspaceHandle
from archipelago.models import ChangeSetRef, FeatureDefinition


class AgentInputBase(BaseModel):
    workspace_handle: WorkspaceHandle


class DesignerInput(AgentInputBase):
    feature_definition: FeatureDefinition


class DesignerOutput(BaseModel):
    investigation_summary: Annotated[str, AgentFilePath()]
    design_document: Annotated[str, AgentFilePath()]


class ChangeSetPlannerInput(AgentInputBase):
    design_document: str
    feature_definition: FeatureDefinition


class ChangeSetPlannerOutput(BaseModel):
    change_sets_document: Annotated[str, AgentFilePath()]


class TDDPlannerInput(AgentInputBase):
    design_document: str
    feature_definition: FeatureDefinition
    current_change_set: ChangeSetRef
    change_set_workspace_path: str
    steps_document_path: str


class TDDPlannerOutput(BaseModel):
    steps_document: Annotated[str, AgentFilePath()]


class TesterInput(AgentInputBase):
    pass


class TesterOutput(BaseModel):
    pass


class DeveloperInput(AgentInputBase):
    pass


class DeveloperOutput(BaseModel):
    pass
