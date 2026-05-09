"""Design pipeline — Phase 2's runnable system.

Given a feature definition and a target codebase, compose workspace
bootstrap + Designer into a Sequence and run it to produce a design
document.
"""

from __future__ import annotations

import re
import time

from agent_foundry.orchestration import run_primitive_plan
from agent_foundry.primitives.models import Sequence
from agent_foundry.primitives.plan import PrimitivePlan
from agent_foundry.responders.protocol import static_provider
from agent_foundry.responders.stdin import StdinResponder
from pydantic import BaseModel

from archipelago.actions import WorkspaceHandle, workspace_bootstrap
from archipelago.agents.designer import DesignerOutput, designer
from archipelago.models import CodebaseSource, FeatureDefinition
from archipelago.systems._artifacts import run_artifacts_layout as _run_artifacts_layout
from archipelago.systems._lessons_learned import make_lessons_learned_hook

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


design_pipeline = Sequence[DesignPipelineState, DesignPipelineState](
    steps=[workspace_bootstrap, designer],
)


async def run_design_pipeline(
    *,
    feature_definition: FeatureDefinition,
    codebase_source: CodebaseSource,
) -> DesignPipelineState:
    """Run the design pipeline and return the final state.

    Generates the workspace-volume name once and threads it into both
    the initial state (for bootstrap_fn) and the run_primitive_plan
    workspace_volume kwarg (for the container registry), so both sides
    agree on the name of the Docker volume the designer container will
    mount.
    """
    slug = (
        feature_definition.frontmatter.feature_slug
        if feature_definition.frontmatter is not None
        else "unnamed"
    )
    volume_name = generate_volume_name(slug)
    initial_state = DesignPipelineState(
        feature_definition=feature_definition,
        codebase_source=codebase_source,
        volume_name=volume_name,
    )
    artifacts_parent, run_id = _run_artifacts_layout()
    final = await run_primitive_plan(
        PrimitivePlan(root=design_pipeline),
        initial_state=initial_state,
        artifacts_dir=artifacts_parent,
        run_id=run_id,
        workspace_volume=volume_name,
        base_image_tag=BASE_IMAGE_TAG,
        responder_provider=static_provider(StdinResponder()),
        on_run_ended=[make_lessons_learned_hook(volume_name)],
    )
    assert isinstance(final, DesignPipelineState), (
        f"run_primitive_plan returned {type(final).__name__}, expected DesignPipelineState"
    )
    return final
