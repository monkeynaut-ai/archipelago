# CS7 Plan 1: AgentAction Primitive, Validator, and Compiler — Implementation Plan

> **Roadmap:** docs/plans/stage1/2026-04-03-review-feedback-loop-roadmap.md (Change Set 7)
> **For agents:** Use team-dev (parallel) or sdd (sequential) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Where this plan fits in CS7

CS7 is split into four plans. This is Plan 1.

- **Plan 1 (this document)** — roadmap Tasks 1–2 (`AgentAction` primitive + compiler) plus a validator registry refactor that emerged during planning. Compiler delegates to a stub `run_agent_in_container`.
- **Plan 2** — roadmap Tasks 3–4 (lifecycle orchestration replaces the stub; basic lifecycle tracking). Container reuse is part of Task 3's scope.
- **Plan 3** — roadmap Tasks 5–6 (`lessons-learned` skill move; base `CLAUDE.md` update). Independent of Plans 1 and 2.
- **Plan 4** — roadmap Tasks 7–12 (four Archipelago agents, two function actions, four instruction files).

Dependency shape: Plan 1 → Plan 2 → Plan 4; Plan 3 is independent. Each subsequent plan is drafted just-in-time after the prior plan lands.

**Goal:** Introduce `AgentAction[I, O]` as a new Agent Foundry primitive — define the model, validate it in the type graph, and compile it to a LangGraph node that delegates to a stub execution function.

**Architecture:** `AgentAction` is a leaf primitive (like `FunctionAction`, `GateAction`) with product-side collaborator callables (`prompt_builder`, `instructions_provider`), a required response channel (`StructuredOutputChannel` or `FileCollectionChannel`), and a required `executor` callable that actually runs the agent. The compiler produces a LangGraph node structurally parallel to `FunctionAction`'s: validate input state against `I`, build the prompt via `prompt_builder`, call `action.executor(primitive=action, prompt=prompt)`, verify the returned model is an instance of `O`, merge into state. The executor owns envelope unwrapping, schema validation, and channel branching — the compiler does not, and the compiler has no knowledge of whether the agent runs in a container, via SDK, or via API. Plan 1 ships `run_agent_in_container` as the container executor; CS10.5 adds SDK and API executors. Validator dispatch is refactored to a registry; unknown primitive types raise `UnregisteredPrimitiveError`, and applications can register validators for their own `Primitive` subclasses.

**Tech Stack:** Python 3.13+, Pydantic v2, LangGraph, pytest (with pytest-xdist).

**Scope boundary:** This plan stops at the primitive/validator/compiler layer. The compiler's node function delegates to `run_agent_in_container`, defined as a module-level stub that raises `NotImplementedError`. Plan 2 replaces the stub with real Docker orchestration. Container reuse policy, lockdown enforcement, lifecycle tracking, and non-success-outcome handling are all Plan 2 concerns.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `agent-foundry/src/agent_foundry/primitives/models.py` | Modify | Add `ContainerReusePolicy` enum, `StructuredOutputChannel`/`FileCollectionChannel` response channels, and `AgentAction[I, O]` primitive class |
| `agent-foundry/src/agent_foundry/primitives/__init__.py` | Modify | Export `AgentAction`, `ContainerReusePolicy`, `StructuredOutputChannel`, `FileCollectionChannel`, `register_validator`, `UnregisteredPrimitiveError` |
| `agent-foundry/src/agent_foundry/primitives/validators.py` | Modify | Refactor dispatch to a registry; register validators for all built-in primitives including `AgentAction` |
| `agent-foundry/src/agent_foundry/primitives/errors.py` | Modify | Add `UnregisteredPrimitiveError` for primitive types with no registered validator |
| `agent-foundry/src/agent_foundry/acp/agent_runner.py` | Create | Module holding the stub `run_agent_in_container` executor (container strategy) |
| `agent-foundry/src/agent_foundry/compiler/primitive_compiler.py` | Modify | Register `_compile_agent_action` (calls `action.executor`; no `agent_runner` import in compiler) |
| `agent-foundry/tests/agent_foundry/primitives/test_agent_action_model.py` | Create | Unit tests for `AgentAction` primitive model (fields, response channels, executor, config defaults) |
| `agent-foundry/tests/agent_foundry/primitives/test_primitive_models.py` | Modify | Add `AgentAction`, `ContainerReusePolicy`, response channel types to public API import test |
| `agent-foundry/tests/agent_foundry/primitives/test_primitive_validators.py` | Modify | Add validator registry tests and `AgentAction` composition tests; update existing tests to use `FunctionAction` as leaf stand-in (replaces bare `Primitive[...]`) |
| `agent-foundry/tests/agent_foundry/acp/test_agent_runner_stub.py` | Create | Unit tests for the stub `run_agent_in_container` (raises `NotImplementedError` for every `ContainerReusePolicy`) |
| `agent-foundry/tests/agent_foundry/compiler/test_agent_action_compiler.py` | Create | Unit tests for compiled `AgentAction` node (executor invocation, state merge, exception propagation, channel-agnostic, empty-dirs valid, Sequence composition) |

---

## Tech assumptions

- Tests live under `agent-foundry/tests/agent_foundry/` following the package structure.
- Test runner: `pdm test-unit` (from the agent-foundry repo root).
- Commit convention (per `archipelago/jig.config.md`): `type(scope): message`. Scopes used here: `primitives`, `compiler`, `acp`.

---

## Task 1: Add `ContainerReusePolicy` Enum

**Files:**
- Modify: `agent-foundry/src/agent_foundry/primitives/models.py`
- Test: `agent-foundry/tests/agent_foundry/primitives/test_agent_action_model.py`

**Dependencies:** None.

- [ ] **Step 1: Create the test file with a failing test**

Create `agent-foundry/tests/agent_foundry/primitives/test_agent_action_model.py`:

```python
"""Tests for the AgentAction primitive model."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from agent_foundry.primitives.models import (
    AgentAction,
    ContainerReusePolicy,
    Primitive,
    get_type_args,
)


class StubInput(BaseModel):
    value: str


class StubOutput(BaseModel):
    result: str


# ======================================================================
# ContainerReusePolicy
# ======================================================================


class TestContainerReusePolicy:
    """ContainerReusePolicy enumerates supported reuse modes."""

    def test_has_new_each_time(self):
        assert ContainerReusePolicy.NEW_EACH_TIME.value == "new_each_time"

    def test_has_reuse_resume(self):
        assert ContainerReusePolicy.REUSE_RESUME.value == "reuse_resume"

    def test_has_reuse_new_session(self):
        assert ContainerReusePolicy.REUSE_NEW_SESSION.value == "reuse_new_session"

    def test_is_str_enum(self):
        assert ContainerReusePolicy.NEW_EACH_TIME == "new_each_time"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/markn/engineering/jig-archipelago/agent-foundry && pdm test-unit tests/agent_foundry/primitives/test_agent_action_model.py`
Expected: FAIL with `ImportError: cannot import name 'AgentAction'` (or `ContainerReusePolicy`)

- [ ] **Step 3: Add the `ContainerReusePolicy` enum**

In `agent-foundry/src/agent_foundry/primitives/models.py`, add at the top after the existing imports (update imports to include `StrEnum`):

```python
from enum import StrEnum
```

Add after the existing imports but before `class Primitive`:

```python
class ContainerReusePolicy(StrEnum):
    """Policy for whether and how an AgentAction reuses containers across invocations.

    - NEW_EACH_TIME: Each invocation creates a fresh container, destroyed after.
    - REUSE_RESUME: Subsequent invocations reuse the same container with the
      agent session resumed (same conversation context).
    - REUSE_NEW_SESSION: Subsequent invocations reuse the container but start
      a fresh agent session (no conversation history, filesystem state persists).
    """

    NEW_EACH_TIME = "new_each_time"
    REUSE_RESUME = "reuse_resume"
    REUSE_NEW_SESSION = "reuse_new_session"
```

- [ ] **Step 4: Run test to verify the enum tests pass**

Run: `cd /home/markn/engineering/jig-archipelago/agent-foundry && pdm test-unit tests/agent_foundry/primitives/test_agent_action_model.py::TestContainerReusePolicy`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/markn/engineering/jig-archipelago/agent-foundry
git add src/agent_foundry/primitives/models.py tests/agent_foundry/primitives/test_agent_action_model.py
git commit -m "feat(primitives): add ContainerReusePolicy enum"
```

---

## Task 2: Define `AgentAction` Primitive — Required Fields

**Files:**
- Modify: `agent-foundry/src/agent_foundry/primitives/models.py`
- Test: `agent-foundry/tests/agent_foundry/primitives/test_agent_action_model.py`

**Dependencies:** Task 1.

**Design note**: `instructions_provider` is a callable (not a path) returning the instructions text. This is consistent with `prompt_builder` also being a callable. Today the common case is reading a markdown file from disk: `lambda: Path("/abs/path/planner.md").read_text()`. Later a recipe model can assemble text programmatically without a field-shape change.

- [ ] **Step 1: Add failing tests for `AgentAction` construction with required fields**

Append to `agent-foundry/tests/agent_foundry/primitives/test_agent_action_model.py`:

```python
# ======================================================================
# AgentAction — required fields
# ======================================================================


def _stub_prompt_builder(state: StubInput) -> str:
    return f"prompt: {state.value}"


def _stub_instructions_provider() -> str:
    return "# Agent instructions\n\nDo the thing."


class TestAgentActionRequiredFields:
    """AgentAction requires prompt_builder and instructions_provider."""

    def test_given_all_required_fields_when_created_then_succeeds(self):
        action = AgentAction[StubInput, StubOutput](
            prompt_builder=_stub_prompt_builder,
            instructions_provider=_stub_instructions_provider,
        )
        assert callable(action.prompt_builder)
        assert callable(action.instructions_provider)

    def test_unparameterized_raises(self):
        with pytest.raises(ValidationError, match="must be parameterized"):
            AgentAction(
                prompt_builder=_stub_prompt_builder,
                instructions_provider=_stub_instructions_provider,
            )

    def test_missing_prompt_builder_raises(self):
        with pytest.raises(ValidationError):
            AgentAction[StubInput, StubOutput](
                instructions_provider=_stub_instructions_provider,
            )

    def test_missing_instructions_provider_raises(self):
        with pytest.raises(ValidationError):
            AgentAction[StubInput, StubOutput](
                prompt_builder=_stub_prompt_builder,
            )

    def test_get_type_args_returns_parameterized_types(self):
        action = AgentAction[StubInput, StubOutput](
            prompt_builder=_stub_prompt_builder,
            instructions_provider=_stub_instructions_provider,
        )
        input_type, output_type = get_type_args(action)
        assert input_type is StubInput
        assert output_type is StubOutput

    def test_prompt_builder_is_callable(self):
        action = AgentAction[StubInput, StubOutput](
            prompt_builder=_stub_prompt_builder,
            instructions_provider=_stub_instructions_provider,
        )
        result = action.prompt_builder(StubInput(value="hello"))
        assert result == "prompt: hello"

    def test_instructions_provider_is_callable(self):
        action = AgentAction[StubInput, StubOutput](
            prompt_builder=_stub_prompt_builder,
            instructions_provider=_stub_instructions_provider,
        )
        text = action.instructions_provider()
        assert text.startswith("# Agent instructions")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/markn/engineering/jig-archipelago/agent-foundry && pdm test-unit tests/agent_foundry/primitives/test_agent_action_model.py::TestAgentActionRequiredFields`
Expected: FAIL with `ImportError: cannot import name 'AgentAction'`

- [ ] **Step 3: Add `AgentAction` class with required fields**

In `agent-foundry/src/agent_foundry/primitives/models.py`, add after the `GateAction` class (before `get_type_args`):

```python
class AgentAction[I: BaseModel, O: BaseModel](Primitive[I, O]):
    """Run an LLM agent in a container to transform input state to output state.

    Two-sided interface:
      - Product side declares agent configuration via collaborator callables
        (``prompt_builder``, ``instructions_provider``).
      - Platform side handles container lifecycle, instruction injection,
        structured output, and response validation.

    This primitive is a leaf (no children). The compiler registers a node
    that calls the prompt builder, then delegates to the agent runner.
    """

    prompt_builder: Callable[[I], str]
    instructions_provider: Callable[[], str]
```

Also add `AgentAction.model_rebuild()` at the bottom of the file, alongside the other rebuild calls.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/markn/engineering/jig-archipelago/agent-foundry && pdm test-unit tests/agent_foundry/primitives/test_agent_action_model.py::TestAgentActionRequiredFields`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/markn/engineering/jig-archipelago/agent-foundry
git add src/agent_foundry/primitives/models.py tests/agent_foundry/primitives/test_agent_action_model.py
git commit -m "feat(primitives): add AgentAction primitive with prompt_builder and instructions_provider"
```

---

## Task 3: Add `AgentAction` Response Channel and Configuration Fields

**Files:**
- Modify: `agent-foundry/src/agent_foundry/primitives/models.py`
- Test: `agent-foundry/tests/agent_foundry/primitives/test_agent_action_model.py`

**Dependencies:** Task 2.

**Design note — `response_channel` is required.** Each agent chooses exactly one response channel at design time:

- `StructuredOutputChannel` — agent returns its output via `--json-schema`; the runner validates `AgentTurnEnvelope[O]` and returns an `O`.
- `FileCollectionChannel` — the runner collects files from listed container paths, passes their contents to a builder callable that constructs an `O`.

An agent does not switch channels at runtime. No default — product must choose, matching the safe-by-default philosophy used for lockdown dirs.

**Design note — `executor` is required.** The `executor` field holds a callable that actually runs the agent and returns an instance of `O`. The product declares which executor each agent uses; the platform ships executors as library capabilities.

Plan 1 ships one executor — `run_agent_in_container` (container + Claude Code CLI). CS10.5 will add SDK and API executors as additional callables products can choose. Different agents in the same system can use different executors; that choice lives on the primitive declaration, not in platform code.

Making `executor` a field (rather than having the compiler import a specific runner) achieves three things:
- Product owns the complete declaration of the agent, including *how* it runs.
- Tests construct the primitive with a stub executor — no monkeypatching needed.
- CS10.5 extension ships new executors as library callables without any primitive change.

- [ ] **Step 1: Add failing tests for response channel and configuration fields**

Append to `agent-foundry/tests/agent_foundry/primitives/test_agent_action_model.py`:

```python
# ======================================================================
# AgentAction — response channels
# ======================================================================


from agent_foundry.primitives.models import (
    FileCollectionChannel,
    StructuredOutputChannel,
)


def _stub_file_builder(files: dict[str, str]) -> StubOutput:
    return StubOutput(result=files.get("/workspace/out.md", ""))


class TestAgentActionResponseChannel:
    """response_channel is required; product must choose structured or file."""

    def test_missing_response_channel_raises(self):
        with pytest.raises(ValidationError):
            AgentAction[StubInput, StubOutput](
                prompt_builder=_stub_prompt_builder,
                instructions_provider=_stub_instructions_provider,
            )

    def test_structured_output_channel_accepted(self):
        action = AgentAction[StubInput, StubOutput](
            prompt_builder=_stub_prompt_builder,
            instructions_provider=_stub_instructions_provider,
            response_channel=StructuredOutputChannel(),
        )
        assert isinstance(action.response_channel, StructuredOutputChannel)

    def test_file_collection_channel_accepted(self):
        action = AgentAction[StubInput, StubOutput](
            prompt_builder=_stub_prompt_builder,
            instructions_provider=_stub_instructions_provider,
            response_channel=FileCollectionChannel(
                files=["/workspace/out.md"],
                builder=_stub_file_builder,
            ),
        )
        assert isinstance(action.response_channel, FileCollectionChannel)
        assert action.response_channel.files == ["/workspace/out.md"]
        assert callable(action.response_channel.builder)

    def test_file_collection_requires_files(self):
        with pytest.raises(ValidationError):
            FileCollectionChannel(builder=_stub_file_builder)

    def test_file_collection_requires_builder(self):
        with pytest.raises(ValidationError):
            FileCollectionChannel(files=["/workspace/out.md"])


# ======================================================================
# AgentAction — executor
# ======================================================================


def _stub_executor(*, primitive, prompt) -> StubOutput:
    return StubOutput(result="stub")


class TestAgentActionExecutor:
    """executor is required; product supplies the callable that runs the agent."""

    def test_missing_executor_raises(self):
        with pytest.raises(ValidationError):
            AgentAction[StubInput, StubOutput](
                prompt_builder=_stub_prompt_builder,
                instructions_provider=_stub_instructions_provider,
                response_channel=StructuredOutputChannel(),
            )

    def test_executor_accepted(self):
        action = AgentAction[StubInput, StubOutput](
            prompt_builder=_stub_prompt_builder,
            instructions_provider=_stub_instructions_provider,
            response_channel=StructuredOutputChannel(),
            executor=_stub_executor,
        )
        assert action.executor is _stub_executor

    def test_executor_is_callable(self):
        action = AgentAction[StubInput, StubOutput](
            prompt_builder=_stub_prompt_builder,
            instructions_provider=_stub_instructions_provider,
            response_channel=StructuredOutputChannel(),
            executor=_stub_executor,
        )
        result = action.executor(primitive=action, prompt="hi")
        assert result == StubOutput(result="stub")


# ======================================================================
# AgentAction — configuration fields with platform defaults
# ======================================================================


def _new_structured_action() -> AgentAction:
    return AgentAction[StubInput, StubOutput](
        prompt_builder=_stub_prompt_builder,
        instructions_provider=_stub_instructions_provider,
        response_channel=StructuredOutputChannel(),
        executor=_stub_executor,
    )


class TestAgentActionConfigFields:
    """AgentAction has configuration fields with platform defaults."""

    def test_timeout_seconds_defaults_to_3600(self):
        action = _new_structured_action()
        assert action.timeout_seconds == 3600

    def test_timeout_seconds_must_be_positive(self):
        with pytest.raises(ValidationError):
            AgentAction[StubInput, StubOutput](
                prompt_builder=_stub_prompt_builder,
                instructions_provider=_stub_instructions_provider,
                response_channel=StructuredOutputChannel(),
                executor=_stub_executor,
                timeout_seconds=0,
            )

    def test_skip_permissions_defaults_to_false(self):
        action = _new_structured_action()
        assert action.skip_permissions is False

    def test_visible_dirs_default_to_empty(self):
        # Safe-by-default: nothing under /workspace is visible unless declared.
        assert _new_structured_action().visible_dirs == []

    def test_writable_dirs_default_to_empty(self):
        # Safe-by-default: nothing under /workspace is writable unless declared.
        assert _new_structured_action().writable_dirs == []

    def test_reuse_policy_defaults_to_new_each_time(self):
        assert _new_structured_action().reuse_policy == ContainerReusePolicy.NEW_EACH_TIME

    def test_reuse_policy_accepts_all_values(self):
        for policy in ContainerReusePolicy:
            action = AgentAction[StubInput, StubOutput](
                prompt_builder=_stub_prompt_builder,
                instructions_provider=_stub_instructions_provider,
                response_channel=StructuredOutputChannel(),
                executor=_stub_executor,
                reuse_policy=policy,
            )
            assert action.reuse_policy == policy
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/markn/engineering/jig-archipelago/agent-foundry && pdm test-unit tests/agent_foundry/primitives/test_agent_action_model.py`
Expected: FAIL — `StructuredOutputChannel`/`FileCollectionChannel` not importable; `response_channel` required field missing; other fields (`visible_dirs`, etc.) also missing.

- [ ] **Step 3: Add response channel types and extend `AgentAction`**

In `agent-foundry/src/agent_foundry/primitives/models.py`, at the top of the file after existing imports, add:

```python
from typing import Annotated, Any, Literal
```

Add these classes before `class AgentAction` (the response channel types are leaf Pydantic models used as a discriminated union):

```python
class StructuredOutputChannel(BaseModel):
    """Agent returns its output via ``--json-schema`` structured output.

    The runner derives the JSON schema from the AgentAction's output type
    ``O``, passes it to Claude Code, and validates the returned
    ``AgentTurnEnvelope[O]`` structurally before returning an ``O`` instance.
    """

    kind: Literal["structured_output"] = "structured_output"


class FileCollectionChannel(BaseModel):
    """Agent returns its output by writing files to the workspace.

    The runner reads the files listed in ``files`` from the container
    after the agent completes, then calls ``builder`` with a mapping
    of container path to file contents to construct an ``O`` instance.
    """

    kind: Literal["file_collection"] = "file_collection"
    files: list[str] = Field(min_length=1)
    builder: Callable[[dict[str, str]], BaseModel]


ResponseChannel = Annotated[
    StructuredOutputChannel | FileCollectionChannel,
    Field(discriminator="kind"),
]
```

Replace the `AgentAction` class body in `models.py` with:

```python
class AgentAction[I: BaseModel, O: BaseModel](Primitive[I, O]):
    """Run an LLM agent in a container to transform input state to output state.

    Two-sided interface:
      - Product side declares agent configuration via collaborator callables
        (``prompt_builder``, ``instructions_provider``) and chooses a
        response channel (``response_channel``).
      - Platform side handles container lifecycle, instruction injection,
        structured output, and response validation.

    This primitive is a leaf (no children). The compiler registers a node
    that calls the prompt builder, then delegates to the agent runner.
    The runner always returns an instance of ``O``, regardless of response
    channel — the channel is a runner-internal concern.
    """

    # Product-side collaborators
    prompt_builder: Callable[[I], str]
    instructions_provider: Callable[[], str]

    # Response channel — required, no default. Product chooses at design time;
    # an agent does not switch channels at runtime.
    response_channel: ResponseChannel

    # Executor — required, no default. The callable that actually runs the
    # agent and returns an instance of ``O``. Plan 1 ships
    # ``run_agent_in_container`` (container + Claude Code CLI). CS10.5 will
    # add SDK and API executors as additional callables products can choose.
    # Different agents in the same system can use different executors.
    #
    # Contract: ``executor(*, primitive: AgentAction, prompt: str) -> O``.
    # The compiler calls the executor with keyword arguments; the primitive
    # passed in is the same ``AgentAction`` instance (the executor can read
    # ``instructions_provider``, ``response_channel``, container config, etc.
    # from it).
    executor: Callable[..., BaseModel]

    # Container configuration (platform defaults, product may override)
    timeout_seconds: int = Field(default=3600, ge=1)
    skip_permissions: bool = False

    # Filesystem access — governs /workspace only; paths outside /workspace
    # are unaffected (they are baked into the image and not mounted).
    # Safe-by-default: both default to empty, meaning the agent sees nothing
    # under /workspace and can write nothing under /workspace. Product must
    # explicitly opt in by listing directories.
    #
    # writable implies visible. If the agent needs /workspace itself visible
    # (e.g. to run `pwd` or navigate), the product must list "/workspace"
    # in visible_dirs. Misconfiguration produces a runtime failure from the
    # agent (e.g. "permission denied writing to /workspace/src") — not a
    # silent grant of access.
    visible_dirs: list[str] = Field(default_factory=list)
    writable_dirs: list[str] = Field(default_factory=list)

    # Container reuse
    reuse_policy: ContainerReusePolicy = ContainerReusePolicy.NEW_EACH_TIME
```

Ensure `StructuredOutputChannel` and `FileCollectionChannel` each get a `model_rebuild()` call at the bottom of the file, alongside the other primitive rebuilds.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/markn/engineering/jig-archipelago/agent-foundry && pdm test-unit tests/agent_foundry/primitives/test_agent_action_model.py`
Expected: PASS (all `TestAgentAction*` tests)

- [ ] **Step 5: Commit**

```bash
cd /home/markn/engineering/jig-archipelago/agent-foundry
git add src/agent_foundry/primitives/models.py tests/agent_foundry/primitives/test_agent_action_model.py
git commit -m "feat(primitives): add AgentAction response channels and configuration fields"
```

---

## Task 4: Export `AgentAction` from Package

**Files:**
- Modify: `agent-foundry/src/agent_foundry/primitives/__init__.py`
- Modify: `agent-foundry/tests/agent_foundry/primitives/test_primitive_models.py`

**Dependencies:** Task 3.

- [ ] **Step 1: Add failing test for package export**

In `agent-foundry/tests/agent_foundry/primitives/test_primitive_models.py`, find `class TestPublicAPI`. Add these tests inside that class:

```python
    def test_agent_action_importable_from_package(self):
        from agent_foundry.primitives import AgentAction

        assert AgentAction is not None

    def test_container_reuse_policy_importable_from_package(self):
        from agent_foundry.primitives import ContainerReusePolicy

        assert ContainerReusePolicy is not None

    def test_response_channels_importable_from_package(self):
        from agent_foundry.primitives import (
            FileCollectionChannel,
            StructuredOutputChannel,
        )

        assert StructuredOutputChannel is not None
        assert FileCollectionChannel is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/markn/engineering/jig-archipelago/agent-foundry && pdm test-unit tests/agent_foundry/primitives/test_primitive_models.py::TestPublicAPI`
Expected: FAIL with `ImportError: cannot import name 'AgentAction' from 'agent_foundry.primitives'`

- [ ] **Step 3: Export from `__init__.py`**

In `agent-foundry/src/agent_foundry/primitives/__init__.py`, replace the entire file with:

```python
"""Composable, typed plan primitives for Agent Foundry."""

from agent_foundry.primitives.errors import (
    InvalidPromptKeyError,
    PrimitiveCompilationError,
    PrimitiveValidationError,
    TypeMismatchError,
)
from agent_foundry.primitives.models import (
    AgentAction,
    Conditional,
    ContainerReusePolicy,
    FileCollectionChannel,
    FunctionAction,
    GateAction,
    Loop,
    Primitive,
    Retry,
    Sequence,
    StructuredOutputChannel,
)
from agent_foundry.primitives.plan import PrimitivePlan
from agent_foundry.primitives.validators import validate_primitive

__all__ = [
    "AgentAction",
    "Conditional",
    "ContainerReusePolicy",
    "FileCollectionChannel",
    "FunctionAction",
    "GateAction",
    "InvalidPromptKeyError",
    "Loop",
    "Primitive",
    "PrimitiveCompilationError",
    "PrimitivePlan",
    "PrimitiveValidationError",
    "Retry",
    "Sequence",
    "StructuredOutputChannel",
    "TypeMismatchError",
    "validate_primitive",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/markn/engineering/jig-archipelago/agent-foundry && pdm test-unit tests/agent_foundry/primitives/test_primitive_models.py::TestPublicAPI`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/markn/engineering/jig-archipelago/agent-foundry
git add src/agent_foundry/primitives/__init__.py tests/agent_foundry/primitives/test_primitive_models.py
git commit -m "feat(primitives): export AgentAction and ContainerReusePolicy from package"
```

---

## Task 5: Refactor Validator to Use a Registry

**Files:**
- Modify: `agent-foundry/src/agent_foundry/primitives/validators.py`
- Modify: `agent-foundry/src/agent_foundry/primitives/errors.py`
- Modify: `agent-foundry/src/agent_foundry/primitives/__init__.py`
- Modify: `agent-foundry/tests/agent_foundry/primitives/test_primitive_validators.py`

**Dependencies:** Task 4.

**Background**: Today `validate_primitive` is an if/elif chain over concrete types. Adding a new primitive requires editing this chain — closed to extension. The compiler already uses a registry (`register_compiler`); we mirror that pattern for validation so applications can define their own primitives with their own validators.

Unknown primitive types (no registered validator) raise `UnregisteredPrimitiveError`. Silent no-op fallback is rejected — it hides misconfiguration.

**Sequential-execution constraint with Task 4**: Both Task 4 and Task 5 (Step 5) perform wholesale replacement of `primitives/__init__.py`. If these tasks are parallelized (e.g., via `team-dev`), only one write lands — losing `register_validator`/`UnregisteredPrimitiveError` exports or the `AgentAction` export, silently. Task 5 must run sequentially after Task 4 completes. If using `team-dev`, serialize these two tasks explicitly.

- [ ] **Step 1: Add the new error class**

In `agent-foundry/src/agent_foundry/primitives/errors.py`, append:

```python
class UnregisteredPrimitiveError(PrimitiveValidationError):
    """No validator registered for a primitive type encountered during validation."""

    def __init__(self, message: str, primitive_type: type):
        self.primitive_type = primitive_type
        super().__init__(message)
```

- [ ] **Step 2: Write failing tests for the registry API**

Create a new test class at the top of `agent-foundry/tests/agent_foundry/primitives/test_primitive_validators.py`. If you need to add imports, include:

```python
import pytest
from pydantic import BaseModel

from agent_foundry.primitives.errors import (
    TypeMismatchError,
    UnregisteredPrimitiveError,
)
from agent_foundry.primitives.models import (
    AgentAction,
    Primitive,
    Sequence,
)
from agent_foundry.primitives.validators import (
    register_validator,
    validate_primitive,
)
```

Add these test cases (use a unique name prefix so they don't collide with existing tests):

```python
# ======================================================================
# Validator registry
# ======================================================================


class _RegInput(BaseModel):
    value: str


class _RegOutput(BaseModel):
    result: str


class TestValidatorRegistry:
    """Validator dispatch uses a registry keyed by primitive type."""

    def test_unknown_primitive_type_raises(self):
        class MyCustomPrimitive[I: BaseModel, O: BaseModel](Primitive[I, O]):
            pass

        prim = MyCustomPrimitive[_RegInput, _RegOutput]()
        with pytest.raises(UnregisteredPrimitiveError, match="MyCustomPrimitive"):
            validate_primitive(prim)

    def test_registering_validator_allows_validation(self):
        class MyCustomPrimitive2[I: BaseModel, O: BaseModel](Primitive[I, O]):
            pass

        calls: list[object] = []

        def _my_validator(prim):
            calls.append(prim)

        register_validator(MyCustomPrimitive2, _my_validator)

        prim = MyCustomPrimitive2[_RegInput, _RegOutput]()
        validate_primitive(prim)
        assert len(calls) == 1
        assert calls[0] is prim

    def test_registry_walks_mro_for_subclasses(self):
        class ParentPrim[I: BaseModel, O: BaseModel](Primitive[I, O]):
            pass

        class ChildPrim[I: BaseModel, O: BaseModel](ParentPrim[I, O]):
            pass

        calls: list[str] = []

        def _parent_validator(prim):
            calls.append("parent")

        register_validator(ParentPrim, _parent_validator)

        child = ChildPrim[_RegInput, _RegOutput]()
        validate_primitive(child)
        assert calls == ["parent"]

    def test_reregistering_overwrites_previous(self):
        """Last-write-wins is intentional — products may override built-in validators."""

        class OverridePrim[I: BaseModel, O: BaseModel](Primitive[I, O]):
            pass

        calls: list[str] = []

        def _first(prim):
            calls.append("first")

        def _second(prim):
            calls.append("second")

        register_validator(OverridePrim, _first)
        register_validator(OverridePrim, _second)

        prim = OverridePrim[_RegInput, _RegOutput]()
        validate_primitive(prim)
        assert calls == ["second"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /home/markn/engineering/jig-archipelago/agent-foundry && pdm test-unit tests/agent_foundry/primitives/test_primitive_validators.py::TestValidatorRegistry`
Expected: FAIL — `register_validator` not importable, `UnregisteredPrimitiveError` not raised. (4 tests total: unknown raises, register allows, MRO walk, re-registration overwrites.)

- [ ] **Step 4: Refactor `validators.py` to use a registry**

Replace the contents of `agent-foundry/src/agent_foundry/primitives/validators.py` with:

```python
"""Graph-level type compatibility validation for primitives.

Uses a registry keyed by primitive type. Built-in primitives register
their validators at module import. Applications can define their own
Primitive subclasses and register validators for them via
``register_validator``.

Unknown primitive types raise ``UnregisteredPrimitiveError`` — silent
no-op fallback is rejected to prevent misconfiguration.
"""

from __future__ import annotations

from collections.abc import Callable

from agent_foundry.primitives.errors import (
    InvalidPromptKeyError,
    TypeMismatchError,
    UnregisteredPrimitiveError,
)
from agent_foundry.primitives.models import (
    AgentAction,
    Conditional,
    FunctionAction,
    GateAction,
    Loop,
    Primitive,
    Retry,
    Sequence,
    get_type_args,
)

# -- Registry --

type ValidatorFn = Callable[[Primitive], None]

_validator_registry: dict[type[Primitive], ValidatorFn] = {}


def register_validator(prim_type: type[Primitive], fn: ValidatorFn) -> None:
    """Register a validator function for a primitive type."""
    _validator_registry[prim_type] = fn


def validate_primitive(prim: Primitive) -> None:
    """Validate a primitive (and recursively, its children).

    Walks the type's MRO so a validator registered for a parent class
    handles subclasses unless a subclass has its own entry.

    Raises ``UnregisteredPrimitiveError`` if no validator is registered
    for any class in the primitive's MRO.
    """
    prim_type = type(prim)
    for cls in prim_type.__mro__:
        fn = _validator_registry.get(cls)
        if fn is not None:
            fn(prim)
            return
    raise UnregisteredPrimitiveError(
        f"No validator registered for {prim_type.__name__}; "
        f"register one with register_validator(...)",
        primitive_type=prim_type,
    )


# -- Helpers --


def _types_match(a: type, b: type) -> bool:
    """Check if two types are exactly the same (no subtype checks)."""
    return a is b


def _fields_available(required_type: type, available_fields: set[str], position: str) -> None:
    """Validate that all fields of required_type are present in available_fields."""
    required_fields = set(required_type.model_fields.keys())
    missing = required_fields - available_fields
    if missing:
        raise TypeMismatchError(
            message=(
                f"{position}: {required_type.__name__} requires fields "
                f"{sorted(missing)} not available in accumulated state "
                f"(available: {sorted(available_fields)})"
            ),
            expected=required_type,
            actual=required_type,
            position=position,
        )


# -- Per-type validators --


def _validate_sequence(seq: Sequence) -> None:
    seq_in, seq_out = get_type_args(seq)
    step_types = [get_type_args(s) for s in seq.steps]

    accumulated_fields = set(seq_in.model_fields.keys())

    for i, (step_in, step_out) in enumerate(step_types):
        _fields_available(step_in, accumulated_fields, f"Sequence step {i} input")
        accumulated_fields |= set(step_out.model_fields.keys())

    _fields_available(seq_out, accumulated_fields, "Sequence output")

    for step in seq.steps:
        validate_primitive(step)


def _validate_loop(loop: Loop) -> None:
    # Loop body type compatibility is deferred to the compiler (CS3).
    validate_primitive(loop.body)


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


def _validate_conditional(cond: Conditional) -> None:
    cond_in, cond_out = get_type_args(cond)
    then_in, then_out = get_type_args(cond.then_branch)

    if cond.else_branch is None:
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


def _validate_gate_action(gate: GateAction) -> None:
    input_type, _ = get_type_args(gate)
    available = list(input_type.model_fields.keys())
    if gate.prompt_key not in available:
        raise InvalidPromptKeyError(
            message=(
                f"GateAction prompt_key '{gate.prompt_key}' not found in "
                f"{input_type.__name__}; available fields: {available}"
            ),
            prompt_key=gate.prompt_key,
            available_fields=available,
        )


def _validate_function_action(action: FunctionAction) -> None:
    # FunctionAction has no graph-level constraints beyond Primitive
    # parameterization (enforced at construction).
    return


def _validate_agent_action(action: AgentAction) -> None:
    # AgentAction is a leaf — no children to recurse into, no
    # graph-level constraints beyond Primitive parameterization.
    return


# -- Registration --

register_validator(Sequence, _validate_sequence)
register_validator(Loop, _validate_loop)
register_validator(Retry, _validate_retry)
register_validator(Conditional, _validate_conditional)
register_validator(GateAction, _validate_gate_action)
register_validator(FunctionAction, _validate_function_action)
register_validator(AgentAction, _validate_agent_action)
```

- [ ] **Step 5: Export `register_validator` and `UnregisteredPrimitiveError` from the package**

In `agent-foundry/src/agent_foundry/primitives/__init__.py`, update the imports and `__all__`:

```python
"""Composable, typed plan primitives for Agent Foundry."""

from agent_foundry.primitives.errors import (
    InvalidPromptKeyError,
    PrimitiveCompilationError,
    PrimitiveValidationError,
    TypeMismatchError,
    UnregisteredPrimitiveError,
)
from agent_foundry.primitives.models import (
    AgentAction,
    Conditional,
    ContainerReusePolicy,
    FileCollectionChannel,
    FunctionAction,
    GateAction,
    Loop,
    Primitive,
    Retry,
    Sequence,
    StructuredOutputChannel,
)
from agent_foundry.primitives.plan import PrimitivePlan
from agent_foundry.primitives.validators import register_validator, validate_primitive

__all__ = [
    "AgentAction",
    "Conditional",
    "ContainerReusePolicy",
    "FileCollectionChannel",
    "FunctionAction",
    "GateAction",
    "InvalidPromptKeyError",
    "Loop",
    "Primitive",
    "PrimitiveCompilationError",
    "PrimitivePlan",
    "PrimitiveValidationError",
    "Retry",
    "Sequence",
    "StructuredOutputChannel",
    "TypeMismatchError",
    "UnregisteredPrimitiveError",
    "register_validator",
    "validate_primitive",
]
```

- [ ] **Step 6: Update existing validator tests — replace bare `Primitive[...]` leaves with `FunctionAction`**

**Why:** The existing `test_primitive_validators.py` uses `Primitive[StateA, StateB]()` as a stand-in leaf in ~37 places (nested inside Sequence, Loop, Retry, Conditional tests). The old if/elif dispatch silently no-opped for bare `Primitive`. The new registry raises `UnregisteredPrimitiveError` for any type with no registered validator — and `Primitive` itself has none (by design — see the lesson "unknown types raise, don't silently no-op"). Registering a no-op for `Primitive` would also apply to any user-defined subclass via MRO, defeating the safety guarantee. Instead, rewrite the tests to use `FunctionAction` (which has a registered no-op validator) as the leaf stand-in.

**Mechanical transformation:** every occurrence of
```python
Primitive[X, Y]()
```
becomes
```python
FunctionAction[X, Y](function=lambda s: Y(...))
```
where the lambda returns a `Y` instance. For type-mismatch test fixtures, the lambda body doesn't matter — the validator runs on types alone, never calls the function. Use `Y.model_construct()` (bypasses Pydantic validation) or a minimal valid instance — whatever is simplest per fixture.

**How:** In `agent-foundry/tests/agent_foundry/primitives/test_primitive_validators.py`:

1. Update imports to replace `Primitive` with `FunctionAction`:
   ```python
   from agent_foundry.primitives.models import (
       Conditional,
       FunctionAction,
       GateAction,
       Loop,
       Retry,
       Sequence,
   )
   ```
   (Remove `Primitive` from this import if it's no longer used; keep it if any other test still references it.)

2. Grep for every `Primitive[` in this file and replace with `FunctionAction[`, adding `function=lambda s: <OutputType>.model_construct()` to each construction. Example:
   ```python
   # Before:
   step = Primitive[StateA, StateB]()
   # After:
   step = FunctionAction[StateA, StateB](function=lambda s: StateB.model_construct())
   ```

3. For `Primitive[StateX, StateX]()` (same type in and out), use:
   ```python
   step = FunctionAction[StateX, StateX](function=lambda s: s)
   ```

4. Affected test classes (per earlier grep — confirm with the actual file): `TestValidateSequence`, `TestValidateLoop`, `TestValidateRetry`, `TestValidateConditional`, and any tests using `Primitive[...]()` as a body/step/branch.

- [ ] **Step 7: Run all validator tests and full primitives suite**

Run: `cd /home/markn/engineering/jig-archipelago/agent-foundry && pdm test-unit tests/agent_foundry/primitives/`
Expected: PASS — all existing validator tests still pass (behavior preserved via `FunctionAction` leaves), plus the 3 new registry tests from Step 2.

If tests fail with `UnregisteredPrimitiveError`, a `Primitive[...]` construction was missed — grep again and update.

- [ ] **Step 8: Commit**

```bash
cd /home/markn/engineering/jig-archipelago/agent-foundry
git add src/agent_foundry/primitives/validators.py src/agent_foundry/primitives/errors.py src/agent_foundry/primitives/__init__.py tests/agent_foundry/primitives/test_primitive_validators.py
git commit -m "refactor(primitives): open validator dispatch via registry; register AgentAction"
```

---

## Task 5b: Validate `AgentAction` Composition Scenarios

**Files:**
- Modify: `agent-foundry/tests/agent_foundry/primitives/test_primitive_validators.py`

**Dependencies:** Task 5.

**Background**: With `AgentAction` registered, confirm it works correctly when nested inside parent primitives (`Sequence`, `Retry`). These tests verify behavior end-to-end; Task 5 only tested the registry itself.

- [ ] **Step 1: Add failing tests for `AgentAction` composition**

Add the `StructuredOutputChannel` import to the top of `test_primitive_validators.py` if not already present:

```python
from agent_foundry.primitives.models import (
    AgentAction,
    StructuredOutputChannel,
    # ... other imports that already exist
)
```

Append to `agent-foundry/tests/agent_foundry/primitives/test_primitive_validators.py`:

```python
# ======================================================================
# AgentAction composition validation
# ======================================================================


class _AgentValInput(BaseModel):
    value: str


class _AgentValOutput(BaseModel):
    value: str
    result: str


def _stub_prompt_builder_for_validator(state):
    return "prompt"


def _stub_instructions_for_validator() -> str:
    return "# instructions"


def _stub_executor_for_validator(*, primitive, prompt) -> _AgentValOutput:
    return _AgentValOutput(value="v", result="r")


def _make_agent_action(input_type, output_type):
    """Build an AgentAction with all required fields populated."""
    return AgentAction[input_type, output_type](
        prompt_builder=_stub_prompt_builder_for_validator,
        instructions_provider=_stub_instructions_for_validator,
        response_channel=StructuredOutputChannel(),
        executor=_stub_executor_for_validator,
    )


class TestAgentActionCompositionValidation:
    """AgentAction composes correctly inside parent primitives."""

    def test_standalone_agent_action_validates(self):
        action = _make_agent_action(_AgentValInput, _AgentValOutput)
        validate_primitive(action)  # should not raise

    def test_agent_action_in_sequence_validates_types(self):
        action = _make_agent_action(_AgentValInput, _AgentValOutput)
        seq = Sequence[_AgentValInput, _AgentValOutput](steps=[action])
        validate_primitive(seq)  # should not raise

    def test_agent_action_in_sequence_with_missing_input_raises(self):
        class _OtherInput(BaseModel):
            other: str

        action = _make_agent_action(_OtherInput, _AgentValOutput)
        seq = Sequence[_AgentValInput, _AgentValOutput](steps=[action])
        with pytest.raises(TypeMismatchError):
            validate_primitive(seq)
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd /home/markn/engineering/jig-archipelago/agent-foundry && pdm test-unit tests/agent_foundry/primitives/test_primitive_validators.py::TestAgentActionCompositionValidation`
Expected: PASS (3 tests)

- [ ] **Step 3: Commit**

```bash
cd /home/markn/engineering/jig-archipelago/agent-foundry
git add tests/agent_foundry/primitives/test_primitive_validators.py
git commit -m "test(primitives): verify AgentAction composes correctly under validation"
```

---

## Task 6: Create Stub `agent_runner` Module (Container Executor)

**Files:**
- Create: `agent-foundry/src/agent_foundry/acp/agent_runner.py`
- Create: `agent-foundry/tests/agent_foundry/acp/test_agent_runner_stub.py`

**Dependencies:** Task 4.

**Background**: `run_agent_in_container` is the platform-provided container executor — a callable products can supply as `AgentAction.executor`. Its signature matches the executor contract: `(*, primitive: AgentAction, prompt: str) -> BaseModel`. It returns an instance of the primitive's output type `O` — envelope unwrapping, structured-output vs. file-collection branching, and schema validation all happen inside the executor, not in the compiler.

Diagnostics (exit codes, raw stdout lines) are not returned — they flow through the lifecycle tracker in Plan 2.

The stub raises `NotImplementedError`. Tests that exercise the compiler use their own stub executors (no monkeypatching needed — the executor is a field on `AgentAction`).

- [ ] **Step 1: Write failing tests for the stub**

Create `agent-foundry/tests/agent_foundry/acp/test_agent_runner_stub.py`:

```python
"""Tests for the agent runner stub (Plan 1 scope).

The real implementation lands in Plan 2. This test file verifies that
``run_agent_in_container`` is importable and raises NotImplementedError
when called — so real invocations before Plan 2 fail loudly rather than
silently.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from agent_foundry.acp.agent_runner import run_agent_in_container
from agent_foundry.primitives.models import (
    AgentAction,
    ContainerReusePolicy,
    StructuredOutputChannel,
)


class _StubInput(BaseModel):
    value: str


class _StubOutput(BaseModel):
    result: str


class TestRunAgentInContainerStub:
    @pytest.mark.parametrize("policy", list(ContainerReusePolicy))
    def test_raises_not_implemented_error_for_every_reuse_policy(self, policy):
        # The stub ignores reuse_policy; all values raise NotImplementedError.
        # Plan 2 will implement policy-specific behavior — this test pins
        # the stub's policy-agnostic contract until then.
        action = AgentAction[_StubInput, _StubOutput](
            prompt_builder=lambda s: "prompt",
            instructions_provider=lambda: "instructions",
            response_channel=StructuredOutputChannel(),
            executor=run_agent_in_container,
            reuse_policy=policy,
        )
        with pytest.raises(NotImplementedError, match="Plan 2"):
            run_agent_in_container(primitive=action, prompt="hi")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/markn/engineering/jig-archipelago/agent-foundry && pdm test-unit tests/agent_foundry/acp/test_agent_runner_stub.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_foundry.acp.agent_runner'`

- [ ] **Step 3: Create the stub module**

Create `agent-foundry/src/agent_foundry/acp/agent_runner.py`:

```python
"""Container executor for AgentAction — runs an agent in a Docker container.

This is the platform-provided container executor. Products pass it (or a
substitute) as the ``executor`` field on an ``AgentAction``:

    action = AgentAction[...](
        ...,
        executor=run_agent_in_container,
    )

The real implementation lands in Plan 2 of CS7. Plan 1 establishes only
the function signature so products can wire it up and the compiler has
a callable to invoke. The Plan 1 body raises ``NotImplementedError`` —
any real invocation before Plan 2 fails loudly. Tests that exercise
the compiler supply their own executor directly on the ``AgentAction``
(no monkeypatching — ``executor`` is an explicit field).

Design note: the executor returns an instance of the ``AgentAction``'s
output type ``O``, not a wrapper result object. This mirrors
``FunctionAction.function``: the thing the compiler calls returns ``O``
or raises. Diagnostics (exit codes, stdout lines) flow to the lifecycle
tracker in Plan 2, not through the return value.
"""

from __future__ import annotations

from pydantic import BaseModel

from agent_foundry.primitives.models import AgentAction


def run_agent_in_container(
    *,
    primitive: AgentAction,
    prompt: str,
) -> BaseModel:
    """Run the agent described by ``primitive`` with ``prompt``.

    The runner takes the full ``AgentAction`` primitive so it can read
    all configuration (instructions provider, response channel, container
    settings, reuse policy) without the compiler having to forward each
    field individually.

    Returns an instance of the primitive's output type ``O``. The caller
    is expected to merge it into graph state.

    Raises:
        NotImplementedError: Always, until Plan 2 lands.
    """
    raise NotImplementedError(
        "run_agent_in_container is a stub until CS7 Plan 2 lands. "
        "Tests exercising the AgentAction compiler should supply their own "
        "executor callable on the AgentAction rather than using this stub."
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/markn/engineering/jig-archipelago/agent-foundry && pdm test-unit tests/agent_foundry/acp/test_agent_runner_stub.py`
Expected: PASS (3 tests — one per `ContainerReusePolicy` value)

- [ ] **Step 5: Commit**

```bash
cd /home/markn/engineering/jig-archipelago/agent-foundry
git add src/agent_foundry/acp/agent_runner.py tests/agent_foundry/acp/test_agent_runner_stub.py
git commit -m "feat(acp): add agent_runner stub with primitive + prompt signature"
```

---

## Task 7: Compile `AgentAction`

**Files:**
- Modify: `agent-foundry/src/agent_foundry/compiler/primitive_compiler.py`
- Create: `agent-foundry/tests/agent_foundry/compiler/test_agent_action_compiler.py`

**Dependencies:** Tasks 5b and 6.

**Background — structural parity with FunctionAction**: The compiler node for `AgentAction` mirrors `FunctionAction`:

```
FunctionAction node:        AgentAction node:
  validate input state  →     validate input state
  build I model         →     build I model
  call action.function  →     build prompt via prompt_builder
  return result         →     call action.executor(primitive, prompt)
                              return result
```

Both primitives invoke a product-supplied callable on the primitive itself (`action.function` / `action.executor`). The executor owns envelope unwrapping, schema validation, and response-channel branching. The compiler simply: validates input, builds the prompt, calls the executor, merges returned `O` into state.

No `agent_runner` import in the compiler. The compiler doesn't know whether the agent runs in a container, via SDK, or via API — that's the product's declaration.

- [ ] **Step 1: Write failing tests**

Create `agent-foundry/tests/agent_foundry/compiler/test_agent_action_compiler.py`:

```python
"""Tests for the AgentAction compiler node."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from agent_foundry.compiler.primitive_compiler import compile_primitive
from agent_foundry.primitives.errors import PrimitiveCompilationError
from agent_foundry.primitives.models import (
    AgentAction,
    StructuredOutputChannel,
)
from agent_foundry.primitives.plan import PrimitivePlan


class AgentInput(BaseModel):
    query: str


class AgentOutput(BaseModel):
    answer: str


_prompts_built: list[str] = []


def _record_prompt_builder(state: AgentInput) -> str:
    prompt = f"Q: {state.query}"
    _prompts_built.append(prompt)
    return prompt


def _stub_instructions() -> str:
    return "instructions"


@pytest.fixture(autouse=True)
def reset_recorded_prompts():
    _prompts_built.clear()
    yield
    _prompts_built.clear()


class TestAgentActionCompiler:
    """The AgentAction compiler node mirrors FunctionAction behavior.

    The compiler calls ``action.executor(primitive=action, prompt=...)``.
    Tests supply their executor directly on the AgentAction — no monkey-
    patching, because the executor is an explicit field on the primitive.
    """

    def test_executor_called_with_primitive_and_prompt(self):
        captured: dict[str, Any] = {}

        def _executor(*, primitive, prompt):
            captured["primitive"] = primitive
            captured["prompt"] = prompt
            return AgentOutput(answer="42")

        action = AgentAction[AgentInput, AgentOutput](
            prompt_builder=_record_prompt_builder,
            instructions_provider=_stub_instructions,
            response_channel=StructuredOutputChannel(),
            executor=_executor,
        )
        plan = PrimitivePlan(root=action)
        graph = compile_primitive(plan)

        graph.invoke({"query": "hello"})

        assert _prompts_built == ["Q: hello"]
        assert captured["prompt"] == "Q: hello"
        assert captured["primitive"] is action

    def test_missing_required_input_field_raises(self):
        def _executor(*, primitive, prompt):
            return AgentOutput(answer="42")

        action = AgentAction[AgentInput, AgentOutput](
            prompt_builder=_record_prompt_builder,
            instructions_provider=_stub_instructions,
            response_channel=StructuredOutputChannel(),
            executor=_executor,
        )
        plan = PrimitivePlan(root=action)
        graph = compile_primitive(plan)

        with pytest.raises(PrimitiveCompilationError, match="Boundary validation failed"):
            graph.invoke({})  # missing `query`

    def test_executor_output_merged_into_state(self):
        def _executor(*, primitive, prompt):
            return AgentOutput(answer="42")

        action = AgentAction[AgentInput, AgentOutput](
            prompt_builder=_record_prompt_builder,
            instructions_provider=_stub_instructions,
            response_channel=StructuredOutputChannel(),
            executor=_executor,
        )
        plan = PrimitivePlan(root=action)
        graph = compile_primitive(plan)

        result = graph.invoke({"query": "hello"})

        assert result["answer"] == "42"

    def test_executor_must_return_instance_of_output_type(self):
        class WrongType(BaseModel):
            other: str

        def _executor(*, primitive, prompt):
            return WrongType(other="oops")

        action = AgentAction[AgentInput, AgentOutput](
            prompt_builder=_record_prompt_builder,
            instructions_provider=_stub_instructions,
            response_channel=StructuredOutputChannel(),
            executor=_executor,
        )
        plan = PrimitivePlan(root=action)
        graph = compile_primitive(plan)

        with pytest.raises(PrimitiveCompilationError, match="AgentOutput"):
            graph.invoke({"query": "hello"})

    def test_compiler_is_agnostic_to_response_channel(self):
        """The compiler must not branch on response_channel — that's executor-internal.

        Confirm by compiling an AgentAction that uses FileCollectionChannel
        and verifying it behaves identically to the StructuredOutputChannel
        cases above: executor is called, result is merged into state.
        """
        from agent_foundry.primitives.models import FileCollectionChannel

        def _executor(*, primitive, prompt):
            return AgentOutput(answer="42")

        def _builder(files: dict[str, str]) -> AgentOutput:
            return AgentOutput(answer=files.get("/workspace/out.md", ""))

        action = AgentAction[AgentInput, AgentOutput](
            prompt_builder=_record_prompt_builder,
            instructions_provider=_stub_instructions,
            response_channel=FileCollectionChannel(
                files=["/workspace/out.md"],
                builder=_builder,
            ),
            executor=_executor,
        )
        plan = PrimitivePlan(root=action)
        graph = compile_primitive(plan)

        result = graph.invoke({"query": "hello"})

        assert result["answer"] == "42"

    def test_compiles_with_empty_lockdown_dirs(self):
        """Empty visible_dirs/writable_dirs are a valid configuration.

        Safe-by-default invariant: empty dirs means no access, not
        no-compilation. Plan 2 implementers must not add a guard that
        rejects empty dirs.
        """

        def _executor(*, primitive, prompt):
            return AgentOutput(answer="42")

        action = AgentAction[AgentInput, AgentOutput](
            prompt_builder=_record_prompt_builder,
            instructions_provider=_stub_instructions,
            response_channel=StructuredOutputChannel(),
            executor=_executor,
            # visible_dirs and writable_dirs default to empty.
        )
        plan = PrimitivePlan(root=action)
        graph = compile_primitive(plan)

        result = graph.invoke({"query": "hello"})

        assert result["answer"] == "42"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/markn/engineering/jig-archipelago/agent-foundry && pdm test-unit tests/agent_foundry/compiler/test_agent_action_compiler.py`
Expected: FAIL with `PrimitiveCompilationError: No compiler registered for AgentAction[AgentInput, AgentOutput]`

- [ ] **Step 3: Register the `AgentAction` compiler**

In `agent-foundry/src/agent_foundry/compiler/primitive_compiler.py`, update the imports:

```python
from agent_foundry.primitives.models import (
    AgentAction,
    Conditional,
    FunctionAction,
    GateAction,
    Loop,
    Primitive,
    Retry,
    Sequence,
    get_type_args,
)
```

Add this compiler function at the end of the file (after `_compile_gate_action` and its `register_compiler` call):

```python
def _compile_agent_action(
    graph: StateGraph,
    action: AgentAction,
    prefix: str,
    gate_ids: list[str],
) -> tuple[str, str]:
    node_id = prefix
    input_type, output_type = get_type_args(action)
    prompt_builder = action.prompt_builder
    executor = action.executor

    def node_fn(state: dict[str, Any]) -> dict[str, Any]:
        _validate_boundary(state, input_type, node_id)
        model_input = input_type.model_validate(state)
        prompt = prompt_builder(model_input)

        result = executor(primitive=action, prompt=prompt)

        if not isinstance(result, output_type):
            raise PrimitiveCompilationError(
                f"AgentAction {node_id}: executor returned "
                f"{type(result).__name__}, expected {output_type.__name__}",
                primitive_type=node_id,
            )

        return result.model_dump()

    graph.add_node(node_id, node_fn)
    return (node_id, node_id)


register_compiler(AgentAction, _compile_agent_action)
```

No import of `agent_runner` is needed — the compiler doesn't know or care which executor is used.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/markn/engineering/jig-archipelago/agent-foundry && pdm test-unit tests/agent_foundry/compiler/test_agent_action_compiler.py`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/markn/engineering/jig-archipelago/agent-foundry
git add src/agent_foundry/compiler/primitive_compiler.py tests/agent_foundry/compiler/test_agent_action_compiler.py
git commit -m "feat(compiler): compile AgentAction node delegating to action.executor"
```

---

## Task 8: Verify Runner Exceptions Propagate

**Files:**
- Modify: `agent-foundry/tests/agent_foundry/compiler/test_agent_action_compiler.py`

**Dependencies:** Task 7.

**Background**: The runner owns envelope unwrapping, schema validation, and response-channel branching. When the runner detects a non-success envelope outcome, schema mismatch, container crash, or any other runtime failure, it raises an exception. The compiler node does not catch — exceptions propagate up to the graph invoker. This task verifies propagation works as expected.

- [ ] **Step 1: Add failing test for exception propagation**

Append to `agent-foundry/tests/agent_foundry/compiler/test_agent_action_compiler.py`:

```python
# ======================================================================
# AgentAction compiler — exception propagation
# ======================================================================


class _ExecutorFailure(RuntimeError):
    """Simulates any executor-level failure (non-success envelope, crash, etc)."""


class TestAgentActionCompiler_ExceptionPropagation:
    """Executor exceptions propagate through the compiled node."""

    def test_executor_exception_propagates(self):
        def _executor(*, primitive, prompt):
            raise _ExecutorFailure("agent failed")

        action = AgentAction[AgentInput, AgentOutput](
            prompt_builder=_record_prompt_builder,
            instructions_provider=_stub_instructions,
            response_channel=StructuredOutputChannel(),
            executor=_executor,
        )
        plan = PrimitivePlan(root=action)
        graph = compile_primitive(plan)

        with pytest.raises(_ExecutorFailure, match="agent failed"):
            graph.invoke({"query": "hello"})
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd /home/markn/engineering/jig-archipelago/agent-foundry && pdm test-unit tests/agent_foundry/compiler/test_agent_action_compiler.py::TestAgentActionCompiler_ExceptionPropagation`
Expected: PASS — the Task 7 compiler node calls the executor without catching, so exceptions bubble through LangGraph to the caller.

If it fails, investigate: LangGraph may wrap exceptions in some cases. Adjust the assertion to match (`match="agent failed"` should still work even if wrapped).

- [ ] **Step 3: Commit**

```bash
cd /home/markn/engineering/jig-archipelago/agent-foundry
git add tests/agent_foundry/compiler/test_agent_action_compiler.py
git commit -m "test(compiler): verify executor exceptions propagate through AgentAction node"
```

---

## Task 9: Integration Test — `AgentAction` Inside a `Sequence`

**Files:**
- Modify: `agent-foundry/tests/agent_foundry/compiler/test_agent_action_compiler.py`

**Dependencies:** Task 8.

**Background**: Final test — an `AgentAction` nested inside a `Sequence` end-to-end, to confirm the compiler's state boundary handling works correctly under composition.

- [ ] **Step 1: Add failing integration test**

Append to `agent-foundry/tests/agent_foundry/compiler/test_agent_action_compiler.py`:

```python
# ======================================================================
# AgentAction integration — nested composition
# ======================================================================


class SeqInput(BaseModel):
    query: str


class SeqMid(BaseModel):
    query: str
    answer: str


class SeqOutput(BaseModel):
    query: str
    answer: str
    annotated: str


class TestAgentActionCompiler_Composition:
    def test_agent_action_inside_sequence(self):
        from agent_foundry.primitives.models import FunctionAction, Sequence

        class AgentStepInput(BaseModel):
            query: str

        class AgentStepOutput(BaseModel):
            answer: str

        def _executor(*, primitive, prompt):
            return AgentStepOutput(answer="42")

        agent_step = AgentAction[AgentStepInput, AgentStepOutput](
            prompt_builder=lambda s: f"Q: {s.query}",
            instructions_provider=_stub_instructions,
            response_channel=StructuredOutputChannel(),
            executor=_executor,
        )
        annotate_step = FunctionAction[SeqMid, SeqOutput](
            function=lambda s: SeqOutput(
                query=s.query,
                answer=s.answer,
                annotated=f"[{s.answer}]",
            ),
        )
        seq = Sequence[SeqInput, SeqOutput](steps=[agent_step, annotate_step])
        plan = PrimitivePlan(root=seq)
        graph = compile_primitive(plan)

        result = graph.invoke({"query": "hello"})

        assert result["query"] == "hello"
        assert result["answer"] == "42"
        assert result["annotated"] == "[42]"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd /home/markn/engineering/jig-archipelago/agent-foundry && pdm test-unit tests/agent_foundry/compiler/test_agent_action_compiler.py::TestAgentActionCompiler_Composition`
Expected: PASS

If it fails, diagnose — likely a state-merging issue in the Sequence subgraph. The existing Sequence compiler merges step outputs into accumulated state; the `AgentAction` node now does the same via `dict.update`. It should work.

- [ ] **Step 3: Commit**

```bash
cd /home/markn/engineering/jig-archipelago/agent-foundry
git add tests/agent_foundry/compiler/test_agent_action_compiler.py
git commit -m "test(compiler): verify AgentAction composes correctly inside Sequence"
```

---

## Task 10: Final Verification — Full Test Suite Green

**Files:** None (verification only).

**Dependencies:** Task 9.

- [ ] **Step 1: Run the full agent-foundry unit test suite**

Run: `cd /home/markn/engineering/jig-archipelago/agent-foundry && pdm test-unit`
Expected: PASS (all existing + new tests from this plan)

- [ ] **Step 2: Run typecheck if available**

Run: `cd /home/markn/engineering/jig-archipelago/agent-foundry && pdm run typecheck` (if this command exists; otherwise skip)
Expected: PASS (no new type errors)

- [ ] **Step 3: If any failures, fix and commit**

Diagnose and fix. Commit any fixes as `fix(scope): description`.

---

## Self-Review Checklist

After completing all tasks, re-read this plan and verify:

1. **Spec coverage** — Every requirement from CS7 Agent Foundry Tasks AF-1 (primitive model), AF-2 (validator), AF-3 (compiler) in the roadmap is covered by a task here. AF-4, AF-5, AF-6, AF-7, AF-8 are deferred to later plans.
2. **Placeholder scan** — No TBD, TODO, or "figure it out later" in any step.
3. **Type consistency** — `AgentAction`, `ContainerReusePolicy`, `StructuredOutputChannel`, `FileCollectionChannel`, `run_agent_in_container` names used identically across tasks. Field names (`prompt_builder`, `instructions_provider`, `response_channel`, `executor`, `timeout_seconds`, `skip_permissions`, `visible_dirs`, `writable_dirs`, `reuse_policy`) consistent. No references to `AgentRunResult`, `instructions_path`, `output_schema`, `collect_files`, `acp_hidden_dirs`, `acp_readonly_dirs`, `_patch_runner` (all deleted). The compiler does not import `agent_runner` — it calls `action.executor` directly.
4. **Dependency ordering** — Task 1 → 2 → 3 → 4 → 5 → 5b → 7 → 8 → 9 → 10, with Task 6 parallel to Tasks 5/5b (Task 6 depends only on Task 4). Tasks 4 and 5 both write `primitives/__init__.py` — they must be serialized (not parallelized) since later writes overwrite earlier ones. Each task's dependencies are declared in its header.
5. **Command accuracy** — `pdm test-unit` is the test runner per `CLAUDE.md`. Repo is at `/home/markn/engineering/jig-archipelago/agent-foundry`.

---

## Notes for Implementers

- **TDD discipline**: Every task has a "write failing test → run to confirm fail → implement → confirm pass → commit" cycle. Do not skip the red step.
- **No monkeypatching**: Tests from Task 7 onward supply the executor directly on `AgentAction` via the `executor` field. The compiler calls `action.executor(...)` — there is no module-level `run_agent_in_container` import to patch. If you find yourself reaching for `monkeypatch.setattr`, stop and construct the primitive with your stub executor instead.
- **No real Docker in tests**: Plan 1 does not require Docker to be running. The stub `run_agent_in_container` raises `NotImplementedError`; tests that exercise the compiler never call it — they supply their own executor callable.
- **No AgentTurnEnvelope unwrapping in Plan 1**: The compiler does not inspect envelopes — it calls `executor(primitive=action, prompt=prompt)` and expects an instance of `O` back. Envelope unwrapping, schema validation, and response-channel branching live inside the executor (Plan 2's `run_agent_in_container` implementation). Test executors return plain `O` instances directly.

---

## Out of Scope for Plan 1

The following are deferred to later plans in CS7:

- **Real Docker orchestration** — `run_agent_in_container` body (Plan 2: AF-5). Includes envelope unwrapping, schema validation, response-channel branching, structured-output vs. file-collection handling.
- **Container reuse** — `reuse_policy` field is defined and accepted but the stub ignores it (Plan 2: AF-6).
- **Lifecycle tracking** — no tracker in this plan. Diagnostic output (exit codes, stdout lines) is not returned from the runner and will flow to the tracker in Plan 2 (AF-4).
- **Non-success envelope outcomes** — in Plan 1, all non-success outcome kinds (`clarification_needed`, `permission_needed`, `failed`) propagate as untyped exceptions from the executor. The compiler does not distinguish between them. Plan 2 will define whether each outcome maps to a typed exception class, a LangGraph interrupt, or some other mechanism — Plan 1's contract is deliberately minimal to avoid committing Plan 2 to a specific shape.
- **`lessons-learned` skill move** — (Plan 3: AF-7).
- **Base `CLAUDE.md` update** — (Plan 3: AF-8).
- **Archipelago agent implementations** — (Plan 4: AR-1..6).
