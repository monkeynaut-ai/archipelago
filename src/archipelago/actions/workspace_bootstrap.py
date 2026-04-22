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

import contextlib
import os

import docker
from agent_foundry.primitives.models import FunctionAction
from archetype.markdown import render_instance
from pydantic import BaseModel, ConfigDict

from archipelago.actions import _workspace_ops as _ops
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


def bootstrap_fn(state: BootstrapInput) -> BootstrapOutput:
    """Provision the workspace volume.

    Pre-pulls both throwaway-container images before touching any state,
    so a broken network fails fast and doesn't leave an orphan volume.
    The volume name is supplied by the caller (run_design_pipeline) —
    bootstrap_fn never generates names.
    """
    client = docker.from_env()
    github_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

    # 1. Pre-pull images. Fail fast before creating any state.
    _ops.pull_image(client, _ops.GIT_IMAGE)
    _ops.pull_image(client, _ops.ALPINE_IMAGE)

    # 2. Create the volume with the caller-supplied name.
    _ops.create_volume(client, state.volume_name)

    # Steps 3-6 are the critical section: any failure past this point
    # would leave an orphan volume, so we remove it on any exception
    # before re-raising.
    try:
        # 3. Clone, checkout ref, resolve SHA.
        resolved_sha = _ops.clone_and_resolve_ref(
            client,
            volume_name=state.volume_name,
            repo_url=state.codebase_source.repo_url,
            ref=state.codebase_source.ref,
            github_token=github_token,
        )

        # 4. Lock working tree, preserve .git/ writable.
        _ops.chmod_tree_excluding_git(
            client,
            volume_name=state.volume_name,
            path="/workspace/codebase",
            mode="555",
        )

        # 5. Ensure documents dir exists and is writable to the designer UID.
        _ops.prepare_documents_dir(client, volume_name=state.volume_name)

        # 6. Stage the feature definition file (locked to 444 once written).
        _ops.write_file(
            client,
            volume_name=state.volume_name,
            path="/workspace/documents/feature_definition.md",
            content=render_instance(state.feature_definition),
            mode="444",
        )
    except Exception:
        # Partial failure — remove the volume so we don't accumulate orphans.
        # Swallow cleanup errors; the original exception is what the caller
        # needs to see.
        with contextlib.suppress(Exception):
            client.volumes.get(state.volume_name).remove(force=True)
        raise

    handle = WorkspaceHandle(
        volume_name=state.volume_name,
        root="/workspace",
        documents_path="/workspace/documents",
        codebase_path="/workspace/codebase",
        feature_definition_path="/workspace/documents/feature_definition.md",
        codebase_source_ref=state.codebase_source.ref,
        codebase_resolved_sha=resolved_sha,
    )
    return BootstrapOutput(workspace_handle=handle)


workspace_bootstrap = FunctionAction[BootstrapInput, BootstrapOutput](
    function=bootstrap_fn,
)
