# CS3: Primitive Compiler — Implementation Plan

> **Design:** docs/plans/stage1/2026-04-03-review-feedback-loop-design.md
> **Roadmap:** docs/plans/stage1/2026-04-03-review-feedback-loop-roadmap.md
> **For agents:** Use team-dev (parallel) or sdd (sequential) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update primitive models (rename Action → FunctionAction, Gate → GateAction, remove on_exhausted from Retry), then compile the typed primitive graph into an executable LangGraph `StateGraph` with a fully typed public API. The old `compile_plan(GraphWiringPlan)` path is deleted after the new compiler proves working.

**Architecture — Direct to LangGraph with subgraph-based state isolation:**

The compiler walks the primitive tree recursively, generating LangGraph nodes and edges directly. No intermediate `GraphWiringPlan`.

**Composite primitives compile as subgraphs** (Sequence, Loop, Retry, Conditional). Each subgraph has its own state type derived from its I/O models. State is scoped at every composition boundary:
1. **Scope in**: extract child's I fields from parent state → construct child's fresh input dict
2. **Execute**: child subgraph runs in isolation — cannot see or mutate parent state
3. **Scope out**: extract child's O fields from subgraph result → merge back into parent state

**Leaf primitives compile as nodes** (FunctionAction, GateAction). They receive scoped state from their parent subgraph.

This guarantees that "anything not in output is discarded when the primitive completes" (per design doc). Loop iterations get a fresh scope each time — no state leakage between iterations.

**Key design decisions:**
- **Typed public API**: `run_primitive_plan(plan, input: I) -> O` — Pydantic models in and out, no dicts exposed
- **Compiler registry**: `dict[type[Primitive], CompilerFn]` — extensible dispatch, no isinstance chains
- **Subgraph isolation**: composite primitives are LangGraph subgraphs with scoped state derived from Pydantic I/O types
- **`_compile_node()` returns `(entry_id, exit_id)` tuples** — parents wire edges between children without knowing internal structure
- **Pydantic boundary validation** at scope-in/scope-out transitions
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


# ======================================================================
# State Scoping
# ======================================================================


class TestScopeIn:
    def test_extracts_only_model_fields(self):
        from agent_foundry.compiler.primitive_compiler import _scope_in

        parent_state = {"query": "hello", "result": "world", "extra": "ignored"}
        scoped = _scope_in(parent_state, InputState)
        assert scoped == {"query": "hello"}
        assert "result" not in scoped
        assert "extra" not in scoped

    def test_validates_required_fields(self):
        from agent_foundry.compiler.primitive_compiler import _scope_in

        with pytest.raises(PrimitiveCompilationError):
            _scope_in({}, InputState)


class TestScopeOut:
    def test_extracts_only_output_fields(self):
        from agent_foundry.compiler.primitive_compiler import _scope_out

        child_result = {"query": "hello", "result": "HELLO", "internal": "temp"}
        scoped = _scope_out(child_result, OutputState)
        assert scoped == {"query": "hello", "result": "HELLO"}
        assert "internal" not in scoped

    def test_validates_output(self):
        from agent_foundry.compiler.primitive_compiler import _scope_out

        with pytest.raises(PrimitiveCompilationError):
            _scope_out({}, OutputState)  # missing required fields
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


def _scope_in(
    parent_state: dict[str, Any], child_input_type: type[BaseModel]
) -> dict[str, Any]:
    """Scope parent state down to child's input fields. Validates required fields."""
    fields = set(child_input_type.model_fields.keys())
    scoped = {k: v for k, v in parent_state.items() if k in fields}
    try:
        child_input_type.model_validate(scoped)
    except ValidationError as e:
        raise PrimitiveCompilationError(
            f"Scope-in failed: {e}", primitive_type="scope_in"
        ) from e
    return scoped


def _scope_out(
    child_result: dict[str, Any], child_output_type: type[BaseModel]
) -> dict[str, Any]:
    """Scope child result down to output fields. Validates output completeness."""
    fields = set(child_output_type.model_fields.keys())
    scoped = {k: v for k, v in child_result.items() if k in fields}
    try:
        child_output_type.model_validate(scoped)
    except ValidationError as e:
        raise PrimitiveCompilationError(
            f"Scope-out failed: {e}", primitive_type="scope_out"
        ) from e
    return scoped


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
Expected: PASS (13 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/primitives/errors.py src/agent_foundry/compiler/primitive_compiler.py tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "feat(compiler): add compiler infrastructure (registry, state derivation, scoping, boundary validation)"
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

    # State isolation tests are in the dedicated TestStateIsolation class
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Write minimal implementation**

The Sequence compiles as a subgraph. Steps run inside the subgraph's isolated state. The subgraph's state type is derived from the Sequence's I and O types. Scope-in extracts I fields from parent, scope-out extracts O fields back to parent.

```python
from agent_foundry.primitives.models import Sequence

def _compile_sequence(
    graph: StateGraph, seq: Sequence, prefix: str, gate_ids: list[str]
) -> tuple[str, str]:
    seq_in, seq_out = get_type_args(seq)

    # Build subgraph with its own state type
    sub_state_type = _derive_state_type(seq_in, seq_out)
    sub_graph = StateGraph(sub_state_type)

    first_entry = None
    prev_exit = None
    for i, step in enumerate(seq.steps):
        child_prefix = f"{prefix}_step_{i}"
        entry, exit_ = _compile_node(sub_graph, step, child_prefix, gate_ids)
        if first_entry is None:
            first_entry = entry
        if prev_exit is not None:
            sub_graph.add_edge(prev_exit, entry)
        prev_exit = exit_
    assert first_entry is not None
    assert prev_exit is not None

    sub_graph.set_entry_point(first_entry)
    sub_graph.add_edge(prev_exit, END)
    compiled_sub = sub_graph.compile()

    # Wrapper node: scope-in → execute subgraph → scope-out
    node_id = f"{prefix}_seq"

    def seq_node(state: dict[str, Any]) -> dict[str, Any]:
        scoped_input = _scope_in(state, seq_in)
        result = compiled_sub.invoke(scoped_input)
        return _scope_out(result, seq_out)

    graph.add_node(node_id, seq_node)
    return (node_id, node_id)

register_compiler(Sequence, _compile_sequence)
```

- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/compiler/primitive_compiler.py tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "feat(compiler): add Sequence compilation with subgraph state isolation"
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

Conditional compiles as a subgraph. Router evaluates condition in closure. Branches are compiled inside the subgraph. Scope-in/scope-out at the boundary.

```python
from agent_foundry.primitives.models import Conditional

def _compile_conditional(
    graph: StateGraph, cond: Conditional, prefix: str, gate_ids: list[str]
) -> tuple[str, str]:
    cond_in, cond_out = get_type_args(cond)

    # Build subgraph
    sub_state_type = _derive_state_type(cond_in, cond_out)
    sub_graph = StateGraph(sub_state_type)

    router_id = f"{prefix}_router"
    merge_id = f"{prefix}_merge"

    then_entry, then_exit = _compile_node(sub_graph, cond.then_branch, f"{prefix}_then", gate_ids)

    if cond.else_branch is not None:
        else_entry, else_exit = _compile_node(sub_graph, cond.else_branch, f"{prefix}_else", gate_ids)
        targets = [then_entry, else_entry]
    else:
        targets = [then_entry, merge_id]

    condition_fn = cond.condition

    def router_fn(state: dict[str, Any]) -> str:
        model = cond_in.model_validate(state)
        if condition_fn(model):
            return then_entry
        return else_entry if cond.else_branch is not None else merge_id

    sub_graph.add_node(router_id, lambda state: state)
    sub_graph.add_conditional_edges(router_id, router_fn, targets)

    sub_graph.add_node(merge_id, lambda state: state)
    sub_graph.add_edge(then_exit, merge_id)
    if cond.else_branch is not None:
        sub_graph.add_edge(else_exit, merge_id)

    sub_graph.set_entry_point(router_id)
    sub_graph.add_edge(merge_id, END)
    compiled_sub = sub_graph.compile()

    # Wrapper node: scope-in → execute subgraph → scope-out
    node_id = f"{prefix}_cond"

    def cond_node(state: dict[str, Any]) -> dict[str, Any]:
        scoped_input = _scope_in(state, cond_in)
        result = compiled_sub.invoke(scoped_input)
        return _scope_out(result, cond_out)

    graph.add_node(node_id, cond_node)
    return (node_id, node_id)

register_compiler(Conditional, _compile_conditional)
```

- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/compiler/primitive_compiler.py tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "feat(compiler): add Conditional compilation with subgraph isolation"
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

    # Per-iteration isolation tests are in the dedicated TestStateIsolation class
```

- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write minimal implementation**

Loop compiles the body as a subgraph. Each iteration: scope-in (extract body.I fields + inject current item under item_key) → execute body subgraph → scope-out (extract body.O fields back to loop state). Fresh scope per iteration — no state leakage.

```python
from agent_foundry.primitives.models import Loop

def _compile_loop(
    graph: StateGraph, loop: Loop, prefix: str, gate_ids: list[str]
) -> tuple[str, str]:
    loop_in, loop_out = get_type_args(loop)
    body_in, body_out = get_type_args(loop.body)

    # Compile body as isolated subgraph
    body_state_type = _derive_state_type(body_in, body_out)
    body_graph = StateGraph(body_state_type)
    body_entry, body_exit = _compile_node(body_graph, loop.body, f"{prefix}_body", gate_ids)
    body_graph.set_entry_point(body_entry)
    body_graph.add_edge(body_exit, END)
    compiled_body = body_graph.compile()

    over_fn = loop.over
    item_key = loop.item_key
    max_iter = loop.max_iterations

    # Wrapper node: iterates, scoping in/out per iteration
    node_id = f"{prefix}_loop"

    def loop_node(state: dict[str, Any]) -> dict[str, Any]:
        model = loop_in.model_validate(state)
        items = over_fn(model)
        current_state = dict(state)

        for i, item in enumerate(items):
            if i >= max_iter:
                break
            # Scope in: body.I fields from current state + item injection
            scoped = _scope_in(current_state, body_in)
            scoped[item_key] = item
            # Execute body in isolation
            result = compiled_body.invoke(scoped)
            # Scope out: merge body.O fields back
            updates = _scope_out(result, body_out)
            current_state.update(updates)

        return _scope_out(current_state, loop_out)

    graph.add_node(node_id, loop_node)
    return (node_id, node_id)

register_compiler(Loop, _compile_loop)
```

- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/compiler/primitive_compiler.py tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "feat(compiler): add Loop compilation with per-iteration state isolation"
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

Retry compiles the body as a subgraph. Each attempt: scope-in → execute body → scope-out → check `until`. Body output feeds back as input on re-entry (same type by validator constraint). On exhaustion, exits normally with domain state intact.

```python
from agent_foundry.primitives.models import Retry

def _compile_retry(
    graph: StateGraph, retry: Retry, prefix: str, gate_ids: list[str]
) -> tuple[str, str]:
    retry_in, retry_out = get_type_args(retry)
    body_in, body_out = get_type_args(retry.body)

    # Compile body as isolated subgraph
    body_state_type = _derive_state_type(body_in, body_out)
    body_graph = StateGraph(body_state_type)
    body_entry, body_exit = _compile_node(body_graph, retry.body, f"{prefix}_body", gate_ids)
    body_graph.set_entry_point(body_entry)
    body_graph.add_edge(body_exit, END)
    compiled_body = body_graph.compile()

    until_fn = retry.until
    max_attempts = retry.max_attempts

    # Wrapper node: retry loop with scoped body execution
    node_id = f"{prefix}_retry"

    def retry_node(state: dict[str, Any]) -> dict[str, Any]:
        current_state = _scope_in(state, retry_in)
        for attempt in range(max_attempts):
            # Execute body in isolation
            scoped = _scope_in(current_state, body_in)
            result = compiled_body.invoke(scoped)
            current_state.update(_scope_out(result, body_out))
            # Check until condition
            model = retry_in.model_validate(current_state)
            if until_fn(model):
                break
        return _scope_out(current_state, retry_out)

    graph.add_node(node_id, retry_node)
    return (node_id, node_id)

register_compiler(Retry, _compile_retry)
```

- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

```bash
git add src/agent_foundry/compiler/primitive_compiler.py tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "feat(compiler): add Retry compilation with subgraph isolation"
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

### Task 11: State Isolation Tests

**Files:**
- Modify: `tests/agent_foundry/primitives/test_primitive_compiler.py`

**Dependencies:** Tasks 3-10

Isolation is essential to correctness. This dedicated test class verifies that state scoping works at every composition boundary, including nested primitives.

- [ ] **Step 1: Write tests**

```python
class TestStateIsolation:
    """Verify state scoping at every composition boundary."""

    def test_conditional_branches_dont_leak(self):
        """then_branch internal fields don't appear in parent output."""

        class CondIn(BaseModel):
            flag: bool
            value: str

        class BranchInternal(BaseModel):
            flag: bool
            value: str
            branch_temp: str  # internal to branch

        class CondOut(BaseModel):
            flag: bool
            value: str

        then = FunctionAction[CondIn, BranchInternal](
            function=lambda s: BranchInternal(
                flag=s.flag, value="then", branch_temp="should_not_leak"
            ),
        )
        else_ = FunctionAction[CondIn, BranchInternal](
            function=lambda s: BranchInternal(
                flag=s.flag, value="else", branch_temp="also_should_not_leak"
            ),
        )
        cond = Conditional[CondIn, CondOut](
            condition=lambda s: s.flag,
            then_branch=then,
            else_branch=else_,
        )
        plan = PrimitivePlan(root=cond)
        graph = compile_primitive(plan)
        result = graph.invoke({"flag": True, "value": "start"})
        assert result["value"] == "then"
        assert "branch_temp" not in result

    def test_retry_body_internals_dont_leak(self):
        """Retry body's internal fields don't appear in retry output."""

        class RetryIn(BaseModel):
            attempts: int = 0
            done: bool = False

        class BodyInternal(BaseModel):
            attempts: int
            done: bool
            debug_info: str = ""  # internal to body

        class RetryOut(BaseModel):
            attempts: int
            done: bool

        body = FunctionAction[RetryIn, BodyInternal](
            function=lambda s: BodyInternal(
                attempts=s.attempts + 1, done=True, debug_info="internal"
            ),
        )
        retry = Retry[RetryIn, RetryOut](
            max_attempts=3, until=lambda s: s.done, body=body,
        )
        plan = PrimitivePlan(root=retry)
        graph = compile_primitive(plan)
        result = graph.invoke({"attempts": 0, "done": False})
        assert result["attempts"] == 1
        assert "debug_info" not in result

    def test_sibling_primitives_dont_interfere(self):
        """Two sequential steps using the same internal field name don't collide."""

        class StepIn(BaseModel):
            value: str

        class StepMid(BaseModel):
            value: str
            temp: str  # both steps use 'temp' internally

        class StepOut(BaseModel):
            value: str

        step1 = FunctionAction[StepIn, StepMid](
            function=lambda s: StepMid(value=s.value + "_a", temp="from_step1"),
        )
        step2 = FunctionAction[StepMid, StepOut](
            function=lambda s: StepOut(value=s.value + "_b"),
        )
        seq = Sequence[StepIn, StepOut](steps=[step1, step2])
        plan = PrimitivePlan(root=seq)
        graph = compile_primitive(plan)
        result = graph.invoke({"value": "start"})
        assert result["value"] == "start_a_b"
        assert "temp" not in result

    def test_nested_loop_in_sequence_isolation(self):
        """Loop body internals don't leak to sequence siblings."""

        class SeqState(BaseModel):
            items: list[str]
            results: list[str] = []
            current_item: str = ""

        class BodyState(BaseModel):
            items: list[str]
            results: list[str]
            current_item: str
            processing_temp: str = ""  # internal to loop body

        pre = FunctionAction[SeqState, SeqState](
            function=lambda s: SeqState(
                items=s.items, results=["pre"], current_item=s.current_item,
            ),
        )
        body = FunctionAction[BodyState, BodyState](
            function=lambda s: BodyState(
                items=s.items,
                results=[*s.results, s.current_item.upper()],
                current_item=s.current_item,
                processing_temp="should_not_leak",
            ),
        )
        loop = Loop[SeqState, SeqState](
            over=lambda s: s.items, item_key="current_item", body=body,
        )
        post = FunctionAction[SeqState, SeqState](
            function=lambda s: SeqState(
                items=s.items, results=[*s.results, "post"],
                current_item=s.current_item,
            ),
        )
        seq = Sequence[SeqState, SeqState](steps=[pre, loop, post])
        plan = PrimitivePlan(root=seq)
        graph = compile_primitive(plan)
        result = graph.invoke({"items": ["a", "b"], "results": []})
        assert result["results"] == ["pre", "A", "B", "post"]
        assert "processing_temp" not in result

    def test_loop_iterations_get_fresh_scope(self):
        """Each loop iteration starts fresh — previous iteration's internal state doesn't leak."""

        class LoopState(BaseModel):
            items: list[str]
            results: list[str] = []
            current_item: str = ""
            temp: str = ""

        def body_fn(s: LoopState) -> LoopState:
            assert s.temp == "", f"temp leaked from previous iteration: {s.temp}"
            return LoopState(
                items=s.items,
                results=[*s.results, s.current_item],
                current_item=s.current_item,
                temp="was_set",
            )

        body = FunctionAction[LoopState, LoopState](function=body_fn)
        loop = Loop[LoopState, LoopState](
            over=lambda s: s.items, item_key="current_item", body=body,
        )
        plan = PrimitivePlan(root=loop)
        graph = compile_primitive(plan)
        result = graph.invoke({"items": ["a", "b", "c"], "results": []})
        assert result["results"] == ["a", "b", "c"]

    def test_three_levels_deep_isolation(self):
        """Isolation holds across Sequence > Loop > Sequence > FunctionAction."""

        class Outer(BaseModel):
            items: list[str]
            final: list[str] = []
            current_item: str = ""

        class Inner(BaseModel):
            items: list[str]
            final: list[str]
            current_item: str
            inner_temp: str = ""

        step1 = FunctionAction[Inner, Inner](
            function=lambda s: Inner(
                items=s.items, final=s.final, current_item=s.current_item,
                inner_temp="deep_internal",
            ),
        )
        step2 = FunctionAction[Inner, Outer](
            function=lambda s: Outer(
                items=s.items,
                final=[*s.final, s.current_item.upper()],
                current_item=s.current_item,
            ),
        )
        inner_seq = Sequence[Inner, Outer](steps=[step1, step2])
        loop = Loop[Outer, Outer](
            over=lambda s: s.items, item_key="current_item", body=inner_seq,
        )
        outer_seq = Sequence[Outer, Outer](steps=[loop])
        plan = PrimitivePlan(root=outer_seq)
        graph = compile_primitive(plan)
        result = graph.invoke({"items": ["x", "y"], "final": []})
        assert result["final"] == ["X", "Y"]
        assert "inner_temp" not in result
```

- [ ] **Step 2: Run tests**

Run: `pdm run pytest tests/agent_foundry/primitives/test_primitive_compiler.py::TestStateIsolation -x`
Expected: PASS (6 tests)

- [ ] **Step 3: Commit**

```bash
git add tests/agent_foundry/primitives/test_primitive_compiler.py
git commit -m "test(compiler): add dedicated state isolation test class"
```

---

### Task 12: Final Exports and Full Verification

**Files:**
- Modify: `src/agent_foundry/primitives/__init__.py`
- Modify: `src/agent_foundry/compiler/__init__.py`

**Dependencies:** Tasks 1-11

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
