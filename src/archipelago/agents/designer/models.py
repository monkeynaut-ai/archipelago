"""Designer agent state models.

Input: workspace handle (paths, volume, ref/SHA) + parsed
FeatureDefinition (the feature title is inlined into instructions via
Jinja; the agent reads the full feature definition from the workspace).

Output: an envelope pointing at the agent's two artifact paths in the
workspace — the investigation summary written before drafting, and the
final design document. Both fields use `Annotated[str, AgentFilePath()]`
so the container executor's file-verification machinery checks existence
and size bounds when the agent emits success — runs that skip the
investigation checkpoint will fail verification rather than silently
shipping a no-investigation design.
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
    investigation_summary: Annotated[str, AgentFilePath()]
    design_document: Annotated[str, AgentFilePath()]
