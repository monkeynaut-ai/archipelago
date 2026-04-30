"""Typed read helpers for documents stored in the workspace volume.

Inter-agent data exchange in Archipelago happens through markdown files
in the shared workspace, not through typed messages on the orchestration
boundary — see `docs/archipelago-vision.md` for the rationale. This
module provides the seam the orchestrator uses to *consume* those
files: `read_markdown` wraps "spawn an alpine container, cat the file,
validate against the document model" so callers (e.g., Loop `over`
projections) stay thin and don't import `workspace_ops` or `docker`
directly.
"""

from __future__ import annotations

import docker
from archetype.markdown import MarkdownHeader, validate_markdown

from archipelago.actions import workspace_ops
from archipelago.actions.workspace_bootstrap import WorkspaceHandle


def read_markdown[T: MarkdownHeader](
    workspace_handle: WorkspaceHandle,
    path: str,
    model_type: type[T],
) -> T:
    """Read a markdown file from the workspace volume and validate it
    against `model_type`.

    Spawns a throwaway alpine container that mounts the volume read-only
    and `cat`s the file (delegated to `workspace_ops.read_file`). Returns
    the validated Pydantic instance.

    Raises `MarkdownValidationError` if the file does not parse as
    `model_type`. Propagates `RuntimeError` from `workspace_ops.read_file`
    when the underlying container call fails.
    """
    client = docker.from_env()
    text = workspace_ops.read_file(
        client,
        volume_name=workspace_handle.volume_name,
        path=path,
    )
    return validate_markdown(text, model_type)
