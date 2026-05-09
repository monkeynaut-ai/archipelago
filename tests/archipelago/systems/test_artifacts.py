"""Tests for the shared run_artifacts_layout helper.

Both design_pipeline and full_pipeline land per-run artifacts under
`cwd/runs/<YYYY-MM-DD-HH-MM-SS>/`. The helper returns (parent, run_id)
so callers can pass them to ``run_primitive_plan`` directly;
``agent_foundry`` always creates ``<artifacts_dir>/<run_id>/``, so this
shape collapses to a single timestamp-named layer.
"""

from __future__ import annotations

import re
from pathlib import Path

from archipelago.systems._artifacts import run_artifacts_layout


class TestRunArtifactsLayout:
    def test_given_called_when_invoked_then_parent_is_runs_under_cwd(self):
        parent, _ = run_artifacts_layout()
        assert parent == Path.cwd() / "runs"

    def test_given_called_when_invoked_then_run_id_is_second_resolution_timestamp(self):
        _, run_id = run_artifacts_layout()
        assert re.match(r"^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}$", run_id), run_id

    def test_given_called_when_invoked_then_combined_path_is_runs_timestamp(self):
        parent, run_id = run_artifacts_layout()
        combined = parent / run_id
        assert combined.parent == Path.cwd() / "runs"
        assert re.match(r"^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}$", combined.name)


class TestPipelinesUseSharedHelper:
    """Both pipelines should funnel through the shared helper, not
    keep their own local copy. Pin that by importing the modules
    explicitly and asserting they re-export the same callable."""

    def test_given_design_pipeline_module_when_inspected_then_imports_shared_helper(self):
        import importlib

        design_module = importlib.import_module("archipelago.systems.design_pipeline")
        assert design_module._run_artifacts_layout is run_artifacts_layout

    def test_given_full_pipeline_module_when_inspected_then_imports_shared_helper(self):
        import importlib

        pipeline_module = importlib.import_module("archipelago.systems.pipeline")
        assert pipeline_module._run_artifacts_layout is run_artifacts_layout
