"""Agent state models for all Archipelago agents."""

from __future__ import annotations

from typing import Annotated

from agent_foundry.models.markers import AgentFilePath
from pydantic import BaseModel

from archipelago.actions import WorkspaceHandle
from archipelago.models import (
    ChangeSetRef,
    CodebaseSource,
    DesignReviewVerdict,
    FeatureDefinition,
)


class AgentInputBase(BaseModel):
    workspace_handle: WorkspaceHandle


class DesignerInput(AgentInputBase):
    feature_definition: FeatureDefinition
    # Present on revision passes (populated by the prior Retry iteration); None
    # on the first pass. Drives designer_prompt_builder's revise-vs-fresh branch.
    design_review_verdict: DesignReviewVerdict | None = None
    design_document_path: str | None = None


class DesignerOutput(BaseModel):
    investigation_summary_path: Annotated[str, AgentFilePath()]
    design_document_path: Annotated[str, AgentFilePath()]


class ChangeSetPlannerInput(AgentInputBase):
    design_document_path: str
    feature_definition: FeatureDefinition


class ChangeSetPlannerOutput(BaseModel):
    change_sets_document_path: Annotated[str, AgentFilePath()]


class TDDPlannerInput(AgentInputBase):
    design_document_path: str
    feature_definition: FeatureDefinition
    current_change_set: ChangeSetRef
    change_set_workspace_path: str
    tdd_plan_path: str


class TDDPlannerOutput(BaseModel):
    tdd_plan_path: Annotated[str, AgentFilePath()]


class TesterInput(AgentInputBase):
    pass


class TesterOutput(BaseModel):
    pass


class ImplementerInput(AgentInputBase):
    pass


class ImplementerOutput(BaseModel):
    pass


class PrCreatorInput(AgentInputBase):
    feature_definition: FeatureDefinition
    codebase_source: CodebaseSource
    design_document_path: str | None = None


class PrCreatorOutput(BaseModel):
    pr_url: str | None = None
