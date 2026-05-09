"""Tests for run_design_pipeline (run_primitive_plan + executor patched)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from archipelago.agents.designer import DesignerOutput
from archipelago.constants import WORKSPACE_DOCUMENTS_PATH
from archipelago.models import CodebaseSource
from archipelago.systems.design_pipeline import (
    BASE_IMAGE_TAG,
    DesignPipelineState,
    run_design_pipeline,
)


@pytest.fixture
def patched_runner():
    with patch(
        "archipelago.systems.design_pipeline.run_primitive_plan",
        new_callable=AsyncMock,
    ) as mock:
        yield mock


class TestRunDesignPipeline:
    @pytest.mark.asyncio
    async def test_given_inputs_when_run_then_plan_invoked_with_initial_state(
        self, patched_runner, minimal_feature_definition
    ):
        cs = CodebaseSource(repo_url="u", ref="r")
        final = DesignPipelineState(
            feature_definition=minimal_feature_definition,
            codebase_source=cs,
            volume_name="archipelago-ws-demo-1",
            designer_output=DesignerOutput(
                investigation_summary_path=f"{WORKSPACE_DOCUMENTS_PATH}/investigation.md",
                design_document_path=f"{WORKSPACE_DOCUMENTS_PATH}/design.md",
            ),
        )
        patched_runner.return_value = final

        result = await run_design_pipeline(
            feature_definition=minimal_feature_definition,
            codebase_source=cs,
        )

        assert result is final
        patched_runner.assert_called_once()
        kwargs = patched_runner.call_args.kwargs

        # initial_state carries the generated volume_name.
        initial_state = kwargs["initial_state"]
        assert isinstance(initial_state, DesignPipelineState)
        assert initial_state.feature_definition is minimal_feature_definition
        assert initial_state.codebase_source is cs
        assert initial_state.volume_name.startswith("archipelago-ws-")
        assert initial_state.workspace_handle is None
        assert initial_state.designer_output is None

        # workspace_volume kwarg passed to run_primitive_plan equals the
        # volume_name in initial_state — they must agree.
        assert kwargs["workspace_volume"] == initial_state.volume_name

        # base_image_tag from the module constant.
        assert kwargs["base_image_tag"] == BASE_IMAGE_TAG

        # responder_provider is a zero-arg callable that returns a
        # StdinResponder instance.
        from agent_foundry.responders.stdin import StdinResponder

        responder = kwargs["responder_provider"]()
        assert isinstance(responder, StdinResponder)

        # artifacts_dir is the cwd/runs parent; run_id is the timestamp.
        # ``agent_foundry`` creates ``<artifacts_dir>/<run_id>/``, so
        # this shape collapses to ``runs/<timestamp>/`` as a single layer.
        artifacts_dir = kwargs["artifacts_dir"]
        assert isinstance(artifacts_dir, Path)
        assert artifacts_dir.name == "runs"
        # YYYY-MM-DD-HH-MM-SS — second-resolution timestamp.
        import re

        run_id = kwargs["run_id"]
        assert re.match(r"^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}$", run_id), run_id

    @pytest.mark.asyncio
    async def test_given_plan_raises_when_run_then_error_propagates(
        self, patched_runner, minimal_feature_definition
    ):
        patched_runner.side_effect = RuntimeError("bootstrap exploded")
        with pytest.raises(RuntimeError, match="bootstrap exploded"):
            await run_design_pipeline(
                feature_definition=minimal_feature_definition,
                codebase_source=CodebaseSource(repo_url="u", ref="r"),
            )
