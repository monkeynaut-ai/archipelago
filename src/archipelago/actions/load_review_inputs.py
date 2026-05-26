"""Bridge Designer's on-disk artifacts into in-process review state.

Designer writes the design document and investigation summary as files in
the workspace volume. These two FunctionActions load them into typed state
slots the reviewers read: the design parsed as a DesignDocument, the
investigation summary as raw markdown text.
"""

from __future__ import annotations

from agent_foundry.primitives.models import FunctionAction
from pydantic import BaseModel

from archipelago.actions.workspace_bootstrap import WorkspaceHandle
from archipelago.actions.workspace_io import read_markdown, read_workspace_file
from archipelago.models.design_document import DesignDocument


class LoadDesignInput(BaseModel):
    workspace_handle: WorkspaceHandle
    design_document_path: str


class LoadDesignOutput(BaseModel):
    design_document: DesignDocument


def load_design_into_state_fn(state: LoadDesignInput) -> LoadDesignOutput:
    doc = read_markdown(state.workspace_handle, state.design_document_path, DesignDocument)
    return LoadDesignOutput(design_document=doc)


load_design_into_state = FunctionAction[LoadDesignInput, LoadDesignOutput](
    function=load_design_into_state_fn,
    name="load_design_into_state",
)


class LoadInvestigationInput(BaseModel):
    workspace_handle: WorkspaceHandle
    investigation_summary_path: str


class LoadInvestigationOutput(BaseModel):
    investigation_summary_text: str


def load_investigation_into_state_fn(state: LoadInvestigationInput) -> LoadInvestigationOutput:
    text = read_workspace_file(state.workspace_handle, state.investigation_summary_path)
    return LoadInvestigationOutput(investigation_summary_text=text)


load_investigation_into_state = FunctionAction[LoadInvestigationInput, LoadInvestigationOutput](
    function=load_investigation_into_state_fn,
    name="load_investigation_into_state",
)
