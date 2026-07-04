"""`run_full_pipeline` returns the runner's `RunOutcome` envelope verbatim.

`run_process` returns exactly one `RunOutcome` variant and never re-raises
an in-graph exception, so the orchestrator must hand that envelope back to
its caller unchanged rather than type-asserting against the inner state.
"""

from __future__ import annotations

import pytest
from agent_foundry.orchestration import (
    FailureKind,
    RunAborted,
    RunCompleted,
    RunFailed,
)

from archipelago.models import CodebaseSource
from archipelago.systems import pipeline


@pytest.fixture
def source() -> CodebaseSource:
    return CodebaseSource(repo_url="https://example.invalid/x.git", ref="main")


def _patch_run_process(monkeypatch, outcome) -> None:
    async def _fake(*_args, **_kwargs):
        return outcome

    monkeypatch.setattr(pipeline, "run_process", _fake)


@pytest.mark.asyncio
async def test_returns_run_completed_verbatim(
    monkeypatch, minimal_feature_definition, source
) -> None:
    state = pipeline.FullPipelineState(
        feature_definition=minimal_feature_definition,
        codebase_source=source,
        volume_name="v",
        base_image_tag="t",
    )
    outcome = RunCompleted(output=state)
    _patch_run_process(monkeypatch, outcome)

    result = await pipeline.run_full_pipeline(
        feature_definition=minimal_feature_definition, codebase_source=source
    )

    assert result is outcome


@pytest.mark.asyncio
async def test_returns_run_aborted_verbatim(
    monkeypatch, minimal_feature_definition, source
) -> None:
    outcome = RunAborted(reason="operator blocked on infra")
    _patch_run_process(monkeypatch, outcome)

    result = await pipeline.run_full_pipeline(
        feature_definition=minimal_feature_definition, codebase_source=source
    )

    assert result is outcome


@pytest.mark.asyncio
async def test_returns_run_failed_verbatim(monkeypatch, minimal_feature_definition, source) -> None:
    outcome = RunFailed(
        error_kind=FailureKind.BACKSTOP,
        error_type="ResolverDidNotConvergeError",
        message="operator retries did not converge",
    )
    _patch_run_process(monkeypatch, outcome)

    result = await pipeline.run_full_pipeline(
        feature_definition=minimal_feature_definition, codebase_source=source
    )

    assert result is outcome
