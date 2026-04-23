"""Tests for the design_pipeline Sequence composition."""

from __future__ import annotations

from agent_foundry.primitives.models import Sequence

from archipelago.actions import workspace_bootstrap
from archipelago.agents.designer import designer
from archipelago.systems.design_pipeline import design_pipeline


class TestDesignPipelineSequence:
    def test_given_pipeline_when_inspected_then_is_sequence(self):
        assert isinstance(design_pipeline, Sequence)

    def test_given_pipeline_when_inspected_then_steps_are_bootstrap_then_designer(self):
        assert design_pipeline.steps == [workspace_bootstrap, designer]

    def test_given_pipeline_when_inspected_then_step_order_preserved(self):
        first, second = design_pipeline.steps[0], design_pipeline.steps[1]
        assert first is workspace_bootstrap
        assert second is designer
