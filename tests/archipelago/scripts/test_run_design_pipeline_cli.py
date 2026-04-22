"""Tests for the run_design_pipeline CLI."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from agent_foundry.orchestration.errors import AgentFailedError

from archipelago.agents.designer import DesignerOutput
from archipelago.models import CodebaseSource
from archipelago.systems.design_pipeline import DesignPipelineState


@pytest.fixture
def cli_module():
    path = Path(__file__).resolve().parents[3] / "scripts" / "run_design_pipeline.py"
    spec = importlib.util.spec_from_file_location("run_design_pipeline_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_design_pipeline_script"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def run_pipeline_mock():
    with patch(
        "run_design_pipeline_script.run_design_pipeline",
        new_callable=AsyncMock,
    ) as mock:
        yield mock


class TestCLISuccess:
    def test_given_all_flags_when_main_then_success(
        self, cli_module, run_pipeline_mock, tmp_path, capsys, minimal_feature_definition
    ):
        repo_root = Path(__file__).resolve().parents[3]
        text = (repo_root / "examples" / "features" / "run-observability.md").read_text(
            encoding="utf-8"
        )
        feature_file = tmp_path / "feature.md"
        feature_file.write_text(text, encoding="utf-8")

        run_pipeline_mock.return_value = DesignPipelineState(
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(repo_url="u", ref="r"),
            volume_name="archipelago-ws-demo-1",
            designer_output=DesignerOutput(design_document="/workspace/documents/design.md"),
        )
        # Populate workspace_handle to exercise the success-print path.
        from archipelago.actions import WorkspaceHandle

        run_pipeline_mock.return_value = run_pipeline_mock.return_value.model_copy(
            update={
                "workspace_handle": WorkspaceHandle(
                    volume_name="archipelago-ws-demo-1",
                    root="/workspace",
                    documents_path="/workspace/documents",
                    codebase_path="/workspace/codebase",
                    feature_definition_path="/workspace/documents/feature_definition.md",
                    codebase_source_ref="r",
                    codebase_resolved_sha="a" * 40,
                )
            }
        )

        result = cli_module.main(
            [
                "--feature",
                str(feature_file),
                "--repo",
                "https://github.com/730alchemy/agent-foundry.git",
                "--ref",
                "main",
            ]
        )
        assert result == 0
        run_pipeline_mock.assert_called_once()
        out, _ = capsys.readouterr()
        assert "/workspace/documents/design.md" in out
        assert "archipelago-ws-demo-1" in out


class TestCLIArgValidation:
    def test_given_missing_required_flags_when_main_then_nonzero_exit(self, cli_module):
        with pytest.raises(SystemExit) as exc:
            cli_module.main(["--feature", "/tmp/x.md"])
        assert exc.value.code != 0

    def test_given_missing_feature_file_when_main_then_exit_2(self, cli_module, capsys):
        result = cli_module.main(
            [
                "--feature",
                "/does/not/exist.md",
                "--repo",
                "u",
                "--ref",
                "r",
            ]
        )
        assert result == 2
        _, err = capsys.readouterr()
        assert "/does/not/exist.md" in err

    def test_given_unparseable_feature_when_main_then_exit_2(self, cli_module, tmp_path, capsys):
        bad = tmp_path / "bad.md"
        bad.write_text("garbage without structure", encoding="utf-8")
        result = cli_module.main(
            [
                "--feature",
                str(bad),
                "--repo",
                "u",
                "--ref",
                "r",
            ]
        )
        assert result == 2
        _, err = capsys.readouterr()
        assert "parse" in err.lower() or "validation" in err.lower()


class TestCLIFailures:
    def test_given_designer_failure_when_main_then_exit_1(
        self, cli_module, run_pipeline_mock, tmp_path, capsys
    ):
        repo_root = Path(__file__).resolve().parents[3]
        text = (repo_root / "examples" / "features" / "run-observability.md").read_text(
            encoding="utf-8"
        )
        feature_file = tmp_path / "feature.md"
        feature_file.write_text(text, encoding="utf-8")
        run_pipeline_mock.side_effect = AgentFailedError("designer emitted failed: reason=X")

        result = cli_module.main(
            [
                "--feature",
                str(feature_file),
                "--repo",
                "u",
                "--ref",
                "r",
            ]
        )
        assert result == 1
        _, err = capsys.readouterr()
        assert "designer" in err.lower()
        assert "reason=X" in err

    def test_given_bootstrap_failure_when_main_then_exit_1(
        self, cli_module, run_pipeline_mock, tmp_path, capsys
    ):
        repo_root = Path(__file__).resolve().parents[3]
        text = (repo_root / "examples" / "features" / "run-observability.md").read_text(
            encoding="utf-8"
        )
        feature_file = tmp_path / "feature.md"
        feature_file.write_text(text, encoding="utf-8")
        run_pipeline_mock.side_effect = RuntimeError("git clone failed for repo=...")

        result = cli_module.main(
            [
                "--feature",
                str(feature_file),
                "--repo",
                "u",
                "--ref",
                "r",
            ]
        )
        assert result == 1
        _, err = capsys.readouterr()
        assert "bootstrap" in err.lower() or "git clone" in err.lower()
