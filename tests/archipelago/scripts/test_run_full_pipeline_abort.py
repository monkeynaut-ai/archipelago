from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from agent_foundry.constructs import RetryAborted

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


def test_main_handles_operator_abort(monkeypatch, tmp_path, capsys) -> None:
    cli = _load_cli()
    feature = tmp_path / "feature.md"
    feature.write_text("placeholder", encoding="utf-8")

    monkeypatch.setattr(cli, "parse_markdown_as", lambda *a, **k: object())

    async def _raise(**_kwargs):
        raise RetryAborted("operator aborted: blocked on infra")

    monkeypatch.setattr(cli, "run_full_pipeline", _raise)

    code = cli.main(["--feature", str(feature), "--repo", "https://x/y.git", "--ref", "main"])
    assert code == 1
    assert "operator aborted: blocked on infra" in capsys.readouterr().err


def test_main_handles_resolver_nonconvergence(monkeypatch, tmp_path, capsys) -> None:
    from agent_foundry.constructs.retry_types import ResolverDidNotConvergeError

    cli = _load_cli()
    feature = tmp_path / "feature.md"
    feature.write_text("placeholder", encoding="utf-8")
    monkeypatch.setattr(cli, "parse_markdown_as", lambda *a, **k: object())

    async def _raise(**_kwargs):
        raise ResolverDidNotConvergeError(50)

    monkeypatch.setattr(cli, "run_full_pipeline", _raise)
    code = cli.main(["--feature", str(feature), "--repo", "https://x/y.git", "--ref", "main"])
    assert code == 1
    err = capsys.readouterr().err
    assert "converge" in err.lower()
