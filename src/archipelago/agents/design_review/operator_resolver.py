"""Operator-intervention resolver for the design-review Retry loop.

Consulted when the loop exhausts ``max_attempts`` without passing. Prompts a
human operator over stdin for one of three dispositions: abort, accept (continue
downstream with the current design), or retry with guidance for the designer.

The ``FunctionAction`` wrapper is constructed in ``systems.pipeline`` (alongside
``DesignReviewState``) to avoid a circular import — this module holds only the
logic and is duck-typed over the state object.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from agent_foundry.primitives import DispositionKind, ResolverDisposition

from archipelago.models.design_review import DimensionScore

if TYPE_CHECKING:
    from archipelago.systems.pipeline import DesignReviewState

_CHOICES = frozenset({"abort", "accept", "retry"})


def _format_summary(state: DesignReviewState) -> str:
    lines = ["", "=== Design review exhausted ==="]
    if state.exhaustion_reason is not None:
        lines.append(f"Reason: {state.exhaustion_reason.value}")
    verdict = state.design_review_verdict
    if verdict is not None:
        attempts = len(state.design_review_history) or verdict.attempt_number
        lines.append(f"Attempts: {attempts}")
        findings = [*verdict.correctness.must_fix_findings, *verdict.quality.must_fix_findings]
        if findings:
            lines.append("Must-fix findings:")
            lines.extend(
                f"  - [{f.dimension.value}] {f.description} — {f.suggested_resolution}"
                for f in findings
            )
        inadequate = [
            d.value
            for scores in (
                verdict.correctness.dimension_scores,
                verdict.quality.dimension_scores,
            )
            for d, s in scores.items()
            if s == DimensionScore.INADEQUATE
        ]
        if inadequate:
            lines.append(f"INADEQUATE dimensions: {', '.join(inadequate)}")
    return "\n".join(lines)


def resolve_operator_intervention(
    state: DesignReviewState,
    prompt: Callable[[str], str] = input,
    out: Callable[[str], None] = print,
) -> DesignReviewState:
    """Prompt the operator and return ``state`` with a ``disposition`` set."""
    out(_format_summary(state))
    while True:
        choice = prompt("Operator decision [abort/accept/retry]: ").strip().lower()
        if choice in _CHOICES:
            break
        out(f"Invalid choice {choice!r}. Enter one of: abort, accept, retry.")

    if choice == "accept":
        return state.model_copy(
            update={"disposition": ResolverDisposition(kind=DispositionKind.ACCEPT)}
        )
    if choice == "abort":
        reason = prompt("Abort reason: ").strip()
        return state.model_copy(
            update={"disposition": ResolverDisposition(kind=DispositionKind.ABORT, reason=reason)}
        )

    while True:
        guidance = prompt("Guidance for the designer: ").strip()
        if guidance:
            break
        out("Guidance cannot be empty for a retry.")
    return state.model_copy(
        update={
            "disposition": ResolverDisposition(kind=DispositionKind.RETRY),
            "operator_guidance": guidance,
        }
    )


def operator_intervention_fn(state: DesignReviewState) -> DesignReviewState:
    """Thin ``FunctionAction`` body using the real stdin/stdout."""
    return resolve_operator_intervention(state)
