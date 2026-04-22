"""Runnable Archipelago systems — compositions of primitives.

`design_pipeline` is the Phase 2 pipeline: workspace_bootstrap → designer.
Given a feature definition and a target codebase, it produces a design
document.
"""

from __future__ import annotations

from archipelago.systems.design_pipeline import (
    BASE_IMAGE_TAG,
    DesignPipelineState,
    design_pipeline,
    generate_volume_name,
    run_design_pipeline,
)

__all__ = [
    "BASE_IMAGE_TAG",
    "DesignPipelineState",
    "design_pipeline",
    "generate_volume_name",
    "run_design_pipeline",
]
