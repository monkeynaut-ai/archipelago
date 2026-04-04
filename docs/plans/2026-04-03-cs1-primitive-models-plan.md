# CS1: Primitive Pydantic Models — Implementation Plan

> **Design:** docs/plans/2026-04-03-review-feedback-loop-design.md
> **Roadmap:** docs/plans/2026-04-03-review-feedback-loop-roadmap.md
> **For agents:** Use team-dev (parallel) or sdd (sequential) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define the six composable primitive types (Sequence, Loop, Retry, Conditional, Gate, Action) as typed Pydantic models in Agent Foundry, with input/output type boundaries and composition by direct object reference.

**Architecture:** New `primitives` package in Agent Foundry (`src/agent_foundry/primitives/`) containing Pydantic models for each primitive type, a base class establishing the common interface, and a `PrimitivePlan` container for graph introspection. No names or string-based references — composition is by direct Python object reference. Diagnostic labels are inferred from class names via introspection. All primitives use Pydantic `BaseModel` subclasses with `model_validator` for cross-field constraints, following existing patterns in `planner/wiring_plan.py`.

**Status: COMPLETED** — implemented and committed to Agent Foundry on branch `support-review-with-jig`.

**Tech Stack:** Python 3.14, Pydantic >=2.12.5, pytest

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/agent_foundry/primitives/__init__.py` | Create | Package init, re-exports public API |
| `src/agent_foundry/primitives/models.py` | Create | Primitive base class and all six primitive models |
| `src/agent_foundry/primitives/plan.py` | Create | PrimitivePlan container with reference resolution |
| `tests/agent_foundry/primitives/__init__.py` | Create | Test package init |
| `tests/agent_foundry/primitives/test_primitive_models.py` | Create | Tests for all primitive models |
| `tests/agent_foundry/primitives/test_primitive_plan.py` | Create | Tests for PrimitivePlan and reference resolution |

All paths relative to `/home/markn/engineering/jig-archipelago/agent-foundry/`.

---

### Task 1: Primitive Base Model

**Files:**
- Create: `src/agent_foundry/primitives/__init__.py`
- Create: `src/agent_foundry/primitives/models.py`
- Test: `tests/agent_foundry/primitives/__init__.py`
- Test: `tests/agent_foundry/primitives/test_primitive_models.py`

**Dependencies:** None

- [ ] **Step 1: Write the failing test**

```python
"""Tests for primitive base model and common contract."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from agent_foundry.primitives.models import Primitive


class StubInput(BaseModel):
    value: str


class StubOutput(BaseModel):
    result: str


class TestPrimitiveBase:
    """Primitive base model enforces name, input, and output."""

    def test_given_valid_fields_when_created_then_succeeds(self):
        p = Primitive(name="test_prim", input=StubInput, output=StubOutput)
        assert p.name == "test_prim"
        assert p.input is StubInput
        assert p.output is StubOutput

    def test_given_missing_name_when_created_then_raises(self):
        with pytest.raises(ValidationError):
            Primitive(input=StubInput, output=StubOutput)

    def test_given_empty_name_when_created_then_raises(self):
        with pytest.raises(ValidationError):
            Primitive(name="", input=StubInput, output=StubOutput)

    def test_given_missing_input_when_created_then_raises(self):
        with pytest.raises(ValidationError):
            Primitive(name="test", output=StubOutput)

    def test_given_missing_output_when_created_then_raises(self):
        with pytest.raises(ValidationError):
            Primitive(name="test", input=StubInput)

    def test_given_non_basemodel_input_when_created_then_raises(self):
        with pytest.raises(ValidationError):
            Primitive(name="test", input=str, output=StubOutput)

    def test_given_non_basemodel_output_when_created_then_raises(self):
        with pytest.raises(ValidationError):
            Primitive(name="test", input=StubInput, output=str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_models.py::TestPrimitiveBase -x`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_foundry.primitives'`

- [ ] **Step 3: Write minimal implementation**

`src/agent_foundry/primitives/__init__.py`:
```python
"""Composable, typed plan primitives for Agent Foundry."""
```

`tests/agent_foundry/primitives/__init__.py`:
```python
```

`src/agent_foundry/primitives/models.py`:
```python
"""Primitive Pydantic models — composable, named, typed building blocks."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _is_basemodel_subclass(v: Any) -> bool:
    return isinstance(v, type) and issubclass(v, BaseModel)


class Primitive(BaseModel):
    """Base class for all plan primitives.

    Every primitive has a unique name, a typed input boundary, and a typed
    output boundary.  Input/output are Pydantic BaseModel subclasses that
    define the state keys the primitive reads from and writes back to its
    parent scope.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(min_length=1)
    input: type[BaseModel]
    output: type[BaseModel]

    @model_validator(mode="after")
    def _validate_type_fields(self) -> Primitive:
        if not _is_basemodel_subclass(self.input):
            raise ValueError(
                f"Primitive '{self.name}': 'input' must be a BaseModel subclass, "
                f"got {self.input}"
            )
        if not _is_basemodel_subclass(self.output):
            raise ValueError(
                f"Primitive '{self.name}': 'output' must be a BaseModel subclass, "
                f"got {self.output}"
            )
        return self
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_models.py::TestPrimitiveBase -x`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/primitives/__init__.py src/agent_foundry/primitives/models.py tests/agent_foundry/primitives/__init__.py tests/agent_foundry/primitives/test_primitive_models.py
git commit -m "feat(primitives): add Primitive base model with name, input, output"
```

---

### Task 2: Sequence Primitive

**Files:**
- Modify: `src/agent_foundry/primitives/models.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_models.py`

**Dependencies:** Task 1

- [ ] **Step 1: Write the failing test**

Append to `tests/agent_foundry/primitives/test_primitive_models.py`:

```python
from agent_foundry.primitives.models import Primitive, Sequence


class TestSequence:
    """Sequence primitive executes steps in order."""

    def test_given_valid_steps_when_created_then_succeeds(self):
        inner = Primitive(name="inner", input=StubInput, output=StubOutput)
        seq = Sequence(
            name="my_seq",
            input=StubInput,
            output=StubOutput,
            steps=[inner],
        )
        assert seq.name == "my_seq"
        assert len(seq.steps) == 1
        assert seq.steps[0].name == "inner"

    def test_given_string_refs_in_steps_when_created_then_succeeds(self):
        seq = Sequence(
            name="my_seq",
            input=StubInput,
            output=StubOutput,
            steps=["planner", "test_agent", "implementer"],
        )
        assert seq.steps == ["planner", "test_agent", "implementer"]

    def test_given_mixed_refs_and_primitives_when_created_then_succeeds(self):
        inner = Primitive(name="inner", input=StubInput, output=StubOutput)
        seq = Sequence(
            name="my_seq",
            input=StubInput,
            output=StubOutput,
            steps=[inner, "other_ref"],
        )
        assert len(seq.steps) == 2

    def test_given_empty_steps_when_created_then_raises(self):
        with pytest.raises(ValidationError):
            Sequence(
                name="empty",
                input=StubInput,
                output=StubOutput,
                steps=[],
            )

    def test_given_no_steps_when_created_then_raises(self):
        with pytest.raises(ValidationError):
            Sequence(name="no_steps", input=StubInput, output=StubOutput)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_models.py::TestSequence -x`
Expected: FAIL with `ImportError: cannot import name 'Sequence'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/agent_foundry/primitives/models.py`:

```python
class Sequence(Primitive):
    """Execute steps in order, passing state between them.

    Steps can be Primitive instances (inline) or strings (named references
    resolved by PrimitivePlan at compile time).
    """

    steps: list[Primitive | str] = Field(min_length=1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_models.py::TestSequence -x`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/primitives/models.py tests/agent_foundry/primitives/test_primitive_models.py
git commit -m "feat(primitives): add Sequence primitive with ordered steps"
```

---

### Task 3: Loop Primitive

**Files:**
- Modify: `src/agent_foundry/primitives/models.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_models.py`

**Dependencies:** Task 1

- [ ] **Step 1: Write the failing test**

Append to `tests/agent_foundry/primitives/test_primitive_models.py`:

```python
from agent_foundry.primitives.models import Primitive, Sequence, Loop


class ChangeSet(BaseModel):
    name: str
    steps: list[str]


class LoopInput(BaseModel):
    change_sets: list[ChangeSet]


class LoopOutput(BaseModel):
    change_sets: list[ChangeSet]


class TestLoop:
    """Loop primitive iterates over a collection in state."""

    def test_given_valid_config_when_created_then_succeeds(self):
        body = Primitive(name="body", input=StubInput, output=StubOutput)
        loop = Loop(
            name="cs_loop",
            input=LoopInput,
            output=LoopOutput,
            over=lambda state: state.change_sets,
            item_key="current_change_set",
            body=body,
        )
        assert loop.name == "cs_loop"
        assert loop.item_key == "current_change_set"
        assert loop.max_iterations == 100

    def test_given_string_ref_body_when_created_then_succeeds(self):
        loop = Loop(
            name="cs_loop",
            input=LoopInput,
            output=LoopOutput,
            over=lambda state: state.change_sets,
            item_key="current_change_set",
            body="implement_change_set",
        )
        assert loop.body == "implement_change_set"

    def test_given_custom_max_iterations_when_created_then_stored(self):
        loop = Loop(
            name="cs_loop",
            input=LoopInput,
            output=LoopOutput,
            over=lambda state: state.change_sets,
            item_key="current_change_set",
            body="body_ref",
            max_iterations=50,
        )
        assert loop.max_iterations == 50

    def test_given_zero_max_iterations_when_created_then_raises(self):
        with pytest.raises(ValidationError):
            Loop(
                name="bad",
                input=LoopInput,
                output=LoopOutput,
                over=lambda state: state.change_sets,
                item_key="current_change_set",
                body="body_ref",
                max_iterations=0,
            )

    def test_given_empty_item_key_when_created_then_raises(self):
        with pytest.raises(ValidationError):
            Loop(
                name="bad",
                input=LoopInput,
                output=LoopOutput,
                over=lambda state: state.change_sets,
                item_key="",
                body="body_ref",
            )

    def test_given_missing_over_when_created_then_raises(self):
        with pytest.raises(ValidationError):
            Loop(
                name="bad",
                input=LoopInput,
                output=LoopOutput,
                item_key="item",
                body="body_ref",
            )

    def test_over_callable_is_invocable(self):
        loop = Loop(
            name="cs_loop",
            input=LoopInput,
            output=LoopOutput,
            over=lambda state: state.change_sets,
            item_key="current_change_set",
            body="body_ref",
        )
        state = LoopInput(change_sets=[ChangeSet(name="cs1", steps=["s1"])])
        result = loop.over(state)
        assert len(result) == 1
        assert result[0].name == "cs1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_models.py::TestLoop -x`
Expected: FAIL with `ImportError: cannot import name 'Loop'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/agent_foundry/primitives/models.py`:

```python
from collections.abc import Callable


class Loop(Primitive):
    """Iterate over a collection in state, executing body per item.

    The ``over`` callable extracts the collection from the input state.
    The ``item_key`` names the state key that each item is bound to
    during iteration.  The body can be a Primitive instance or a string
    reference.
    """

    over: Callable
    item_key: str = Field(min_length=1)
    body: Primitive | str
    max_iterations: int = Field(default=100, ge=1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_models.py::TestLoop -x`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/primitives/models.py tests/agent_foundry/primitives/test_primitive_models.py
git commit -m "feat(primitives): add Loop primitive with over, item_key, body"
```

---

### Task 4: Retry Primitive

**Files:**
- Modify: `src/agent_foundry/primitives/models.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_models.py`

**Dependencies:** Task 1

- [ ] **Step 1: Write the failing test**

Append to `tests/agent_foundry/primitives/test_primitive_models.py`:

```python
from agent_foundry.primitives.models import Primitive, Sequence, Loop, Retry


class RetryInput(BaseModel):
    findings: list[str]
    no_must_fix: bool


class RetryOutput(BaseModel):
    findings: list[str]
    no_must_fix: bool


class TestRetry:
    """Retry primitive repeats body until condition met or exhausted."""

    def test_given_valid_config_when_created_then_succeeds(self):
        retry = Retry(
            name="review_fix",
            input=RetryInput,
            output=RetryOutput,
            max_attempts=2,
            until=lambda state: state.no_must_fix,
            body="review_and_fix",
            on_exhausted="escalate",
        )
        assert retry.name == "review_fix"
        assert retry.max_attempts == 2
        assert retry.on_exhausted == "escalate"

    def test_given_primitive_body_when_created_then_succeeds(self):
        body = Primitive(name="body", input=StubInput, output=StubOutput)
        retry = Retry(
            name="review_fix",
            input=RetryInput,
            output=RetryOutput,
            max_attempts=2,
            until=lambda state: state.no_must_fix,
            body=body,
            on_exhausted="escalate",
        )
        assert isinstance(retry.body, Primitive)

    def test_until_callable_is_invocable(self):
        retry = Retry(
            name="review_fix",
            input=RetryInput,
            output=RetryOutput,
            max_attempts=2,
            until=lambda state: state.no_must_fix,
            body="review_and_fix",
            on_exhausted="escalate",
        )
        state = RetryInput(findings=[], no_must_fix=True)
        assert retry.until(state) is True

    def test_given_zero_max_attempts_when_created_then_raises(self):
        with pytest.raises(ValidationError):
            Retry(
                name="bad",
                input=RetryInput,
                output=RetryOutput,
                max_attempts=0,
                until=lambda state: state.no_must_fix,
                body="body",
                on_exhausted="escalate",
            )

    def test_given_missing_on_exhausted_when_created_then_raises(self):
        with pytest.raises(ValidationError):
            Retry(
                name="bad",
                input=RetryInput,
                output=RetryOutput,
                max_attempts=2,
                until=lambda state: state.no_must_fix,
                body="body",
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_models.py::TestRetry -x`
Expected: FAIL with `ImportError: cannot import name 'Retry'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/agent_foundry/primitives/models.py`:

```python
class Retry(Primitive):
    """Execute body, evaluate condition, repeat up to max_attempts times.

    The ``until`` callable checks a condition on the state — when it returns
    True, the retry stops.  If max_attempts is exhausted without the condition
    being met, the ``on_exhausted`` action is taken (e.g. "escalate").
    """

    max_attempts: int = Field(ge=1)
    until: Callable
    body: Primitive | str
    on_exhausted: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_models.py::TestRetry -x`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/primitives/models.py tests/agent_foundry/primitives/test_primitive_models.py
git commit -m "feat(primitives): add Retry primitive with until condition and on_exhausted"
```

---

### Task 5: Conditional Primitive

**Files:**
- Modify: `src/agent_foundry/primitives/models.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_models.py`

**Dependencies:** Task 1

- [ ] **Step 1: Write the failing test**

Append to `tests/agent_foundry/primitives/test_primitive_models.py`:

```python
from agent_foundry.primitives.models import Primitive, Sequence, Loop, Retry, Conditional


class CondInput(BaseModel):
    has_findings: bool


class CondOutput(BaseModel):
    handled: bool


class TestConditional:
    """Conditional primitive branches based on state."""

    def test_given_both_branches_when_created_then_succeeds(self):
        cond = Conditional(
            name="check_findings",
            input=CondInput,
            output=CondOutput,
            condition=lambda state: state.has_findings,
            then_branch="handle_findings",
            else_branch="skip",
        )
        assert cond.name == "check_findings"
        assert cond.then_branch == "handle_findings"
        assert cond.else_branch == "skip"

    def test_given_no_else_branch_when_created_then_none(self):
        cond = Conditional(
            name="check_findings",
            input=CondInput,
            output=CondOutput,
            condition=lambda state: state.has_findings,
            then_branch="handle_findings",
        )
        assert cond.else_branch is None

    def test_given_primitive_branches_when_created_then_succeeds(self):
        then = Primitive(name="then", input=StubInput, output=StubOutput)
        else_ = Primitive(name="else", input=StubInput, output=StubOutput)
        cond = Conditional(
            name="check",
            input=CondInput,
            output=CondOutput,
            condition=lambda state: state.has_findings,
            then_branch=then,
            else_branch=else_,
        )
        assert isinstance(cond.then_branch, Primitive)
        assert isinstance(cond.else_branch, Primitive)

    def test_condition_callable_is_invocable(self):
        cond = Conditional(
            name="check",
            input=CondInput,
            output=CondOutput,
            condition=lambda state: state.has_findings,
            then_branch="handle",
        )
        state = CondInput(has_findings=True)
        assert cond.condition(state) is True

    def test_given_missing_then_branch_when_created_then_raises(self):
        with pytest.raises(ValidationError):
            Conditional(
                name="bad",
                input=CondInput,
                output=CondOutput,
                condition=lambda state: state.has_findings,
            )

    def test_given_missing_condition_when_created_then_raises(self):
        with pytest.raises(ValidationError):
            Conditional(
                name="bad",
                input=CondInput,
                output=CondOutput,
                then_branch="handle",
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_models.py::TestConditional -x`
Expected: FAIL with `ImportError: cannot import name 'Conditional'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/agent_foundry/primitives/models.py`:

```python
class Conditional(Primitive):
    """Branch based on a state condition.

    The ``condition`` callable evaluates the state and returns a boolean.
    If True, ``then_branch`` executes.  If False and ``else_branch`` is
    provided, it executes.  Otherwise, the primitive is a no-op.
    """

    condition: Callable
    then_branch: Primitive | str
    else_branch: Primitive | str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_models.py::TestConditional -x`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/primitives/models.py tests/agent_foundry/primitives/test_primitive_models.py
git commit -m "feat(primitives): add Conditional primitive with then/else branches"
```

---

### Task 6: Gate Primitive

**Files:**
- Modify: `src/agent_foundry/primitives/models.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_models.py`

**Dependencies:** Task 1

- [ ] **Step 1: Write the failing test**

Append to `tests/agent_foundry/primitives/test_primitive_models.py`:

```python
from agent_foundry.primitives.models import (
    Primitive, Sequence, Loop, Retry, Conditional, Gate,
)


class GateInput(BaseModel):
    must_fix_remain: bool
    escalation_context: str


class GateOutput(BaseModel):
    human_response: str


class TestGate:
    """Gate primitive blocks execution until external input."""

    def test_given_valid_config_when_created_then_succeeds(self):
        gate = Gate(
            name="escalate",
            input=GateInput,
            output=GateOutput,
            condition=lambda state: state.must_fix_remain,
            interaction="human_stdin",
            prompt_key="escalation_context",
        )
        assert gate.name == "escalate"
        assert gate.interaction == "human_stdin"
        assert gate.prompt_key == "escalation_context"

    def test_condition_callable_is_invocable(self):
        gate = Gate(
            name="escalate",
            input=GateInput,
            output=GateOutput,
            condition=lambda state: state.must_fix_remain,
            interaction="human_stdin",
            prompt_key="escalation_context",
        )
        state = GateInput(must_fix_remain=True, escalation_context="help")
        assert gate.condition(state) is True

    def test_given_false_condition_gate_is_skippable(self):
        gate = Gate(
            name="escalate",
            input=GateInput,
            output=GateOutput,
            condition=lambda state: state.must_fix_remain,
            interaction="human_stdin",
            prompt_key="escalation_context",
        )
        state = GateInput(must_fix_remain=False, escalation_context="")
        assert gate.condition(state) is False

    def test_given_missing_interaction_when_created_then_raises(self):
        with pytest.raises(ValidationError):
            Gate(
                name="bad",
                input=GateInput,
                output=GateOutput,
                condition=lambda state: state.must_fix_remain,
                prompt_key="escalation_context",
            )

    def test_given_missing_prompt_key_when_created_then_raises(self):
        with pytest.raises(ValidationError):
            Gate(
                name="bad",
                input=GateInput,
                output=GateOutput,
                condition=lambda state: state.must_fix_remain,
                interaction="human_stdin",
            )

    def test_given_empty_interaction_when_created_then_raises(self):
        with pytest.raises(ValidationError):
            Gate(
                name="bad",
                input=GateInput,
                output=GateOutput,
                condition=lambda state: state.must_fix_remain,
                interaction="",
                prompt_key="escalation_context",
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_models.py::TestGate -x`
Expected: FAIL with `ImportError: cannot import name 'Gate'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/agent_foundry/primitives/models.py`:

```python
class Gate(Primitive):
    """Block execution until external input is received.

    The ``condition`` callable determines whether the gate activates.
    If True, execution blocks and ``prompt_key`` identifies which state
    field to display to the human.  The ``interaction`` field specifies
    the interaction method (e.g. "human_stdin").
    """

    condition: Callable
    interaction: str = Field(min_length=1)
    prompt_key: str = Field(min_length=1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_models.py::TestGate -x`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/primitives/models.py tests/agent_foundry/primitives/test_primitive_models.py
git commit -m "feat(primitives): add Gate primitive with condition and interaction"
```

---

### Task 7: Action Primitive

**Files:**
- Modify: `src/agent_foundry/primitives/models.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_models.py`

**Dependencies:** Task 1

- [ ] **Step 1: Write the failing test**

Append to `tests/agent_foundry/primitives/test_primitive_models.py`:

```python
from agent_foundry.primitives.models import (
    Primitive, Sequence, Loop, Retry, Conditional, Gate, Action,
)


class CommitInput(BaseModel):
    workspace_volume: str


class CommitOutput(BaseModel):
    commit_hash: str


def fake_commit(state: CommitInput) -> CommitOutput:
    return CommitOutput(commit_hash="abc123")


class TestAction:
    """Action primitive wraps a deterministic, non-AI function."""

    def test_given_valid_function_when_created_then_succeeds(self):
        action = Action(
            name="commit",
            input=CommitInput,
            output=CommitOutput,
            function=fake_commit,
        )
        assert action.name == "commit"
        assert callable(action.function)

    def test_function_is_invocable(self):
        action = Action(
            name="commit",
            input=CommitInput,
            output=CommitOutput,
            function=fake_commit,
        )
        result = action.function(CommitInput(workspace_volume="vol-1"))
        assert result.commit_hash == "abc123"

    def test_given_lambda_function_when_created_then_succeeds(self):
        action = Action(
            name="noop",
            input=StubInput,
            output=StubOutput,
            function=lambda state: StubOutput(result="done"),
        )
        result = action.function(StubInput(value="test"))
        assert result.result == "done"

    def test_given_missing_function_when_created_then_raises(self):
        with pytest.raises(ValidationError):
            Action(
                name="bad",
                input=CommitInput,
                output=CommitOutput,
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_models.py::TestAction -x`
Expected: FAIL with `ImportError: cannot import name 'Action'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/agent_foundry/primitives/models.py`:

```python
class Action(Primitive):
    """A deterministic, non-AI step.

    Wraps a plain function that transforms input state to output state
    without invoking an LLM.  Used for operations like git commit,
    PR submission, file generation.
    """

    function: Callable
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_models.py::TestAction -x`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/primitives/models.py tests/agent_foundry/primitives/test_primitive_models.py
git commit -m "feat(primitives): add Action primitive wrapping deterministic functions"
```

---

### Task 8: Forward Reference Resolution (model_rebuild)

**Files:**
- Modify: `src/agent_foundry/primitives/models.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_models.py`

**Dependencies:** Tasks 1-7

- [ ] **Step 1: Write the failing test**

Append to `tests/agent_foundry/primitives/test_primitive_models.py`:

```python
class TestForwardReferences:
    """Primitives can be nested recursively via forward references."""

    def test_sequence_containing_loop(self):
        loop = Loop(
            name="step_loop",
            input=LoopInput,
            output=LoopOutput,
            over=lambda state: state.change_sets,
            item_key="current",
            body="inner_seq",
        )
        seq = Sequence(
            name="outer",
            input=StubInput,
            output=StubOutput,
            steps=[loop, "submit_pr"],
        )
        assert isinstance(seq.steps[0], Loop)
        assert seq.steps[1] == "submit_pr"

    def test_retry_containing_sequence(self):
        inner_seq = Sequence(
            name="fix_seq",
            input=StubInput,
            output=StubOutput,
            steps=["planner", "test_agent", "implementer"],
        )
        retry = Retry(
            name="review_fix",
            input=RetryInput,
            output=RetryOutput,
            max_attempts=2,
            until=lambda state: state.no_must_fix,
            body=inner_seq,
            on_exhausted="escalate",
        )
        assert isinstance(retry.body, Sequence)
        assert retry.body.name == "fix_seq"

    def test_sequence_containing_conditional_containing_loop(self):
        loop = Loop(
            name="fix_loop",
            input=LoopInput,
            output=LoopOutput,
            over=lambda state: state.change_sets,
            item_key="current",
            body="implement_task",
        )
        cond = Conditional(
            name="check",
            input=CondInput,
            output=CondOutput,
            condition=lambda state: state.has_findings,
            then_branch=loop,
        )
        seq = Sequence(
            name="pipeline",
            input=StubInput,
            output=StubOutput,
            steps=["reviewer", cond],
        )
        assert isinstance(seq.steps[1], Conditional)
        assert isinstance(seq.steps[1].then_branch, Loop)
```

- [ ] **Step 2: Run test to verify it passes (or fails if rebuild needed)**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_models.py::TestForwardReferences -x`
Expected: Should PASS since all types are defined in the same module with `from __future__ import annotations`. If it fails due to forward reference issues, add `Sequence.model_rebuild()` etc. at the bottom of models.py.

- [ ] **Step 3: Add model_rebuild calls if needed**

Append to bottom of `src/agent_foundry/primitives/models.py`:

```python
# Resolve forward references for recursive primitive nesting.
Sequence.model_rebuild()
Loop.model_rebuild()
Retry.model_rebuild()
Conditional.model_rebuild()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_models.py::TestForwardReferences -x`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/primitives/models.py tests/agent_foundry/primitives/test_primitive_models.py
git commit -m "feat(primitives): resolve forward references for recursive nesting"
```

---

### Task 9: PrimitivePlan Container

**Files:**
- Create: `src/agent_foundry/primitives/plan.py`
- Create: `tests/agent_foundry/primitives/test_primitive_plan.py`

**Dependencies:** Tasks 1-8

- [ ] **Step 1: Write the failing test**

```python
"""Tests for PrimitivePlan container and reference resolution."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from agent_foundry.primitives.models import (
    Action,
    Conditional,
    Gate,
    Loop,
    Primitive,
    Retry,
    Sequence,
)
from agent_foundry.primitives.plan import PrimitivePlan


class In(BaseModel):
    value: str


class Out(BaseModel):
    result: str


class TestPrimitivePlan:
    """PrimitivePlan holds a root primitive and resolves named references."""

    def test_given_root_primitive_when_created_then_succeeds(self):
        root = Primitive(name="root", input=In, output=Out)
        plan = PrimitivePlan(root=root)
        assert plan.root.name == "root"

    def test_resolve_finds_root_by_name(self):
        root = Primitive(name="root", input=In, output=Out)
        plan = PrimitivePlan(root=root)
        assert plan.resolve("root") is root

    def test_resolve_finds_nested_primitive_by_name(self):
        inner = Primitive(name="inner", input=In, output=Out)
        seq = Sequence(name="outer", input=In, output=Out, steps=[inner, "ref"])
        plan = PrimitivePlan(root=seq)
        assert plan.resolve("inner") is inner

    def test_resolve_finds_deeply_nested_primitive(self):
        deep = Primitive(name="deep", input=In, output=Out)
        inner_seq = Sequence(name="inner_seq", input=In, output=Out, steps=[deep])
        loop = Loop(
            name="loop",
            input=In,
            output=Out,
            over=lambda s: [],
            item_key="item",
            body=inner_seq,
        )
        root = Sequence(name="root", input=In, output=Out, steps=[loop])
        plan = PrimitivePlan(root=root)
        assert plan.resolve("deep") is deep
        assert plan.resolve("inner_seq") is inner_seq
        assert plan.resolve("loop") is loop

    def test_resolve_unknown_name_returns_none(self):
        root = Primitive(name="root", input=In, output=Out)
        plan = PrimitivePlan(root=root)
        assert plan.resolve("nonexistent") is None

    def test_all_primitives_returns_complete_registry(self):
        inner = Primitive(name="inner", input=In, output=Out)
        seq = Sequence(name="outer", input=In, output=Out, steps=[inner])
        plan = PrimitivePlan(root=seq)
        all_prims = plan.all_primitives()
        names = {p.name for p in all_prims}
        assert names == {"outer", "inner"}

    def test_duplicate_names_detected(self):
        dup1 = Primitive(name="same", input=In, output=Out)
        dup2 = Primitive(name="same", input=In, output=Out)
        seq = Sequence(name="root", input=In, output=Out, steps=[dup1, dup2])
        plan = PrimitivePlan(root=seq)
        with pytest.raises(ValueError, match="Duplicate primitive name"):
            plan.validate_unique_names()

    def test_resolve_through_retry_body(self):
        inner = Primitive(name="inner", input=In, output=Out)
        retry = Retry(
            name="retry",
            input=In,
            output=Out,
            max_attempts=2,
            until=lambda s: True,
            body=inner,
            on_exhausted="fail",
        )
        plan = PrimitivePlan(root=retry)
        assert plan.resolve("inner") is inner

    def test_resolve_through_conditional_branches(self):
        then = Primitive(name="then_prim", input=In, output=Out)
        else_ = Primitive(name="else_prim", input=In, output=Out)
        cond = Conditional(
            name="cond",
            input=In,
            output=Out,
            condition=lambda s: True,
            then_branch=then,
            else_branch=else_,
        )
        plan = PrimitivePlan(root=cond)
        assert plan.resolve("then_prim") is then
        assert plan.resolve("else_prim") is else_
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_plan.py -x`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_foundry.primitives.plan'`

- [ ] **Step 3: Write minimal implementation**

`src/agent_foundry/primitives/plan.py`:

```python
"""PrimitivePlan — top-level container for a primitive graph."""

from __future__ import annotations

from agent_foundry.primitives.models import (
    Conditional,
    Loop,
    Primitive,
    Retry,
    Sequence,
)


class PrimitivePlan:
    """Holds a root primitive and provides name-based resolution.

    Walks the primitive graph to build an index of all named primitives,
    enabling reference resolution at compile time.
    """

    def __init__(self, root: Primitive) -> None:
        self.root = root
        self._index: dict[str, Primitive] | None = None

    def resolve(self, name: str) -> Primitive | None:
        """Find a primitive by name, or return None."""
        return self._build_index().get(name)

    def all_primitives(self) -> list[Primitive]:
        """Return all primitives in the graph."""
        return list(self._build_index().values())

    def validate_unique_names(self) -> None:
        """Raise ValueError if any primitive names are duplicated."""
        seen: dict[str, int] = {}
        for prim in self._walk(self.root):
            seen[prim.name] = seen.get(prim.name, 0) + 1
        duplicates = [name for name, count in seen.items() if count > 1]
        if duplicates:
            raise ValueError(f"Duplicate primitive name(s): {', '.join(duplicates)}")

    def _build_index(self) -> dict[str, Primitive]:
        if self._index is None:
            self._index = {p.name: p for p in self._walk(self.root)}
        return self._index

    def _walk(self, prim: Primitive) -> list[Primitive]:
        """Recursively collect all Primitive instances in the graph."""
        result = [prim]
        if isinstance(prim, Sequence):
            for step in prim.steps:
                if isinstance(step, Primitive):
                    result.extend(self._walk(step))
        elif isinstance(prim, Loop):
            if isinstance(prim.body, Primitive):
                result.extend(self._walk(prim.body))
        elif isinstance(prim, Retry):
            if isinstance(prim.body, Primitive):
                result.extend(self._walk(prim.body))
        elif isinstance(prim, Conditional):
            if isinstance(prim.then_branch, Primitive):
                result.extend(self._walk(prim.then_branch))
            if isinstance(prim.else_branch, Primitive):
                result.extend(self._walk(prim.else_branch))
        return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_plan.py -x`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/primitives/plan.py tests/agent_foundry/primitives/test_primitive_plan.py
git commit -m "feat(primitives): add PrimitivePlan with name resolution and graph walking"
```

---

### Task 10: Public API Exports and Full Test Suite Run

**Files:**
- Modify: `src/agent_foundry/primitives/__init__.py`

**Dependencies:** Tasks 1-9

- [ ] **Step 1: Write the failing test**

Append to `tests/agent_foundry/primitives/test_primitive_models.py`:

```python
class TestPublicAPI:
    """All primitives are importable from the package."""

    def test_import_from_package(self):
        from agent_foundry.primitives import (
            Action,
            Conditional,
            Gate,
            Loop,
            Primitive,
            PrimitivePlan,
            Retry,
            Sequence,
        )
        assert Primitive is not None
        assert Sequence is not None
        assert Loop is not None
        assert Retry is not None
        assert Conditional is not None
        assert Gate is not None
        assert Action is not None
        assert PrimitivePlan is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_models.py::TestPublicAPI -x`
Expected: FAIL with `ImportError: cannot import name 'Sequence' from 'agent_foundry.primitives'`

- [ ] **Step 3: Write minimal implementation**

Update `src/agent_foundry/primitives/__init__.py`:

```python
"""Composable, typed plan primitives for Agent Foundry."""

from agent_foundry.primitives.models import (
    Action,
    Conditional,
    Gate,
    Loop,
    Primitive,
    Retry,
    Sequence,
)
from agent_foundry.primitives.plan import PrimitivePlan

__all__ = [
    "Action",
    "Conditional",
    "Gate",
    "Loop",
    "Primitive",
    "PrimitivePlan",
    "Retry",
    "Sequence",
]
```

- [ ] **Step 4: Run full test suite to verify nothing is broken**

Run: `pdm run pytest tests/agent_foundry/primitives/ -v`
Expected: ALL PASS (total ~47 tests across both test files)

Run: `pdm run pytest tests/ -v`
Expected: ALL PASS (existing tests unaffected)

- [ ] **Step 5: Run linting and type checking**

Run: `pdm run lint`
Expected: Clean

Run: `pdm run typecheck`
Expected: Clean (or only pre-existing warnings)

- [ ] **Step 6: Commit**

```bash
git add src/agent_foundry/primitives/__init__.py tests/agent_foundry/primitives/test_primitive_models.py
git commit -m "feat(primitives): export public API from primitives package"
```

---

## Verification

After all tasks complete:

1. `pdm run pytest tests/agent_foundry/primitives/ -v` — all primitive tests pass
2. `pdm run pytest tests/ -v` — full suite passes, no regressions
3. `pdm run lint` — clean
4. `pdm run typecheck` — clean on new code
5. Manual verification: open a Python REPL and construct a nested primitive graph matching the Archipelago control flow:
   ```python
   from agent_foundry.primitives import *
   # Build implement_task -> step_loop -> review_fix -> gate -> sequence
   # Verify PrimitivePlan.resolve() finds all primitives by name
   ```
