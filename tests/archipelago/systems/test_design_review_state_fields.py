from __future__ import annotations

from agent_foundry.primitives import (
    DispositionKind,
    ResolverDisposition,
    RetryExhaustionReason,
)

from archipelago.systems.pipeline import DesignReviewState


def test_new_fields_default_to_none() -> None:
    state = DesignReviewState.model_construct()
    assert state.disposition is None
    assert state.operator_guidance is None
    assert state.exhaustion_reason is None


def test_fields_round_trip() -> None:
    state = DesignReviewState.model_construct(
        disposition=ResolverDisposition(kind=DispositionKind.RETRY),
        operator_guidance="use a queue",
        exhaustion_reason=RetryExhaustionReason.CONDITION_NOT_MET,
    )
    assert state.disposition.kind is DispositionKind.RETRY
    assert state.operator_guidance == "use a queue"
    assert state.exhaustion_reason is RetryExhaustionReason.CONDITION_NOT_MET
