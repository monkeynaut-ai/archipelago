"""Tests for the shared artifacts_dir_for_run helper.

Both design_pipeline and full_pipeline land per-run artifacts under
`cwd/runs/<YYYY-MM-DD-HH-MM-SS>/`. The helper is the single source of
truth for that path; the pipelines import it.
"""

from __future__ import annotations

import re
from pathlib import Path

from archipelago.systems._artifacts import artifacts_dir_for_run


class TestArtifactsDirForRun:
    def test_given_called_when_invoked_then_parent_is_runs_under_cwd(self):
        result = artifacts_dir_for_run()
        assert result.parent == Path.cwd() / "runs"

    def test_given_called_when_invoked_then_leaf_is_second_resolution_timestamp(self):
        result = artifacts_dir_for_run()
        assert re.match(r"^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}$", result.name), result.name

    def test_given_called_when_invoked_then_path_is_absolute_or_relative_to_cwd(self):
        result = artifacts_dir_for_run()
        # Either absolute or anchored on Path.cwd() — both are acceptable
        # for a value the orchestrator will pass to run_primitive_plan.
        assert result.is_absolute() or (Path.cwd() / "runs" / result.name) == result.resolve()


class TestPipelinesUseSharedHelper:
    """Both pipelines should funnel through the shared helper, not
    keep their own local copy. Pin that by importing the modules
    explicitly and asserting they re-export the same callable."""

    def test_given_design_pipeline_module_when_inspected_then_imports_shared_helper(self):
        import importlib

        design_module = importlib.import_module("archipelago.systems.design_pipeline")
        assert design_module._artifacts_dir_for_run is artifacts_dir_for_run

    def test_given_full_pipeline_module_when_inspected_then_imports_shared_helper(self):
        import importlib

        pipeline_module = importlib.import_module("archipelago.systems.pipeline")
        assert pipeline_module._artifacts_dir_for_run is artifacts_dir_for_run
