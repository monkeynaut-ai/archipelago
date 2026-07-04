from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from agent_foundry.orchestration.run_outcome import (
    FailureKind,
    RunAborted,
    RunCompleted,
    RunFailed,
)

import archipelago


def _load_cli() -> ModuleType:
    root = Path(archipelago.__file__).parents[2]
    spec = importlib.util.spec_from_file_location(
        "rfp_cli", root / "scripts" / "run_full_pipeline.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_cli(cli: ModuleType, tmp_path: Path, outcome):
    feature = tmp_path / "feature.md"
    feature.write_text("placeholder", encoding="utf-8")

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(cli, "parse_markdown_as", lambda *a, **k: object())

    async def _return(**_kwargs):
        return outcome

    monkeypatch.setattr(cli, "run_full_pipeline", _return)
    try:
        return cli.main(["--feature", str(feature), "--repo", "https://x/y.git", "--ref", "main"])
    finally:
        monkeypatch.undo()


def test_main_handles_operator_abort(tmp_path, capsys) -> None:
    cli = _load_cli()
    code = _run_cli(cli, tmp_path, RunAborted(reason="blocked on infra"))
    assert code == 1
    assert "blocked on infra" in capsys.readouterr().err


def test_main_handles_run_failure(tmp_path, capsys) -> None:
    cli = _load_cli()
    code = _run_cli(
        cli,
        tmp_path,
        RunFailed(
            error_kind=FailureKind.BACKSTOP,
            error_type="ResolverDidNotConvergeError",
            message="operator retries did not converge",
        ),
    )
    assert code == 1
    err = capsys.readouterr().err
    assert "converge" in err.lower()


def test_main_prints_artifacts_on_success(tmp_path, capsys, minimal_feature_definition) -> None:
    cli = _load_cli()
    from archipelago.models import CodebaseSource
    from archipelago.systems import FullPipelineState

    state = FullPipelineState(
        feature_definition=minimal_feature_definition,
        codebase_source=CodebaseSource(repo_url="https://x/y.git", ref="main"),
        volume_name="v",
        base_image_tag="t",
        design_document_path="/runs/x/design.md",
        pr_url="https://github.com/o/r/pull/1",
    )
    code = _run_cli(cli, tmp_path, RunCompleted(output=state))
    assert code == 0
    out = capsys.readouterr().out
    assert "/runs/x/design.md" in out
    assert "https://github.com/o/r/pull/1" in out
