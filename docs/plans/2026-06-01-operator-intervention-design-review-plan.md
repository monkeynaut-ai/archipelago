# Operator Intervention for Design-Review Exhaustion Implementation Plan

> **Design:** docs/plans/2026-06-01-operator-intervention-design-review-design.md
> **For agents:** Use team-dev (parallel) or sdd (sequential) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the design-review `Retry` loop exhausts its attempts, prompt a human operator over stdin to abort, accept the current design, or retry with guidance.

**Architecture:** Configure Agent Foundry's `Retry.on_max_attempts_resolver` seat with a synchronous `FunctionAction` that interacts with the operator over stdin/stdout. The operator's choice maps to a `ResolverDisposition` (ABORT/ACCEPT/RETRY); RETRY injects operator guidance into state for the designer. Runs inside the existing single blocking `asyncio.run` — no checkpointer or resume loop.

**Tech Stack:** Python 3.14, Pydantic, Agent Foundry primitives (`Retry`, `FunctionAction`, `ResolverDisposition`), PDM, pytest.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/archipelago/systems/pipeline.py` | Modify | Add `disposition`/`operator_guidance`/`exhaustion_reason` to `DesignReviewState`; construct `operator_resolver` FunctionAction; wire it onto `design_review_loop` |
| `src/archipelago/agents/models.py` | Modify | Add `operator_guidance` to `DesignerInput` |
| `src/archipelago/agents/designer/primitive.py` | Modify | Append operator-guidance section to the revision prompt |
| `src/archipelago/agents/design_review/operator_resolver.py` | Create | Operator-intervention resolver logic (stdin/stdout) |
| `scripts/run_full_pipeline.py` | Modify | Catch `RetryAborted`, print reason, exit non-zero cleanly |
| `tests/archipelago/systems/test_design_review_state_fields.py` | Create | Asserts new `DesignReviewState` fields and defaults |
| `tests/archipelago/agents/test_designer_prompt.py` | Modify | Asserts guidance appears in the revision prompt |
| `tests/archipelago/agents/design_review/test_operator_resolver.py` | Create | Resolver branch behavior with injected prompt |
| `tests/archipelago/systems/test_operator_resolver_wiring.py` | Create | Asserts resolver wired onto the loop |
| `tests/archipelago/scripts/test_run_full_pipeline_abort.py` | Create | Asserts CLI handles `RetryAborted` cleanly |

---

## Task 1: DesignReviewState operator-intervention fields

**Files:**
- Modify: `src/archipelago/systems/pipeline.py`
- Test: `tests/archipelago/systems/test_design_review_state_fields.py`

**Dependencies:** none

- [ ] **Step 1: Write the failing test**

Create `tests/archipelago/systems/test_design_review_state_fields.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/archipelago/systems/test_design_review_state_fields.py -q`
Expected: FAIL — `AttributeError`/`ValidationError` on `disposition` (field not defined yet), or `ImportError` if names unavailable.

- [ ] **Step 3: Write minimal implementation**

In `src/archipelago/systems/pipeline.py`, add to the imports near the other `agent_foundry.primitives` imports (after line 25):

```python
from agent_foundry.primitives import ResolverDisposition, RetryExhaustionReason
```

Then add three fields to `DesignReviewState` (after `design_review_history`, currently line 209):

```python
    design_review_history: list[DesignReviewVerdict] = []
    # Operator-intervention fields, populated only when the loop exhausts and
    # the resolver runs. `disposition` is the resolver output contract the
    # compiler reads to route ACCEPT/ABORT/RETRY; `operator_guidance` carries
    # operator instructions into the guided re-attempt; `exhaustion_reason` is
    # the well-known metadata the compiler writes before the resolver node.
    disposition: ResolverDisposition | None = None
    operator_guidance: str | None = None
    exhaustion_reason: RetryExhaustionReason | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/archipelago/systems/test_design_review_state_fields.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/archipelago/systems/pipeline.py tests/archipelago/systems/test_design_review_state_fields.py
git commit -m "feat(design-review): add operator-intervention fields to DesignReviewState"
```

---

## Task 2: Operator guidance in the designer revision prompt

**Files:**
- Modify: `src/archipelago/agents/models.py`
- Modify: `src/archipelago/agents/designer/primitive.py`
- Test: `tests/archipelago/agents/test_designer_prompt.py`

**Dependencies:** none (independent of Task 1)

- [ ] **Step 1: Write the failing test**

Append to `tests/archipelago/agents/test_designer_prompt.py`:

```python
def test_revision_prompt_includes_operator_guidance() -> None:
    prompt = designer_prompt_builder(
        _input(
            design_review_verdict=_failing_verdict(),
            design_document_path="/workspace/documents/design.md",
            operator_guidance="Use an event queue instead of polling.",
        )
    )
    assert "Use an event queue instead of polling." in prompt
    assert "operator" in prompt.lower()


def test_revision_prompt_omits_guidance_section_when_absent() -> None:
    prompt = designer_prompt_builder(
        _input(
            design_review_verdict=_failing_verdict(),
            design_document_path="/workspace/documents/design.md",
        )
    )
    assert "operator guidance" not in prompt.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/archipelago/agents/test_designer_prompt.py -q`
Expected: FAIL — `DesignerInput` has no `operator_guidance` field (`_input` passes an unknown kwarg / attribute missing), and the guidance text is absent from the prompt.

- [ ] **Step 3: Write minimal implementation**

In `src/archipelago/agents/models.py`, add a field to `DesignerInput` (after `design_document_path`, currently line 28):

```python
    design_document_path: str | None = None
    # Set only when an operator chose RETRY at design-review exhaustion; steers
    # the revision alongside the reviewer findings.
    operator_guidance: str | None = None
```

In `src/archipelago/agents/designer/primitive.py`, replace the revision-branch `return` (currently lines 51-58) with a version that appends a guidance section:

```python
    guidance_section = ""
    if state.operator_guidance is not None:
        guidance_section = (
            f"\n\nAn operator reviewed the failed attempts and provided this "
            f"guidance — treat it as the top priority:\n{state.operator_guidance}"
        )
    return (
        f"The workspace is mounted at {state.workspace_handle.root}. "
        f"Your prior design at {state.design_document_path} did not pass review "
        f"(attempt {verdict.attempt_number}). Read it, then revise it in place to "
        f"resolve the following must-fix findings:\n\n{findings_text}\n\n"
        f"Dimensions scored INADEQUATE: {', '.join(inadequate)}. "
        f"Write the revised design document to the same path."
        f"{guidance_section}"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/archipelago/agents/test_designer_prompt.py -q`
Expected: PASS (all tests in the file, including the pre-existing ones).

- [ ] **Step 5: Commit**

```bash
git add src/archipelago/agents/models.py src/archipelago/agents/designer/primitive.py tests/archipelago/agents/test_designer_prompt.py
git commit -m "feat(designer): inject operator guidance into revision prompt"
```

---

## Task 3: Operator-intervention resolver

**Files:**
- Create: `src/archipelago/agents/design_review/operator_resolver.py`
- Test: `tests/archipelago/agents/design_review/test_operator_resolver.py`

**Dependencies:** Requires Task 1 (uses `DesignReviewState.disposition`/`operator_guidance`).

- [ ] **Step 1: Write the failing test**

Create `tests/archipelago/agents/design_review/__init__.py` (empty) and `tests/archipelago/agents/design_review/test_operator_resolver.py`:

```python
from __future__ import annotations

from collections.abc import Callable

from agent_foundry.primitives import DispositionKind, RetryExhaustionReason

from archipelago.agents.design_review.operator_resolver import (
    resolve_operator_intervention,
)
from archipelago.models.design_review import (
    CorrectnessDimension,
    CorrectnessMustFixFinding,
    CorrectnessVerdict,
    DesignReviewVerdict,
    DimensionScore,
    QualityDimension,
    QualityVerdict,
)
from archipelago.systems.pipeline import DesignReviewState


def _scripted(answers: list[str]) -> Callable[[str], str]:
    it = iter(answers)

    def _prompt(_message: str) -> str:
        return next(it)

    return _prompt


def _exhausted_state() -> DesignReviewState:
    correctness = CorrectnessVerdict(
        dimension_scores={d: DimensionScore.MEETS_BAR for d in CorrectnessDimension}
        | {CorrectnessDimension.REQUIREMENT_COVERAGE: DimensionScore.INADEQUATE},
        must_fix_findings=[
            CorrectnessMustFixFinding(
                description="AC-2 missing",
                suggested_resolution="add AC-2 handling",
                dimension=CorrectnessDimension.REQUIREMENT_COVERAGE,
            )
        ],
        reviewer_notes="n",
    )
    quality = QualityVerdict(
        dimension_scores={d: DimensionScore.MEETS_BAR for d in QualityDimension},
        must_fix_findings=[],
        reviewer_notes="n",
    )
    verdict = DesignReviewVerdict(
        correctness=correctness, quality=quality, passed=False, attempt_number=3
    )
    return DesignReviewState.model_construct(
        design_document_path="/workspace/documents/design.md",
        design_review_verdict=verdict,
        design_review_history=[verdict, verdict, verdict],
        exhaustion_reason=RetryExhaustionReason.CONDITION_NOT_MET,
    )


def test_accept_disposition() -> None:
    result = resolve_operator_intervention(
        _exhausted_state(), prompt=_scripted(["accept"]), out=lambda _m: None
    )
    assert result.disposition.kind is DispositionKind.ACCEPT
    assert result.operator_guidance is None


def test_abort_disposition_carries_reason() -> None:
    result = resolve_operator_intervention(
        _exhausted_state(),
        prompt=_scripted(["abort", "blocked on infra"]),
        out=lambda _m: None,
    )
    assert result.disposition.kind is DispositionKind.ABORT
    assert result.disposition.reason == "blocked on infra"


def test_retry_disposition_carries_guidance() -> None:
    result = resolve_operator_intervention(
        _exhausted_state(),
        prompt=_scripted(["retry", "use a queue instead of polling"]),
        out=lambda _m: None,
    )
    assert result.disposition.kind is DispositionKind.RETRY
    assert result.operator_guidance == "use a queue instead of polling"


def test_invalid_choice_reprompts() -> None:
    result = resolve_operator_intervention(
        _exhausted_state(), prompt=_scripted(["maybe", "accept"]), out=lambda _m: None
    )
    assert result.disposition.kind is DispositionKind.ACCEPT


def test_blank_guidance_reprompts() -> None:
    result = resolve_operator_intervention(
        _exhausted_state(),
        prompt=_scripted(["retry", "   ", "real guidance"]),
        out=lambda _m: None,
    )
    assert result.operator_guidance == "real guidance"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/archipelago/agents/design_review/test_operator_resolver.py -q`
Expected: FAIL — `ModuleNotFoundError: archipelago.agents.design_review.operator_resolver`.

- [ ] **Step 3: Write minimal implementation**

Create `src/archipelago/agents/design_review/operator_resolver.py`:

```python
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
            update={
                "disposition": ResolverDisposition(kind=DispositionKind.ABORT, reason=reason)
            }
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/archipelago/agents/design_review/test_operator_resolver.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/archipelago/agents/design_review/operator_resolver.py tests/archipelago/agents/design_review/
git commit -m "feat(design-review): add operator-intervention stdin resolver"
```

---

## Task 4: Wire the resolver onto the design-review loop

**Files:**
- Modify: `src/archipelago/systems/pipeline.py`
- Test: `tests/archipelago/systems/test_operator_resolver_wiring.py`

**Dependencies:** Requires Task 1 and Task 3.

- [ ] **Step 1: Write the failing test**

Create `tests/archipelago/systems/test_operator_resolver_wiring.py`:

```python
from __future__ import annotations

from archipelago.agents.design_review.operator_resolver import operator_intervention_fn
from archipelago.systems.pipeline import design_review_loop, operator_resolver


def test_resolver_wired_onto_loop() -> None:
    assert design_review_loop.on_max_attempts_resolver is operator_resolver


def test_resolver_uses_intervention_fn() -> None:
    assert operator_resolver.function is operator_intervention_fn
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/archipelago/systems/test_operator_resolver_wiring.py -q`
Expected: FAIL — `ImportError: cannot import name 'operator_resolver'` from pipeline.

- [ ] **Step 3: Write minimal implementation**

In `src/archipelago/systems/pipeline.py`:

Add `FunctionAction` to the primitives-models import (currently line 24):

```python
from agent_foundry.primitives.models import FunctionAction, Loop, Retry, Sequence
```

Add the resolver import near the other `archipelago.agents` imports (after line 43):

```python
from archipelago.agents.design_review.operator_resolver import operator_intervention_fn
```

Immediately after the `_design_review_passed` function (currently ends line 213), construct the resolver:

```python
operator_resolver = FunctionAction[DesignReviewState, DesignReviewState](
    function=operator_intervention_fn,
    name="operator-intervention",
)
```

Add the resolver to the `Retry` (currently lines 227-240) by inserting the seat argument:

```python
design_review_loop = Retry[DesignReviewState, DesignReviewState](
    max_attempts=3,
    until=_design_review_passed,
    on_max_attempts_resolver=operator_resolver,
    body=Sequence[DesignReviewState, DesignReviewState](
        steps=[
            designer,
            load_design_into_state,
            load_investigation_into_state,
            design_correctness_review,
            design_quality_review,
            aggregate_design_verdict,
        ],
    ),
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/archipelago/systems/test_operator_resolver_wiring.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/archipelago/systems/pipeline.py tests/archipelago/systems/test_operator_resolver_wiring.py
git commit -m "feat(design-review): wire operator resolver into design-review loop"
```

---

## Task 5: CLI handles operator abort cleanly

**Files:**
- Modify: `scripts/run_full_pipeline.py`
- Test: `tests/archipelago/scripts/test_run_full_pipeline_abort.py`

**Dependencies:** none (independent; `RetryAborted` import is from Agent Foundry)

- [ ] **Step 1: Write the failing test**

Create `tests/archipelago/scripts/test_run_full_pipeline_abort.py`:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import archipelago
from agent_foundry.primitives import RetryAborted


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

    monkeypatch.setattr(cli, "validate_markdown", lambda *a, **k: object())

    async def _raise(**_kwargs):
        raise RetryAborted("operator aborted: blocked on infra")

    monkeypatch.setattr(cli, "run_full_pipeline", _raise)

    code = cli.main(
        ["--feature", str(feature), "--repo", "https://x/y.git", "--ref", "main"]
    )
    assert code == 1
    assert "operator aborted: blocked on infra" in capsys.readouterr().err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/archipelago/scripts/test_run_full_pipeline_abort.py -q`
Expected: FAIL — `RetryAborted` propagates out of `main` (uncaught), so the call raises instead of returning `1`.

- [ ] **Step 3: Write minimal implementation**

In `scripts/run_full_pipeline.py`, add the import near the other Agent Foundry import (after line 25):

```python
from agent_foundry.primitives import RetryAborted
```

Add an `except` clause to the `try` around `asyncio.run` (currently lines 79-86), before the `AgentFailedError` clause:

```python
    try:
        final = asyncio.run(run_full_pipeline(feature_definition=feature, codebase_source=source))
    except RetryAborted as exc:
        print(f"aborted by operator: {exc.reason}", file=sys.stderr)
        return 1
    except AgentFailedError as exc:
        print(f"error: agent failed: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"error: pipeline failed: {exc}", file=sys.stderr)
        return 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/archipelago/scripts/test_run_full_pipeline_abort.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/run_full_pipeline.py tests/archipelago/scripts/test_run_full_pipeline_abort.py
git commit -m "feat(cli): handle operator abort cleanly in run_full_pipeline"
```

---

## Final verification

- [ ] **Run the full gate**

Run: `pdm test-all`
Expected: PASS (integration tests requiring Docker may skip — acceptable; no failures).

---

## Self-review notes

- **Spec coverage:** state fields (Task 1), designer guidance (Task 2), resolver logic + three dispositions + re-prompt (Task 3), wiring (Task 4), CLI clean abort (Task 5) — all design sections covered.
- **Type consistency:** `resolve_operator_intervention` / `operator_intervention_fn` / `operator_resolver` names used identically across Tasks 3–4; `ResolverDisposition`, `DispositionKind`, `RetryExhaustionReason`, `RetryAborted` all imported from `agent_foundry.primitives`.
- **Circular import:** resolved by constructing the `FunctionAction` in `pipeline.py` and keeping logic in `operator_resolver.py` (duck-typed; `DesignReviewState` only referenced under `TYPE_CHECKING`).
- **Dependency ordering:** Task 3 needs Task 1; Task 4 needs Tasks 1 and 3. Tasks 2 and 5 are independent and can run in parallel with the rest.
- **Commands:** `pdm run pytest <path>` for targeted runs, `pdm test-all` for the gate — matches the project toolchain.
