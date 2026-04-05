# CS3: Primitive Compiler — Implementation Plan

> **Design:** docs/plans/2026-04-03-review-feedback-loop-design.md
> **Roadmap:** docs/plans/2026-04-03-review-feedback-loop-roadmap.md
> **For agents:** Use team-dev (parallel) or sdd (sequential) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update primitive models (rename Action → FunctionAction, Gate → GateAction, remove on_exhausted from Retry), then compile the typed primitive graph into an executable LangGraph `StateGraph` with a fully typed public API. The old `compile_plan(GraphWiringPlan)` path is deleted after the new compiler proves working.

**Architecture — Direct to LangGraph:** The compiler walks the primitive tree recursively, generating LangGraph nodes and edges directly. No intermediate `GraphWiringPlan`.

**Key design decisions:**
- **Typed public API**: `run_primitive_plan(plan, input: I) -> O` — Pydantic models in and out, no dicts exposed
- **Compiler registry**: `dict[type[Primitive], CompilerFn]` — extensible dispatch, no isinstance chains
- **`_compile_node()` returns `(entry_id, exit_id)` tuples** — parents wire LangGraph edges between children without knowing internal structure
- **State type** derived from union of root primitive's I and O model fields as `TypedDict(total=False)`
- **Pydantic boundary validation** at each primitive entry (construct model from state dict)
- **Router functions close over condition callables** — no state pollution with routing flags or magic string keys
- **Loop/Retry iteration** tracked via closure dicts
- **GateAction auto-injects `MemorySaver`** + `interrupt_before` when detected anywhere in tree
- **Retry exhaustion is domain state** — no `on_exhausted` field, parent reads output and routes

**Tech Stack:** Python 3.14, Pydantic >=2.12.5, langgraph >=1.1.2, pytest

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/agent_foundry/primitives/models.py` | Modify | Rename Action → FunctionAction, Gate → GateAction, remove on_exhausted from Retry |
| `src/agent_foundry/primitives/validators.py` | Modify | Update for renamed types, GateAction has no condition |
| `src/agent_foundry/primitives/__init__.py` | Modify | Update exports |
| `src/agent_foundry/primitives/errors.py` | Modify | Add `PrimitiveCompilationError` |
| `src/agent_foundry/compiler/primitive_compiler.py` | Create | `compile_primitive()`, `run_primitive_plan()`, compiler registry, per-type compilers |
| `tests/agent_foundry/primitives/test_primitive_models.py` | Modify | Update for renamed types |
| `tests/agent_foundry/primitives/test_primitive_validators.py` | Modify | Update for renamed types, GateAction changes |
| `tests/agent_foundry/primitives/test_primitive_compiler.py` | Create | All compiler tests |
| `src/agent_foundry/compiler/compiler.py` | Delete | Old `compile_plan(GraphWiringPlan)` path |
| `src/agent_foundry/compiler/errors.py` | Delete | Old compiler errors |
| `src/agent_foundry/compiler/templates.py` | Delete | Old template expansion |
| `src/agent_foundry/planner/` | Delete | Old `GraphWiringPlan`, `validate_plan()`, planner errors |
| `src/agent_foundry/demo/runner.py` | Delete | Old demo using `run_plan()` |
| 11 test files | Delete | Old compiler/planner/demo tests |

All paths relative to `/home/markn/engineering/jig-archipelago/agent-foundry/`.

---

### Task 1: Rename Action → FunctionAction, Gate → GateAction, Remove on_exhausted

**Files:**
- Modify: `src/agent_foundry/primitives/models.py`
- Modify: `src/agent_foundry/primitives/validators.py`
- Modify: `src/agent_foundry/primitives/__init__.py`
- Modify: `src/agent_foundry/primitives/plan.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_models.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_validators.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_plan.py`

**Dependencies:** None

**Changes to models.py:**
- Rename `Action` class to `FunctionAction`
- Rename `Gate` class to `GateAction`
- Remove `condition: Callable[[I], bool]` from GateAction (always blocks when reached)
- Remove `on_exhausted: str` from Retry
- Update `model_rebuild()` calls at bottom of file

**Changes to validators.py:**
- Update `_validate_gate` → `_validate_gate_action` — only validates `prompt_key` (no condition to check)
- Update isinstance checks for renamed types

**Changes to tests:**
- Rename all `Action[` → `FunctionAction[` in test fixtures
- Rename all `Gate[` → `GateAction[` in test fixtures
- Remove `condition=` from GateAction test construction
- Remove `on_exhausted=` from Retry test construction
- Update import statements

- [ ] **Step 1: Update models.py**
- [ ] **Step 2: Update validators.py**
- [ ] **Step 3: Update plan.py**
- [ ] **Step 4: Update __init__.py exports**
- [ ] **Step 5: Update all test files**
- [ ] **Step 6: Run full test suite**

Run: `pdm run pytest tests/ -q`
Expected: ALL PASS

Run: `pdm run lint`
Expected: Clean

- [ ] **Step 7: Commit**

```bash
git add src/agent_foundry/primitives/ tests/agent_foundry/primitives/
git commit -m "refactor(primitives): rename Action to FunctionAction, Gate to GateAction, remove on_exhausted

Action → FunctionAction: clarifies it's one action variant among many.
Gate → GateAction: reclassified as a leaf action, not structural primitive.
Remove condition from GateAction: always blocks, routing is parent's job.
Remove on_exhausted from Retry: parent reads domain state to route."
```

---

### Task 2: Compiler Infrastructure (Error Type, State Derivation, Registry, Boundary Validation)

**Files:**
- Modify: `src/agent_foundry/primitives/errors.py`
- Create: `src/agent_foundry/compiler/primitive_compiler.py`
- Create: `tests/agent_foundry/primitives/test_primitive_compiler.py`

**Dependencies:** Task 1

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
        err = PrimitiveCompilationError("compilation failed", primitive_type="FunctionAction")
        assert isinstance(err, Exception)
        assert str(err) == "compilation failed"
        assert err.primitive_type == "FunctionAction"


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
# Compiler Registry
# ======================================================================


class TestCompilerRegistry:
    def test_register_and_retrieve(self):
        from agent_foundry.compiler.primitive_compiler import (
            _compiler_registry,
            register_compiler,
        )
        from agent_foundry.primitives.models import FunctionAction

        # FunctionAction should be registered by module load
        assert FunctionAction in _compiler_registry

    def test_unknown_type_raises(self):
        from agent_foundry.compiler.primitive_compiler import compile_primitive
        from agent_foundry.primitives.models import Primitive
        from agent_foundry.primitives.plan import PrimitivePlan

        # Base Primitive has no registered compiler
        prim = Primitive[InputState, InputState]()
        plan = PrimitivePlan(root=prim)
        with pytest.raises(PrimitiveCompilationError, match="No compiler registered"):
            compile_primitive(plan)


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

from collections.abc import Callable
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, ValidationError

from agent_foundry.primitives.errors import PrimitiveCompilationError
from agent_foundry.primitives.models import Primitive, get_type_args
from agent_foundry.primitives.plan import PrimitivePlan

# -- Compiler registry --

type CompilerFn = Callable[[StateGraph, Primitive, str, list[str]], tuple[str, str]]

_compiler_registry: dict[type[Primitive], CompilerFn] = {}


def register_compiler(
    prim_type: type[Primitive], compiler_fn: CompilerFn
) -> None:
    """Register a compiler function for a primitive type."""
    _compiler_registry[prim_type] = compiler_fn


# -- Helpers --


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
    """Validate state at a primitive boundary via Pydantic model construction."""
    try:
        model_type.model_validate(state)
    except ValidationError as e:
        raise PrimitiveCompilationError(
            f"Boundary validation failed at {node_id}: {e}",
            primitive_type=node_id,
        ) from e
    return state


def _compile_node(
    graph: StateGraph, prim: Primitive, prefix: str, gate_ids: list[str]
) -> tuple[str, str]:
    """Compile a primitive into graph nodes/edges. Returns (entry_id, exit_id)."""
    compiler = _compiler_registry.get(type(prim))
    if compiler is None:
        raise PrimitiveCompilationError(
            f"No compiler registered for {type(prim).__name__}",
            primitive_type=type(prim).__name__,
        )
    return compiler(graph, prim, prefix, gate_ids)


# -- Entry points --


def compile_primitive(plan: PrimitivePlan) -> Any:
    """Compile a PrimitivePlan into an executable LangGraph."""
    plan.validate()
    root = plan.root
    root_in, root_out = get_type_args(root)
    state_type = _derive_state_type(root_in, root_out)
    graph = StateGraph(state_type)

    gate_ids: list[str] = []
    entry_id, exit_id = _compile_node(graph, root, "root", gate_ids)
    graph.set_entry_point(entry_id)
    graph.add_edge(exit_id, END)

    compile_kwargs: dict[str, Any] = {}
    if gate_ids:
        from langgraph.checkpoint.memory import MemorySaver

        compile_kwargs["checkpointer"] = MemorySaver()
        compile_kwargs["interrupt_before"] = gate_ids

    return graph.compile(**compile_kwargs)


def run_primitive_plan(
    plan: PrimitivePlan,
    initial_state: BaseModel | None = None,
    config: dict[str, Any] | None = None,
) -> BaseModel:
    """Compile and execute a PrimitivePlan with typed input/output."""
    root_in, root_out = get_type_args(plan.root)
    graph = compile_primitive(plan)

    input_dict = initial_state.model_dump() if initial_state is not None else {}
    result_dict = graph.invoke(input_dict, config=config or {})
    return root_out.model_validate(result_dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_compiler.py -x`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/primitives/errors.py src/agent_foundry/compiler/primitive_compiler.py tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "feat(compiler): add compiler infrastructure (registry, state derivation, boundary validation)"
```

---

### Task 3: FunctionAction Compilation

**Files:**
- Modify: `src/agent_foundry/compiler/primitive_compiler.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_compiler.py`

**Dependencies:** Task 2

- [ ] **Step 1: Write the failing test**

```python
from agent_foundry.primitives.models import FunctionAction, Sequence
from agent_foundry.primitives.plan import PrimitivePlan
from agent_foundry.compiler.primitive_compiler import compile_primitive, run_primitive_plan


class TransformOutput(BaseModel):
    result: str


class TestCompileFunctionAction:
    def test_returns_compiled_graph(self):
        action = FunctionAction[InputState, TransformOutput](
            function=lambda s: TransformOutput(result=s.query.upper()),
        )
        plan = PrimitivePlan(root=action)
        graph = compile_primitive(plan)
        assert hasattr(graph, "invoke")

    def test_invoke_produces_correct_output(self):
        action = FunctionAction[InputState, TransformOutput](
            function=lambda s: TransformOutput(result=s.query.upper()),
        )
        plan = PrimitivePlan(root=action)
        graph = compile_primitive(plan)
        result = graph.invoke({"query": "hello"})
        assert result["result"] == "HELLO"

    def test_validates_input_boundary(self):
        action = FunctionAction[InputState, TransformOutput](
            function=lambda s: TransformOutput(result=s.query.upper()),
        )
        plan = PrimitivePlan(root=action)
        graph = compile_primitive(plan)
        with pytest.raises(Exception):
            graph.invoke({})  # missing required 'query'

    def test_run_primitive_plan_typed(self):
        """run_primitive_plan accepts and returns Pydantic models."""
        action = FunctionAction[InputState, TransformOutput](
            function=lambda s: TransformOutput(result=s.query.upper()),
        )
        plan = PrimitivePlan(root=action)
        result = run_primitive_plan(plan, InputState(query="hello"))
        assert isinstance(result, TransformOutput)
        assert result.result == "HELLO"

    def test_run_primitive_plan_default_input(self):
        class DefaultInput(BaseModel):
            value: str = "default"

        class DefaultOutput(BaseModel):
            value: str
            result: str

        action = FunctionAction[DefaultInput, DefaultOutput](
            function=lambda s: DefaultOutput(value=s.value, result=s.value.upper()),
        )
        plan = PrimitivePlan(root=action)
        result = run_primitive_plan(plan)
        assert isinstance(result, DefaultOutput)
        assert result.result == "DEFAULT"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_compiler.py::TestCompileFunctionAction -x`
Expected: FAIL — FunctionAction not in registry

- [ ] **Step 3: Write minimal implementation**

Add to `primitive_compiler.py`:

```python
from agent_foundry.primitives.models import FunctionAction


def _compile_function_action(
    graph: StateGraph, action: FunctionAction, prefix: str, gate_ids: list[str]
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


register_compiler(FunctionAction, _compile_function_action)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_compiler.py::TestCompileFunctionAction -x`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/compiler/primitive_compiler.py tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "feat(compiler): add FunctionAction compilation with typed run_primitive_plan"
```

---

### Task 4: Sequence Compilation

**Files:**
- Modify: `src/agent_foundry/compiler/primitive_compiler.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_compiler.py`

**Dependencies:** Task 3

- [ ] **Step 1: Write the failing test**

```python
class MidState(BaseModel):
    query: str
    mid: str


class TestCompileSequence:
    def test_single_step(self):
        step = FunctionAction[InputState, TransformOutput](
            function=lambda s: TransformOutput(result=s.query.upper()),
        )
        seq = Sequence[InputState, TransformOutput](steps=[step])
        plan = PrimitivePlan(root=seq)
        graph = compile_primitive(plan)
        result = graph.invoke({"query": "hello"})
        assert result["result"] == "HELLO"

    def test_two_steps_chain(self):
        step1 = FunctionAction[InputState, MidState](
            function=lambda s: MidState(query=s.query, mid=s.query.upper()),
        )
        step2 = FunctionAction[MidState, OutputState](
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

        s1 = FunctionAction[ListState, ListState](function=append_a)
        s2 = FunctionAction[ListState, ListState](function=append_b)
        s3 = FunctionAction[ListState, ListState](function=append_c)
        seq = Sequence[ListState, ListState](steps=[s1, s2, s3])
        plan = PrimitivePlan(root=seq)
        graph = compile_primitive(plan)
        result = graph.invoke({"items": []})
        assert result["items"] == ["a", "b", "c"]
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Write minimal implementation**

```python
from agent_foundry.primitives.models import Sequence

def _compile_sequence(
    graph: StateGraph, seq: Sequence, prefix: str, gate_ids: list[str]
) -> tuple[str, str]:
    first_entry = None
    prev_exit = None
    for i, step in enumerate(seq.steps):
        child_prefix = f"{prefix}_step_{i}"
        entry, exit_ = _compile_node(graph, step, child_prefix, gate_ids)
        if first_entry is None:
            first_entry = entry
        if prev_exit is not None:
            graph.add_edge(prev_exit, entry)
        prev_exit = exit_
    assert first_entry is not None
    assert prev_exit is not None
    return (first_entry, prev_exit)

register_compiler(Sequence, _compile_sequence)
```

- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/compiler/primitive_compiler.py tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "feat(compiler): add Sequence compilation"
```

---

### Task 5: Conditional Compilation

**Files:**
- Modify: `src/agent_foundry/compiler/primitive_compiler.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_compiler.py`

**Dependencies:** Task 3

- [ ] **Step 1: Write the failing test**

```python
from agent_foundry.primitives.models import Conditional


class BranchState(BaseModel):
    value: str
    flag: bool


class TestCompileConditional:
    def test_then_branch_taken(self):
        then = FunctionAction[BranchState, BranchState](
            function=lambda s: BranchState(value="then", flag=s.flag),
        )
        else_ = FunctionAction[BranchState, BranchState](
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
        then = FunctionAction[BranchState, BranchState](
            function=lambda s: BranchState(value="then", flag=s.flag),
        )
        else_ = FunctionAction[BranchState, BranchState](
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
        then = FunctionAction[BranchState, BranchState](
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
        then = FunctionAction[BranchState, BranchState](
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
- [ ] **Step 3: Write minimal implementation**

Router function evaluates condition directly in the router closure — no state pollution:

```python
from agent_foundry.primitives.models import Conditional

def _compile_conditional(
    graph: StateGraph, cond: Conditional, prefix: str, gate_ids: list[str]
) -> tuple[str, str]:
    input_type, _ = get_type_args(cond)
    router_id = f"{prefix}_router"
    merge_id = f"{prefix}_merge"

    then_entry, then_exit = _compile_node(graph, cond.then_branch, f"{prefix}_then", gate_ids)

    if cond.else_branch is not None:
        else_entry, else_exit = _compile_node(graph, cond.else_branch, f"{prefix}_else", gate_ids)
        targets = [then_entry, else_entry]
    else:
        targets = [then_entry, merge_id]

    condition_fn = cond.condition

    def router_fn(state: dict[str, Any]) -> str:
        model = input_type.model_validate(state)
        if condition_fn(model):
            return then_entry
        return else_entry if cond.else_branch is not None else merge_id

    graph.add_node(router_id, lambda state: state)
    graph.add_conditional_edges(router_id, router_fn, targets)

    graph.add_node(merge_id, lambda state: state)
    graph.add_edge(then_exit, merge_id)
    if cond.else_branch is not None:
        graph.add_edge(else_exit, merge_id)

    return (router_id, merge_id)

register_compiler(Conditional, _compile_conditional)
```

- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/compiler/primitive_compiler.py tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "feat(compiler): add Conditional compilation"
```

---

### Task 6: Loop Compilation

**Files:**
- Modify: `src/agent_foundry/compiler/primitive_compiler.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_compiler.py`

**Dependencies:** Task 3

- [ ] **Step 1: Write the failing test**

```python
from agent_foundry.primitives.models import Loop


class LoopInput(BaseModel):
    items: list[str]
    processed: list[str] = []
    current_item: str = ""


class TestCompileLoop:
    def test_iterates_over_collection(self):
        body = FunctionAction[LoopInput, LoopInput](
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
        body = FunctionAction[LoopInput, LoopInput](
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
        body = FunctionAction[LoopInput, LoopInput](
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
        body = FunctionAction[LoopInput, LoopInput](
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
- [ ] **Step 3: Write minimal implementation**

```python
from agent_foundry.primitives.models import Loop

def _compile_loop(
    graph: StateGraph, loop: Loop, prefix: str, gate_ids: list[str]
) -> tuple[str, str]:
    input_type, _ = get_type_args(loop)
    ctrl_id = f"{prefix}_ctrl"
    exit_id = f"{prefix}_exit"
    inc_id = f"{prefix}_inc"

    body_entry, body_exit = _compile_node(graph, loop.body, f"{prefix}_body", gate_ids)

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

register_compiler(Loop, _compile_loop)
```

- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/compiler/primitive_compiler.py tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "feat(compiler): add Loop compilation"
```

---

### Task 7: Retry Compilation

**Files:**
- Modify: `src/agent_foundry/compiler/primitive_compiler.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_compiler.py`

**Dependencies:** Task 3

Retry no longer has `on_exhausted`. When attempts exhaust, Retry exits normally — the domain state carries the signal. The parent reads output and routes (e.g., via Conditional).

- [ ] **Step 1: Write the failing test**

```python
from agent_foundry.primitives.models import Retry


class RetryState(BaseModel):
    attempts: int = 0
    done: bool = False


class TestCompileRetry:
    def test_succeeds_first_attempt(self):
        body = FunctionAction[RetryState, RetryState](
            function=lambda s: RetryState(attempts=s.attempts + 1, done=True),
        )
        retry = Retry[RetryState, RetryState](
            max_attempts=3,
            until=lambda s: s.done,
            body=body,
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

        body = FunctionAction[RetryState, RetryState](function=body_fn)
        retry = Retry[RetryState, RetryState](
            max_attempts=5,
            until=lambda s: s.done,
            body=body,
        )
        plan = PrimitivePlan(root=retry)
        graph = compile_primitive(plan)
        result = graph.invoke({"attempts": 0, "done": False})
        assert result["attempts"] == 2
        assert result["done"] is True

    def test_exhausted_exits_normally(self):
        """When max_attempts exhausted, Retry exits with domain state intact (done=False)."""
        body = FunctionAction[RetryState, RetryState](
            function=lambda s: RetryState(attempts=s.attempts + 1, done=False),
        )
        retry = Retry[RetryState, RetryState](
            max_attempts=2,
            until=lambda s: s.done,
            body=body,
        )
        plan = PrimitivePlan(root=retry)
        graph = compile_primitive(plan)
        result = graph.invoke({"attempts": 0, "done": False})
        assert result["attempts"] == 2
        assert result["done"] is False  # parent can check this to route

    def test_max_attempts_one(self):
        body = FunctionAction[RetryState, RetryState](
            function=lambda s: RetryState(attempts=s.attempts + 1, done=False),
        )
        retry = Retry[RetryState, RetryState](
            max_attempts=1,
            until=lambda s: s.done,
            body=body,
        )
        plan = PrimitivePlan(root=retry)
        graph = compile_primitive(plan)
        result = graph.invoke({"attempts": 0, "done": False})
        assert result["attempts"] == 1
        assert result["done"] is False
```

- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write minimal implementation**

```python
from agent_foundry.primitives.models import Retry

def _compile_retry(
    graph: StateGraph, retry: Retry, prefix: str, gate_ids: list[str]
) -> tuple[str, str]:
    input_type, _ = get_type_args(retry)
    start_id = f"{prefix}_start"
    check_id = f"{prefix}_check"
    exit_id = f"{prefix}_exit"

    body_entry, body_exit = _compile_node(graph, retry.body, f"{prefix}_body", gate_ids)

    attempt = {"count": 0}
    until_fn = retry.until
    max_attempts = retry.max_attempts

    def check_node(state: dict[str, Any]) -> dict[str, Any]:
        attempt["count"] += 1
        return state

    def router(state: dict[str, Any]) -> str:
        model = input_type.model_validate(state)
        if until_fn(model):
            return exit_id
        if attempt["count"] >= max_attempts:
            return exit_id  # exit normally — domain state carries the signal
        return body_entry

    graph.add_node(start_id, lambda state: state)
    graph.add_node(check_id, check_node)
    graph.add_node(exit_id, lambda state: state)

    graph.add_edge(start_id, body_entry)
    graph.add_edge(body_exit, check_id)
    graph.add_conditional_edges(check_id, router, [exit_id, body_entry])

    return (start_id, exit_id)

register_compiler(Retry, _compile_retry)
```

- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/compiler/primitive_compiler.py tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "feat(compiler): add Retry compilation (exhaustion exits normally)"
```

---

### Task 8: GateAction Compilation

**Files:**
- Modify: `src/agent_foundry/compiler/primitive_compiler.py`
- Modify: `tests/agent_foundry/primitives/test_primitive_compiler.py`

**Dependencies:** Task 3

GateAction always blocks when reached — no condition. The parent routes to it via Conditional. Auto-injects MemorySaver when any GateAction is in the tree.

- [ ] **Step 1: Write the failing test**

```python
from agent_foundry.primitives.models import GateAction


class GateInput(BaseModel):
    escalation_context: str
    value: str = ""


class GateOutput(BaseModel):
    escalation_context: str
    value: str
    human_response: str = ""


class TestCompileGateAction:
    def test_auto_injects_checkpointer(self):
        """Compile should succeed with a GateAction — MemorySaver auto-injected."""
        gate = GateAction[GateInput, GateOutput](
            interaction="human_stdin",
            prompt_key="escalation_context",
        )
        plan = PrimitivePlan(root=gate)
        graph = compile_primitive(plan)
        assert graph is not None

    def test_interrupts_execution(self):
        gate = GateAction[GateInput, GateOutput](
            interaction="human_stdin",
            prompt_key="escalation_context",
        )
        plan = PrimitivePlan(root=gate)
        graph = compile_primitive(plan)
        result = graph.invoke(
            {"escalation_context": "need help", "value": "stuck"},
            config={"configurable": {"thread_id": "test-1"}},
        )
        # Gate interrupts — state reflects pre-gate values
        assert result["escalation_context"] == "need help"

    def test_prompt_key_value_in_interrupted_state(self):
        gate = GateAction[GateInput, GateOutput](
            interaction="human_stdin",
            prompt_key="escalation_context",
        )
        plan = PrimitivePlan(root=gate)
        graph = compile_primitive(plan)
        result = graph.invoke(
            {"escalation_context": "review failed twice", "value": "blocked"},
            config={"configurable": {"thread_id": "test-2"}},
        )
        assert result["escalation_context"] == "review failed twice"
```

- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write minimal implementation**

```python
from agent_foundry.primitives.models import GateAction

def _compile_gate_action(
    graph: StateGraph, gate: GateAction, prefix: str, gate_ids: list[str]
) -> tuple[str, str]:
    gate_id = prefix

    def gate_node(state: dict[str, Any]) -> dict[str, Any]:
        return state  # interrupt_before pauses BEFORE this node

    graph.add_node(gate_id, gate_node)
    gate_ids.append(gate_id)
    return (gate_id, gate_id)

register_compiler(GateAction, _compile_gate_action)
```

- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/compiler/primitive_compiler.py tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "feat(compiler): add GateAction compilation with MemorySaver auto-injection"
```

---

### Task 9: Delete Old Compiler and Planner Code

**Files:**
- Delete: `src/agent_foundry/compiler/compiler.py`
- Delete: `src/agent_foundry/compiler/errors.py`
- Delete: `src/agent_foundry/compiler/templates.py`
- Delete: `src/agent_foundry/planner/` (entire directory)
- Delete: `src/agent_foundry/demo/runner.py`
- Delete: 11 test files (see list below)
- Modify: `tests/agent_foundry/conftest.py` — remove `make_plan()` factory

**Keep (shared infrastructure):**
- `src/agent_foundry/registry/` — RoleRegistry, RoleSpec, execute_role()
- `src/agent_foundry/agents/connector.py` — make_typed_connector()
- `src/agent_foundry/agents/protocol.py` — TypedAgent protocol

**Dependencies:** Task 8 (all new LangGraph patterns established)

- [ ] **Step 1: Delete old source files**

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

- [ ] **Step 3: Clean up conftest.py and fix broken imports**
- [ ] **Step 4: Run full test suite**

Run: `pdm run pytest tests/ -q`
Expected: ALL PASS (reduced count)

Run: `pdm run lint`
Expected: Clean

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(compiler): delete old GraphWiringPlan compiler and planner

Remove compile_plan(), GraphWiringPlan, validate_plan(), and all related
code. The primitive compiler (compile_primitive) replaces this path.
Registry and agent protocol infrastructure retained for future use."
```

---

### Task 10: Nested Composition Tests

**Files:**
- Modify: `tests/agent_foundry/primitives/test_primitive_compiler.py`

**Dependencies:** Tasks 3-9

- [ ] **Step 1: Write tests**

```python
class TestNestedComposition:
    def test_sequence_of_actions(self):
        class S(BaseModel):
            n: int = 0

        s1 = FunctionAction[S, S](function=lambda s: S(n=s.n + 1))
        s2 = FunctionAction[S, S](function=lambda s: S(n=s.n + 10))
        s3 = FunctionAction[S, S](function=lambda s: S(n=s.n + 100))
        seq = Sequence[S, S](steps=[s1, s2, s3])
        plan = PrimitivePlan(root=seq)
        graph = compile_primitive(plan)
        result = graph.invoke({"n": 0})
        assert result["n"] == 111

    def test_loop_body_is_sequence(self):
        class S(BaseModel):
            items: list[str] = []
            processed: list[str] = []
            current_item: str = ""

        step1 = FunctionAction[S, S](
            function=lambda s: S(
                items=s.items, processed=s.processed,
                current_item=s.current_item.upper(),
            ),
        )
        step2 = FunctionAction[S, S](
            function=lambda s: S(
                items=s.items, processed=[*s.processed, s.current_item],
                current_item=s.current_item,
            ),
        )
        body = Sequence[S, S](steps=[step1, step2])
        loop = Loop[S, S](over=lambda s: s.items, item_key="current_item", body=body)
        plan = PrimitivePlan(root=loop)
        graph = compile_primitive(plan)
        result = graph.invoke({"items": ["a", "b"], "processed": []})
        assert result["processed"] == ["A", "B"]

    def test_retry_then_conditional_escalation(self):
        """Retry exhausts, parent Conditional routes to escalation based on domain state."""

        class S(BaseModel):
            n: int = 0
            done: bool = False

        body = FunctionAction[S, S](
            function=lambda s: S(n=s.n + 1, done=False),
        )
        retry = Retry[S, S](max_attempts=2, until=lambda s: s.done, body=body)
        escalation = FunctionAction[S, S](
            function=lambda s: S(n=s.n, done=True),  # human resolves
        )
        check_exhausted = Conditional[S, S](
            condition=lambda s: not s.done,
            then_branch=escalation,
        )
        seq = Sequence[S, S](steps=[retry, check_exhausted])
        plan = PrimitivePlan(root=seq)
        graph = compile_primitive(plan)
        result = graph.invoke({"n": 0, "done": False})
        assert result["n"] == 2
        assert result["done"] is True  # escalation resolved it

    def test_sequence_containing_conditional(self):
        class S(BaseModel):
            value: str = ""
            flag: bool = True

        step1 = FunctionAction[S, S](function=lambda s: S(value="step1", flag=s.flag))
        then = FunctionAction[S, S](function=lambda s: S(value=s.value + "_then", flag=s.flag))
        else_ = FunctionAction[S, S](function=lambda s: S(value=s.value + "_else", flag=s.flag))
        cond = Conditional[S, S](
            condition=lambda s: s.flag,
            then_branch=then,
            else_branch=else_,
        )
        step3 = FunctionAction[S, S](function=lambda s: S(value=s.value + "_done", flag=s.flag))
        seq = Sequence[S, S](steps=[step1, cond, step3])
        plan = PrimitivePlan(root=seq)
        graph = compile_primitive(plan)
        result = graph.invoke({"value": "", "flag": True})
        assert result["value"] == "step1_then_done"
```

- [ ] **Step 2: Run tests**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_compiler.py::TestNestedComposition -x`
Expected: PASS (4 tests)

- [ ] **Step 3: Commit**

```bash
git add tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "test(compiler): add nested composition tests including retry-conditional escalation"
```

---

### Task 11: Final Exports and Full Verification

**Files:**
- Modify: `src/agent_foundry/primitives/__init__.py`
- Modify: `src/agent_foundry/compiler/__init__.py`

**Dependencies:** Tasks 1-10

- [ ] **Step 1: Update exports**

Add to `primitives/__init__.py`: `PrimitiveCompilationError`
Create/update `compiler/__init__.py`: export `compile_primitive`, `run_primitive_plan`, `register_compiler`

- [ ] **Step 2: Run full test suite**

Run: `pdm run pytest tests/agent_foundry/primitives/ -v`
Expected: ALL PASS

Run: `pdm run pytest tests/ -q`
Expected: ALL PASS, no regressions

Run: `pdm run lint`
Expected: Clean

- [ ] **Step 3: Commit**

```bash
git add src/agent_foundry/primitives/__init__.py src/agent_foundry/compiler/__init__.py
git commit -m "feat(compiler): add public exports for primitive compiler"
```

---

## Verification

After all tasks complete:

1. `pdm run pytest tests/agent_foundry/primitives/ -v` — all primitive tests pass
2. `pdm run pytest tests/ -q` — full suite passes, no regressions
3. `pdm run lint` — clean
