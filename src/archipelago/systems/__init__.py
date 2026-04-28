"""Runnable Archipelago systems — compositions of primitives.

`design_pipeline` (in `archipelago.systems.design_pipeline`): the Stage 1
pipeline (workspace_bootstrap → designer). Given a feature definition
and a target codebase, produces a design document. Preserved for
design-only smoke runs.

`full_pipeline` (in `archipelago.systems.pipeline`): the Stage 2
working-session topography skeleton. Extends design_pipeline's primitives
with change_set_planner, an outer Loop over change sets containing
prepare_change_set_workspace + log_change_set_name + tdd_planner + an
inner Loop over change-set-steps with log_change_set_step_name. Per-loop-
body state scoping per the topography design.
"""

from __future__ import annotations

from archipelago.systems.design_pipeline import (
    BASE_IMAGE_TAG,
    DesignPipelineState,
    design_pipeline,
    generate_volume_name,
    run_design_pipeline,
)
from archipelago.systems.pipeline import (
    ChangeSetProcessingState,
    ChangeSetsLoopState,
    FullPipelineState,
    StepProcessingState,
    StepsLoopState,
    full_pipeline,
    run_full_pipeline,
)

__all__ = [
    "BASE_IMAGE_TAG",
    "ChangeSetProcessingState",
    "ChangeSetsLoopState",
    "DesignPipelineState",
    "FullPipelineState",
    "StepProcessingState",
    "StepsLoopState",
    "design_pipeline",
    "full_pipeline",
    "generate_volume_name",
    "run_design_pipeline",
    "run_full_pipeline",
]
