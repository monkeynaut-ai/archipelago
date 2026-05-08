"""Tests for the design_pipeline Sequence composition."""

from __future__ import annotations

from agent_foundry.primitives.models import Loop, Sequence

from archipelago.actions import workspace_bootstrap
from archipelago.agents.designer import designer
from archipelago.systems.design_pipeline import design_pipeline
from archipelago.systems.pipeline import full_pipeline


class TestFullPipelineSequence:
    def test_given_full_pipeline_when_inspected_then_is_sequence(self):
        assert isinstance(full_pipeline, Sequence)

    def test_given_full_pipeline_when_inspected_then_last_step_is_pr_creator(self):
        from archipelago.agents.pr_creator import pr_creator

        assert full_pipeline.steps[-1] is pr_creator

    def test_given_full_pipeline_when_inspected_then_outer_loop_precedes_pr_creator(self):
        second_to_last = full_pipeline.steps[-2]
        assert isinstance(second_to_last, Loop)


class TestDesignPipelineSequence:
    def test_given_pipeline_when_inspected_then_is_sequence(self):
        assert isinstance(design_pipeline, Sequence)

    def test_given_pipeline_when_inspected_then_steps_are_bootstrap_then_designer(self):
        assert design_pipeline.steps == [workspace_bootstrap, designer]

    def test_given_pipeline_when_inspected_then_step_order_preserved(self):
        first, second = design_pipeline.steps[0], design_pipeline.steps[1]
        assert first is workspace_bootstrap
        assert second is designer
