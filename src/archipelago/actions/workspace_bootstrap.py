"""Workspace-bootstrap function action.

Provisions a Docker volume seeded with a cloned codebase (working tree
read-only, .git/ writable for git tooling) and a rendered
feature-definition file (read-only). The writable documents directory
is owned by the designer container's UID so the agent can write
design.md.

The caller (run_design_pipeline) supplies the volume name so the
container registry and bootstrap agree on it. bootstrap_fn does not
generate names itself.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from archipelago.models import CodebaseSource, FeatureDefinition


class WorkspaceHandle(BaseModel):
    """Pointer to the provisioned workspace volume."""

    volume_name: str
    root: str
    documents_path: str
    codebase_path: str
    feature_definition_path: str
    codebase_source_ref: str
    codebase_resolved_sha: str


class BootstrapInput(BaseModel):
    # Explicit extra="ignore" documents that the compiler passes the full
    # pipeline state into model_validate; extra fields (workspace_handle,
    # designer_output) must be silently dropped.
    model_config = ConfigDict(extra="ignore")

    feature_definition: FeatureDefinition
    codebase_source: CodebaseSource
    volume_name: str


class BootstrapOutput(BaseModel):
    workspace_handle: WorkspaceHandle
