# CS2: Primitive Validators — Implementation Plan

> **Design:** docs/plans/2026-04-03-review-feedback-loop-design.md
> **Roadmap:** docs/plans/2026-04-03-review-feedback-loop-roadmap.md
> **For agents:** Use team-dev (parallel) or sdd (sequential) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add graph-level type compatibility validation for primitive compositions. Validate type boundaries between connected primitives at graph construction time, not at runtime. Two composition modes: **chaining** (Sequence steps — output feeds next input) and **containment** (Loop/Retry/Conditional wrapping a body — body operates within the parent's scope).

**Design decision — exact type matching:** All type boundaries use exact match (`is`), not subtype checks (`issubclass`). State models use composition, not inheritance — subtype polymorphism across graph boundaries leads to subtle runtime errors with Pydantic models. The compiler (CS3) does runtime Pydantic validation anyway; the static validator catches wiring mistakes.

**Type boundary summary:**

| Primitive | Boundaries | Rule |
|-----------|-----------|------|
| Sequence | I→first.I, adjacent chaining, last.O→O | 3 `is` checks |
| Retry | I→body.I, body.O→O, re-entry body.O→body.I | All 4 types identical |
| Conditional (with else) | I→then.I, then.O→O, I→else.I, else.O→O | 4 `is` checks |
| Conditional (no else) | I==O==then.I==then.O | All 4 types identical (detour, not fork) |
| Loop | None (body types deferred to CS3 — item_key injection creates joined scope) | Recurse only |
| Gate | prompt_key ∈ I.model_fields | 1 field check |
| Action | None | None |

**Architecture:** A `validate_primitive()` function recursively walks the primitive tree and checks type boundaries using `get_type_args()`. Error classes carry structured context (expected/actual types, position). Follows the `validate_plan()` pattern in `planner/validators.py`. A `validate()` convenience method is added to `PrimitivePlan`.

**Tech Stack:** Python 3.14, Pydantic >=2.12.5, pytest

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/agent_foundry/primitives/errors.py` | Create | Validation error classes |
| `src/agent_foundry/primitives/validators.py` | Create | `validate_primitive()` and per-type validators |
| `src/agent_foundry/primitives/plan.py` | Modify | Add `validate()` method |
| `src/agent_foundry/primitives/__init__.py` | Modify | Export `validate_primitive` |
| `tests/agent_foundry/primitives/test_primitive_validators.py` | Create | All validator tests |

All paths relative to `/home/markn/engineering/jig-archipelago/agent-foundry/`.

---

### Task 1: Error Classes

**Files:**
- Create: `src/agent_foundry/primitives/errors.py`
- Test: `tests/agent_foundry/primitives/test_primitive_validators.py`

**Dependencies:** None

- [ ] **Step 1: Write the failing test**

```python
"""Tests for primitive graph validators."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from agent_foundry.primitives.errors import (
    InvalidPromptKeyError,
    PrimitiveValidationError,
    TypeMismatchError,
)


# -- Test fixtures --


class StateA(BaseModel):
    x: str


class StateB(BaseModel):
    y: int


class StateC(BaseModel):
    z: float


class GateState(BaseModel):
    should_block: bool
    escalation_context: str


class GateOutput(BaseModel):
    human_response: str


# ======================================================================
# Error Classes
# ======================================================================


class TestPrimitiveValidationError:
    def test_is_exception(self):
        err = PrimitiveValidationError("something broke")
        assert isinstance(err, Exception)
        assert str(err) == "something broke"


class TestTypeMismatchError:
    def test_carries_context(self):
        err = TypeMismatchError(
            message="output StateA does not match input StateB",
            expected=StateB,
            actual=StateA,
            position="Sequence step 0 -> step 1",
        )
        assert isinstance(err, PrimitiveValidationError)
        assert err.expected is StateB
        assert err.actual is StateA
        assert err.position == "Sequence step 0 -> step 1"
        assert "StateA" in str(err)


class TestInvalidPromptKeyError:
    def test_carries_context(self):
        err = InvalidPromptKeyError(
            message="prompt_key 'missing' not found",
            prompt_key="missing",
            available_fields=["should_block", "escalation_context"],
        )
        assert isinstance(err, PrimitiveValidationError)
        assert err.prompt_key == "missing"
        assert err.available_fields == ["should_block", "escalation_context"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_validators.py -x`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_foundry.primitives.errors'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Typed exceptions for primitive graph validation."""


class PrimitiveValidationError(Exception):
    """Base for all primitive graph validation errors."""

    def __init__(self, message: str):
        super().__init__(message)


class TypeMismatchError(PrimitiveValidationError):
    """Adjacent primitives have incompatible input/output types."""

    def __init__(self, message: str, expected: type, actual: type, position: str):
        self.expected = expected
        self.actual = actual
        self.position = position
        super().__init__(message)


class InvalidPromptKeyError(PrimitiveValidationError):
    """Gate prompt_key not found in input type's model_fields."""

    def __init__(self, message: str, prompt_key: str, available_fields: list[str]):
        self.prompt_key = prompt_key
        self.available_fields = available_fields
        super().__init__(message)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_validators.py -x`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/primitives/errors.py tests/agent_foundry/primitives/test_primitive_validators.py
git commit -m "feat(primitives): add validation error classes"
```

---

### Task 2: Sequence Validation

**Files:**
- Create: `src/agent_foundry/primitives/validators.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_validators.py`

**Dependencies:** Task 1

- [ ] **Step 1: Write the failing test**

Append to `tests/agent_foundry/primitives/test_primitive_validators.py`:

```python
from agent_foundry.primitives.models import (
    Conditional,
    Gate,
    Loop,
    Primitive,
    Retry,
    Sequence,
)
from agent_foundry.primitives.validators import validate_primitive


# ======================================================================
# Sequence Validation
# ======================================================================


class TestSequenceValidation:
    def test_valid_single_step(self):
        step = Primitive[StateA, StateB]()
        seq = Sequence[StateA, StateB](steps=[step])
        validate_primitive(seq)  # should not raise

    def test_valid_chain(self):
        s1 = Primitive[StateA, StateB]()
        s2 = Primitive[StateB, StateC]()
        seq = Sequence[StateA, StateC](steps=[s1, s2])
        validate_primitive(seq)  # should not raise

    def test_first_step_input_mismatch(self):
        step = Primitive[StateB, StateB]()
        seq = Sequence[StateA, StateB](steps=[step])
        with pytest.raises(TypeMismatchError, match="Sequence step 0 input"):
            validate_primitive(seq)

    def test_last_step_output_mismatch(self):
        step = Primitive[StateA, StateA]()
        seq = Sequence[StateA, StateB](steps=[step])
        with pytest.raises(TypeMismatchError, match="Sequence step 0 output"):
            validate_primitive(seq)

    def test_adjacent_step_mismatch(self):
        s1 = Primitive[StateA, StateB]()
        s2 = Primitive[StateC, StateC]()  # expects StateC, gets StateB
        seq = Sequence[StateA, StateC](steps=[s1, s2])
        with pytest.raises(TypeMismatchError, match="step 0 output .* step 1 input"):
            validate_primitive(seq)

    def test_recurses_into_steps(self):
        """A nested sequence with an internal mismatch is caught."""
        bad_inner = Primitive[StateC, StateC]()  # wrong input
        inner_seq = Sequence[StateA, StateC](steps=[bad_inner])
        outer_seq = Sequence[StateA, StateC](steps=[inner_seq])
        with pytest.raises(TypeMismatchError):
            validate_primitive(outer_seq)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_validators.py::TestSequenceValidation -x`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_foundry.primitives.validators'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Graph-level type compatibility validation for primitives."""

from __future__ import annotations

from agent_foundry.primitives.errors import InvalidPromptKeyError, TypeMismatchError
from agent_foundry.primitives.models import (
    Conditional,
    Gate,
    Loop,
    Primitive,
    Retry,
    Sequence,
    get_type_args,
)


def validate_primitive(prim: Primitive) -> None:
    """Recursively validate type compatibility across a primitive tree.

    Raises TypeMismatchError or InvalidPromptKeyError on the first
    incompatibility found.
    """
    if isinstance(prim, Sequence):
        _validate_sequence(prim)
    elif isinstance(prim, Loop):
        _validate_loop(prim)
    elif isinstance(prim, Retry):
        _validate_retry(prim)
    elif isinstance(prim, Conditional):
        _validate_conditional(prim)
    elif isinstance(prim, Gate):
        _validate_gate(prim)


def _types_match(a: type, b: type) -> bool:
    """Check if two types are exactly the same (no subtype checks)."""
    return a is b


def _validate_sequence(seq: Sequence) -> None:
    seq_in, seq_out = get_type_args(seq)
    step_types = [get_type_args(s) for s in seq.steps]

    # First step input must match sequence input
    first_in = step_types[0][0]
    if not _types_match(seq_in, first_in):
        raise TypeMismatchError(
            message=(
                f"Sequence step 0 input type {first_in.__name__} "
                f"does not match Sequence input type {seq_in.__name__}"
            ),
            expected=seq_in,
            actual=first_in,
            position="Sequence step 0 input",
        )

    # Adjacent steps must chain
    for i in range(len(step_types) - 1):
        out_type = step_types[i][1]
        next_in = step_types[i + 1][0]
        if not _types_match(next_in, out_type):
            raise TypeMismatchError(
                message=(
                    f"Sequence step {i} output type {out_type.__name__} "
                    f"does not match step {i + 1} input type {next_in.__name__}"
                ),
                expected=next_in,
                actual=out_type,
                position=f"step {i} output -> step {i + 1} input",
            )

    # Last step output must match sequence output
    last_out = step_types[-1][1]
    if not _types_match(seq_out, last_out):
        raise TypeMismatchError(
            message=(
                f"Sequence step {len(step_types) - 1} output type {last_out.__name__} "
                f"does not match Sequence output type {seq_out.__name__}"
            ),
            expected=seq_out,
            actual=last_out,
            position=f"Sequence step {len(step_types) - 1} output",
        )

    # Recurse into each step
    for step in seq.steps:
        validate_primitive(step)


def _validate_loop(loop: Loop) -> None:
    pass


def _validate_retry(retry: Retry) -> None:
    pass


def _validate_conditional(cond: Conditional) -> None:
    pass


def _validate_gate(gate: Gate) -> None:
    pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_validators.py::TestSequenceValidation -x`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/primitives/validators.py tests/agent_foundry/primitives/test_primitive_validators.py
git commit -m "feat(primitives): add sequence type compatibility validation"
```

---

### Task 3: Loop — Recurse Only (Body Type Validation Deferred)

**Files:**
- Modify: `src/agent_foundry/primitives/validators.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_validators.py`

**Dependencies:** Task 2

Loop body type validation is **deferred to the compiler (CS3)**. A loop body's input type may legitimately differ from the loop's input type — the loop injects the current item via `item_key` and the body may need parent context (a "joined scope"). We don't yet have a mechanism for expressing this at the type level. The compiler will handle state injection and can validate at that point.

For now, the validator only recurses into the body to catch errors within it.

- [ ] **Step 1: Write the failing test**

Append to `tests/agent_foundry/primitives/test_primitive_validators.py`:

```python
class TestLoopValidation:
    def test_valid_loop_passes(self):
        body = Primitive[StateA, StateA]()
        loop = Loop[StateA, StateA](
            over=lambda s: [],
            item_key="item",
            body=body,
        )
        validate_primitive(loop)  # should not raise

    def test_recurses_into_body(self):
        """Errors inside the loop body are caught."""
        bad_step = Primitive[StateC, StateC]()
        inner_seq = Sequence[StateA, StateA](steps=[bad_step])
        loop = Loop[StateA, StateA](
            over=lambda s: [],
            item_key="item",
            body=inner_seq,
        )
        with pytest.raises(TypeMismatchError):
            validate_primitive(loop)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_validators.py::TestLoopValidation -x`
Expected: FAIL — `test_recurses_into_body` passes when it should raise (stub `_validate_loop` does nothing)

- [ ] **Step 3: Write minimal implementation**

Replace the stub `_validate_loop` in `validators.py`:

```python
def _validate_loop(loop: Loop) -> None:
    # Loop body type compatibility is deferred to the compiler (CS3).
    # The body's input type may differ from the loop's input type due to
    # item_key injection and parent context joining. Only recurse into
    # the body to catch errors within it.
    validate_primitive(loop.body)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_validators.py::TestLoopValidation -x`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/primitives/validators.py tests/agent_foundry/primitives/test_primitive_validators.py
git commit -m "feat(primitives): add loop validation (recurse only, body types deferred to CS3)"
```

---

### Task 4: Retry Body Validation (with Re-entry Constraint)

**Files:**
- Modify: `src/agent_foundry/primitives/validators.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_validators.py`

**Dependencies:** Task 2

Retry has a unique constraint: the body runs, then `until` checks if we're done. If not, the body runs *again on its own output*. So `body.O` must be compatible with `body.I` (re-entry), in addition to the boundary checks against the Retry's own types.

- [ ] **Step 1: Write the failing test**

Append to `tests/agent_foundry/primitives/test_primitive_validators.py`:

```python
class TestRetryValidation:
    def test_valid_body(self):
        body = Primitive[StateA, StateA]()
        retry = Retry[StateA, StateA](
            max_attempts=2,
            until=lambda s: True,
            body=body,
            on_exhausted="escalate",
        )
        validate_primitive(retry)  # should not raise

    def test_body_input_mismatch(self):
        body = Primitive[StateB, StateA]()
        retry = Retry[StateA, StateA](
            max_attempts=2,
            until=lambda s: True,
            body=body,
            on_exhausted="escalate",
        )
        with pytest.raises(TypeMismatchError, match="Retry body input"):
            validate_primitive(retry)

    def test_body_output_mismatch(self):
        body = Primitive[StateA, StateB]()
        retry = Retry[StateA, StateA](
            max_attempts=2,
            until=lambda s: True,
            body=body,
            on_exhausted="escalate",
        )
        with pytest.raises(TypeMismatchError, match="Retry body output"):
            validate_primitive(retry)

    def test_body_reentry_mismatch(self):
        """Body output must be compatible with body input for re-entry."""
        body = Primitive[StateA, StateB]()
        retry = Retry[StateA, StateB](
            max_attempts=2,
            until=lambda s: True,
            body=body,
            on_exhausted="escalate",
        )
        with pytest.raises(TypeMismatchError, match="re-entry"):
            validate_primitive(retry)

    def test_body_reentry_valid_when_same_type(self):
        body = Primitive[StateA, StateA]()
        retry = Retry[StateA, StateA](
            max_attempts=2,
            until=lambda s: True,
            body=body,
            on_exhausted="escalate",
        )
        validate_primitive(retry)  # should not raise

    def test_recurses_into_body(self):
        bad_step = Primitive[StateC, StateC]()
        inner_seq = Sequence[StateA, StateA](steps=[bad_step])
        retry = Retry[StateA, StateA](
            max_attempts=2,
            until=lambda s: True,
            body=inner_seq,
            on_exhausted="escalate",
        )
        with pytest.raises(TypeMismatchError):
            validate_primitive(retry)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_validators.py::TestRetryValidation -x`
Expected: FAIL — `test_body_input_mismatch` passes when it should raise

- [ ] **Step 3: Write minimal implementation**

Replace the stub `_validate_retry` in `validators.py`:

```python
def _validate_retry(retry: Retry) -> None:
    retry_in, retry_out = get_type_args(retry)
    body_in, body_out = get_type_args(retry.body)

    if not _types_match(retry_in, body_in):
        raise TypeMismatchError(
            message=(
                f"Retry body input type {body_in.__name__} "
                f"does not match Retry input type {retry_in.__name__}"
            ),
            expected=retry_in,
            actual=body_in,
            position="Retry body input",
        )

    if not _types_match(retry_out, body_out):
        raise TypeMismatchError(
            message=(
                f"Retry body output type {body_out.__name__} "
                f"does not match Retry output type {retry_out.__name__}"
            ),
            expected=retry_out,
            actual=body_out,
            position="Retry body output",
        )

    # Re-entry: body output feeds back as body input on next attempt
    if not _types_match(body_in, body_out):
        raise TypeMismatchError(
            message=(
                f"Retry body output type {body_out.__name__} "
                f"does not match body input type {body_in.__name__} "
                f"for re-entry on next attempt"
            ),
            expected=body_in,
            actual=body_out,
            position="Retry body re-entry",
        )

    validate_primitive(retry.body)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_validators.py::TestRetryValidation -x`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/primitives/validators.py tests/agent_foundry/primitives/test_primitive_validators.py
git commit -m "feat(primitives): add retry body validation with re-entry constraint"
```

---

### Task 5: Conditional Branch Validation

**Files:**
- Modify: `src/agent_foundry/primitives/validators.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_validators.py`

**Dependencies:** Task 2

- [ ] **Step 1: Write the failing test**

Append to `tests/agent_foundry/primitives/test_primitive_validators.py`:

```python
class TestConditionalValidation:
    def test_valid_both_branches(self):
        then = Primitive[StateA, StateB]()
        else_ = Primitive[StateA, StateB]()
        cond = Conditional[StateA, StateB](
            condition=lambda s: True,
            then_branch=then,
            else_branch=else_,
        )
        validate_primitive(cond)  # should not raise

    def test_valid_no_else(self):
        """No else branch: all types must be identical (detour pattern)."""
        then = Primitive[StateA, StateA]()
        cond = Conditional[StateA, StateA](
            condition=lambda s: True,
            then_branch=then,
        )
        validate_primitive(cond)  # should not raise

    def test_no_else_input_output_mismatch(self):
        """No else branch but Conditional.I != Conditional.O — not a valid detour."""
        then = Primitive[StateA, StateB]()
        cond = Conditional[StateA, StateB](
            condition=lambda s: True,
            then_branch=then,
        )
        with pytest.raises(TypeMismatchError, match="no else_branch"):
            validate_primitive(cond)

    def test_no_else_then_output_mismatch(self):
        """No else branch but then_branch.O != Conditional.I — not a valid detour."""
        then = Primitive[StateA, StateB]()
        cond = Conditional[StateA, StateA](
            condition=lambda s: True,
            then_branch=then,
        )
        with pytest.raises(TypeMismatchError, match="then_branch output"):
            validate_primitive(cond)

    def test_then_input_mismatch(self):
        then = Primitive[StateC, StateB]()
        cond = Conditional[StateA, StateB](
            condition=lambda s: True,
            then_branch=then,
        )
        with pytest.raises(TypeMismatchError, match="then_branch input"):
            validate_primitive(cond)

    def test_then_output_mismatch(self):
        then = Primitive[StateA, StateC]()
        cond = Conditional[StateA, StateB](
            condition=lambda s: True,
            then_branch=then,
        )
        with pytest.raises(TypeMismatchError, match="then_branch output"):
            validate_primitive(cond)

    def test_else_input_mismatch(self):
        then = Primitive[StateA, StateB]()
        else_ = Primitive[StateC, StateB]()
        cond = Conditional[StateA, StateB](
            condition=lambda s: True,
            then_branch=then,
            else_branch=else_,
        )
        with pytest.raises(TypeMismatchError, match="else_branch input"):
            validate_primitive(cond)

    def test_else_output_mismatch(self):
        then = Primitive[StateA, StateB]()
        else_ = Primitive[StateA, StateC]()
        cond = Conditional[StateA, StateB](
            condition=lambda s: True,
            then_branch=then,
            else_branch=else_,
        )
        with pytest.raises(TypeMismatchError, match="else_branch output"):
            validate_primitive(cond)

    def test_recurses_into_then_branch(self):
        """Errors inside then_branch are caught (with else present)."""
        bad_step = Primitive[StateC, StateC]()
        bad_seq = Sequence[StateA, StateB](steps=[bad_step])
        good_else = Primitive[StateA, StateB]()
        cond = Conditional[StateA, StateB](
            condition=lambda s: True,
            then_branch=bad_seq,
            else_branch=good_else,
        )
        with pytest.raises(TypeMismatchError):
            validate_primitive(cond)

    def test_recurses_into_else_branch(self):
        """Errors inside else_branch are caught."""
        good_then = Primitive[StateA, StateB]()
        bad_step = Primitive[StateC, StateC]()
        bad_seq = Sequence[StateA, StateB](steps=[bad_step])
        cond = Conditional[StateA, StateB](
            condition=lambda s: True,
            then_branch=good_then,
            else_branch=bad_seq,
        )
        with pytest.raises(TypeMismatchError):
            validate_primitive(cond)

    def test_recurses_into_no_else_then_branch(self):
        """Errors inside then_branch are caught (no else, detour pattern)."""
        bad_step = Primitive[StateC, StateC]()
        bad_seq = Sequence[StateA, StateA](steps=[bad_step])
        cond = Conditional[StateA, StateA](
            condition=lambda s: True,
            then_branch=bad_seq,
        )
        with pytest.raises(TypeMismatchError):
            validate_primitive(cond)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_validators.py::TestConditionalValidation -x`
Expected: FAIL — `test_then_input_mismatch` passes when it should raise

- [ ] **Step 3: Write minimal implementation**

Replace the stub `_validate_conditional` in `validators.py`:

```python
def _validate_conditional(cond: Conditional) -> None:
    cond_in, cond_out = get_type_args(cond)
    then_in, then_out = get_type_args(cond.then_branch)

    if cond.else_branch is None:
        # No else branch: this is a "detour" — state type must be stable.
        # All four types must be identical: Conditional.I == Conditional.O
        # == then.I == then.O
        if not _types_match(cond_in, cond_out):
            raise TypeMismatchError(
                message=(
                    f"Conditional with no else_branch requires input and output "
                    f"types to match, got {cond_in.__name__} and {cond_out.__name__}"
                ),
                expected=cond_in,
                actual=cond_out,
                position="Conditional no else_branch: input != output",
            )

        if not _types_match(cond_in, then_in):
            raise TypeMismatchError(
                message=(
                    f"Conditional then_branch input type {then_in.__name__} "
                    f"does not match Conditional input type {cond_in.__name__}"
                ),
                expected=cond_in,
                actual=then_in,
                position="Conditional then_branch input",
            )

        if not _types_match(cond_in, then_out):
            raise TypeMismatchError(
                message=(
                    f"Conditional then_branch output type {then_out.__name__} "
                    f"does not match Conditional input type {cond_in.__name__}"
                ),
                expected=cond_in,
                actual=then_out,
                position="Conditional then_branch output",
            )
    else:
        # Both branches present: standard boundary checks.
        if not _types_match(cond_in, then_in):
            raise TypeMismatchError(
                message=(
                    f"Conditional then_branch input type {then_in.__name__} "
                    f"does not match Conditional input type {cond_in.__name__}"
                ),
                expected=cond_in,
                actual=then_in,
                position="Conditional then_branch input",
            )

        if not _types_match(cond_out, then_out):
            raise TypeMismatchError(
                message=(
                    f"Conditional then_branch output type {then_out.__name__} "
                    f"does not match Conditional output type {cond_out.__name__}"
                ),
                expected=cond_out,
                actual=then_out,
                position="Conditional then_branch output",
            )

        else_in, else_out = get_type_args(cond.else_branch)

        if not _types_match(cond_in, else_in):
            raise TypeMismatchError(
                message=(
                    f"Conditional else_branch input type {else_in.__name__} "
                    f"does not match Conditional input type {cond_in.__name__}"
                ),
                expected=cond_in,
                actual=else_in,
                position="Conditional else_branch input",
            )

        if not _types_match(cond_out, else_out):
            raise TypeMismatchError(
                message=(
                    f"Conditional else_branch output type {else_out.__name__} "
                    f"does not match Conditional output type {cond_out.__name__}"
                ),
                expected=cond_out,
                actual=else_out,
                position="Conditional else_branch output",
            )

        validate_primitive(cond.else_branch)

    validate_primitive(cond.then_branch)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_validators.py::TestConditionalValidation -x`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/primitives/validators.py tests/agent_foundry/primitives/test_primitive_validators.py
git commit -m "feat(primitives): add conditional branch type compatibility validation"
```

---

### Task 6: Gate prompt_key Validation

**Files:**
- Modify: `src/agent_foundry/primitives/validators.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_validators.py`

**Dependencies:** Task 2

- [ ] **Step 1: Write the failing test**

Append to `tests/agent_foundry/primitives/test_primitive_validators.py`:

```python
class TestGateValidation:
    def test_valid_prompt_key(self):
        gate = Gate[GateState, GateOutput](
            condition=lambda s: s.should_block,
            interaction="human_stdin",
            prompt_key="escalation_context",
        )
        validate_primitive(gate)  # should not raise

    def test_invalid_prompt_key(self):
        gate = Gate[GateState, GateOutput](
            condition=lambda s: s.should_block,
            interaction="human_stdin",
            prompt_key="nonexistent_field",
        )
        with pytest.raises(InvalidPromptKeyError) as exc_info:
            validate_primitive(gate)
        assert exc_info.value.prompt_key == "nonexistent_field"
        assert "should_block" in exc_info.value.available_fields
        assert "escalation_context" in exc_info.value.available_fields
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_validators.py::TestGateValidation -x`
Expected: FAIL — `test_invalid_prompt_key` passes when it should raise

- [ ] **Step 3: Write minimal implementation**

Replace the stub `_validate_gate` in `validators.py`:

```python
def _validate_gate(gate: Gate) -> None:
    input_type, _ = get_type_args(gate)
    available = list(input_type.model_fields.keys())
    if gate.prompt_key not in available:
        raise InvalidPromptKeyError(
            message=(
                f"Gate prompt_key '{gate.prompt_key}' not found in "
                f"{input_type.__name__}; available fields: {available}"
            ),
            prompt_key=gate.prompt_key,
            available_fields=available,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_validators.py::TestGateValidation -x`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/primitives/validators.py tests/agent_foundry/primitives/test_primitive_validators.py
git commit -m "feat(primitives): add gate prompt_key field validation"
```

---

### Task 7: PrimitivePlan.validate() and Exports

**Files:**
- Modify: `src/agent_foundry/primitives/plan.py`
- Modify: `src/agent_foundry/primitives/__init__.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_validators.py`

**Dependencies:** Tasks 1-6

- [ ] **Step 1: Write the failing test**

Append to `tests/agent_foundry/primitives/test_primitive_validators.py`:

```python
from agent_foundry.primitives.plan import PrimitivePlan


class TestPrimitivePlanValidate:
    def test_valid_plan_passes(self):
        s1 = Primitive[StateA, StateB]()
        s2 = Primitive[StateB, StateC]()
        seq = Sequence[StateA, StateC](steps=[s1, s2])
        plan = PrimitivePlan(root=seq)
        plan.validate()  # should not raise

    def test_invalid_plan_raises(self):
        bad = Primitive[StateC, StateC]()
        seq = Sequence[StateA, StateB](steps=[bad])
        plan = PrimitivePlan(root=seq)
        with pytest.raises(TypeMismatchError):
            plan.validate()


class TestValidatorPublicAPI:
    def test_import_validate_primitive_from_package(self):
        from agent_foundry.primitives import validate_primitive

        assert validate_primitive is not None

    def test_import_errors_from_package(self):
        from agent_foundry.primitives import (
            InvalidPromptKeyError,
            PrimitiveValidationError,
            TypeMismatchError,
        )

        assert PrimitiveValidationError is not None
        assert TypeMismatchError is not None
        assert InvalidPromptKeyError is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_validators.py::TestPrimitivePlanValidate -x`
Expected: FAIL with `AttributeError: 'PrimitivePlan' object has no attribute 'validate'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/agent_foundry/primitives/plan.py`:

```python
from agent_foundry.primitives.validators import validate_primitive
```

And add the `validate` method to PrimitivePlan:

```python
    def validate(self) -> None:
        """Validate type compatibility across the entire primitive graph."""
        validate_primitive(self.root)
```

Update `src/agent_foundry/primitives/__init__.py` to export:

```python
from agent_foundry.primitives.errors import (
    InvalidPromptKeyError,
    PrimitiveValidationError,
    TypeMismatchError,
)
from agent_foundry.primitives.validators import validate_primitive
```

Add to `__all__`:
```python
    "InvalidPromptKeyError",
    "PrimitiveValidationError",
    "TypeMismatchError",
    "validate_primitive",
```

- [ ] **Step 4: Run full test suite**

Run: `pdm run pytest tests/agent_foundry/primitives/ -v`
Expected: ALL PASS

Run: `pdm run pytest tests/ -q`
Expected: ALL PASS, no regressions

Run: `pdm run lint`
Expected: Clean

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/primitives/plan.py src/agent_foundry/primitives/__init__.py tests/agent_foundry/primitives/test_primitive_validators.py
git commit -m "feat(primitives): add PrimitivePlan.validate() and export validators"
```

---

## Verification

After all tasks complete:

1. `pdm run pytest tests/agent_foundry/primitives/ -v` — all primitive tests pass
2. `pdm run pytest tests/ -q` — full suite passes, no regressions
3. `pdm run lint` — clean
