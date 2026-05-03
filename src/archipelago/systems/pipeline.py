"""Archipelago v0.1 working-session pipeline (topography skeleton).

Composes the existing design-half primitives (workspace_bootstrap,
designer) with the new working-session primitives (change_set_planner,
prepare_change_set_workspace, log actions, tdd_planner) into a single
nested-loop topology declared in `full_pipeline`.

State scope (per topography design §5):
- `FullPipelineState`           pre-loop fields, top-level Sequence I/O.
- `ChangeSetsLoopState`         outer Loop's I/O.
- `ChangeSetProcessingState`    outer body Sequence's I/O.
- `StepsLoopState`              inner Loop's I/O.
- `StepProcessingState`         inner body Sequence's I/O.

Per-loop scope is the state model — each primitive declares only the
fields it needs; the platform projects via field-level slicing.

`design_pipeline` is preserved (in `archipelago.systems.design_pipeline`)
for design-only smoke runs; this module is independent of it and adds
its own composition.
"""

from __future__ import annotations

from agent_foundry.orchestration import run_primitive_plan
from agent_foundry.primitives.models import Loop, Sequence
from agent_foundry.primitives.plan import PrimitivePlan
from agent_foundry.responders.protocol import static_provider
from agent_foundry.responders.stdin import StdinResponder
from pydantic import BaseModel

from archipelago.actions import (
    WorkspaceHandle,
    log_change_set_name,
    log_change_set_step_name,
    prepare_change_set_workspace,
    read_markdown,
    workspace_bootstrap,
)
from archipelago.agents.change_set_planner import change_set_planner
from archipelago.agents.designer import designer
from archipelago.agents.tdd_planner import tdd_planner
from archipelago.models import (
    ChangeSetRef,
    ChangeSetsDocument,
    CodebaseSource,
    FeatureDefinition,
    StepRef,
    StepsDocument,
)
from archipelago.systems._artifacts import artifacts_dir_for_run as _artifacts_dir_for_run
from archipelago.systems.design_pipeline import (
    BASE_IMAGE_TAG,
    generate_volume_name,
)
from archipelago.telemetry import attach_mlflow_adapter, telemetry_configuration

# ============================================================
# State models
# ============================================================


class FullPipelineState(BaseModel):
    """Top-level pipeline state. Pre-loop fields only; per-iteration
    fields live in the loop-scoped types below.

    AgentAction outputs are merged FLAT into accumulated state (the
    AgentAction compiler returns ``typed.model_dump()``), so this
    model carries each agent's output fields directly rather than
    nesting them under a wrapper. For Designer this means
    ``investigation_summary`` and ``design_document`` (DesignerOutput's
    fields) appear here as top-level optional strings; same shape for
    Change Set Planner's ``change_sets_document``.
    """

    feature_definition: FeatureDefinition
    codebase_source: CodebaseSource
    volume_name: str
    workspace_handle: WorkspaceHandle | None = None
    # Designer's flat output:
    investigation_summary: str | None = None
    design_document_path: str | None = None
    # Change Set Planner's flat output:
    change_sets_document: str | None = None


class ChangeSetsLoopState(BaseModel):
    """Outer Loop's view: fields the Loop reads (for `over`) plus
    inheritable context for the body."""

    change_sets_document: str
    workspace_handle: WorkspaceHandle
    design_document_path: str
    feature_definition: FeatureDefinition


class ChangeSetProcessingState(BaseModel):
    """Outer body Sequence's view: bound iteration item + inherited
    context + slots for per-iteration writes."""

    # Bound by outer Loop's item_key:
    current_change_set: ChangeSetRef

    # Inherited from ChangeSetsLoopState:
    workspace_handle: WorkspaceHandle
    design_document_path: str
    feature_definition: FeatureDefinition

    # Written by body steps:
    change_set_workspace_path: str | None = None
    steps_document_path: str | None = None
    steps_document: str | None = None  # TDD Planner's flat output


class StepsLoopState(BaseModel):
    """Inner Loop's view. Includes `workspace_handle` so the `over`
    callable can read steps.md from the volume."""

    steps_document: str
    change_set_workspace_path: str
    workspace_handle: WorkspaceHandle


class StepProcessingState(BaseModel):
    """Inner body Sequence's view. Future iterations will widen this as
    Test Agent / Implementer / CommitAction need design context, current
    change set, etc."""

    current_step: StepRef
    change_set_workspace_path: str


# ============================================================
# Loop `over` callables — read the typed document at the path stored
# in state, then project the field that holds the iteration items.
# Reads go through `read_markdown` so this module doesn't pull in
# Docker or `workspace_ops` directly.
# ============================================================


def _change_sets_over(state: ChangeSetsLoopState) -> list[ChangeSetRef]:
    return read_markdown(
        state.workspace_handle, state.change_sets_document, ChangeSetsDocument
    ).change_sets


def _steps_over(state: StepsLoopState) -> list[StepRef]:
    return read_markdown(state.workspace_handle, state.steps_document, StepsDocument).steps


# ============================================================
# Composed topology
# ============================================================


full_pipeline = Sequence[FullPipelineState, FullPipelineState](
    steps=[
        workspace_bootstrap,
        designer,
        change_set_planner,
        Loop[ChangeSetsLoopState, ChangeSetsLoopState](
            over=_change_sets_over,
            item_key="current_change_set",
            body=Sequence[ChangeSetProcessingState, ChangeSetProcessingState](
                steps=[
                    prepare_change_set_workspace,
                    log_change_set_name,
                    tdd_planner,
                    Loop[StepsLoopState, StepsLoopState](
                        over=_steps_over,
                        item_key="current_step",
                        body=Sequence[StepProcessingState, StepProcessingState](
                            steps=[log_change_set_step_name],
                        ),
                    ),
                ],
            ),
        ),
    ],
)


# ============================================================
# Orchestrator
# ============================================================


async def run_full_pipeline(
    *,
    feature_definition: FeatureDefinition,
    codebase_source: CodebaseSource,
) -> FullPipelineState:
    """Run the full working-session pipeline and return the final state.

    Generates the workspace-volume name once and threads it into both
    the initial state (for bootstrap_fn) and the run_primitive_plan
    workspace_volume kwarg (for the container registry), so both sides
    agree on the name of the Docker volume containers will mount.
    """
    slug = (
        feature_definition.frontmatter.feature_slug
        if feature_definition.frontmatter is not None
        else "unnamed"
    )
    volume_name = generate_volume_name(slug)
    initial_state = FullPipelineState(
        feature_definition=feature_definition,
        codebase_source=codebase_source,
        volume_name=volume_name,
    )
    final = await run_primitive_plan(
        PrimitivePlan(root=full_pipeline),
        initial_state=initial_state,
        artifacts_dir=_artifacts_dir_for_run(),
        workspace_volume=volume_name,
        base_image_tag=BASE_IMAGE_TAG,
        responder_provider=static_provider(StdinResponder()),
        telemetry=telemetry_configuration,
        on_run_starting=[attach_mlflow_adapter],
    )
    assert isinstance(final, FullPipelineState), (
        f"run_primitive_plan returned {type(final).__name__}, expected FullPipelineState"
    )
    return final
