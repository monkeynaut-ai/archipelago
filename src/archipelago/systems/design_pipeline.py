"""Design pipeline — Phase 2's runnable system.

Given a feature definition and a target codebase, compose workspace
bootstrap + Designer into a Sequence and run it to produce a design
document.
"""

from __future__ import annotations

import re
import time

from pydantic import BaseModel

from archipelago.actions import WorkspaceHandle
from archipelago.agents.designer import DesignerOutput
from archipelago.models import CodebaseSource, FeatureDefinition

# Base image for AgentAction containers. Hardcoded for Phase 2; sourced
# from Phase 3's published image once that ships. If the tag needs to
# change, update here and redeploy.
BASE_IMAGE_TAG = "agent-worker:latest"


_VOLUME_NAME_UNSAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def generate_volume_name(feature_slug: str) -> str:
    """Produce a unique Docker-volume name for one pipeline run.

    Form: `archipelago-ws-{sanitized-slug}-{unix_nanoseconds}`. The
    nanosecond suffix makes same-second collisions astronomically rare
    (no observed collisions in practice at this resolution). The caller
    (run_design_pipeline) passes this name into both the container
    registry and bootstrap_fn so they agree on it.
    """
    sanitized = _VOLUME_NAME_UNSAFE.sub("-", feature_slug).strip("-") or "unnamed"
    return f"archipelago-ws-{sanitized}-{time.time_ns()}"


class DesignPipelineState(BaseModel):
    """State that flows through the design pipeline Sequence.

    `feature_definition`, `codebase_source`, and `volume_name` are
    populated at pipeline entry. `workspace_handle` is filled by
    `workspace_bootstrap`. `designer_output` is filled by `designer`.
    """

    feature_definition: FeatureDefinition
    codebase_source: CodebaseSource
    volume_name: str
    workspace_handle: WorkspaceHandle | None = None
    designer_output: DesignerOutput | None = None
