# CS3: Primitive Compiler — Implementation Plan

> **Design:** docs/plans/2026-04-03-review-feedback-loop-design.md
> **Roadmap:** docs/plans/2026-04-03-review-feedback-loop-roadmap.md
> **For agents:** Use team-dev (parallel) or sdd (sequential) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Translate the typed primitive graph (from CS1/CS2) into an executable LangGraph `StateGraph`. The old `compile_plan(GraphWiringPlan)` path and all related code is deleted after the new compiler proves working (Task 8).

**Architecture — Direct to LangGraph:** The compiler walks the primitive tree recursively, generating LangGraph nodes and edges directly. No intermediate `GraphWiringPlan` — primitives are typed Python objects with Pydantic models, and the impedance mismatch with JSON Schema/string-based wiring would add complexity without benefit.

**Key design decisions:**
- `_compile_node()` returns `(entry_id, exit_id)` tuples — parents wire edges between children without knowing internal structure
- State type derived from union of root primitive's I and O model fields as `TypedDict(total=False)`
- Pydantic boundary validation at each primitive entry (construct model from state dict)
- Router functions close over condition callables directly — no state pollution with routing flags
- Loop/Retry iteration state tracked via closure dicts, reset on each graph invocation
- Gate auto-injects `MemorySaver` + `interrupt_before` when detected anywhere in tree

**Tech Stack:** Python 3.14, Pydantic >=2.12.5, langgraph >=1.1.2, pytest

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/agent_foundry/primitives/errors.py` | Modify | Add `PrimitiveCompilationError` |
| `src/agent_foundry/compiler/primitive_compiler.py` | Create | `compile_primitive()`, `run_primitive_plan()`, per-type compilers, helpers |
| `tests/agent_foundry/primitives/test_primitive_compiler.py` | Create | All compiler tests |
| `src/agent_foundry/compiler/compiler.py` | Delete | Old `compile_plan(GraphWiringPlan)` path |
| `src/agent_foundry/compiler/errors.py` | Delete | Old compiler errors |
| `src/agent_foundry/compiler/templates.py` | Delete | Old template expansion |
| `src/agent_foundry/planner/` | Delete | Old `GraphWiringPlan`, `validate_plan()`, planner errors |
| `src/agent_foundry/demo/runner.py` | Delete | Old demo using `run_plan()` |
| 11 test files | Delete | Old compiler/planner/demo tests |

All paths relative to `/home/markn/engineering/jig-archipelago/agent-foundry/`.

---

### Task 1: Error Type + State Type Derivation + Boundary Validation

**Files:**
- Modify: `src/agent_foundry/primitives/errors.py`
- Create: `src/agent_foundry/compiler/primitive_compiler.py`
- Create: `tests/agent_foundry/primitives/test_primitive_compiler.py`

**Dependencies:** None

- [ ] **Step 1: Write the failing test**

```python
"""Tests for primitive compiler."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from agent_foundry.primitives.errors import PrimitiveCompilationError


# -- Test fixtures --


class InputState(BaseModel):
    query: str


class OutputState(BaseModel):
    query: str
    result: str


class CounterState(BaseModel):
    value: int
    count: int


# ======================================================================
# Error Types
# ======================================================================


class TestPrimitiveCompilationError:
    def test_is_exception(self):
        err = PrimitiveCompilationError("compilation failed", primitive_type="Action")
        assert isinstance(err, Exception)
        assert str(err) == "compilation failed"
        assert err.primitive_type == "Action"


# ======================================================================
# State Type Derivation
# ======================================================================


class TestDeriveStateType:
    def test_single_model(self):
        from agent_foundry.compiler.primitive_compiler import _derive_state_type

        state_type = _derive_state_type(CounterState, CounterState)
        hints = state_type.__annotations__
        assert "value" in hints
        assert "count" in hints

    def test_unions_input_and_output_fields(self):
        from agent_foundry.compiler.primitive_compiler import _derive_state_type

        state_type = _derive_state_type(InputState, OutputState)
        hints = state_type.__annotations__
        assert "query" in hints
        assert "result" in hints

    def test_annotations_are_any(self):
        from agent_foundry.compiler.primitive_compiler import _derive_state_type

        state_type = _derive_state_type(InputState, OutputState)
        hints = state_type.__annotations__
        for v in hints.values():
            assert v is Any


# ======================================================================
# Boundary Validation
# ======================================================================


class TestValidateBoundary:
    def test_valid_state(self):
        from agent_foundry.compiler.primitive_compiler import _validate_boundary

        result = _validate_boundary({"query": "hello"}, InputState, "test_node")
        assert result == {"query": "hello"}

    def test_extra_keys_preserved(self):
        """Extra keys pass through — LangGraph state may contain keys from other primitives."""
        from agent_foundry.compiler.primitive_compiler import _validate_boundary

        state = {"query": "hello", "other": "stuff"}
        result = _validate_boundary(state, InputState, "test_node")
        assert result["query"] == "hello"

    def test_missing_required_field_raises(self):
        from agent_foundry.compiler.primitive_compiler import _validate_boundary

        with pytest.raises(PrimitiveCompilationError):
            _validate_boundary({}, InputState, "test_node")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_compiler.py -x`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write minimal implementation**

Add to `src/agent_foundry/primitives/errors.py`:
```python
class PrimitiveCompilationError(Exception):
    """Raised when a primitive cannot be compiled or validated at runtime."""

    def __init__(self, message: str, primitive_type: str = ""):
        self.primitive_type = primitive_type
        super().__init__(message)
```

Create `src/agent_foundry/compiler/primitive_compiler.py`:
```python
"""Primitive compiler: translates typed primitive graphs into executable LangGraph."""

from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, ValidationError

from agent_foundry.primitives.errors import PrimitiveCompilationError


def _derive_state_type(
    input_type: type[BaseModel], output_type: type[BaseModel]
) -> type:
    """Derive a TypedDict(total=False) from the union of I and O model fields."""
    fields: dict[str, Any] = {}
    for model in (input_type, output_type):
        for name in model.model_fields:
            fields[name] = Any
    return TypedDict("PrimitiveState", fields, total=False)  # type: ignore[call-overload]


def _validate_boundary(
    state: dict[str, Any], model_type: type[BaseModel], node_id: str
) -> dict[str, Any]:
    """Validate state at a primitive boundary via Pydantic model construction.

    Validates that required fields are present and values conform to the model.
    Returns the original state dict (not stripped — LangGraph state may contain
    keys from other primitives in the graph).
    """
    try:
        model_type.model_validate(state)
    except ValidationError as e:
        raise PrimitiveCompilationError(
            f"Boundary validation failed at {node_id}: {e}",
            primitive_type=node_id,
        ) from e
    return state
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_compiler.py -x`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/primitives/errors.py src/agent_foundry/compiler/primitive_compiler.py tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "feat(compiler): add primitive compiler infrastructure (state derivation, boundary validation)"
```

---

### Task 2: Action Compilation

**Files:**
- Modify: `src/agent_foundry/compiler/primitive_compiler.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_compiler.py`

**Dependencies:** Task 1

- [ ] **Step 1: Write the failing test**

Append to test file:

```python
from agent_foundry.primitives.models import Action, Sequence
from agent_foundry.primitives.plan import PrimitivePlan
from agent_foundry.compiler.primitive_compiler import compile_primitive


class TransformOutput(BaseModel):
    result: str


class TestCompileAction:
    def test_returns_compiled_graph(self):
        action = Action[InputState, TransformOutput](
            function=lambda s: TransformOutput(result=s.query.upper()),
        )
        plan = PrimitivePlan(root=action)
        graph = compile_primitive(plan)
        assert hasattr(graph, "invoke")

    def test_invoke_produces_correct_output(self):
        action = Action[InputState, TransformOutput](
            function=lambda s: TransformOutput(result=s.query.upper()),
        )
        plan = PrimitivePlan(root=action)
        graph = compile_primitive(plan)
        result = graph.invoke({"query": "hello"})
        assert result["result"] == "HELLO"

    def test_validates_input_boundary(self):
        action = Action[InputState, TransformOutput](
            function=lambda s: TransformOutput(result=s.query.upper()),
        )
        plan = PrimitivePlan(root=action)
        graph = compile_primitive(plan)
        with pytest.raises(Exception):
            graph.invoke({})  # missing required 'query'

    def test_state_merges_output_fields(self):
        """Output fields merge into state; input fields persist."""
        action = Action[InputState, OutputState](
            function=lambda s: OutputState(query=s.query, result=s.query.upper()),
        )
        plan = PrimitivePlan(root=action)
        graph = compile_primitive(plan)
        result = graph.invoke({"query": "hello"})
        assert result["query"] == "hello"
        assert result["result"] == "HELLO"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_compiler.py::TestCompileAction -x`
Expected: FAIL with `ImportError` (no `compile_primitive`)

- [ ] **Step 3: Write minimal implementation**

Add to `primitive_compiler.py`:

```python
from langgraph.graph import END, StateGraph

from agent_foundry.primitives.models import (
    Action,
    Primitive,
    get_type_args,
)
from agent_foundry.primitives.plan import PrimitivePlan


def compile_primitive(plan: PrimitivePlan) -> Any:
    """Compile a PrimitivePlan into an executable LangGraph.

    Validates the primitive tree, then recursively compiles each primitive
    into LangGraph nodes and edges.
    """
    plan.validate()
    root = plan.root
    root_in, root_out = get_type_args(root)
    state_type = _derive_state_type(root_in, root_out)
    graph = StateGraph(state_type)

    entry_id, exit_id = _compile_node(graph, root, "root")
    graph.set_entry_point(entry_id)
    graph.add_edge(exit_id, END)
    return graph.compile()


def _compile_node(
    graph: StateGraph, prim: Primitive, prefix: str
) -> tuple[str, str]:
    """Compile a primitive into graph nodes/edges. Returns (entry_id, exit_id)."""
    if isinstance(prim, Action):
        return _compile_action(graph, prim, prefix)
    raise PrimitiveCompilationError(
        f"Unsupported primitive type: {type(prim).__name__}",
        primitive_type=type(prim).__name__,
    )


def _compile_action(
    graph: StateGraph, action: Action, prefix: str
) -> tuple[str, str]:
    node_id = prefix
    input_type, output_type = get_type_args(action)
    fn = action.function

    def node_fn(state: dict[str, Any]) -> dict[str, Any]:
        _validate_boundary(state, input_type, node_id)
        model_input = input_type.model_validate(state)
        result = fn(model_input)
        return result.model_dump()

    graph.add_node(node_id, node_fn)
    return (node_id, node_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_compiler.py::TestCompileAction -x`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/compiler/primitive_compiler.py tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "feat(compiler): add Action primitive compilation"
```

---

### Task 3: Sequence Compilation

**Files:**
- Modify: `src/agent_foundry/compiler/primitive_compiler.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_compiler.py`

**Dependencies:** Task 2

- [ ] **Step 1: Write the failing test**

```python
class MidState(BaseModel):
    query: str
    mid: str


class TestCompileSequence:
    def test_single_step(self):
        step = Action[InputState, TransformOutput](
            function=lambda s: TransformOutput(result=s.query.upper()),
        )
        seq = Sequence[InputState, TransformOutput](steps=[step])
        plan = PrimitivePlan(root=seq)
        graph = compile_primitive(plan)
        result = graph.invoke({"query": "hello"})
        assert result["result"] == "HELLO"

    def test_two_steps_chain(self):
        step1 = Action[InputState, MidState](
            function=lambda s: MidState(query=s.query, mid=s.query.upper()),
        )
        step2 = Action[MidState, OutputState](
            function=lambda s: OutputState(query=s.mid, result=f"processed:{s.mid}"),
        )
        seq = Sequence[InputState, OutputState](steps=[step1, step2])
        plan = PrimitivePlan(root=seq)
        graph = compile_primitive(plan)
        result = graph.invoke({"query": "hello"})
        assert result["result"] == "processed:HELLO"

    def test_three_steps_order(self):
        """Verify steps execute in order by accumulating into a list."""

        class ListState(BaseModel):
            items: list[str] = []

        def append_a(s: ListState) -> ListState:
            return ListState(items=[*s.items, "a"])

        def append_b(s: ListState) -> ListState:
            return ListState(items=[*s.items, "b"])

        def append_c(s: ListState) -> ListState:
            return ListState(items=[*s.items, "c"])

        s1 = Action[ListState, ListState](function=append_a)
        s2 = Action[ListState, ListState](function=append_b)
        s3 = Action[ListState, ListState](function=append_c)
        seq = Sequence[ListState, ListState](steps=[s1, s2, s3])
        plan = PrimitivePlan(root=seq)
        graph = compile_primitive(plan)
        result = graph.invoke({"items": []})
        assert result["items"] == ["a", "b", "c"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_compiler.py::TestCompileSequence -x`
Expected: FAIL with `PrimitiveCompilationError: Unsupported primitive type: Sequence`

- [ ] **Step 3: Write minimal implementation**

Add Sequence import and compilation:

```python
from agent_foundry.primitives.models import Action, Sequence, Primitive, get_type_args

def _compile_node(graph, prim, prefix):
    if isinstance(prim, Sequence):
        return _compile_sequence(graph, prim, prefix)
    if isinstance(prim, Action):
        return _compile_action(graph, prim, prefix)
    ...


def _compile_sequence(
    graph: StateGraph, seq: Sequence, prefix: str
) -> tuple[str, str]:
    first_entry = None
    prev_exit = None
    for i, step in enumerate(seq.steps):
        child_prefix = f"{prefix}_step_{i}"
        entry, exit_ = _compile_node(graph, step, child_prefix)
        if first_entry is None:
            first_entry = entry
        if prev_exit is not None:
            graph.add_edge(prev_exit, entry)
        prev_exit = exit_
    assert first_entry is not None
    assert prev_exit is not None
    return (first_entry, prev_exit)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_compiler.py::TestCompileSequence -x`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/compiler/primitive_compiler.py tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "feat(compiler): add Sequence primitive compilation"
```

---

### Task 4: Conditional Compilation

**Files:**
- Modify: `src/agent_foundry/compiler/primitive_compiler.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_compiler.py`

**Dependencies:** Task 2

- [ ] **Step 1: Write the failing test**

```python
from agent_foundry.primitives.models import Action, Conditional, Sequence


class BranchState(BaseModel):
    value: str
    flag: bool


class TestCompileConditional:
    def test_then_branch_taken(self):
        then = Action[BranchState, BranchState](
            function=lambda s: BranchState(value="then", flag=s.flag),
        )
        else_ = Action[BranchState, BranchState](
            function=lambda s: BranchState(value="else", flag=s.flag),
        )
        cond = Conditional[BranchState, BranchState](
            condition=lambda s: s.flag,
            then_branch=then,
            else_branch=else_,
        )
        plan = PrimitivePlan(root=cond)
        graph = compile_primitive(plan)
        result = graph.invoke({"value": "start", "flag": True})
        assert result["value"] == "then"

    def test_else_branch_taken(self):
        then = Action[BranchState, BranchState](
            function=lambda s: BranchState(value="then", flag=s.flag),
        )
        else_ = Action[BranchState, BranchState](
            function=lambda s: BranchState(value="else", flag=s.flag),
        )
        cond = Conditional[BranchState, BranchState](
            condition=lambda s: s.flag,
            then_branch=then,
            else_branch=else_,
        )
        plan = PrimitivePlan(root=cond)
        graph = compile_primitive(plan)
        result = graph.invoke({"value": "start", "flag": False})
        assert result["value"] == "else"

    def test_no_else_passthrough(self):
        """Condition false with no else branch: state passes through unchanged."""
        then = Action[BranchState, BranchState](
            function=lambda s: BranchState(value="detoured", flag=s.flag),
        )
        cond = Conditional[BranchState, BranchState](
            condition=lambda s: s.flag,
            then_branch=then,
        )
        plan = PrimitivePlan(root=cond)
        graph = compile_primitive(plan)
        result = graph.invoke({"value": "original", "flag": False})
        assert result["value"] == "original"

    def test_no_else_condition_true(self):
        then = Action[BranchState, BranchState](
            function=lambda s: BranchState(value="detoured", flag=s.flag),
        )
        cond = Conditional[BranchState, BranchState](
            condition=lambda s: s.flag,
            then_branch=then,
        )
        plan = PrimitivePlan(root=cond)
        graph = compile_primitive(plan)
        result = graph.invoke({"value": "original", "flag": True})
        assert result["value"] == "detoured"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_compiler.py::TestCompileConditional -x`
Expected: FAIL with `PrimitiveCompilationError: Unsupported primitive type: Conditional`

- [ ] **Step 3: Write minimal implementation**

```python
from agent_foundry.primitives.models import Conditional

def _compile_conditional(
    graph: StateGraph, cond: Conditional, prefix: str
) -> tuple[str, str]:
    input_type, _ = get_type_args(cond)
    router_id = f"{prefix}_router"
    merge_id = f"{prefix}_merge"

    # Compile branches
    then_entry, then_exit = _compile_node(graph, cond.then_branch, f"{prefix}_then")

    targets = [then_entry]
    if cond.else_branch is not None:
        else_entry, else_exit = _compile_node(graph, cond.else_branch, f"{prefix}_else")
        targets.append(else_entry)
    else:
        targets.append(merge_id)

    # Router node evaluates condition and routes
    condition_fn = cond.condition

    def router_fn(state: dict[str, Any]) -> str:
        model = input_type.model_validate(state)
        if condition_fn(model):
            return then_entry
        if cond.else_branch is not None:
            return else_entry
        return merge_id

    graph.add_node(router_id, lambda state: state)  # passthrough
    graph.add_conditional_edges(router_id, router_fn, targets)

    # Merge node
    graph.add_node(merge_id, lambda state: state)  # passthrough
    graph.add_edge(then_exit, merge_id)
    if cond.else_branch is not None:
        graph.add_edge(else_exit, merge_id)

    return (router_id, merge_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_compiler.py::TestCompileConditional -x`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/compiler/primitive_compiler.py tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "feat(compiler): add Conditional primitive compilation"
```

---

### Task 5: Loop Compilation

**Files:**
- Modify: `src/agent_foundry/compiler/primitive_compiler.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_compiler.py`

**Dependencies:** Task 2

- [ ] **Step 1: Write the failing test**

```python
from agent_foundry.primitives.models import Loop


class LoopInput(BaseModel):
    items: list[str]
    processed: list[str] = []
    current_item: str = ""


class TestCompileLoop:
    def test_iterates_over_collection(self):
        body = Action[LoopInput, LoopInput](
            function=lambda s: LoopInput(
                items=s.items,
                processed=[*s.processed, s.current_item.upper()],
                current_item=s.current_item,
            ),
        )
        loop = Loop[LoopInput, LoopInput](
            over=lambda s: s.items,
            item_key="current_item",
            body=body,
        )
        plan = PrimitivePlan(root=loop)
        graph = compile_primitive(plan)
        result = graph.invoke({"items": ["a", "b", "c"], "processed": []})
        assert result["processed"] == ["A", "B", "C"]

    def test_respects_max_iterations(self):
        body = Action[LoopInput, LoopInput](
            function=lambda s: LoopInput(
                items=s.items,
                processed=[*s.processed, s.current_item],
                current_item=s.current_item,
            ),
        )
        loop = Loop[LoopInput, LoopInput](
            over=lambda s: s.items,
            item_key="current_item",
            body=body,
            max_iterations=2,
        )
        plan = PrimitivePlan(root=loop)
        graph = compile_primitive(plan)
        result = graph.invoke({"items": ["a", "b", "c", "d", "e"], "processed": []})
        assert len(result["processed"]) == 2

    def test_empty_collection(self):
        body = Action[LoopInput, LoopInput](
            function=lambda s: LoopInput(
                items=s.items,
                processed=[*s.processed, s.current_item],
                current_item=s.current_item,
            ),
        )
        loop = Loop[LoopInput, LoopInput](
            over=lambda s: s.items,
            item_key="current_item",
            body=body,
        )
        plan = PrimitivePlan(root=loop)
        graph = compile_primitive(plan)
        result = graph.invoke({"items": [], "processed": []})
        assert result["processed"] == []

    def test_single_item(self):
        body = Action[LoopInput, LoopInput](
            function=lambda s: LoopInput(
                items=s.items,
                processed=[*s.processed, s.current_item.upper()],
                current_item=s.current_item,
            ),
        )
        loop = Loop[LoopInput, LoopInput](
            over=lambda s: s.items,
            item_key="current_item",
            body=body,
        )
        plan = PrimitivePlan(root=loop)
        graph = compile_primitive(plan)
        result = graph.invoke({"items": ["x"], "processed": []})
        assert result["processed"] == ["X"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_compiler.py::TestCompileLoop -x`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Loop compilation uses a controller node + body + increment node in a cycle:

```python
from agent_foundry.primitives.models import Loop

def _compile_loop(
    graph: StateGraph, loop: Loop, prefix: str
) -> tuple[str, str]:
    input_type, _ = get_type_args(loop)
    ctrl_id = f"{prefix}_ctrl"
    exit_id = f"{prefix}_exit"
    inc_id = f"{prefix}_inc"

    # Compile body
    body_entry, body_exit = _compile_node(graph, loop.body, f"{prefix}_body")

    # Closure state — reset-safe via list wrapper
    iter_state: dict[str, Any] = {"index": 0, "items": []}

    over_fn = loop.over
    item_key = loop.item_key
    max_iter = loop.max_iterations

    def ctrl_node(state: dict[str, Any]) -> dict[str, Any]:
        if iter_state["index"] == 0:
            model = input_type.model_validate(state)
            iter_state["items"] = over_fn(model)
        idx = iter_state["index"]
        if idx < len(iter_state["items"]) and idx < max_iter:
            return {**state, item_key: iter_state["items"][idx]}
        return state

    def router(state: dict[str, Any]) -> str:
        idx = iter_state["index"]
        if idx < len(iter_state["items"]) and idx < max_iter:
            return body_entry
        return exit_id

    def inc_node(state: dict[str, Any]) -> dict[str, Any]:
        iter_state["index"] += 1
        return state

    graph.add_node(ctrl_id, ctrl_node)
    graph.add_node(inc_id, inc_node)
    graph.add_node(exit_id, lambda state: state)

    graph.add_conditional_edges(ctrl_id, router, [body_entry, exit_id])
    graph.add_edge(body_exit, inc_id)
    graph.add_edge(inc_id, ctrl_id)

    return (ctrl_id, exit_id)
```

**Note:** The closure `iter_state` holds mutable state. This is safe for single invocations but means the compiled graph cannot be reused across invocations without resetting. We'll address reuse in Task 8 if needed.

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_compiler.py::TestCompileLoop -x`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/compiler/primitive_compiler.py tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "feat(compiler): add Loop primitive compilation"
```

---

### Task 6: Retry Compilation

**Files:**
- Modify: `src/agent_foundry/compiler/primitive_compiler.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_compiler.py`

**Dependencies:** Task 2

- [ ] **Step 1: Write the failing test**

```python
from agent_foundry.primitives.models import Retry


class RetryState(BaseModel):
    attempts: int = 0
    done: bool = False


class TestCompileRetry:
    def test_succeeds_first_attempt(self):
        body = Action[RetryState, RetryState](
            function=lambda s: RetryState(attempts=s.attempts + 1, done=True),
        )
        retry = Retry[RetryState, RetryState](
            max_attempts=3,
            until=lambda s: s.done,
            body=body,
            on_exhausted="escalate",
        )
        plan = PrimitivePlan(root=retry)
        graph = compile_primitive(plan)
        result = graph.invoke({"attempts": 0, "done": False})
        assert result["attempts"] == 1
        assert result["done"] is True

    def test_succeeds_second_attempt(self):
        call_count = {"n": 0}

        def body_fn(s: RetryState) -> RetryState:
            call_count["n"] += 1
            return RetryState(attempts=s.attempts + 1, done=call_count["n"] >= 2)

        body = Action[RetryState, RetryState](function=body_fn)
        retry = Retry[RetryState, RetryState](
            max_attempts=5,
            until=lambda s: s.done,
            body=body,
            on_exhausted="escalate",
        )
        plan = PrimitivePlan(root=retry)
        graph = compile_primitive(plan)
        result = graph.invoke({"attempts": 0, "done": False})
        assert result["attempts"] == 2
        assert result["done"] is True

    def test_exhausted_sets_action(self):
        body = Action[RetryState, RetryState](
            function=lambda s: RetryState(attempts=s.attempts + 1, done=False),
        )
        retry = Retry[RetryState, RetryState](
            max_attempts=2,
            until=lambda s: s.done,
            body=body,
            on_exhausted="escalate",
        )
        plan = PrimitivePlan(root=retry)
        graph = compile_primitive(plan)
        result = graph.invoke({"attempts": 0, "done": False})
        assert result["attempts"] == 2
        assert result.get("__exhausted_action") == "escalate"

    def test_max_attempts_one(self):
        body = Action[RetryState, RetryState](
            function=lambda s: RetryState(attempts=s.attempts + 1, done=False),
        )
        retry = Retry[RetryState, RetryState](
            max_attempts=1,
            until=lambda s: s.done,
            body=body,
            on_exhausted="error",
        )
        plan = PrimitivePlan(root=retry)
        graph = compile_primitive(plan)
        result = graph.invoke({"attempts": 0, "done": False})
        assert result["attempts"] == 1
        assert result.get("__exhausted_action") == "error"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_compiler.py::TestCompileRetry -x`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
from agent_foundry.primitives.models import Retry

def _compile_retry(
    graph: StateGraph, retry: Retry, prefix: str
) -> tuple[str, str]:
    input_type, _ = get_type_args(retry)
    check_id = f"{prefix}_check"
    exit_id = f"{prefix}_exit"
    exhausted_id = f"{prefix}_exhausted"

    # Compile body
    body_entry, body_exit = _compile_node(graph, retry.body, f"{prefix}_body")

    attempt = {"count": 0}
    until_fn = retry.until
    max_attempts = retry.max_attempts
    on_exhausted = retry.on_exhausted

    def check_node(state: dict[str, Any]) -> dict[str, Any]:
        attempt["count"] += 1
        return state

    def router(state: dict[str, Any]) -> str:
        model = input_type.model_validate(state)
        if until_fn(model):
            return exit_id
        if attempt["count"] >= max_attempts:
            return exhausted_id
        return body_entry

    def exhausted_node(state: dict[str, Any]) -> dict[str, Any]:
        return {**state, "__exhausted_action": on_exhausted}

    graph.add_node(check_id, check_node)
    graph.add_node(exit_id, lambda state: state)
    graph.add_node(exhausted_id, exhausted_node)

    # Flow: body → check → route(exit | exhausted | body)
    graph.add_edge(body_exit, check_id)
    graph.add_conditional_edges(check_id, router, [exit_id, exhausted_id, body_entry])
    graph.add_edge(exhausted_id, exit_id)

    # Entry: first attempt goes to body directly
    # We need a start node that routes to body on first entry
    start_id = f"{prefix}_start"
    graph.add_node(start_id, lambda state: state)
    graph.add_edge(start_id, body_entry)

    return (start_id, exit_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_compiler.py::TestCompileRetry -x`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/compiler/primitive_compiler.py tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "feat(compiler): add Retry primitive compilation with re-entry and exhaustion"
```

---

### Task 7: Gate Compilation

**Files:**
- Modify: `src/agent_foundry/compiler/primitive_compiler.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_compiler.py`

**Dependencies:** Task 2

- [ ] **Step 1: Write the failing test**

```python
from agent_foundry.primitives.models import Gate


class GateInput(BaseModel):
    should_block: bool
    escalation_context: str
    value: str = ""


class GateOutput(BaseModel):
    should_block: bool
    escalation_context: str
    value: str
    human_response: str = ""


class TestCompileGate:
    def test_condition_false_passes_through(self):
        gate = Gate[GateInput, GateOutput](
            condition=lambda s: s.should_block,
            interaction="human_stdin",
            prompt_key="escalation_context",
        )
        plan = PrimitivePlan(root=gate)
        graph = compile_primitive(plan)
        result = graph.invoke(
            {"should_block": False, "escalation_context": "help", "value": "ok"},
            config={"configurable": {"thread_id": "test-1"}},
        )
        assert result["value"] == "ok"

    def test_condition_true_interrupts(self):
        gate = Gate[GateInput, GateOutput](
            condition=lambda s: s.should_block,
            interaction="human_stdin",
            prompt_key="escalation_context",
        )
        plan = PrimitivePlan(root=gate)
        graph = compile_primitive(plan)
        # First invocation should interrupt (return partial state)
        result = graph.invoke(
            {"should_block": True, "escalation_context": "need help", "value": "stuck"},
            config={"configurable": {"thread_id": "test-2"}},
        )
        # Gate interrupts before the gate node — state reflects pre-gate
        assert result["escalation_context"] == "need help"

    def test_auto_injects_checkpointer(self):
        """Compile should succeed with a Gate — MemorySaver auto-injected."""
        gate = Gate[GateInput, GateOutput](
            condition=lambda s: s.should_block,
            interaction="human_stdin",
            prompt_key="escalation_context",
        )
        plan = PrimitivePlan(root=gate)
        # Should not raise — MemorySaver is auto-injected
        graph = compile_primitive(plan)
        assert graph is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_compiler.py::TestCompileGate -x`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Gate compilation + auto-detection of Gate presence:

```python
from langgraph.checkpoint.memory import MemorySaver
from agent_foundry.primitives.models import Gate

def compile_primitive(plan: PrimitivePlan) -> Any:
    plan.validate()
    root = plan.root
    root_in, root_out = get_type_args(root)
    state_type = _derive_state_type(root_in, root_out)
    graph = StateGraph(state_type)

    # Track gate node IDs during compilation
    gate_ids: list[str] = []
    entry_id, exit_id = _compile_node(graph, root, "root", gate_ids)
    graph.set_entry_point(entry_id)
    graph.add_edge(exit_id, END)

    # Auto-inject MemorySaver when Gates are present
    compile_kwargs: dict[str, Any] = {}
    if gate_ids:
        compile_kwargs["checkpointer"] = MemorySaver()
        compile_kwargs["interrupt_before"] = gate_ids

    return graph.compile(**compile_kwargs)


def _compile_node(graph, prim, prefix, gate_ids=None):
    if gate_ids is None:
        gate_ids = []
    if isinstance(prim, Gate):
        return _compile_gate(graph, prim, prefix, gate_ids)
    ...  # pass gate_ids through to all recursive calls


def _compile_gate(
    graph: StateGraph, gate: Gate, prefix: str, gate_ids: list[str]
) -> tuple[str, str]:
    input_type, _ = get_type_args(gate)
    gate_id = prefix
    condition_fn = gate.condition

    def gate_node(state: dict[str, Any]) -> dict[str, Any]:
        # The interrupt_before mechanism pauses BEFORE this node runs
        # when condition is True. When condition is False, pass through.
        return state

    graph.add_node(gate_id, gate_node)

    # Register for interrupt_before — but only if condition activates
    # For simplicity, always add to interrupt list; the condition check
    # happens in a pre-gate router
    check_id = f"{prefix}_check"
    pass_id = f"{prefix}_pass"

    def check_fn(state: dict[str, Any]) -> dict[str, Any]:
        return state

    def router(state: dict[str, Any]) -> str:
        model = input_type.model_validate(state)
        if condition_fn(model):
            return gate_id
        return pass_id

    graph.add_node(check_id, check_fn)
    graph.add_node(pass_id, lambda state: state)
    graph.add_conditional_edges(check_id, router, [gate_id, pass_id])

    # After gate, merge to a single exit
    merge_id = f"{prefix}_merge"
    graph.add_node(merge_id, lambda state: state)
    graph.add_edge(gate_id, merge_id)
    graph.add_edge(pass_id, merge_id)

    gate_ids.append(gate_id)
    return (check_id, merge_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_compiler.py::TestCompileGate -x`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/compiler/primitive_compiler.py tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "feat(compiler): add Gate primitive compilation with MemorySaver auto-injection"
```

---

### Task 8: Delete Old Compiler and Planner Code

**Files:**
- Delete: `src/agent_foundry/compiler/compiler.py` — old `compile_plan(GraphWiringPlan)` path
- Delete: `src/agent_foundry/compiler/errors.py` — old compiler errors (`PrimitiveCompilationError` lives in `primitives/errors.py`)
- Delete: `src/agent_foundry/compiler/templates.py` — old template expansion
- Delete: `src/agent_foundry/planner/` — entire directory (`GraphWiringPlan`, `validate_plan()`, planner errors)
- Delete: `src/agent_foundry/demo/runner.py` — old demo using `run_plan()`
- Delete: `tests/agent_foundry/test_compiler_basic.py`
- Delete: `tests/agent_foundry/test_compiler_advanced.py`
- Delete: `tests/agent_foundry/test_compiler_config_injection.py`
- Delete: `tests/agent_foundry/test_compiler_dynamic_resolution.py`
- Delete: `tests/agent_foundry/test_compiler_resolve_handler.py`
- Delete: `tests/agent_foundry/test_compiler_router.py`
- Delete: `tests/agent_foundry/test_compiler_typed_state.py`
- Delete: `tests/agent_foundry/test_wiring_plan.py`
- Delete: `tests/agent_foundry/test_wiring_plan_validation.py`
- Delete: `tests/agent_foundry/test_compile_time_validation.py`
- Delete: `tests/agent_foundry/test_decision_support_demo.py`
- Modify: `tests/agent_foundry/conftest.py` — remove `make_plan()` factory and `GraphWiringPlan` imports

**Keep (shared infrastructure, not coupled to old compiler):**
- `src/agent_foundry/registry/` — `RoleRegistry`, `RoleSpec`, `execute_role()` (used by both paths, needed for CS5-8)
- `src/agent_foundry/agents/connector.py` — `make_typed_connector()` (general abstraction)
- `src/agent_foundry/agents/protocol.py` — `TypedAgent` protocol (general abstraction)

**Dependencies:** Task 7 (all new LangGraph patterns established)

- [ ] **Step 1: Delete old compiler and planner source files**

```bash
git rm src/agent_foundry/compiler/compiler.py
git rm src/agent_foundry/compiler/errors.py
git rm src/agent_foundry/compiler/templates.py
git rm -r src/agent_foundry/planner/
git rm src/agent_foundry/demo/runner.py
```

- [ ] **Step 2: Delete old test files**

```bash
git rm tests/agent_foundry/test_compiler_basic.py
git rm tests/agent_foundry/test_compiler_advanced.py
git rm tests/agent_foundry/test_compiler_config_injection.py
git rm tests/agent_foundry/test_compiler_dynamic_resolution.py
git rm tests/agent_foundry/test_compiler_resolve_handler.py
git rm tests/agent_foundry/test_compiler_router.py
git rm tests/agent_foundry/test_compiler_typed_state.py
git rm tests/agent_foundry/test_wiring_plan.py
git rm tests/agent_foundry/test_wiring_plan_validation.py
git rm tests/agent_foundry/test_compile_time_validation.py
git rm tests/agent_foundry/test_decision_support_demo.py
```

- [ ] **Step 3: Clean up conftest.py**

Remove `make_plan()` factory and any `GraphWiringPlan` imports from `tests/agent_foundry/conftest.py`.

- [ ] **Step 4: Fix any broken imports**

Grep for remaining imports of deleted modules (`compile_plan`, `GraphWiringPlan`, `validate_plan`, `PlanCompilationError`, `RoleInstantiationError`, `StateSchemaViolationError`, `MaxIterationsExceededError`) and fix or remove them.

- [ ] **Step 5: Run full test suite**

Run: `pdm run pytest tests/ -q`
Expected: ALL PASS (reduced count — old tests deleted, new primitive tests still pass)

Run: `pdm run lint`
Expected: Clean

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(compiler): delete old GraphWiringPlan compiler and planner

Remove compile_plan(), GraphWiringPlan, validate_plan(), and all related
code. The new primitive compiler (compile_primitive) replaces this path.
Registry and agent protocol infrastructure retained for CS5-8.

11 test files deleted (~8,500 lines). Remaining tests pass."
```

---

### Task 9: Nested Composition + Graph Reuse Safety

**Files:**
- Modify: `tests/agent_foundry/primitives/test_primitive_compiler.py`

**Dependencies:** Tasks 2-8

- [ ] **Step 1: Write the failing test**

```python
class TestNestedComposition:
    def test_sequence_of_actions(self):
        """Three Actions in a Sequence."""

        class S(BaseModel):
            n: int = 0

        s1 = Action[S, S](function=lambda s: S(n=s.n + 1))
        s2 = Action[S, S](function=lambda s: S(n=s.n + 10))
        s3 = Action[S, S](function=lambda s: S(n=s.n + 100))
        seq = Sequence[S, S](steps=[s1, s2, s3])
        plan = PrimitivePlan(root=seq)
        graph = compile_primitive(plan)
        result = graph.invoke({"n": 0})
        assert result["n"] == 111

    def test_loop_body_is_sequence(self):
        """Loop whose body is a two-step Sequence."""

        class S(BaseModel):
            items: list[str] = []
            processed: list[str] = []
            current_item: str = ""

        step1 = Action[S, S](
            function=lambda s: S(
                items=s.items,
                processed=s.processed,
                current_item=s.current_item.upper(),
            ),
        )
        step2 = Action[S, S](
            function=lambda s: S(
                items=s.items,
                processed=[*s.processed, s.current_item],
                current_item=s.current_item,
            ),
        )
        body = Sequence[S, S](steps=[step1, step2])
        loop = Loop[S, S](over=lambda s: s.items, item_key="current_item", body=body)
        plan = PrimitivePlan(root=loop)
        graph = compile_primitive(plan)
        result = graph.invoke({"items": ["a", "b"], "processed": []})
        assert result["processed"] == ["A", "B"]

    def test_retry_body_is_sequence(self):

        class S(BaseModel):
            n: int = 0
            done: bool = False

        call_count = {"n": 0}

        def mark_done(s: S) -> S:
            call_count["n"] += 1
            return S(n=s.n, done=call_count["n"] >= 2)

        step1 = Action[S, S](function=lambda s: S(n=s.n + 1, done=s.done))
        step2 = Action[S, S](function=mark_done)
        body = Sequence[S, S](steps=[step1, step2])
        retry = Retry[S, S](
            max_attempts=5,
            until=lambda s: s.done,
            body=body,
            on_exhausted="escalate",
        )
        plan = PrimitivePlan(root=retry)
        graph = compile_primitive(plan)
        result = graph.invoke({"n": 0, "done": False})
        assert result["n"] == 2
        assert result["done"] is True

    def test_sequence_containing_conditional(self):

        class S(BaseModel):
            value: str = ""
            flag: bool = True

        step1 = Action[S, S](function=lambda s: S(value="step1", flag=s.flag))
        then = Action[S, S](function=lambda s: S(value=s.value + "_then", flag=s.flag))
        else_ = Action[S, S](function=lambda s: S(value=s.value + "_else", flag=s.flag))
        cond = Conditional[S, S](
            condition=lambda s: s.flag,
            then_branch=then,
            else_branch=else_,
        )
        step3 = Action[S, S](function=lambda s: S(value=s.value + "_done", flag=s.flag))
        seq = Sequence[S, S](steps=[step1, cond, step3])
        plan = PrimitivePlan(root=seq)
        graph = compile_primitive(plan)
        result = graph.invoke({"value": "", "flag": True})
        assert result["value"] == "step1_then_done"
```

- [ ] **Step 2: Run tests**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_compiler.py::TestNestedComposition -x`
Expected: PASS (4 tests) — no new production code needed

- [ ] **Step 3: Commit**

```bash
git add tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "test(compiler): add nested primitive composition tests"
```

---

### Task 10: `run_primitive_plan()` Entry Point + Exports

**Files:**
- Modify: `src/agent_foundry/compiler/primitive_compiler.py`
- Modify: `src/agent_foundry/primitives/__init__.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_compiler.py`

**Dependencies:** Tasks 1-9

- [ ] **Step 1: Write the failing test**

```python
from agent_foundry.compiler.primitive_compiler import run_primitive_plan
from agent_foundry.primitives.errors import PrimitiveValidationError


class TestRunPrimitivePlan:
    def test_compiles_and_invokes(self):
        action = Action[InputState, TransformOutput](
            function=lambda s: TransformOutput(result=s.query.upper()),
        )
        plan = PrimitivePlan(root=action)
        result = run_primitive_plan(plan, {"query": "hello"})
        assert result["result"] == "HELLO"

    def test_validates_before_compile(self):
        from agent_foundry.primitives.models import Primitive

        bad = Primitive[InputState, InputState]()
        bad_seq = Sequence[InputState, OutputState](steps=[bad])
        plan = PrimitivePlan(root=bad_seq)
        with pytest.raises(Exception):  # TypeMismatchError from validation
            run_primitive_plan(plan, {"query": "hello"})

    def test_default_empty_state(self):

        class EmptyIn(BaseModel):
            value: str = "default"

        class EmptyOut(BaseModel):
            value: str
            result: str

        action = Action[EmptyIn, EmptyOut](
            function=lambda s: EmptyOut(value=s.value, result=s.value.upper()),
        )
        plan = PrimitivePlan(root=action)
        result = run_primitive_plan(plan)
        assert result["result"] == "DEFAULT"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_compiler.py::TestRunPrimitivePlan -x`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write minimal implementation**

Add to `primitive_compiler.py`:

```python
def run_primitive_plan(
    plan: PrimitivePlan,
    initial_state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile and execute a PrimitivePlan."""
    graph = compile_primitive(plan)
    return graph.invoke(initial_state or {}, config=config or {})
```

Update `src/agent_foundry/primitives/__init__.py` to export `PrimitiveCompilationError`.

- [ ] **Step 4: Run full test suite**

Run: `pdm run pytest tests/agent_foundry/primitives/ -v`
Expected: ALL PASS

Run: `pdm run pytest tests/ -q`
Expected: ALL PASS, no regressions

Run: `pdm run lint`
Expected: Clean

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/compiler/primitive_compiler.py src/agent_foundry/primitives/__init__.py src/agent_foundry/primitives/errors.py tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "feat(compiler): add run_primitive_plan() entry point and exports"
```

---

## Verification

After all tasks complete:

1. `pdm run pytest tests/agent_foundry/primitives/ -v` — all primitive tests pass
2. `pdm run pytest tests/ -q` — full suite passes, no regressions
3. `pdm run lint` — clean
