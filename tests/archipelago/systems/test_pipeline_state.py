"""Tests for FullPipelineState and its step-input field invariants."""

from __future__ import annotations

from archipelago.models import CodebaseSource
from archipelago.systems.pipeline import FullPipelineState


class TestFullPipelineState:
    def test_given_required_fields_when_constructed_then_pr_url_defaults_to_none(
        self, minimal_feature_definition
    ):
        state = FullPipelineState(
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(repo_url="u", ref="r"),
            volume_name="archipelago-ws-demo-1",
            base_image_tag="agent-worker:latest",
        )
        assert state.pr_url is None

    def test_given_pr_creator_input_fields_when_inspected_then_subset_of_full_pipeline_state(self):
        from archipelago.agents.models import PrCreatorInput

        assert set(PrCreatorInput.model_fields.keys()) <= set(FullPipelineState.model_fields.keys())


class TestStateFieldInvariants:
    """Compile-time invariants: each step's input-type fields must be a
    subset of FullPipelineState fields, so the compiler's state-extraction
    pass finds every field it needs."""

    def test_given_bootstrap_input_when_inspected_then_fields_subset_of_pipeline_state(self):
        from archipelago.actions import BootstrapInput

        assert set(BootstrapInput.model_fields.keys()) <= set(FullPipelineState.model_fields.keys())

    def test_given_designer_input_when_inspected_then_fields_subset_of_pipeline_state(self):
        from archipelago.agents.designer import DesignerInput

        # DesignerInput needs workspace_handle (from BootstrapOutput's
        # unpacking) + feature_definition (from the initial state).
        # Both must be keys of FullPipelineState.
        expected_subset = set(DesignerInput.model_fields.keys())
        available = set(FullPipelineState.model_fields.keys())
        assert expected_subset <= available, (
            f"DesignerInput fields not in FullPipelineState: {expected_subset - available}"
        )
