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
                investigation_summary=f"{WORKSPACE_DOCUMENTS_PATH}/investigation.md",
                design_document=f"{WORKSPACE_DOCUMENTS_PATH}/design.md",
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

        # artifacts_dir is a Path under cwd/runs/ with a timestamp name.
        artifacts_dir = kwargs["artifacts_dir"]
        assert isinstance(artifacts_dir, Path)
        assert artifacts_dir.parent.name == "runs"
        # YYYY-MM-DD-HH-MM-SS — second-resolution timestamp.
        import re

        assert re.match(r"^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}$", artifacts_dir.name), (
            artifacts_dir.name
        )

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
