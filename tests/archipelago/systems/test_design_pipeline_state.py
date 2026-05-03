"""Tests for DesignPipelineState and the volume-name helper."""

from __future__ import annotations

import re

from archipelago.actions import WorkspaceHandle
from archipelago.agents.designer import DesignerOutput
from archipelago.constants import WORKSPACE_CODEBASE_PATH, WORKSPACE_DOCUMENTS_PATH, WORKSPACE_ROOT
from archipelago.models import CodebaseSource
from archipelago.systems.design_pipeline import DesignPipelineState, generate_volume_name


def _handle() -> WorkspaceHandle:
    return WorkspaceHandle(
        volume_name="v",
        root=WORKSPACE_ROOT,
        documents_path=WORKSPACE_DOCUMENTS_PATH,
        codebase_path=WORKSPACE_CODEBASE_PATH,
        feature_definition_path=f"{WORKSPACE_DOCUMENTS_PATH}/feature_definition.md",
        codebase_source_ref="main",
        codebase_resolved_sha="a" * 40,
    )


class TestDesignPipelineState:
    def test_given_required_fields_when_constructed_then_optionals_default_to_none(
        self, minimal_feature_definition
    ):
        state = DesignPipelineState(
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(repo_url="u", ref="r"),
            volume_name="archipelago-ws-demo-1",
        )
        assert state.workspace_handle is None
        assert state.designer_output is None

    def test_given_all_fields_when_constructed_then_fields_populated(
        self, minimal_feature_definition
    ):
        state = DesignPipelineState(
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(repo_url="u", ref="r"),
            volume_name="archipelago-ws-demo-1",
            workspace_handle=_handle(),
            designer_output=DesignerOutput(
                investigation_summary=f"{WORKSPACE_DOCUMENTS_PATH}/investigation.md",
                design_document=f"{WORKSPACE_DOCUMENTS_PATH}/design.md",
            ),
        )
        assert state.workspace_handle is not None
        assert state.designer_output is not None


class TestGenerateVolumeName:
    def test_given_slug_when_generate_then_name_matches_expected_pattern(self):
        name = generate_volume_name("run-observability")
        assert re.match(r"^archipelago-ws-run-observability-\d{19}$", name), name

    def test_given_slug_with_unsafe_chars_when_generate_then_sanitized(self):
        name = generate_volume_name("my weird/slug!")
        assert re.match(r"^archipelago-ws-[a-zA-Z0-9._-]+-\d{19}$", name), name

    def test_given_two_calls_when_generate_then_names_differ(self):
        # time_ns() suffix makes same-second collisions astronomically rare.
        a = generate_volume_name("demo")
        b = generate_volume_name("demo")
        assert a != b


class TestStateFieldInvariants:
    """Compile-time invariants: each step's input-type fields must be a
    subset of DesignPipelineState fields, so the compiler's state-extraction
    pass finds every field it needs."""

    def test_given_bootstrap_input_when_inspected_then_fields_subset_of_pipeline_state(self):
        from archipelago.actions import BootstrapInput

        assert set(BootstrapInput.model_fields.keys()) <= set(
            DesignPipelineState.model_fields.keys()
        )

    def test_given_designer_input_when_inspected_then_fields_subset_of_pipeline_state(self):
        from archipelago.agents.designer import DesignerInput

        # DesignerInput needs workspace_handle (from BootstrapOutput's
        # unpacking) + feature_definition (from the initial state).
        # Both must be keys of DesignPipelineState.
        expected_subset = set(DesignerInput.model_fields.keys())
        available = set(DesignPipelineState.model_fields.keys())
        assert expected_subset <= available, (
            f"DesignerInput fields not in DesignPipelineState: {expected_subset - available}"
        )
