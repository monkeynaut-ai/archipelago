"""Workspace-bootstrap function action.

Provisions a Docker volume seeded with a cloned codebase (working tree
read-only, .git/ writable for git tooling) and a rendered
feature-definition file (read-only). The writable documents directory
is owned by root:GID_DOCUMENTS (mode 775) so any agent holding that
supplementary GID can write there.

The caller supplies the volume name so the container registry and
bootstrap agree on it. bootstrap_fn does not generate names itself.
"""

from __future__ import annotations

import contextlib
import os
import re

import docker
from agent_foundry.primitives.models import FunctionAction
from archetype.markdown import render_instance
from pydantic import BaseModel

from archipelago.actions import workspace_ops as _ops
from archipelago.constants import (
    CHANGE_SETS_DIR_NAME,
    FEATURE_DEFINITION_FILENAME,
    LESSONS_LEARNED_FILENAME,
    WORKSPACE_CODEBASE_PATH,
    WORKSPACE_DOCUMENTS_PATH,
    WORKSPACE_ROOT,
)
from archipelago.models import CodebaseSource, FeatureDefinition

_BRANCH_UNSAFE = re.compile(r"[^a-z0-9-]+")


def _slugify_branch(title: str) -> str:
    """Lowercase, hyphen-separated, alphanumerics-only branch slug."""
    cleaned = _BRANCH_UNSAFE.sub("-", title.lower()).strip("-")
    return cleaned or "unnamed"


def _unique_branch_name(title: str, remote_branches: set[str]) -> str:
    """Return a branch name derived from title that is not in remote_branches.

    First try: the full slug truncated to 24 chars.
    On collision: shorten base to 21 chars and append -1, -2, … up to -99.
    """
    slug = _slugify_branch(title)
    candidate = slug[:24].rstrip("-")
    if candidate not in remote_branches:
        return candidate
    base = slug[:21].rstrip("-")
    for i in range(1, 100):
        candidate = f"{base}-{i}"
        if candidate not in remote_branches:
            return candidate
    raise RuntimeError(f"No unique branch name found for title {title!r}")


class WorkspaceHandle(BaseModel):
    """Pointer to the provisioned workspace volume.

    Computed properties (`design_document_path`, `change_sets_document_path`,
    `change_sets_dir`) expose well-known document and directory paths
    derived from `documents_path`. New agents should read these via the
    typed property rather than hardcoding the path string in instruction
    templates (path-threading principle).
    """

    volume_name: str
    root: str
    documents_path: str
    codebase_path: str
    feature_definition_path: str
    codebase_source_ref: str
    codebase_resolved_sha: str

    @property
    def design_document_path(self) -> str:
        return f"{self.documents_path}/design.md"

    @property
    def change_sets_document_path(self) -> str:
        return f"{self.documents_path}/{CHANGE_SETS_DIR_NAME}.md"

    @property
    def change_sets_dir(self) -> str:
        return f"{self.documents_path}/{CHANGE_SETS_DIR_NAME}"

    @property
    def investigation_document_path(self) -> str:
        return f"{self.documents_path}/investigation.md"

    @property
    def lessons_learned_path(self) -> str:
        return f"{self.documents_path}/{LESSONS_LEARNED_FILENAME}"

    def tdd_plan_path(self, change_set_slug: str) -> str:
        return f"{self.change_sets_dir}/{change_set_slug}/tdd_plan.md"

    @property
    def current_task_path(self) -> str:
        return f"{self.documents_path}/current-task.md"


class BootstrapInput(BaseModel):
    feature_definition: FeatureDefinition
    codebase_source: CodebaseSource
    volume_name: str


class BootstrapOutput(BaseModel):
    workspace_handle: WorkspaceHandle


def bootstrap_fn(state: BootstrapInput) -> BootstrapOutput:
    """Provision the workspace volume.

    Pre-pulls both throwaway-container images before touching any state,
    so a broken network fails fast and doesn't leave an orphan volume.
    The volume name is supplied by the caller — bootstrap_fn never
    generates names.
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
            codebase_path=WORKSPACE_CODEBASE_PATH,
            github_token=github_token,
        )

        # 3b. Determine a unique feature branch name from the feature title.
        remote_branches = _ops.list_remote_branches(
            client,
            volume_name=state.volume_name,
            codebase_path=WORKSPACE_CODEBASE_PATH,
        )
        branch_name = _unique_branch_name(
            state.feature_definition.title,
            remote_branches,
        )

        # 3c. Create and check out the feature branch in the cloned workspace.
        _ops.create_and_checkout_branch(
            client,
            volume_name=state.volume_name,
            codebase_path=WORKSPACE_CODEBASE_PATH,
            branch_name=branch_name,
        )

        # 4. Set codebase ownership: GID_CODEBASE owns the bulk, GID_TESTS
        # owns tests/ (if present). Mode 775 throughout, .git/ preserved.
        # Implementer agents hold GID_CODEBASE (write to source), tester
        # agents hold GID_TESTS (write to tests only); both get read access
        # to the rest via the "other" rx bits.
        _ops.prepare_codebase_tree(
            client,
            volume_name=state.volume_name,
            codebase_path=WORKSPACE_CODEBASE_PATH,
        )

        # 5. Ensure documents dir exists and is writable to the designer UID.
        _ops.prepare_documents_dir(
            client, volume_name=state.volume_name, path=WORKSPACE_DOCUMENTS_PATH
        )

        # 5b. Create change-sets/ subdirectory under documents/. Per-CS
        # subdirs (created later by prepare_change_set_workspace inside
        # the outer loop) inherit the same agent-writable ownership.
        _ops.make_change_sets_dir(
            client,
            volume_name=state.volume_name,
            path=f"{WORKSPACE_DOCUMENTS_PATH}/{CHANGE_SETS_DIR_NAME}",
        )

        # 6. Stage the feature definition file (locked to 444 once written).
        _ops.write_file(
            client,
            volume_name=state.volume_name,
            path=f"{WORKSPACE_DOCUMENTS_PATH}/{FEATURE_DEFINITION_FILENAME}",
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
        root=WORKSPACE_ROOT,
        documents_path=WORKSPACE_DOCUMENTS_PATH,
        codebase_path=WORKSPACE_CODEBASE_PATH,
        feature_definition_path=f"{WORKSPACE_DOCUMENTS_PATH}/{FEATURE_DEFINITION_FILENAME}",
        codebase_source_ref=state.codebase_source.ref,
        codebase_resolved_sha=resolved_sha,
    )
    return BootstrapOutput(workspace_handle=handle)


workspace_bootstrap = FunctionAction[BootstrapInput, BootstrapOutput](
    function=bootstrap_fn,
)
