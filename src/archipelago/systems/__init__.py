"""Runnable Archipelago systems — compositions of primitives.

`full_pipeline` (in `archipelago.systems.pipeline`): the Stage 2
working-session topography skeleton — workspace_bootstrap + designer +
change_set_planner, an outer Loop over change sets containing
prepare_change_set_workspace + log_change_set_name + tdd_planner + an
inner Loop over change-set-steps with log_change_set_step_name. Per-loop-
body state scoping per the topography design.
"""

from __future__ import annotations

from archipelago.systems._workspace import BASE_IMAGE_TAG, generate_volume_name
from archipelago.systems.pipeline import (
    ChangeSetProcessingState,
    ChangeSetsLoopState,
    FullPipelineState,
    TaskProcessingState,
    TDDPlanLoopState,
    full_pipeline,
    run_full_pipeline,
)

__all__ = [
    "BASE_IMAGE_TAG",
    "ChangeSetProcessingState",
    "ChangeSetsLoopState",
    "FullPipelineState",
    "TDDPlanLoopState",
    "TaskProcessingState",
    "full_pipeline",
    "generate_volume_name",
    "run_full_pipeline",
]
