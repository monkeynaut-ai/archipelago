# CS7 Plan 4 Phase 2 Slices 2–5 — Design Pipeline Implementation Plan

> **Design:** `docs/plans/stage1/2026-04-20-cs7-plan4-phase2-design.md`
> **Previous slice (shipped):** `docs/plans/stage1/2026-04-20-cs7-plan4-phase2-slice1-implementation-plan.md`
> **Parent:** `docs/plans/stage1/2026-04-17-cs7-plan4-archipelago-agents-plan.md`
> **Roadmap:** `docs/plans/stage1/2026-04-03-review-feedback-loop-roadmap.md` (CS7 Plan 4)
> **Vision:** `docs/archipelago-vision.md` (§3.1 harness-competing-tensions)
> **For agents:** Use team-dev (parallel) or sdd (sequential) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable Archipelago pipeline — **given a feature definition and a target codebase, produce a design document** — by composing the workspace-bootstrap `FunctionAction` and the Designer `AgentAction` into a single `Sequence` runnable from a CLI.

**Architecture:** Four slices in archipelago. Slice 2 declares two `archetype.markdown` document types (`FeatureDefinition`, `DesignDocument`) plus `CodebaseSource`. Slice 3 adds a `FunctionAction` that provisions a Docker-volume workspace: cloned codebase (read-only working tree, `.git/` preserved writable), rendered feature-definition file (read-only), writable documents directory. Slice 4 packages the Designer `AgentAction`. Slice 5 composes `workspace_bootstrap → designer` into `design_pipeline: Sequence[DesignPipelineState, DesignPipelineState]`, wires `run_design_pipeline(feature_definition, codebase_source)` that generates the workspace-volume name once and threads it into both the container registry and the bootstrap input, and exposes a CLI entry point.

**Tech Stack:** Python 3.14, Pydantic 2.12+, `archetype.markdown` + `archetype.templating` (sibling dependency), `agent_foundry.primitives` (`AgentAction`, `FunctionAction`, `Sequence`, `ContainerReusePolicy`, `PrimitivePlan`), `agent_foundry.orchestration.run_primitive_plan`, `agent_foundry.orchestration.container_executor.run_agent_in_container`, `agent_foundry.orchestration.errors.AgentFailedError`, `agent_foundry.responders.stdin.StdinResponder`, `agent_foundry.responders.protocol.static_provider`, `agent_foundry.models.markers.AgentFilePath`, `docker` (already a dep), `argparse` (stdlib), pytest with `integration` + `timeout` markers, `pytest-xdist`, `pytest-timeout` (new dev dep), `pytest-asyncio`. All work in the **archipelago** repo; agent-foundry is unchanged after the case-insensitive heading match landed in Slice 1's branch (commit `dfb757f`).

---

## Repo orientation

All paths in this plan are relative to the archipelago repo root (`/home/markn/engineering/jig-archipelago/archipelago`). Commit and run all commands inside that repo.

```bash
cd /home/markn/engineering/jig-archipelago/archipelago
```

The rest of the plan assumes that as the working directory.

---

## Dependency graph

```
Task 2.0 (retire legacy) ─▶ Task 2.1 (test infra) ─▶ Slice 2 body (2.2–2.7) ─┬─▶ Slice 3 (3.1 → 3.2…3.8) ─┐
                                                                              │                             ├─▶ Slice 5 (5.1 → 5.6)
                                                                              └─▶ Slice 4 (4.1 → 4.5) ──────┘
```

Slice 4's Task 4.1 imports `WorkspaceHandle` from `archipelago.actions`, so **Task 4.1 depends on Task 3.1** (Slice 3's scaffolding) even though the rest of Slice 4 is otherwise parallel to Slice 3. Slice 5 is Phase 2's completion criterion.

---

## Phase 2 end state (after Slice 5)

```bash
python scripts/run_design_pipeline.py \
    --feature examples/features/run-observability.md \
    --repo https://github.com/730alchemy/agent-foundry.git \
    --ref main
```

produces a Docker volume containing `/workspace/documents/design.md`: eight sections of hand-designed content for Run Observability. Exit 0 on success; non-zero with a readable message on bootstrap failure, designer failure, or input-parse error. Clarification and permission requests route through stdin (`StdinResponder`) and the pipeline continues.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/archipelago/models.py` | **Delete** | Legacy — replaced by `archipelago/models/` package |
| `src/archipelago/types.py` | **Delete** | Legacy — unused after Task 2.0 |
| `src/archipelago/agents/code_writer.py.save` | **Delete** | Legacy placeholder — superseded by Designer |
| `src/archipelago/agents/software_reviewer.py.save` | **Delete** | Legacy placeholder — deferred to future phase |
| `src/archipelago/agents/unit_test_writer.py.save` | **Delete** | Legacy placeholder — deferred to future phase |
| `tests/archipelago/unit/` (dir) | **Delete** | Legacy test layout — replaced by domain-grouped test dirs |
| `tests/archipelago/integration/` (dir) | **Delete** | Legacy test layout — replaced below |
| `pyproject.toml` | Modify | Add `pytest-timeout` dev dep, `asyncio_mode = "strict"`, `timeout` marker |
| `tests/__init__.py` | Create | Enable `from tests.archipelago.*` cross-test imports |
| `tests/archipelago/__init__.py` | Create | Test-package marker |
| `tests/archipelago/conftest.py` | Create | Shared fixtures: `repo_root`, `minimal_feature_definition`, session-scoped orphan-volume cleanup |
| `src/archipelago/__init__.py` | Modify | Add short package docstring |
| `src/archipelago/models/__init__.py` | Create | Public API for `archipelago.models` |
| `src/archipelago/models/codebase_source.py` | Create | `CodebaseSource` |
| `src/archipelago/models/feature_definition.py` | Create | `FeatureDefinitionFrontmatter`, 8 wrapper `MarkdownHeader` subclasses, `FeatureDefinition` |
| `src/archipelago/models/design_document.py` | Create | `DesignDocumentFrontmatter`, `DesignDocument` |
| `tests/archipelago/models/__init__.py` | Create | Test-package marker |
| `tests/archipelago/models/test_codebase_source.py` | Create | `CodebaseSource` tests |
| `tests/archipelago/models/test_feature_definition.py` | Create | Wrapper + document tests |
| `tests/archipelago/models/test_design_document.py` | Create | `DesignDocument` tests |
| `tests/archipelago/models/test_run_observability_round_trip.py` | Create | Real-world round-trip against `examples/features/run-observability.md` |
| `tests/archipelago/models/test_public_api.py` | Create | Public API surface assertion |
| `src/archipelago/actions/__init__.py` | Create | Public API for `archipelago.actions` |
| `src/archipelago/actions/workspace_bootstrap.py` | Create | `BootstrapInput`, `BootstrapOutput`, `WorkspaceHandle`, `bootstrap_fn`, `workspace_bootstrap` primitive |
| `src/archipelago/actions/_workspace_ops.py` | Create | Private Docker + git helpers (`pull_image`, `create_volume`, `clone_and_resolve_ref`, `chmod_tree_excluding_git`, `chmod_path`, `write_file`, `prepare_documents_dir`) |
| `tests/archipelago/actions/__init__.py` | Create | Test-package marker |
| `tests/archipelago/actions/test_workspace_bootstrap_models.py` | Create | State model tests |
| `tests/archipelago/actions/test_workspace_ops.py` | Create | `_workspace_ops` unit tests (Docker client patched) |
| `tests/archipelago/actions/test_bootstrap_fn.py` | Create | `bootstrap_fn` orchestration tests (helpers patched) |
| `tests/archipelago/actions/test_bootstrap_integration.py` | Create | Integration test against a real Docker daemon (marked `integration`) |
| `tests/archipelago/actions/test_public_api.py` | Create | Public API surface assertion |
| `src/archipelago/agents/__init__.py` | Create | Re-export `designer` |
| `src/archipelago/agents/designer/__init__.py` | Create | Public API for designer package |
| `src/archipelago/agents/designer/models.py` | Create | `DesignerInput`, `DesignerOutput` |
| `src/archipelago/agents/designer/instructions_template.md` | Create | Jinja-templated instructions (verbatim from design §6.3) |
| `src/archipelago/agents/designer/callables.py` | Create | `designer_prompt_builder`, `designer_instructions_provider` |
| `src/archipelago/agents/designer/primitive.py` | Create | `designer = AgentAction[DesignerInput, DesignerOutput](...)` |
| `tests/archipelago/agents/__init__.py` | Create | Test-package marker |
| `tests/archipelago/agents/designer/__init__.py` | Create | Test-package marker |
| `tests/archipelago/agents/designer/test_models.py` | Create | Designer model tests |
| `tests/archipelago/agents/designer/test_instructions_template.py` | Create | Template resolution round-trip |
| `tests/archipelago/agents/designer/test_callables.py` | Create | Callable tests |
| `tests/archipelago/agents/designer/test_primitive.py` | Create | Primitive config assertions |
| `tests/archipelago/agents/designer/test_public_api.py` | Create | Public API surface assertion |
| `src/archipelago/systems/__init__.py` | Create | Public API for `archipelago.systems` |
| `src/archipelago/systems/design_pipeline.py` | Create | `DesignPipelineState`, `design_pipeline`, `run_design_pipeline`, volume-name helper, `BASE_IMAGE_TAG` constant |
| `scripts/run_design_pipeline.py` | Create | CLI entry point (`--feature`, `--repo`, `--ref`) |
| `tests/archipelago/systems/__init__.py` | Create | Test-package marker |
| `tests/archipelago/systems/test_design_pipeline_state.py` | Create | State model tests |
| `tests/archipelago/systems/test_sequence_composition.py` | Create | `design_pipeline` Sequence tests |
| `tests/archipelago/systems/test_run_design_pipeline.py` | Create | Orchestrator tests (executor patched) |
| `tests/archipelago/systems/test_design_pipeline_integration.py` | Create | Full E2E test (marked `integration`) |
| `tests/archipelago/systems/test_public_api.py` | Create | Public API surface assertion |
| `tests/archipelago/scripts/__init__.py` | Create | Test-package marker |
| `tests/archipelago/scripts/test_run_design_pipeline_cli.py` | Create | CLI tests |

---

## Conventions

**Test naming:** classes named `Test<Feature>`, methods named `test_given_<context>_when_<action>_then_<expected>`. Matches the style in `agent-foundry/tests/agent_foundry/markdown/test_parser.py`.

**Test commands** (from the archipelago repo root):
- Single test file: `pdm run pytest tests/archipelago/models/test_codebase_source.py -xvs`
- All unit tests: `pdm test-unit`
- Integration tests: `pdm test-integration`
- Full suite: `pdm test-all`

`pdm test-unit` runs `pytest tests/ -m 'not integration and not benchmark'` with `PYTHONPATH=src`.

**Lint and typecheck:** `pdm lint` (ruff), `pdm format`, `pdm typecheck` (pyright).

**Commit convention:** `feat(<scope>): <message>` for code, `test(<scope>): <message>` for test-only commits, `chore(<scope>): <message>` for non-code. Scopes in this plan: `models`, `actions`, `agents-designer`, `systems`, `scripts`, `tests`. Each commit body ends with:

```
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

**TDD discipline:** every code task starts with a failing test, then minimum implementation, then passing tests, then commit. Structural-only tasks (directory creation, config) skip the TDD cycle and commit as `chore`.

**Full test gate:** all tests must pass before every commit (archipelago's pre-commit hook runs unit tests; pre-push runs the full suite).

---

# Slice 2 — Data Models

**Goal:** Archipelago exposes `FeatureDefinition` and `DesignDocument` as `archetype.markdown` document types. Both pass meta-validation at class-definition time, round-trip through render/parse, and surface their body sections via `template_fields()`. `CodebaseSource` is available for Slice 3. The committed `examples/features/run-observability.md` parses to a valid `FeatureDefinition` without modification (archetype now matches headings case-insensitively).

**Depends on:** Slice 1 (shipped in agent-foundry, including `dfb757f` case-insensitive heading matching).

---

## Task 2.0: Retire legacy archipelago code

**Files:**
- Delete: `src/archipelago/models.py`
- Delete: `src/archipelago/types.py`
- Delete: `src/archipelago/agents/code_writer.py.save`
- Delete: `src/archipelago/agents/software_reviewer.py.save`
- Delete: `src/archipelago/agents/unit_test_writer.py.save`
- Delete: `tests/archipelago/unit/` (directory + contents)
- Delete: `tests/archipelago/integration/` (directory + contents)

**Dependencies:** None.

Structural task — no TDD. Single cleanup commit before Slice 2 body begins so the new package-based layout doesn't collide with the legacy module-based one.

- [ ] **Step 1: Verify what's being deleted**

Run: `ls src/archipelago/ tests/archipelago/ src/archipelago/agents/`
Expected: shows `models.py`, `types.py`, `agents/*.save`, `tests/archipelago/unit/`, `tests/archipelago/integration/` — the things to delete. Also shows `logging_config.py` (kept), `docker/` (kept), `__init__.py` (kept). If anything unexpected is present, pause and resolve before proceeding.

- [ ] **Step 2: Delete legacy files and directories**

```bash
git rm src/archipelago/models.py
git rm src/archipelago/types.py
git rm src/archipelago/agents/code_writer.py.save
git rm src/archipelago/agents/software_reviewer.py.save
git rm src/archipelago/agents/unit_test_writer.py.save
git rm -r tests/archipelago/unit/
git rm -r tests/archipelago/integration/
```

- [ ] **Step 3: Confirm no other module references the deleted names**

Run: `grep -rn "from archipelago.models\|from archipelago.types\|import archipelago.models\|import archipelago.types" src/ tests/ scripts/ 2>/dev/null`
Expected: empty output. If any hit appears, delete or refactor that caller before committing.

- [ ] **Step 4: Confirm unit suite still collects and (tautologically) passes**

Run: `pdm test-unit`
Expected: `collected 0 items` or a very small set (any remaining tests not in `unit/`/`integration/`) — all green.

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
chore: retire legacy archipelago source and tests

Removes the pre-Phase-2 source layout (archipelago.models module,
archipelago.types, .save placeholder agents) and the corresponding
unit/ and integration/ test subdirectories. Phase 2 introduces a new
package-based layout; keeping the legacy files would shadow it.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2.1: Test infrastructure

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/__init__.py`
- Create: `tests/archipelago/__init__.py`
- Create: `tests/archipelago/conftest.py`

**Dependencies:** Task 2.0.

Structural + configuration task. Sets up the test package so cross-test imports work, configures pytest-asyncio in strict mode, adds `pytest-timeout` as a dev dependency and registers the `timeout` marker, and provides two shared fixtures (`repo_root`, `minimal_feature_definition`) plus a session-scoped safety net that removes any `archipelago-ws-*` Docker volumes at session end.

- [ ] **Step 1: Add `pytest-timeout` to dev deps**

Run: `pdm add -dG dev pytest-timeout>=2.3`
Expected: `pyproject.toml` updated, `pdm.lock` regenerated, `pytest-timeout` installed.

- [ ] **Step 2: Update pytest config in `pyproject.toml`**

Find the `[tool.pytest.ini_options]` block and update it to:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src", "."]
addopts = "-m 'not benchmark' -n 8"
asyncio_mode = "strict"
markers = [
    "benchmark: performance benchmark tests (excluded from normal runs)",
    "integration: integration tests (require Docker, external services)",
    "timeout: mark a test with a maximum runtime in seconds (requires pytest-timeout)",
]
```

Changes from the previous block:
- `pythonpath = ["src", "."]` (added `.` so `tests.archipelago.*` imports resolve).
- `asyncio_mode = "strict"` (so `@pytest.mark.asyncio`-decorated tests run, matching agent-foundry's configuration).
- `timeout` marker registered (so `@pytest.mark.timeout(N)` doesn't warn with `PytestUnknownMarkWarning`).

- [ ] **Step 3: Create test-package markers and shared conftest**

Create `tests/__init__.py` (empty file; marker only).

Create `tests/archipelago/__init__.py` (empty file; marker only).

Create `tests/archipelago/conftest.py`:

```python
"""Shared pytest fixtures for archipelago tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    """Absolute path to the archipelago repo root.

    Resolves relative to this file: conftest.py → tests/archipelago → tests
    → repo root. That's two parents up.
    """
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def minimal_feature_definition():
    """A fully-populated FeatureDefinition for tests that need one.

    Imported lazily so this module can be imported before Slice 2 body
    tasks land (during Task 2.1, archipelago.models doesn't exist yet).
    Tests that use this fixture implicitly depend on Task 2.4 having
    landed.
    """
    from archipelago.models import (
        AcceptanceCriteria,
        Assumptions,
        BusinessOutcomes,
        Constraints,
        Dependencies,
        DesiredOutcomes,
        FeatureDefinition,
        FeatureDefinitionFrontmatter,
        ScopeBoundaries,
        UserOutcomes,
    )

    return FeatureDefinition(
        frontmatter=FeatureDefinitionFrontmatter(
            feature_slug="demo",
            created_at="2026-04-21",
        ),
        title="Demo Feature",
        problem_statement="A gap exists.",
        feature_intent="Close the gap.",
        desired_outcomes=DesiredOutcomes(
            user_outcomes=UserOutcomes(items=["u1"]),
            business_outcomes=BusinessOutcomes(items=["b1"]),
        ),
        scope_boundaries=ScopeBoundaries(items=["not-X"]),
        assumptions=Assumptions(items=["a1"]),
        dependencies=Dependencies(items=["d1"]),
        constraints=Constraints(items=["c1"]),
        acceptance_criteria=AcceptanceCriteria(items=["ac1"]),
    )


@pytest.fixture(scope="session")
def archipelago_volume_registry() -> set[str]:
    """Session-scoped set of workspace-volume names that integration tests
    have created. Tests register names via `archipelago_volume_registry.add(...)`
    after creating a volume; the session finalizer removes exactly those
    names (not all `archipelago-ws-*` volumes on the host — a blanket sweep
    would destroy a developer's manually-created inspection volumes).
    """
    return set()


@pytest.fixture(scope="session", autouse=True)
def _cleanup_registered_volumes(archipelago_volume_registry):
    """Session-end cleanup: remove volumes that tests explicitly registered.
    No-op when Docker isn't reachable."""
    yield
    if not archipelago_volume_registry:
        return
    try:
        import docker

        client = docker.from_env()
        client.ping()
    except Exception:
        return
    for name in archipelago_volume_registry:
        try:
            client.volumes.get(name).remove(force=True)
        except Exception:
            pass
```

- [ ] **Step 4: Confirm infrastructure is in place**

Run: `pdm run pytest tests/ --collect-only 2>&1 | tail -5`
Expected: `collected 0 items` (no tests yet) with no warnings about unknown markers or asyncio mode.

Run: `pdm run python -c "import tests.archipelago.conftest"`
Expected: no output, exit 0.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml pdm.lock tests/__init__.py tests/archipelago/__init__.py tests/archipelago/conftest.py
git commit -m "$(cat <<'EOF'
chore(tests): set up test infrastructure for Phase 2

- Add pytest-timeout dev dep and register timeout marker.
- Configure asyncio_mode = "strict" to match agent-foundry.
- Add `.` to pythonpath so tests.archipelago.* imports resolve.
- Create shared conftest with repo_root, minimal_feature_definition
  fixtures, and a session-scoped autouse cleanup that removes any
  orphan archipelago-ws-* Docker volumes at session end.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2.2: `CodebaseSource`

**Files:**
- Modify: `src/archipelago/__init__.py`
- Create: `src/archipelago/models/__init__.py`
- Create: `src/archipelago/models/codebase_source.py`
- Create: `tests/archipelago/models/__init__.py`
- Create: `tests/archipelago/models/test_codebase_source.py`

**Dependencies:** Task 2.1.

- [ ] **Step 1: Scaffold the package**

```bash
mkdir -p src/archipelago/models tests/archipelago/models
```

Create `src/archipelago/models/__init__.py`:

```python
"""Archipelago domain models — FeatureDefinition, DesignDocument, and
supporting types. Every boundary type in this package is a Pydantic
BaseModel subclass.
"""
```

Create `tests/archipelago/models/__init__.py` (empty).

Modify `src/archipelago/__init__.py` to:

```python
"""Archipelago — an agentic system for autonomous software engineering.

See `docs/archipelago-vision.md` for the project's vision and the
`harness-competing-tensions` design method that drives agent decomposition.
"""
```

- [ ] **Step 2: Write failing test**

Create `tests/archipelago/models/test_codebase_source.py`:

```python
"""Tests for CodebaseSource."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from archipelago.models.codebase_source import CodebaseSource


class TestCodebaseSource:
    def test_given_https_url_and_ref_when_constructed_then_fields_populated(self):
        source = CodebaseSource(
            repo_url="https://github.com/730alchemy/agent-foundry.git",
            ref="main",
        )
        assert source.repo_url == "https://github.com/730alchemy/agent-foundry.git"
        assert source.ref == "main"

    def test_given_ssh_url_when_constructed_then_stored_opaquely(self):
        source = CodebaseSource(
            repo_url="git@github.com:730alchemy/agent-foundry.git",
            ref="abc1234",
        )
        assert source.repo_url.startswith("git@github.com:")
        assert source.ref == "abc1234"

    def test_given_missing_repo_url_when_constructed_then_validation_error(self):
        with pytest.raises(ValidationError):
            CodebaseSource(ref="main")  # type: ignore[call-arg]

    def test_given_missing_ref_when_constructed_then_validation_error(self):
        with pytest.raises(ValidationError):
            CodebaseSource(repo_url="https://example.com/repo.git")  # type: ignore[call-arg]
```

- [ ] **Step 3: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/models/test_codebase_source.py -xvs`
Expected: `ModuleNotFoundError: No module named 'archipelago.models.codebase_source'`.

- [ ] **Step 4: Write minimal implementation**

Create `src/archipelago/models/codebase_source.py`:

```python
"""CodebaseSource — identifies a target codebase by repo URL + ref.

Ambient credentials (SSH agent / environment token) provide auth for v1;
no auth field on the model.
"""

from __future__ import annotations

from pydantic import BaseModel


class CodebaseSource(BaseModel):
    """A repo URL + a ref (commit SHA, branch, or tag)."""

    repo_url: str
    ref: str
```

- [ ] **Step 5: Run test, confirm passes**

Run: `pdm run pytest tests/archipelago/models/test_codebase_source.py -xvs`
Expected: `4 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/archipelago/__init__.py src/archipelago/models/ tests/archipelago/models/__init__.py tests/archipelago/models/test_codebase_source.py
git commit -m "$(cat <<'EOF'
feat(models): add CodebaseSource and scaffold archipelago.models package

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2.3: `FeatureDefinition` wrapper `MarkdownHeader` subclasses

**Files:**
- Create: `src/archipelago/models/feature_definition.py` (wrappers only; document class added in Task 2.4)
- Create: `tests/archipelago/models/test_feature_definition.py` (wrapper tests only)

**Dependencies:** Task 2.2.

Eight wrapper classes: seven homogeneous simple wrappers (`UserOutcomes`, `BusinessOutcomes`, `ScopeBoundaries`, `Assumptions`, `Dependencies`, `Constraints`, `AcceptanceCriteria`) and one nested (`DesiredOutcomes`).

- [ ] **Step 1: Write failing test**

Create `tests/archipelago/models/test_feature_definition.py`:

```python
"""Tests for FeatureDefinition wrappers and document."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from archipelago.models.feature_definition import (
    AcceptanceCriteria,
    Assumptions,
    BusinessOutcomes,
    Constraints,
    Dependencies,
    DesiredOutcomes,
    ScopeBoundaries,
    UserOutcomes,
)


class TestWrapperDefaults:
    """Every wrapper has a default title matching snake_to_title's output
    for the corresponding top-level field name."""

    def test_given_user_outcomes_when_default_constructed_then_title_is_user_outcomes(self):
        assert UserOutcomes(items=["x"]).title == "User Outcomes"

    def test_given_business_outcomes_when_default_constructed_then_title_is_business_outcomes(self):
        assert BusinessOutcomes(items=["x"]).title == "Business Outcomes"

    def test_given_scope_boundaries_when_default_constructed_then_title_is_scope_boundaries(self):
        assert ScopeBoundaries(items=["x"]).title == "Scope Boundaries"

    def test_given_assumptions_when_default_constructed_then_title_is_assumptions(self):
        assert Assumptions(items=["x"]).title == "Assumptions"

    def test_given_dependencies_when_default_constructed_then_title_is_dependencies(self):
        assert Dependencies(items=["x"]).title == "Dependencies"

    def test_given_constraints_when_default_constructed_then_title_is_constraints(self):
        assert Constraints(items=["x"]).title == "Constraints"

    def test_given_acceptance_criteria_when_default_constructed_then_title_is_acceptance_criteria(self):
        assert AcceptanceCriteria(items=["x"]).title == "Acceptance Criteria"

    def test_given_desired_outcomes_when_default_constructed_then_title_is_desired_outcomes(self):
        wrapper = DesiredOutcomes(
            user_outcomes=UserOutcomes(items=["u"]),
            business_outcomes=BusinessOutcomes(items=["b"]),
        )
        assert wrapper.title == "Desired Outcomes"


class TestSimpleWrapperContent:
    def test_given_empty_items_when_constructed_then_items_is_empty_list(self):
        assert UserOutcomes(items=[]).items == []

    def test_given_list_of_strings_when_constructed_then_items_preserved(self):
        wrapper = ScopeBoundaries(items=["no dashboard", "no visualization"])
        assert wrapper.items == ["no dashboard", "no visualization"]

    def test_given_non_string_item_when_constructed_then_validation_error(self):
        with pytest.raises(ValidationError):
            Assumptions(items=[123])  # type: ignore[list-item]


class TestDesiredOutcomesNesting:
    def test_given_nested_wrappers_when_constructed_then_instances_preserved(self):
        wrapper = DesiredOutcomes(
            user_outcomes=UserOutcomes(items=["u1", "u2"]),
            business_outcomes=BusinessOutcomes(items=["b1"]),
        )
        assert wrapper.user_outcomes.items == ["u1", "u2"]
        assert wrapper.business_outcomes.items == ["b1"]
```

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/models/test_feature_definition.py -xvs`
Expected: `ModuleNotFoundError: No module named 'archipelago.models.feature_definition'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/archipelago/models/feature_definition.py`:

```python
"""FeatureDefinition — canonical Archipelago feature-spec document.

Nine top-level sections. Sections that render as H2 + bullet list are
declared as wrapper MarkdownHeader subclasses carrying a single
`items: list[str]` field, so list[str] typing survives the body-order
rule (every body field opens a heading).

Wrapper `title` defaults use Title Case so they align with
`archetype.markdown._shared.snake_to_title` output for top-level
heading-style fields. Parsing is case-insensitive (since archetype
commit dfb757f), so hand-authored feature defs may use either
sentence case or Title Case for H2/H3 headings.
"""

from __future__ import annotations

from typing import Annotated

from archetype.markdown import AsBulletList, MarkdownHeader


class UserOutcomes(MarkdownHeader):
    title: str = "User Outcomes"
    items: Annotated[list[str], AsBulletList()]


class BusinessOutcomes(MarkdownHeader):
    title: str = "Business Outcomes"
    items: Annotated[list[str], AsBulletList()]


class DesiredOutcomes(MarkdownHeader):
    title: str = "Desired Outcomes"
    user_outcomes: UserOutcomes
    business_outcomes: BusinessOutcomes


class ScopeBoundaries(MarkdownHeader):
    title: str = "Scope Boundaries"
    items: Annotated[list[str], AsBulletList()]


class Assumptions(MarkdownHeader):
    title: str = "Assumptions"
    items: Annotated[list[str], AsBulletList()]


class Dependencies(MarkdownHeader):
    title: str = "Dependencies"
    items: Annotated[list[str], AsBulletList()]


class Constraints(MarkdownHeader):
    title: str = "Constraints"
    items: Annotated[list[str], AsBulletList()]


class AcceptanceCriteria(MarkdownHeader):
    title: str = "Acceptance Criteria"
    items: Annotated[list[str], AsBulletList()]
```

- [ ] **Step 4: Run test, confirm passes**

Run: `pdm run pytest tests/archipelago/models/test_feature_definition.py -xvs`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add src/archipelago/models/feature_definition.py tests/archipelago/models/test_feature_definition.py
git commit -m "$(cat <<'EOF'
feat(models): add FeatureDefinition wrapper MarkdownHeader subclasses

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2.4: `FeatureDefinitionFrontmatter` + `FeatureDefinition` document

**Files:**
- Modify: `src/archipelago/models/feature_definition.py` (append)
- Modify: `tests/archipelago/models/test_feature_definition.py` (append)

**Dependencies:** Task 2.3.

- [ ] **Step 1: Extend test file**

Append to `tests/archipelago/models/test_feature_definition.py`:

```python
from archetype.markdown import render_instance, template_fields, validate_markdown

from archipelago.models.feature_definition import (
    FeatureDefinition,
    FeatureDefinitionFrontmatter,
)


class TestFeatureDefinitionFrontmatter:
    def test_given_slug_and_timestamp_when_constructed_then_fields_populated(self):
        fm = FeatureDefinitionFrontmatter(feature_slug="demo", created_at="2026-04-21")
        assert fm.feature_slug == "demo"
        assert fm.created_at == "2026-04-21"

    def test_given_missing_slug_when_constructed_then_validation_error(self):
        with pytest.raises(ValidationError):
            FeatureDefinitionFrontmatter(created_at="2026-04-21")  # type: ignore[call-arg]


class TestFeatureDefinitionConstruction:
    def test_given_all_sections_when_constructed_then_no_error(self, minimal_feature_definition):
        fd = minimal_feature_definition
        assert fd.title == "Demo Feature"
        assert fd.problem_statement == "A gap exists."
        assert fd.assumptions.items == ["a1"]

    def test_given_missing_problem_statement_when_constructed_then_validation_error(self):
        with pytest.raises(ValidationError):
            FeatureDefinition(
                frontmatter=FeatureDefinitionFrontmatter(feature_slug="x", created_at="x"),
                title="x",
                feature_intent="x",
                desired_outcomes=DesiredOutcomes(
                    user_outcomes=UserOutcomes(items=[]),
                    business_outcomes=BusinessOutcomes(items=[]),
                ),
                scope_boundaries=ScopeBoundaries(items=[]),
                assumptions=Assumptions(items=[]),
                dependencies=Dependencies(items=[]),
                constraints=Constraints(items=[]),
                acceptance_criteria=AcceptanceCriteria(items=[]),
            )  # type: ignore[call-arg]


class TestFeatureDefinitionTemplateFields:
    def test_given_feature_definition_when_template_fields_then_eight_entries(self):
        fields = template_fields(FeatureDefinition)
        assert len(fields) == 8

    def test_given_feature_definition_when_template_fields_then_headings_match(self):
        fields = template_fields(FeatureDefinition)
        assert [f.heading for f in fields] == [
            "Problem Statement",
            "Feature Intent",
            "Desired Outcomes",
            "Scope Boundaries",
            "Assumptions",
            "Dependencies",
            "Constraints",
            "Acceptance Criteria",
        ]

    def test_given_feature_definition_when_template_fields_then_every_field_has_description(self):
        fields = template_fields(FeatureDefinition)
        for field in fields:
            assert field.description is not None, f"{field.heading} has no description"
            assert len(field.description) > 20, f"{field.heading} description too short"


class TestFeatureDefinitionRoundTrip:
    def test_given_instance_when_rendered_then_h1_present(self, minimal_feature_definition):
        rendered = render_instance(minimal_feature_definition)
        assert "# Demo Feature" in rendered

    def test_given_instance_when_rendered_then_all_h2_sections_present(self, minimal_feature_definition):
        rendered = render_instance(minimal_feature_definition)
        for heading in [
            "## Problem Statement",
            "## Feature Intent",
            "## Desired Outcomes",
            "## Scope Boundaries",
            "## Assumptions",
            "## Dependencies",
            "## Constraints",
            "## Acceptance Criteria",
        ]:
            assert heading in rendered, f"missing {heading!r}"

    def test_given_instance_when_rendered_and_parsed_then_semantically_equal(self, minimal_feature_definition):
        rendered = render_instance(minimal_feature_definition)
        reparsed = validate_markdown(rendered, FeatureDefinition)
        assert reparsed == minimal_feature_definition
```

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/models/test_feature_definition.py -xvs`
Expected: `ImportError: cannot import name 'FeatureDefinition' from 'archipelago.models.feature_definition'`.

- [ ] **Step 3: Extend implementation**

Update `src/archipelago/models/feature_definition.py` — add imports and append the frontmatter + document classes:

```python
from archetype.markdown import AsHeading, MarkdownDocument
from pydantic import BaseModel, Field


class FeatureDefinitionFrontmatter(BaseModel):
    feature_slug: str
    created_at: str  # ISO timestamp; string-typed on v1


class FeatureDefinition(MarkdownDocument):
    frontmatter: FeatureDefinitionFrontmatter | None = None
    title: str = Field(
        description=(
            "Feature name. Renders as the document's top-level heading."
        )
    )

    problem_statement: Annotated[str, AsHeading()] = Field(
        description=(
            "The current pain or gap this feature addresses. What's "
            "broken or missing today, before this feature exists?"
        )
    )

    feature_intent: Annotated[str, AsHeading()] = Field(
        description=(
            "Why this feature is the chosen answer to the problem — what "
            "makes this the right solution versus other solutions to the "
            "same problem."
        )
    )

    desired_outcomes: DesiredOutcomes = Field(
        description=(
            "What good looks like after the feature ships, split into "
            "outcomes for users and outcomes for the business."
        )
    )

    scope_boundaries: ScopeBoundaries = Field(
        description=(
            "Explicit statements of what is out of scope — what this "
            "feature does NOT try to do."
        )
    )

    assumptions: Assumptions = Field(
        description=(
            "Truth-claims about the world the design will rest on — "
            "beliefs we're betting on without having verified."
        )
    )

    dependencies: Dependencies = Field(
        description=(
            "External things this feature relies on — services, prior "
            "changes, deployed infrastructure."
        )
    )

    constraints: Constraints = Field(
        description=(
            "Hard limits the solution must respect: must-do's, "
            "must-not-do's, non-functional requirements."
        )
    )

    acceptance_criteria: AcceptanceCriteria = Field(
        description=(
            "Concrete, testable statements of 'done' — what must be true "
            "when this feature is complete."
        )
    )
```

Consolidate imports at the top of the file (the `from typing import Annotated` and `from archetype.markdown import AsBulletList, MarkdownHeader` lines from Task 2.3 stay; add `AsHeading`, `MarkdownDocument` to the archetype import; add the pydantic import).

- [ ] **Step 4: Run test, confirm passes**

Run: `pdm run pytest tests/archipelago/models/test_feature_definition.py -xvs`
Expected: all tests pass (12 wrappers + 12 new = 24 total).

- [ ] **Step 5: Commit**

```bash
git add src/archipelago/models/feature_definition.py tests/archipelago/models/test_feature_definition.py
git commit -m "$(cat <<'EOF'
feat(models): add FeatureDefinition document and frontmatter

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2.5: `DesignDocumentFrontmatter` + `DesignDocument`

**Files:**
- Create: `src/archipelago/models/design_document.py`
- Create: `tests/archipelago/models/test_design_document.py`

**Dependencies:** Task 2.2.

- [ ] **Step 1: Write failing test**

Create `tests/archipelago/models/test_design_document.py`:

```python
"""Tests for DesignDocument."""

from __future__ import annotations

import pytest
from archetype.markdown import render_instance, template_fields, validate_markdown
from pydantic import ValidationError

from archipelago.models.design_document import (
    DesignDocument,
    DesignDocumentFrontmatter,
)


def _minimal_design_document() -> DesignDocument:
    return DesignDocument(
        frontmatter=DesignDocumentFrontmatter(
            feature_slug="demo",
            feature_name="Demo Feature",
            feature_definition_path="/workspace/documents/feature_definition.md",
            codebase_ref="main",
            codebase_resolved_sha="a" * 40,
            generated_at="2026-04-21T12:00:00Z",
        ),
        title="Demo Feature",
        summary="One-paragraph framing.",
        current_state_context="Relevant existing state.",
        components="Component A, Component B.",
        architecture="How they interact.",
        acceptance_criteria="Refined AC.",
        test_strategy="Test approach.",
        risks_and_open_items="Open risks.",
        resolved_assumptions="Dispositions.",
    )


class TestDesignDocumentFrontmatter:
    def test_given_all_fields_when_constructed_then_fields_populated(self):
        fm = DesignDocumentFrontmatter(
            feature_slug="x",
            feature_name="X",
            feature_definition_path="/p",
            codebase_ref="main",
            codebase_resolved_sha="a" * 40,
            generated_at="ts",
        )
        assert fm.feature_slug == "x"
        assert fm.codebase_resolved_sha == "a" * 40

    def test_given_missing_generated_at_when_constructed_then_validation_error(self):
        with pytest.raises(ValidationError):
            DesignDocumentFrontmatter(
                feature_slug="x",
                feature_name="X",
                feature_definition_path="/p",
                codebase_ref="main",
                codebase_resolved_sha="a" * 40,
            )  # type: ignore[call-arg]


class TestDesignDocumentConstruction:
    def test_given_all_sections_when_constructed_then_no_error(self):
        dd = _minimal_design_document()
        assert dd.title == "Demo Feature"
        assert dd.summary == "One-paragraph framing."

    def test_given_missing_architecture_when_constructed_then_validation_error(self):
        with pytest.raises(ValidationError):
            DesignDocument(
                frontmatter=DesignDocumentFrontmatter(
                    feature_slug="x",
                    feature_name="X",
                    feature_definition_path="/p",
                    codebase_ref="main",
                    codebase_resolved_sha="a" * 40,
                    generated_at="ts",
                ),
                title="X",
                summary="s",
                current_state_context="c",
                components="c",
                acceptance_criteria="ac",
                test_strategy="t",
                risks_and_open_items="r",
                resolved_assumptions="a",
            )  # type: ignore[call-arg]


class TestDesignDocumentTemplateFields:
    def test_given_design_document_when_template_fields_then_eight_entries(self):
        fields = template_fields(DesignDocument)
        assert len(fields) == 8

    def test_given_design_document_when_template_fields_then_headings_match(self):
        fields = template_fields(DesignDocument)
        assert [f.heading for f in fields] == [
            "Summary",
            "Current State Context",
            "Components",
            "Architecture",
            "Acceptance Criteria",
            "Test Strategy",
            "Risks And Open Items",
            "Resolved Assumptions",
        ]


class TestDesignDocumentTitleTextTemplate:
    def test_given_instance_when_rendered_then_h1_uses_design_for_prefix(self):
        dd = _minimal_design_document()
        rendered = render_instance(dd)
        assert "# Design for Demo Feature" in rendered


class TestDesignDocumentRoundTrip:
    def test_given_instance_when_rendered_and_parsed_then_semantically_equal(self):
        dd = _minimal_design_document()
        rendered = render_instance(dd)
        reparsed = validate_markdown(rendered, DesignDocument)
        assert reparsed == dd

    def test_given_instance_when_rendered_then_all_frontmatter_fields_present(self):
        dd = _minimal_design_document()
        rendered = render_instance(dd)
        for key in [
            "feature_slug:",
            "feature_name:",
            "feature_definition_path:",
            "codebase_ref:",
            "codebase_resolved_sha:",
            "generated_at:",
        ]:
            assert key in rendered, f"missing frontmatter key {key!r}"
```

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/models/test_design_document.py -xvs`
Expected: `ModuleNotFoundError: No module named 'archipelago.models.design_document'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/archipelago/models/design_document.py`:

```python
"""DesignDocument — the Designer agent's output artifact.

Eight sections, all `Annotated[str, AsHeading()]` — free markdown prose
per section. H1 line uses `TextTemplate("Design for {value}")` to
disambiguate from the FeatureDefinition's H1.
"""

from __future__ import annotations

from typing import Annotated

from archetype.markdown import AsHeading, MarkdownDocument, TextTemplate
from pydantic import BaseModel, Field


class DesignDocumentFrontmatter(BaseModel):
    feature_slug: str
    feature_name: str
    feature_definition_path: str
    codebase_ref: str
    codebase_resolved_sha: str
    generated_at: str  # ISO timestamp


class DesignDocument(MarkdownDocument):
    frontmatter: DesignDocumentFrontmatter | None = None
    title: Annotated[str, TextTemplate("Design for {value}")]

    summary: Annotated[str, AsHeading()] = Field(
        description="A one-paragraph framing of the proposed design."
    )

    current_state_context: Annotated[str, AsHeading()] = Field(
        description=(
            "Relevant existing codebase state found during investigation. "
            "Include only what's load-bearing for understanding the proposal. "
            "Do not summarize the entire codebase."
        )
    )

    components: Annotated[str, AsHeading()] = Field(
        description=(
            "The components — new or modified — that make up the design. "
            "Name each one, state its purpose, and what concern it owns."
        )
    )

    architecture: Annotated[str, AsHeading()] = Field(
        description=(
            "How the components interact: interfaces between them, control "
            "flow (orchestration and sequencing), and data flow (what moves, "
            "in what shape, from where to where)."
        )
    )

    acceptance_criteria: Annotated[str, AsHeading()] = Field(
        description=(
            "Feature-level acceptance criteria refined from the feature "
            "definition. Concrete, testable statements of what must be "
            "true when the feature is complete."
        )
    )

    test_strategy: Annotated[str, AsHeading()] = Field(
        description=(
            "Feature-level test approach: what to test, at what level "
            "(unit, integration, end-to-end), what fixtures or harnesses "
            "are needed."
        )
    )

    risks_and_open_items: Annotated[str, AsHeading()] = Field(
        description=(
            "Concerns and uncertainties the design leaves open: bets made, "
            "decisions deferred, areas where later stages will need judgment."
        )
    )

    resolved_assumptions: Annotated[str, AsHeading()] = Field(
        description=(
            "Disposition of each assumption in the feature definition — "
            "accepted, refined, promoted to constraint, or contradicted — "
            "plus any new assumptions introduced during design."
        )
    )
```

- [ ] **Step 4: Run test, confirm passes**

Run: `pdm run pytest tests/archipelago/models/test_design_document.py -xvs`
Expected: all tests pass (~11 total).

- [ ] **Step 5: Commit**

```bash
git add src/archipelago/models/design_document.py tests/archipelago/models/test_design_document.py
git commit -m "$(cat <<'EOF'
feat(models): add DesignDocument and frontmatter

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2.6: Real-world round-trip against `run-observability.md`

**Files:**
- Create: `tests/archipelago/models/test_run_observability_round_trip.py`

**Dependencies:** Task 2.4.

Case-insensitive heading matching landed in agent-foundry (commit `dfb757f`), so this task is a clean round-trip — no rename fallback needed.

- [ ] **Step 1: Write test**

Create `tests/archipelago/models/test_run_observability_round_trip.py`:

```python
"""Parse the committed examples/features/run-observability.md and verify
it round-trips through FeatureDefinition cleanly.

The committed file uses sentence-case H2/H3 headings; archetype matches
case-insensitively (since agent-foundry dfb757f), so parsing succeeds.
"""

from __future__ import annotations

from pathlib import Path

from archetype.markdown import render_instance, validate_markdown

from archipelago.models.feature_definition import FeatureDefinition


class TestRunObservabilityParse:
    def test_given_committed_file_when_parsed_then_title_is_correct(self, repo_root: Path):
        text = (repo_root / "examples" / "features" / "run-observability.md").read_text(encoding="utf-8")
        fd = validate_markdown(text, FeatureDefinition)
        assert fd.title == "Run Observability"

    def test_given_committed_file_when_parsed_then_frontmatter_slug_is_correct(self, repo_root: Path):
        text = (repo_root / "examples" / "features" / "run-observability.md").read_text(encoding="utf-8")
        fd = validate_markdown(text, FeatureDefinition)
        assert fd.frontmatter.feature_slug == "run-observability"

    def test_given_committed_file_when_parsed_then_body_sections_non_empty(self, repo_root: Path):
        text = (repo_root / "examples" / "features" / "run-observability.md").read_text(encoding="utf-8")
        fd = validate_markdown(text, FeatureDefinition)
        assert len(fd.problem_statement) > 50
        assert len(fd.feature_intent) > 50
        assert len(fd.desired_outcomes.user_outcomes.items) >= 3
        assert len(fd.desired_outcomes.business_outcomes.items) >= 3
        assert len(fd.scope_boundaries.items) >= 3
        assert len(fd.assumptions.items) >= 3
        assert len(fd.dependencies.items) >= 1
        assert len(fd.constraints.items) >= 1
        assert len(fd.acceptance_criteria.items) >= 5


class TestRunObservabilityRoundTrip:
    def test_given_committed_file_when_rendered_and_reparsed_then_semantically_equal(self, repo_root: Path):
        text = (repo_root / "examples" / "features" / "run-observability.md").read_text(encoding="utf-8")
        fd = validate_markdown(text, FeatureDefinition)
        rendered = render_instance(fd)
        reparsed = validate_markdown(rendered, FeatureDefinition)
        assert reparsed == fd
```

- [ ] **Step 2: Run test**

Run: `pdm run pytest tests/archipelago/models/test_run_observability_round_trip.py -xvs`
Expected: 4 passed. (Case-insensitive matching handles `## Problem statement` vs. `snake_to_title("problem_statement") = "Problem Statement"`.)

- [ ] **Step 3: Commit**

```bash
git add tests/archipelago/models/test_run_observability_round_trip.py
git commit -m "$(cat <<'EOF'
test(models): round-trip against run-observability.md feature definition

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2.7: Public API for `archipelago.models`

**Files:**
- Modify: `src/archipelago/models/__init__.py`
- Create: `tests/archipelago/models/test_public_api.py`

**Dependencies:** Tasks 2.2, 2.3, 2.4, 2.5.

- [ ] **Step 1: Write failing test**

Create `tests/archipelago/models/test_public_api.py`:

```python
"""Public API surface for archipelago.models."""

from __future__ import annotations

import archipelago.models as models_pkg


class TestPublicAPI:
    def test_given_archipelago_models_when_imported_then_all_matches_expected(self):
        assert set(models_pkg.__all__) == {
            "AcceptanceCriteria",
            "Assumptions",
            "BusinessOutcomes",
            "CodebaseSource",
            "Constraints",
            "Dependencies",
            "DesignDocument",
            "DesignDocumentFrontmatter",
            "DesiredOutcomes",
            "FeatureDefinition",
            "FeatureDefinitionFrontmatter",
            "ScopeBoundaries",
            "UserOutcomes",
        }

    def test_given_all_names_when_accessed_then_importable(self):
        for name in models_pkg.__all__:
            assert hasattr(models_pkg, name), f"{name} listed in __all__ but missing"
```

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/models/test_public_api.py -xvs`
Expected: `AssertionError: set() != {...}` (since `__init__.py` has no `__all__` yet).

- [ ] **Step 3: Write implementation**

Replace `src/archipelago/models/__init__.py` with:

```python
"""Archipelago domain models — FeatureDefinition, DesignDocument, and
supporting types. Every boundary type in this package is a Pydantic
BaseModel subclass.
"""

from __future__ import annotations

from archipelago.models.codebase_source import CodebaseSource
from archipelago.models.design_document import (
    DesignDocument,
    DesignDocumentFrontmatter,
)
from archipelago.models.feature_definition import (
    AcceptanceCriteria,
    Assumptions,
    BusinessOutcomes,
    Constraints,
    Dependencies,
    DesiredOutcomes,
    FeatureDefinition,
    FeatureDefinitionFrontmatter,
    ScopeBoundaries,
    UserOutcomes,
)

__all__ = [
    "AcceptanceCriteria",
    "Assumptions",
    "BusinessOutcomes",
    "CodebaseSource",
    "Constraints",
    "Dependencies",
    "DesignDocument",
    "DesignDocumentFrontmatter",
    "DesiredOutcomes",
    "FeatureDefinition",
    "FeatureDefinitionFrontmatter",
    "ScopeBoundaries",
    "UserOutcomes",
]
```

- [ ] **Step 4: Run full Slice 2 tests**

Run: `pdm run pytest tests/archipelago/models/ -xvs`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/archipelago/models/__init__.py tests/archipelago/models/test_public_api.py
git commit -m "$(cat <<'EOF'
feat(models): expose public API for archipelago.models

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Slice 2 — Verification

- [ ] `pdm test-unit tests/archipelago/models/` green.
- [ ] Class-definition-time meta-validation passes for every wrapper.
- [ ] Round-trip against `examples/features/run-observability.md` passes without modifying the committed file.
- [ ] `pdm lint` and `pdm typecheck` produce no new findings.
- [ ] Public API surface matches `__all__`.

---

# Slice 3 — Workspace-Bootstrap `FunctionAction`

**Goal:** `workspace_bootstrap: FunctionAction[BootstrapInput, BootstrapOutput]` takes a `FeatureDefinition`, a `CodebaseSource`, and a pre-computed `volume_name` (generated by `run_design_pipeline`), and produces a Docker volume:

```
/workspace/
├── codebase/                       (working tree chmod 555; .git/ left writable)
│   └── .git/                       (preserved writable for git log / git blame)
└── documents/                      (chmod 775, owned by the agent UID)
    └── feature_definition.md       (chmod 444)
```

`bootstrap_fn` pre-pulls the `alpine/git` and `alpine` images before creating the volume, so a pull failure doesn't orphan a volume. The caller (`run_design_pipeline`) is responsible for volume-name generation and uniqueness — bootstrap doesn't pick its own.

**Depends on:** Slice 2 merged.

**Parallelizable with:** Slice 4 (except Task 4.1 depends on Task 3.1 for `WorkspaceHandle`).

---

## Task 3.1: `archipelago.actions` scaffolding + state models

**Files:**
- Create: `src/archipelago/actions/__init__.py` (docstring only; public API filled in Task 3.7)
- Create: `src/archipelago/actions/workspace_bootstrap.py` (models section only)
- Create: `tests/archipelago/actions/__init__.py`
- Create: `tests/archipelago/actions/test_workspace_bootstrap_models.py`

**Dependencies:** Slice 2 merged.
The stub re-exports `WorkspaceHandle` early so Task 4.1 can import it while the rest of Slice 3 is still in progress.

- [ ] **Step 1: Scaffold**

```bash
mkdir -p src/archipelago/actions tests/archipelago/actions
```

Create `src/archipelago/actions/__init__.py`:

```python
"""Archipelago function-action primitives.

A function action executes deterministic Python — no LLM, no container.
`workspace_bootstrap` provisions the shared Docker volume that every
Archipelago run operates on.
"""

from __future__ import annotations

from archipelago.actions.workspace_bootstrap import WorkspaceHandle

__all__ = ["WorkspaceHandle"]
```

Create `tests/archipelago/actions/__init__.py` (empty).

- [ ] **Step 2: Write failing test**

Create `tests/archipelago/actions/test_workspace_bootstrap_models.py`:

```python
"""Tests for workspace-bootstrap state models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from archipelago.actions.workspace_bootstrap import (
    BootstrapInput,
    BootstrapOutput,
    WorkspaceHandle,
)
from archipelago.models import CodebaseSource


def _sample_handle() -> WorkspaceHandle:
    return WorkspaceHandle(
        volume_name="archipelago-ws-demo-1000000000000000000",
        root="/workspace",
        documents_path="/workspace/documents",
        codebase_path="/workspace/codebase",
        feature_definition_path="/workspace/documents/feature_definition.md",
        codebase_source_ref="main",
        codebase_resolved_sha="a" * 40,
    )


class TestWorkspaceHandle:
    def test_given_all_fields_when_constructed_then_fields_populated(self):
        handle = _sample_handle()
        assert handle.root == "/workspace"
        assert handle.codebase_resolved_sha == "a" * 40

    def test_given_missing_volume_name_when_constructed_then_validation_error(self):
        with pytest.raises(ValidationError):
            WorkspaceHandle(
                root="/workspace",
                documents_path="/workspace/documents",
                codebase_path="/workspace/codebase",
                feature_definition_path="/workspace/documents/feature_definition.md",
                codebase_source_ref="main",
                codebase_resolved_sha="a" * 40,
            )  # type: ignore[call-arg]


class TestBootstrapInputOutput:
    def test_given_all_fields_when_bootstrap_input_then_fields_populated(
        self, minimal_feature_definition
    ):
        state = BootstrapInput(
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(
                repo_url="https://github.com/730alchemy/agent-foundry.git",
                ref="main",
            ),
            volume_name="archipelago-ws-demo-1000000000000000000",
        )
        assert state.feature_definition is minimal_feature_definition
        assert state.volume_name.startswith("archipelago-ws-")

    def test_given_missing_volume_name_when_bootstrap_input_then_validation_error(
        self, minimal_feature_definition
    ):
        with pytest.raises(ValidationError):
            BootstrapInput(
                feature_definition=minimal_feature_definition,
                codebase_source=CodebaseSource(repo_url="u", ref="r"),
            )  # type: ignore[call-arg]

    def test_given_handle_when_bootstrap_output_then_handle_preserved(self):
        handle = _sample_handle()
        out = BootstrapOutput(workspace_handle=handle)
        assert out.workspace_handle is handle
```

- [ ] **Step 3: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/actions/test_workspace_bootstrap_models.py -xvs`
Expected: `ModuleNotFoundError: No module named 'archipelago.actions.workspace_bootstrap'`.

- [ ] **Step 4: Write minimal implementation**

Create `src/archipelago/actions/workspace_bootstrap.py` (state models only):

```python
"""Workspace-bootstrap function action.

Provisions a Docker volume seeded with a cloned codebase (working tree
read-only, .git/ writable for git tooling) and a rendered
feature-definition file (read-only). The writable documents directory
is owned by the designer container's UID so the agent can write
design.md.

The caller (run_design_pipeline) supplies the volume name so the
container registry and bootstrap agree on it. bootstrap_fn does not
generate names itself.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from archipelago.models import CodebaseSource, FeatureDefinition


class WorkspaceHandle(BaseModel):
    """Pointer to the provisioned workspace volume."""

    volume_name: str
    root: str
    documents_path: str
    codebase_path: str
    feature_definition_path: str
    codebase_source_ref: str
    codebase_resolved_sha: str


class BootstrapInput(BaseModel):
    # Explicit extra="ignore" documents that the compiler passes the full
    # pipeline state into model_validate; extra fields (workspace_handle,
    # designer_output) must be silently dropped.
    model_config = ConfigDict(extra="ignore")

    feature_definition: FeatureDefinition
    codebase_source: CodebaseSource
    volume_name: str


class BootstrapOutput(BaseModel):
    workspace_handle: WorkspaceHandle
```

- [ ] **Step 5: Run test, confirm passes**

Run: `pdm run pytest tests/archipelago/actions/test_workspace_bootstrap_models.py -xvs`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add src/archipelago/actions/ tests/archipelago/actions/__init__.py tests/archipelago/actions/test_workspace_bootstrap_models.py
git commit -m "$(cat <<'EOF'
feat(actions): scaffold workspace-bootstrap state models

BootstrapInput takes volume_name as an input; the caller
(run_design_pipeline) is responsible for generation and uniqueness so
the container registry and bootstrap agree on the name.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3.2: `_workspace_ops.pull_image` + `create_volume`

**Files:**
- Create: `src/archipelago/actions/_workspace_ops.py` (partial — `pull_image` + `create_volume`)
- Create: `tests/archipelago/actions/test_workspace_ops.py` (partial)

**Dependencies:** Task 3.1.

- [ ] **Step 1: Write failing test**

Create `tests/archipelago/actions/test_workspace_ops.py`:

```python
"""Tests for the private _workspace_ops helpers.

Docker client is patched — these are unit tests. Integration against a
real daemon lives in test_bootstrap_integration.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from archipelago.actions import _workspace_ops as ops


class TestPullImage:
    def test_given_client_when_pull_image_then_images_pull_called_with_tag(self):
        client = MagicMock()
        ops.pull_image(client, "alpine/git:v2.47.2")
        client.images.pull.assert_called_once_with("alpine/git:v2.47.2")

    def test_given_pull_error_when_pull_image_then_error_propagated(self):
        import docker.errors

        client = MagicMock()
        client.images.pull.side_effect = docker.errors.APIError("pull failed")
        with pytest.raises(docker.errors.APIError):
            ops.pull_image(client, "alpine/git:v2.47.2")


class TestCreateVolume:
    def test_given_client_when_create_volume_then_volumes_create_called_with_name(self):
        client = MagicMock()
        ops.create_volume(client, "archipelago-ws-demo-1")
        client.volumes.create.assert_called_once_with(name="archipelago-ws-demo-1")

    def test_given_client_when_create_volume_then_returns_client_result(self):
        client = MagicMock()
        expected = MagicMock()
        client.volumes.create.return_value = expected
        result = ops.create_volume(client, "archipelago-ws-demo-1")
        assert result is expected

    def test_given_conflict_when_create_volume_then_api_error_propagated(self):
        import docker.errors

        client = MagicMock()
        client.volumes.create.side_effect = docker.errors.APIError("conflict")
        with pytest.raises(docker.errors.APIError):
            ops.create_volume(client, "dup")
```

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/actions/test_workspace_ops.py -xvs`
Expected: `ModuleNotFoundError: No module named 'archipelago.actions._workspace_ops'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/archipelago/actions/_workspace_ops.py`:

```python
"""Private helpers that isolate Docker + git side effects for bootstrap_fn.

Every helper takes an explicit docker.DockerClient — no module-level
client, no ambient state. Image tags used by throwaway containers are
pinned; callers pre-pull them via pull_image so bootstrap_fn fails
fast on network issues before creating a volume.
"""

from __future__ import annotations

from docker.client import DockerClient
from docker.models.volumes import Volume


GIT_IMAGE = "alpine/git:v2.47.2"
ALPINE_IMAGE = "alpine:3.20"


def pull_image(client: DockerClient, tag: str) -> None:
    """Pull `tag` so that subsequent `containers.run(tag, ...)` calls
    don't hit an inline pull (and its associated failure modes) during
    the critical section of bootstrap_fn."""
    client.images.pull(tag)


def create_volume(client: DockerClient, name: str) -> Volume:
    """Create a Docker volume with the given name.

    Raises docker.errors.APIError on name conflicts or invalid names.
    """
    return client.volumes.create(name=name)
```

- [ ] **Step 4: Run test, confirm passes**

Run: `pdm run pytest tests/archipelago/actions/test_workspace_ops.py -xvs`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/archipelago/actions/_workspace_ops.py tests/archipelago/actions/test_workspace_ops.py
git commit -m "$(cat <<'EOF'
feat(actions): add _workspace_ops.pull_image and create_volume

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3.3: `_workspace_ops.clone_and_resolve_ref`

**Files:**
- Modify: `src/archipelago/actions/_workspace_ops.py`
- Modify: `tests/archipelago/actions/test_workspace_ops.py`

**Dependencies:** Task 3.2.

- [ ] **Step 1: Append failing test**

Append to `tests/archipelago/actions/test_workspace_ops.py`:

```python
class TestCloneAndResolveRef:
    def test_given_client_when_clone_then_containers_run_mounts_volume_at_workspace(self):
        client = MagicMock()
        client.containers.run.return_value = b"a" * 40 + b"\n"

        sha = ops.clone_and_resolve_ref(
            client,
            volume_name="ws",
            repo_url="https://example.com/repo.git",
            ref="main",
        )

        call = client.containers.run.call_args
        assert call.args[0] == ops.GIT_IMAGE
        assert call.kwargs["volumes"]["ws"]["bind"] == "/workspace"
        assert call.kwargs.get("remove") is True
        assert sha == "a" * 40

    def test_given_repo_and_ref_when_clone_then_command_contains_both(self):
        client = MagicMock()
        client.containers.run.return_value = b"b" * 40 + b"\n"

        ops.clone_and_resolve_ref(
            client,
            volume_name="ws",
            repo_url="https://example.com/repo.git",
            ref="abc123",
        )

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        assert "https://example.com/repo.git" in rendered
        assert "abc123" in rendered
        assert "/workspace/codebase" in rendered
        assert "rev-parse HEAD" in rendered

    def test_given_trailing_whitespace_when_clone_then_sha_stripped(self):
        client = MagicMock()
        client.containers.run.return_value = b"  " + b"c" * 40 + b"\r\n"
        sha = ops.clone_and_resolve_ref(
            client, volume_name="ws", repo_url="u", ref="r"
        )
        assert sha == "c" * 40

    def test_given_container_error_when_clone_then_informative_error_raised(self):
        import docker.errors

        client = MagicMock()
        client.containers.run.side_effect = docker.errors.ContainerError(
            container=MagicMock(),
            exit_status=128,
            command="git clone ...",
            image="alpine/git",
            stderr=b"fatal: repository not found",
        )
        with pytest.raises(RuntimeError) as exc:
            ops.clone_and_resolve_ref(
                client, volume_name="ws", repo_url="https://example.com/x.git", ref="main"
            )
        assert "https://example.com/x.git" in str(exc.value)
        assert "main" in str(exc.value)
```

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/actions/test_workspace_ops.py::TestCloneAndResolveRef -xvs`
Expected: `AttributeError: module 'archipelago.actions._workspace_ops' has no attribute 'clone_and_resolve_ref'`.

- [ ] **Step 3: Append implementation**

Append to `src/archipelago/actions/_workspace_ops.py`:

```python
import docker.errors


def clone_and_resolve_ref(
    client: DockerClient,
    *,
    volume_name: str,
    repo_url: str,
    ref: str,
) -> str:
    """Clone repo_url into /workspace/codebase inside volume_name, check
    out ref, and return the resolved commit SHA.

    Uses a throwaway alpine/git container mounting the volume at
    /workspace. .git/ is preserved for Designer's git log / git blame.
    """
    script = (
        f"set -e && "
        f"git clone {repo_url} /workspace/codebase && "
        f"git -C /workspace/codebase checkout {ref} && "
        f"git -C /workspace/codebase rev-parse HEAD"
    )
    try:
        raw = client.containers.run(
            GIT_IMAGE,
            command=["sh", "-c", script],
            volumes={volume_name: {"bind": "/workspace", "mode": "rw"}},
            remove=True,
            stdout=True,
            stderr=False,
        )
    except docker.errors.ContainerError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
        raise RuntimeError(
            f"git clone failed for repo={repo_url!r} ref={ref!r}: {stderr}"
        ) from exc

    output = raw.decode("utf-8", errors="replace").strip()
    last_line = next(line.strip() for line in reversed(output.splitlines()) if line.strip())
    return last_line
```

- [ ] **Step 4: Run test, confirm passes**

Run: `pdm run pytest tests/archipelago/actions/test_workspace_ops.py -xvs`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/archipelago/actions/_workspace_ops.py tests/archipelago/actions/test_workspace_ops.py
git commit -m "$(cat <<'EOF'
feat(actions): add _workspace_ops.clone_and_resolve_ref

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3.4: `_workspace_ops.chmod_tree_excluding_git` + `chmod_path`

**Files:**
- Modify: `src/archipelago/actions/_workspace_ops.py`
- Modify: `tests/archipelago/actions/test_workspace_ops.py`

**Dependencies:** Task 3.3.

Two helpers:
- `chmod_tree_excluding_git(client, volume, path, mode)` — chmod the working tree while preserving `.git/` writable. Design §5 step 5 requires `.git/` intact for Designer's investigation; a blanket `chmod -R 555` breaks recent git's locking and commit-graph writes.
- `chmod_path(client, volume, path, mode)` — chmod a single path (used for individual files and for the documents directory).

- [ ] **Step 1: Append failing test**

```python
class TestChmodTreeExcludingGit:
    def test_given_path_when_chmod_tree_excluding_git_then_find_excludes_dot_git(self):
        client = MagicMock()
        client.containers.run.return_value = b""

        ops.chmod_tree_excluding_git(
            client, volume_name="ws", path="/workspace/codebase", mode="555"
        )

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        # Implementation uses `find ... -path */.git -prune` so .git/ stays writable.
        assert "/workspace/codebase" in rendered
        assert ".git" in rendered
        assert "555" in rendered
        assert call.kwargs["volumes"]["ws"]["bind"] == "/workspace"
        assert call.kwargs.get("remove") is True

    def test_given_container_error_when_chmod_tree_then_runtime_error_raised(self):
        import docker.errors

        client = MagicMock()
        client.containers.run.side_effect = docker.errors.ContainerError(
            container=MagicMock(),
            exit_status=1,
            command="find ...",
            image="alpine",
            stderr=b"find: cannot access /workspace/nowhere",
        )
        with pytest.raises(RuntimeError) as exc:
            ops.chmod_tree_excluding_git(
                client, volume_name="ws", path="/workspace/nowhere", mode="555"
            )
        assert "/workspace/nowhere" in str(exc.value)

    def test_given_trailing_slash_path_when_chmod_tree_then_no_double_slash_in_command(self):
        client = MagicMock()
        client.containers.run.return_value = b""

        ops.chmod_tree_excluding_git(
            client, volume_name="ws", path="/workspace/codebase/", mode="555"
        )

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        # Defensive rstrip means no `//` sequence appears in the script.
        assert "//" not in rendered, rendered


class TestChmodPath:
    def test_given_mode_when_chmod_path_then_chmod_command_runs(self):
        client = MagicMock()
        client.containers.run.return_value = b""

        ops.chmod_path(
            client,
            volume_name="ws",
            path="/workspace/documents/feature_definition.md",
            mode="444",
        )

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        assert "chmod 444 /workspace/documents/feature_definition.md" in rendered
```

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/actions/test_workspace_ops.py::TestChmodTreeExcludingGit tests/archipelago/actions/test_workspace_ops.py::TestChmodPath -xvs`
Expected: `AttributeError: module 'archipelago.actions._workspace_ops' has no attribute 'chmod_tree_excluding_git'`.

- [ ] **Step 3: Append implementation**

Append to `src/archipelago/actions/_workspace_ops.py`:

```python
def chmod_tree_excluding_git(
    client: DockerClient,
    *,
    volume_name: str,
    path: str,
    mode: str,
) -> None:
    """Apply chmod `mode` recursively to `path`, pruning .git/ so git
    tooling keeps its write access to index and pack locks."""
    # Strip trailing slash so `{path}/.git` renders without a double
    # slash; find's -path comparison is byte-exact and a double slash
    # would silently fail to match real .git/ and wipe its perms.
    path = path.rstrip("/")
    # `find` with -prune excludes .git/ from the traversal; the
    # alternation runs chmod on everything else.
    script = (
        f"find {path} -path '{path}/.git' -prune "
        f"-o -exec chmod {mode} {{}} +"
    )
    try:
        client.containers.run(
            ALPINE_IMAGE,
            command=["sh", "-c", script],
            volumes={volume_name: {"bind": "/workspace", "mode": "rw"}},
            remove=True,
        )
    except docker.errors.ContainerError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
        raise RuntimeError(
            f"chmod -R {mode} {path!r} (excluding .git) failed: {stderr}"
        ) from exc


def chmod_path(
    client: DockerClient,
    *,
    volume_name: str,
    path: str,
    mode: str,
) -> None:
    """chmod `path` to `mode` (non-recursive)."""
    try:
        client.containers.run(
            ALPINE_IMAGE,
            command=["sh", "-c", f"chmod {mode} {path}"],
            volumes={volume_name: {"bind": "/workspace", "mode": "rw"}},
            remove=True,
        )
    except docker.errors.ContainerError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
        raise RuntimeError(
            f"chmod {mode} {path!r} failed: {stderr}"
        ) from exc
```

- [ ] **Step 4: Run test, confirm passes**

Run: `pdm run pytest tests/archipelago/actions/test_workspace_ops.py -xvs`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add src/archipelago/actions/_workspace_ops.py tests/archipelago/actions/test_workspace_ops.py
git commit -m "$(cat <<'EOF'
feat(actions): add chmod_tree_excluding_git and chmod_path helpers

chmod_tree_excluding_git applies a recursive mode to the working tree
but prunes .git/ so git commands retain write access to index and
pack locks, per design §5 step 5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3.5: `_workspace_ops.prepare_documents_dir` + `write_file`

**Files:**
- Modify: `src/archipelago/actions/_workspace_ops.py`
- Modify: `tests/archipelago/actions/test_workspace_ops.py`

**Dependencies:** Task 3.4.

- `prepare_documents_dir` creates `/workspace/documents/` and chmods it to `0775` so the designer container's non-root user can create `design.md` there.
- `write_file` streams content into the volume via `put_archive` on a helper container (atomic, avoids shell-quoting hazards for UTF-8 content).

- [ ] **Step 1: Append failing test**

```python
import io
import tarfile


class TestPrepareDocumentsDir:
    def test_given_volume_when_prepare_documents_then_mkdir_and_chmod_called(self):
        client = MagicMock()
        client.containers.run.return_value = b""

        ops.prepare_documents_dir(client, volume_name="ws")

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        assert "mkdir -p /workspace/documents" in rendered
        assert "chmod 775 /workspace/documents" in rendered


class TestWriteFile:
    def test_given_content_when_write_file_then_put_archive_called(self):
        client = MagicMock()
        helper = MagicMock()
        client.containers.create.return_value = helper

        ops.write_file(
            client,
            volume_name="ws",
            path="/workspace/documents/feature_definition.md",
            content="# hello\n",
        )

        assert client.containers.create.called
        assert helper.put_archive.called
        call = helper.put_archive.call_args
        assert call.args[0] == "/workspace/documents"
        tar_bytes = call.args[1]
        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r") as tar:
            members = tar.getmembers()
            assert len(members) == 1
            assert members[0].name == "feature_definition.md"
            extracted = tar.extractfile(members[0])
            assert extracted is not None
            assert extracted.read() == b"# hello\n"

    def test_given_mode_when_write_file_then_chmod_path_invoked_after_write(self):
        client = MagicMock()
        helper = MagicMock()
        client.containers.create.return_value = helper

        ops.write_file(
            client,
            volume_name="ws",
            path="/workspace/documents/feature_definition.md",
            content="content",
            mode="444",
        )
        # chmod_path dispatches through containers.run with a chmod command.
        chmod_calls = [
            c for c in client.containers.run.call_args_list
            if "chmod" in (" ".join(c.kwargs.get("command", [])) if isinstance(c.kwargs.get("command"), list) else str(c.kwargs.get("command", "")))
        ]
        assert chmod_calls, "chmod container call was not made"

    def test_given_helper_container_when_write_file_then_helper_removed(self):
        client = MagicMock()
        helper = MagicMock()
        client.containers.create.return_value = helper

        ops.write_file(
            client,
            volume_name="ws",
            path="/workspace/documents/feature_definition.md",
            content="content",
        )
        assert helper.remove.called
```

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/actions/test_workspace_ops.py::TestPrepareDocumentsDir tests/archipelago/actions/test_workspace_ops.py::TestWriteFile -xvs`
Expected: `AttributeError: module 'archipelago.actions._workspace_ops' has no attribute 'prepare_documents_dir'`.

- [ ] **Step 3: Append implementation**

```python
import io
import posixpath
import tarfile


DOCUMENTS_DIR_MODE = "775"


def prepare_documents_dir(client: DockerClient, *, volume_name: str) -> None:
    """mkdir -p /workspace/documents and chmod it 0775 so a non-root
    designer container can create design.md there.

    Ownership UID is whatever the throwaway container's default is
    (root in alpine), matched by the agent-worker base image running
    with a matching UID. If a future base image uses a different UID,
    add a chown step here.
    """
    script = "mkdir -p /workspace/documents && chmod 775 /workspace/documents"
    try:
        client.containers.run(
            ALPINE_IMAGE,
            command=["sh", "-c", script],
            volumes={volume_name: {"bind": "/workspace", "mode": "rw"}},
            remove=True,
        )
    except docker.errors.ContainerError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
        raise RuntimeError(f"prepare_documents_dir failed: {stderr}") from exc


def write_file(
    client: DockerClient,
    *,
    volume_name: str,
    path: str,
    content: str,
    mode: str | None = None,
) -> None:
    """Write content to path inside volume_name.

    Streams a tar archive into the target directory via put_archive on a
    helper container — atomic, avoids shell-quoting hazards for UTF-8.
    If `mode` is supplied, chmods the file after writing.
    """
    directory, filename = posixpath.split(path)

    tar_buf = io.BytesIO()
    encoded = content.encode("utf-8")
    with tarfile.open(fileobj=tar_buf, mode="w") as tar:
        info = tarfile.TarInfo(name=filename)
        info.size = len(encoded)
        info.mode = 0o644
        tar.addfile(info, io.BytesIO(encoded))
    tar_bytes = tar_buf.getvalue()

    helper = client.containers.create(
        ALPINE_IMAGE,
        command=["true"],
        volumes={volume_name: {"bind": "/workspace", "mode": "rw"}},
    )
    try:
        helper.put_archive(directory, tar_bytes)
    finally:
        helper.remove()

    if mode is not None:
        chmod_path(client, volume_name=volume_name, path=path, mode=mode)
```

- [ ] **Step 4: Run test, confirm passes**

Run: `pdm run pytest tests/archipelago/actions/test_workspace_ops.py -xvs`
Expected: 16 passed.

- [ ] **Step 5: Commit**

```bash
git add src/archipelago/actions/_workspace_ops.py tests/archipelago/actions/test_workspace_ops.py
git commit -m "$(cat <<'EOF'
feat(actions): add prepare_documents_dir and write_file helpers

prepare_documents_dir mkdir's /workspace/documents and chmods it 0775
so the non-root designer container can create design.md there.
write_file streams via put_archive to avoid shell-quoting hazards.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3.6: `bootstrap_fn` orchestration

**Files:**
- Modify: `src/archipelago/actions/workspace_bootstrap.py`
- Create: `tests/archipelago/actions/test_bootstrap_fn.py`

**Dependencies:** Tasks 3.1, 3.5.

Order of operations inside `bootstrap_fn`:
1. Pre-pull `GIT_IMAGE` and `ALPINE_IMAGE` (fail fast if network is broken — before any volume exists).
2. `create_volume(state.volume_name)`.
3. `clone_and_resolve_ref` → resolved SHA.
4. `chmod_tree_excluding_git('/workspace/codebase', '555')` — locks working tree, preserves `.git/` writable.
5. `prepare_documents_dir` — `/workspace/documents/` exists and is 0775.
6. `write_file('/workspace/documents/feature_definition.md', rendered, mode='444')`.
7. Return `WorkspaceHandle`.

- [ ] **Step 1: Write failing test**

Create `tests/archipelago/actions/test_bootstrap_fn.py`:

```python
"""Tests for bootstrap_fn orchestration (helpers patched)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from archetype.markdown import render_instance

from archipelago.actions.workspace_bootstrap import (
    BootstrapInput,
    BootstrapOutput,
    bootstrap_fn,
)
from archipelago.models import CodebaseSource


@pytest.fixture
def patched_ops():
    with patch("archipelago.actions.workspace_bootstrap._ops") as ops_mod, patch(
        "archipelago.actions.workspace_bootstrap.docker.from_env"
    ) as from_env:
        client = MagicMock()
        from_env.return_value = client
        ops_mod.clone_and_resolve_ref.return_value = "f" * 40
        ops_mod.create_volume.return_value = MagicMock(name="volume")
        ops_mod.GIT_IMAGE = "alpine/git:v2.47.2"
        ops_mod.ALPINE_IMAGE = "alpine:3.20"
        yield ops_mod, client


def _input(minimal_feature_definition, volume_name="archipelago-ws-demo-1") -> BootstrapInput:
    return BootstrapInput(
        feature_definition=minimal_feature_definition,
        codebase_source=CodebaseSource(
            repo_url="https://example.com/repo.git", ref="main"
        ),
        volume_name=volume_name,
    )


class TestBootstrapFn:
    def test_given_input_when_bootstrap_then_helpers_called_in_order(
        self, patched_ops, minimal_feature_definition
    ):
        ops_mod, client = patched_ops
        result = bootstrap_fn(_input(minimal_feature_definition))

        assert isinstance(result, BootstrapOutput)

        # 1. Images pulled before volume creation.
        pull_calls = ops_mod.pull_image.call_args_list
        assert {c.args[1] for c in pull_calls} == {"alpine/git:v2.47.2", "alpine:3.20"}

        # 2. Volume created with the passed name.
        ops_mod.create_volume.assert_called_once_with(client, "archipelago-ws-demo-1")

        # 3. Clone against the passed name.
        ops_mod.clone_and_resolve_ref.assert_called_once_with(
            client,
            volume_name="archipelago-ws-demo-1",
            repo_url="https://example.com/repo.git",
            ref="main",
        )

        # 4. chmod_tree_excluding_git on the codebase path, mode 555.
        ops_mod.chmod_tree_excluding_git.assert_called_once_with(
            client,
            volume_name="archipelago-ws-demo-1",
            path="/workspace/codebase",
            mode="555",
        )

        # 5. Documents dir prepared.
        ops_mod.prepare_documents_dir.assert_called_once_with(
            client, volume_name="archipelago-ws-demo-1"
        )

        # 6. write_file on feature_definition.md with mode 444.
        ops_mod.write_file.assert_called_once()
        kwargs = ops_mod.write_file.call_args.kwargs
        assert kwargs["path"] == "/workspace/documents/feature_definition.md"
        assert kwargs["mode"] == "444"

    def test_given_input_when_bootstrap_then_feature_def_rendered_via_render_instance(
        self, patched_ops, minimal_feature_definition
    ):
        ops_mod, _ = patched_ops
        bootstrap_fn(_input(minimal_feature_definition))

        kwargs = ops_mod.write_file.call_args.kwargs
        assert kwargs["content"] == render_instance(minimal_feature_definition)

    def test_given_input_when_bootstrap_then_handle_records_ref_and_resolved_sha(
        self, patched_ops, minimal_feature_definition
    ):
        ops_mod, _ = patched_ops
        ops_mod.clone_and_resolve_ref.return_value = "d" * 40
        state = BootstrapInput(
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(repo_url="u", ref="v1.2.3"),
            volume_name="archipelago-ws-demo-1",
        )

        result = bootstrap_fn(state)
        assert result.workspace_handle.codebase_source_ref == "v1.2.3"
        assert result.workspace_handle.codebase_resolved_sha == "d" * 40
        assert result.workspace_handle.volume_name == "archipelago-ws-demo-1"

    def test_given_pull_failure_when_bootstrap_then_create_volume_not_called(
        self, patched_ops, minimal_feature_definition
    ):
        ops_mod, _ = patched_ops
        ops_mod.pull_image.side_effect = RuntimeError("network error")
        with pytest.raises(RuntimeError, match="network error"):
            bootstrap_fn(_input(minimal_feature_definition))
        ops_mod.create_volume.assert_not_called()

    def test_given_clone_failure_when_bootstrap_then_chmod_and_write_skipped(
        self, patched_ops, minimal_feature_definition
    ):
        ops_mod, _ = patched_ops
        ops_mod.clone_and_resolve_ref.side_effect = RuntimeError("clone failed")
        with pytest.raises(RuntimeError, match="clone failed"):
            bootstrap_fn(_input(minimal_feature_definition))
        ops_mod.chmod_tree_excluding_git.assert_not_called()
        ops_mod.prepare_documents_dir.assert_not_called()
        ops_mod.write_file.assert_not_called()

    def test_given_post_create_failure_when_bootstrap_then_volume_is_removed(
        self, patched_ops, minimal_feature_definition
    ):
        ops_mod, client = patched_ops
        ops_mod.clone_and_resolve_ref.side_effect = RuntimeError("clone failed")
        state = BootstrapInput(
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(repo_url="u", ref="r"),
            volume_name="archipelago-ws-demo-cleanup",
        )

        with pytest.raises(RuntimeError, match="clone failed"):
            bootstrap_fn(state)

        # Volume removed via client.volumes.get(name).remove(force=True).
        client.volumes.get.assert_called_with("archipelago-ws-demo-cleanup")
        client.volumes.get.return_value.remove.assert_called_with(force=True)
```

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/actions/test_bootstrap_fn.py -xvs`
Expected: `ImportError: cannot import name 'bootstrap_fn' from 'archipelago.actions.workspace_bootstrap'`.

- [ ] **Step 3: Write implementation**

Append to `src/archipelago/actions/workspace_bootstrap.py`:

```python
import docker
from archetype.markdown import render_instance

from archipelago.actions import _workspace_ops as _ops


def bootstrap_fn(state: BootstrapInput) -> BootstrapOutput:
    """Provision the workspace volume.

    Pre-pulls both throwaway-container images before touching any state,
    so a broken network fails fast and doesn't leave an orphan volume.
    The volume name is supplied by the caller (run_design_pipeline) —
    bootstrap_fn never generates names.
    """
    client = docker.from_env()

    # 1. Pre-pull images. Fail fast before creating any state.
    _ops.pull_image(client, _ops.GIT_IMAGE)
    _ops.pull_image(client, _ops.ALPINE_IMAGE)

    # 2. Create the volume with the caller-supplied name.
    _ops.create_volume(client, state.volume_name)

    # Steps 3–6 are the critical section: any failure past this point
    # would leave an orphan volume, so we remove it on any exception
    # before re-raising.
    try:
        # 3. Clone, checkout ref, resolve SHA.
        resolved_sha = _ops.clone_and_resolve_ref(
            client,
            volume_name=state.volume_name,
            repo_url=state.codebase_source.repo_url,
            ref=state.codebase_source.ref,
        )

        # 4. Lock working tree, preserve .git/ writable.
        _ops.chmod_tree_excluding_git(
            client,
            volume_name=state.volume_name,
            path="/workspace/codebase",
            mode="555",
        )

        # 5. Ensure documents dir exists and is writable to the designer UID.
        _ops.prepare_documents_dir(client, volume_name=state.volume_name)

        # 6. Stage the feature definition file (locked to 444 once written).
        _ops.write_file(
            client,
            volume_name=state.volume_name,
            path="/workspace/documents/feature_definition.md",
            content=render_instance(state.feature_definition),
            mode="444",
        )
    except Exception:
        # Partial failure — remove the volume so we don't accumulate orphans.
        # Swallow cleanup errors; the original exception is what the caller
        # needs to see.
        try:
            client.volumes.get(state.volume_name).remove(force=True)
        except Exception:
            pass
        raise

    handle = WorkspaceHandle(
        volume_name=state.volume_name,
        root="/workspace",
        documents_path="/workspace/documents",
        codebase_path="/workspace/codebase",
        feature_definition_path="/workspace/documents/feature_definition.md",
        codebase_source_ref=state.codebase_source.ref,
        codebase_resolved_sha=resolved_sha,
    )
    return BootstrapOutput(workspace_handle=handle)
```

- [ ] **Step 4: Run test, confirm passes**

Run: `pdm run pytest tests/archipelago/actions/test_bootstrap_fn.py -xvs`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/archipelago/actions/workspace_bootstrap.py tests/archipelago/actions/test_bootstrap_fn.py
git commit -m "$(cat <<'EOF'
feat(actions): implement bootstrap_fn orchestration

Pre-pulls both images before any volume creation so network failures
fail fast. Uses caller-supplied volume_name. Preserves .git/ writable
so Designer's git investigation works; prepares documents dir 0775
for design.md writes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3.7: `workspace_bootstrap` primitive + public API

**Files:**
- Modify: `src/archipelago/actions/workspace_bootstrap.py`
- Modify: `src/archipelago/actions/__init__.py`
- Create: `tests/archipelago/actions/test_public_api.py`

**Dependencies:** Task 3.6.

- [ ] **Step 1: Write failing test**

Create `tests/archipelago/actions/test_public_api.py`:

```python
"""Public API surface for archipelago.actions."""

from __future__ import annotations

from agent_foundry.primitives.models import FunctionAction

import archipelago.actions as actions_pkg
from archipelago.actions.workspace_bootstrap import (
    BootstrapInput,
    BootstrapOutput,
    bootstrap_fn,
    workspace_bootstrap,
)


class TestWorkspaceBootstrapPrimitive:
    def test_given_workspace_bootstrap_when_inspected_then_is_function_action(self):
        assert isinstance(workspace_bootstrap, FunctionAction)

    def test_given_workspace_bootstrap_when_inspected_then_function_is_bootstrap_fn(self):
        assert workspace_bootstrap.function is bootstrap_fn

    def test_given_workspace_bootstrap_function_return_type_is_bootstrap_output(self):
        assert workspace_bootstrap.function.__annotations__["return"] is BootstrapOutput


class TestPublicAPI:
    def test_given_actions_package_when_imported_then_all_matches_expected(self):
        assert set(actions_pkg.__all__) == {
            "workspace_bootstrap",
            "BootstrapInput",
            "BootstrapOutput",
            "WorkspaceHandle",
        }

    def test_given_all_names_when_accessed_then_importable(self):
        for name in actions_pkg.__all__:
            assert hasattr(actions_pkg, name)
```

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/actions/test_public_api.py -xvs`
Expected: `ImportError: cannot import name 'workspace_bootstrap' from 'archipelago.actions.workspace_bootstrap'`.

- [ ] **Step 3: Write implementation**

Append to `src/archipelago/actions/workspace_bootstrap.py`:

```python
from agent_foundry.primitives.models import FunctionAction


workspace_bootstrap = FunctionAction[BootstrapInput, BootstrapOutput](
    function=bootstrap_fn,
)
```

Replace `src/archipelago/actions/__init__.py`:

```python
"""Archipelago function-action primitives."""

from __future__ import annotations

from archipelago.actions.workspace_bootstrap import (
    BootstrapInput,
    BootstrapOutput,
    WorkspaceHandle,
    workspace_bootstrap,
)

__all__ = [
    "BootstrapInput",
    "BootstrapOutput",
    "WorkspaceHandle",
    "workspace_bootstrap",
]
```

- [ ] **Step 4: Run test, confirm passes**

Run: `pdm run pytest tests/archipelago/actions/ -xvs`
Expected: all Slice 3 unit tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/archipelago/actions/workspace_bootstrap.py src/archipelago/actions/__init__.py tests/archipelago/actions/test_public_api.py
git commit -m "$(cat <<'EOF'
feat(actions): declare workspace_bootstrap primitive and public API

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3.8: Integration test against a real Docker daemon

**Files:**
- Create: `tests/archipelago/actions/test_bootstrap_integration.py`

**Dependencies:** Task 3.7.

Integration test exercises the full bootstrap against a real Docker daemon + public repo pinned by SHA. Docker-availability check lives inside the fixture (not after the `yield`) so unavailable hosts skip cleanly rather than erroring at fixture setup.

- [ ] **Step 1: Determine a pinned repo + SHA**

Run: `git ls-remote https://github.com/730alchemy/agent-foundry.git main`
Copy the resolved 40-char SHA — that's `PINNED_SHA` in the test below.

- [ ] **Step 2: Write test**

Create `tests/archipelago/actions/test_bootstrap_integration.py`:

```python
"""End-to-end bootstrap against a real Docker daemon."""

from __future__ import annotations

import docker
import pytest

from archipelago.actions import BootstrapInput, BootstrapOutput
from archipelago.actions.workspace_bootstrap import bootstrap_fn
from archipelago.models import CodebaseSource

PINNED_REPO = "https://github.com/730alchemy/agent-foundry.git"
# Replace with the actual SHA from Step 1 before committing.
PINNED_SHA = "<resolved-sha-from-step-1>"

pytestmark = pytest.mark.integration


def _docker_available() -> bool:
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


@pytest.fixture
def docker_client():
    if not _docker_available():
        pytest.skip("Docker daemon not reachable")
    return docker.from_env()


@pytest.fixture
def cleanup_volumes(docker_client, archipelago_volume_registry):
    created: list[str] = []
    try:
        yield created
    finally:
        for name in created:
            archipelago_volume_registry.add(name)
            try:
                docker_client.volumes.get(name).remove(force=True)
            except Exception:
                pass


class TestBootstrapIntegration:
    def test_given_real_repo_when_bootstrap_then_volume_populated_correctly(
        self, docker_client, cleanup_volumes, minimal_feature_definition
    ):
        import time

        volume_name = f"archipelago-ws-test-{time.time_ns()}"
        state = BootstrapInput(
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(repo_url=PINNED_REPO, ref=PINNED_SHA),
            volume_name=volume_name,
        )

        result = bootstrap_fn(state)
        cleanup_volumes.append(result.workspace_handle.volume_name)
        assert isinstance(result, BootstrapOutput)

        output = docker_client.containers.run(
            "alpine:3.20",
            command=[
                "sh",
                "-c",
                "ls -la /workspace/documents && "
                "stat -c '%a %n' /workspace/documents/feature_definition.md && "
                "stat -c '%a %n' /workspace/documents && "
                "test -d /workspace/codebase/.git && echo '.git present' && "
                "find /workspace/codebase -maxdepth 2 -name pyproject.toml "
                "-exec stat -c '%a %n' {} +",
            ],
            volumes={result.workspace_handle.volume_name: {"bind": "/workspace", "mode": "ro"}},
            remove=True,
        ).decode("utf-8", errors="replace")

        assert "feature_definition.md" in output
        assert ".git present" in output
        assert "444 /workspace/documents/feature_definition.md" in output
        assert "775 /workspace/documents" in output
        assert "555 /workspace/codebase/" in output

    def test_given_real_repo_when_bootstrap_then_git_log_still_works(
        self, docker_client, cleanup_volumes, minimal_feature_definition
    ):
        """Regression guard: .git/ must remain writable so git tooling works."""
        import time

        volume_name = f"archipelago-ws-test-git-{time.time_ns()}"
        state = BootstrapInput(
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(repo_url=PINNED_REPO, ref=PINNED_SHA),
            volume_name=volume_name,
        )
        result = bootstrap_fn(state)
        cleanup_volumes.append(result.workspace_handle.volume_name)

        # Run a git command that writes to .git (commit-graph, reachability cache).
        output = docker_client.containers.run(
            "alpine/git:v2.47.2",
            command=[
                "sh",
                "-c",
                "cd /workspace/codebase && git log -1 --oneline",
            ],
            volumes={result.workspace_handle.volume_name: {"bind": "/workspace", "mode": "rw"}},
            remove=True,
        ).decode("utf-8", errors="replace")

        assert output.strip(), "git log produced no output"

    def test_given_real_repo_when_bootstrap_then_resolved_sha_is_40_hex(
        self, docker_client, cleanup_volumes, minimal_feature_definition
    ):
        import time

        volume_name = f"archipelago-ws-test-sha-{time.time_ns()}"
        state = BootstrapInput(
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(repo_url=PINNED_REPO, ref=PINNED_SHA),
            volume_name=volume_name,
        )
        result = bootstrap_fn(state)
        cleanup_volumes.append(result.workspace_handle.volume_name)

        sha = result.workspace_handle.codebase_resolved_sha
        assert len(sha) == 40
        assert all(c in "0123456789abcdef" for c in sha)
```

- [ ] **Step 3: Run integration test**

Run: `pdm test-integration tests/archipelago/actions/test_bootstrap_integration.py -xvs`
Expected on a host with Docker + network: `3 passed`.
Expected on a host without Docker: `3 skipped`.

- [ ] **Step 4: Commit**

```bash
git add tests/archipelago/actions/test_bootstrap_integration.py
git commit -m "$(cat <<'EOF'
test(actions): add workspace-bootstrap integration test

Covers volume layout (chmod 555 on codebase, chmod 775 on documents,
chmod 444 on feature_definition.md), .git/ preserved-writable
regression (git log still works), and resolved-SHA format.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Slice 3 — Verification

- [ ] `pdm test-unit tests/archipelago/actions/` green.
- [ ] `pdm test-integration tests/archipelago/actions/` green on a host with Docker; skips cleanly otherwise.
- [ ] Manual smoke: `docker run --rm -v <volume>:/workspace alpine ls -la /workspace/codebase /workspace/documents` shows expected layout; `alpine/git git log -1` works.
- [ ] `pdm lint` / `pdm typecheck` green.

---

# Slice 4 — Designer `AgentAction`

**Goal:** `designer: AgentAction[DesignerInput, DesignerOutput]` renders its instructions at container-start via `archetype.templating.resolve` against the run's `FeatureDefinition`, points its output envelope at `/workspace/documents/design.md`, and uses the container config from design §6.1.

**Depends on:** Slice 1 (shipped), Slice 2 (for `FeatureDefinition` / `DesignDocument`), **Task 3.1** (for `WorkspaceHandle`). The rest of Slice 3 can run in parallel with Slice 4.

---

## Task 4.1: `archipelago.agents.designer` scaffolding + models

**Files:**
- Create: `src/archipelago/agents/__init__.py`
- Create: `src/archipelago/agents/designer/__init__.py` (public API filled in Task 4.5)
- Create: `src/archipelago/agents/designer/models.py`
- Create: `tests/archipelago/agents/__init__.py`
- Create: `tests/archipelago/agents/designer/__init__.py`
- Create: `tests/archipelago/agents/designer/test_models.py`

**Dependencies:** Slice 2 merged + Task 3.1 merged.

- [ ] **Step 1: Scaffold**

```bash
mkdir -p src/archipelago/agents/designer tests/archipelago/agents/designer
```

Create empty test markers:

```python
# tests/archipelago/agents/__init__.py
```

```python
# tests/archipelago/agents/designer/__init__.py
```

Create `src/archipelago/agents/__init__.py` (docstring only — public API filled in Task 4.5):

```python
"""Archipelago agents package. Public entry points for agent primitives."""
```

Create `src/archipelago/agents/designer/__init__.py`:

```python
"""Designer agent — Cluster A in the Phase 2 tensions analysis.

Reads a FeatureDefinition + target codebase and produces a DesignDocument.
"""
```

- [ ] **Step 2: Write failing test**

Create `tests/archipelago/agents/designer/test_models.py`:

```python
"""Tests for Designer input/output/slice models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from archipelago.actions import WorkspaceHandle
from archipelago.agents.designer.models import (
    DesignerInput,
    DesignerOutput,
)


def _sample_handle() -> WorkspaceHandle:
    return WorkspaceHandle(
        volume_name="v",
        root="/workspace",
        documents_path="/workspace/documents",
        codebase_path="/workspace/codebase",
        feature_definition_path="/workspace/documents/feature_definition.md",
        codebase_source_ref="main",
        codebase_resolved_sha="a" * 40,
    )


class TestDesignerInput:
    def test_given_handle_and_feature_when_constructed_then_fields_populated(
        self, minimal_feature_definition
    ):
        state = DesignerInput(
            workspace_handle=_sample_handle(),
            feature_definition=minimal_feature_definition,
        )
        assert state.workspace_handle.root == "/workspace"
        assert state.feature_definition.title == "Demo Feature"

    def test_given_missing_workspace_handle_when_constructed_then_validation_error(
        self, minimal_feature_definition
    ):
        with pytest.raises(ValidationError):
            DesignerInput(feature_definition=minimal_feature_definition)  # type: ignore[call-arg]


class TestDesignerOutput:
    def test_given_path_when_constructed_then_stored_as_string(self):
        out = DesignerOutput(design_document="/workspace/documents/design.md")
        assert out.design_document == "/workspace/documents/design.md"

    def test_given_json_schema_when_generated_then_design_document_carries_agent_file_path_marker(self):
        schema = DesignerOutput.model_json_schema()
        path_schema = schema["properties"]["design_document"]
        assert "x-agent-file-path" in path_schema


```

- [ ] **Step 3: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/agents/designer/test_models.py -xvs`
Expected: `ModuleNotFoundError: No module named 'archipelago.agents.designer.models'`.

- [ ] **Step 4: Write minimal implementation**

Create `src/archipelago/agents/designer/models.py`:

```python
"""Designer agent state models.

Input: workspace handle (paths, volume, ref/SHA) + parsed
FeatureDefinition (inlined into instructions via Jinja).

Output: a single envelope pointing at the design document's path in
the workspace. `Annotated[str, AgentFilePath()]` causes the container
executor's file-verification machinery to check existence + size bounds
when the agent emits success.
"""

from __future__ import annotations

from typing import Annotated

from agent_foundry.models.markers import AgentFilePath
from pydantic import BaseModel, ConfigDict

from archipelago.actions import WorkspaceHandle
from archipelago.models import FeatureDefinition


class DesignerInput(BaseModel):
    # Explicit extra="ignore" — the compiler passes the full pipeline
    # state; extra fields must be dropped.
    model_config = ConfigDict(extra="ignore")

    workspace_handle: WorkspaceHandle
    feature_definition: FeatureDefinition


class DesignerOutput(BaseModel):
    design_document: Annotated[str, AgentFilePath()]
```

- [ ] **Step 5: Run test, confirm passes**

Run: `pdm run pytest tests/archipelago/agents/designer/test_models.py -xvs`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add src/archipelago/agents/ tests/archipelago/agents/
git commit -m "$(cat <<'EOF'
feat(agents-designer): add Designer input/output models

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4.2: Designer instructions template + resolution round-trip

**Files:**
- Create: `src/archipelago/agents/designer/instructions_template.md`
- Create: `tests/archipelago/agents/designer/test_instructions_template.py`

**Dependencies:** Task 4.1.

Content verbatim from Phase 2 design §6.3. Six sections: role preamble, input, output, investigation, design, output protocol.

- [ ] **Step 1: Write failing test**

Create `tests/archipelago/agents/designer/test_instructions_template.py`:

```python
"""Tests for the Designer instructions template.

Loads the bundled template, resolves it against the minimal fixture,
asserts structural and content markers are present.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from archetype.markdown import template_fields
from archetype.templating import resolve

from archipelago.models import DesignDocument, FeatureDefinition

TEMPLATE_PATH = (
    Path(__file__).resolve().parents[4]
    / "src"
    / "archipelago"
    / "agents"
    / "designer"
    / "instructions_template.md"
)


def _template_text() -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8")


class TestTemplateFile:
    def test_given_template_path_when_read_then_exists_and_non_empty(self):
        text = _template_text()
        assert len(text) > 500


class TestTemplateResolution:
    def test_given_template_when_resolved_then_no_exception(self, minimal_feature_definition):
        resolved = resolve(
            _template_text(),
            feature=minimal_feature_definition,
            FeatureDefinition=FeatureDefinition,
            DesignDocument=DesignDocument,
        )
        assert len(resolved) > 500

    def test_given_resolved_when_checked_then_contains_feature_definition_headings(
        self, minimal_feature_definition
    ):
        resolved = resolve(
            _template_text(),
            feature=minimal_feature_definition,
            FeatureDefinition=FeatureDefinition,
            DesignDocument=DesignDocument,
        )
        for field in template_fields(FeatureDefinition):
            assert field.heading in resolved, (
                f"missing FeatureDefinition heading {field.heading!r}"
            )

    def test_given_resolved_when_checked_then_contains_design_document_skeleton(
        self, minimal_feature_definition
    ):
        resolved = resolve(
            _template_text(),
            feature=minimal_feature_definition,
            FeatureDefinition=FeatureDefinition,
            DesignDocument=DesignDocument,
        )
        for field in template_fields(DesignDocument):
            assert f"## {field.heading}" in resolved, (
                f"missing DesignDocument section '## {field.heading}'"
            )

    def test_given_resolved_when_checked_then_inlines_feature_prose(
        self, minimal_feature_definition
    ):
        resolved = resolve(
            _template_text(),
            feature=minimal_feature_definition,
            FeatureDefinition=FeatureDefinition,
            DesignDocument=DesignDocument,
        )
        assert minimal_feature_definition.problem_statement in resolved
        assert minimal_feature_definition.feature_intent in resolved

    def test_given_resolved_when_checked_then_inlines_list_items(
        self, minimal_feature_definition
    ):
        resolved = resolve(
            _template_text(),
            feature=minimal_feature_definition,
            FeatureDefinition=FeatureDefinition,
            DesignDocument=DesignDocument,
        )
        for item in minimal_feature_definition.desired_outcomes.user_outcomes.items:
            assert item in resolved
        for item in minimal_feature_definition.assumptions.items:
            assert item in resolved
        for item in minimal_feature_definition.acceptance_criteria.items:
            assert item in resolved

    def test_given_resolved_when_checked_then_mentions_workspace_paths(
        self, minimal_feature_definition
    ):
        resolved = resolve(
            _template_text(),
            feature=minimal_feature_definition,
            FeatureDefinition=FeatureDefinition,
            DesignDocument=DesignDocument,
        )
        assert "/workspace/documents/feature_definition.md" in resolved
        assert "/workspace/codebase/" in resolved
        assert "/workspace/documents/design.md" in resolved
```

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/agents/designer/test_instructions_template.py -xvs`
Expected: `FileNotFoundError: ...instructions_template.md`.

- [ ] **Step 3: Create the template file**

Create `src/archipelago/agents/designer/instructions_template.md` with content verbatim from Phase 2 design §6.3:

```markdown
# Designer

You are the Designer for Archipelago — an autonomous software
engineering system. Your job is to produce a design document for
a given feature, informed by the feature definition and the target
codebase. Your document is the input to the three downstream
stages: decomposition into change sets, planning of TDD steps,
and implementation. Write for them.

## Your input

Read the feature definition at `/workspace/documents/feature_definition.md`.

The feature definition has these sections:
{% for field in template_fields(FeatureDefinition) %}
- **{{ field.heading }}** — {{ field.description }}
{% endfor %}

This run, you are designing for the feature **{{ feature.title }}**.

**Problem statement:** {{ feature.problem_statement }}

**Feature intent:** {{ feature.feature_intent }}

**User outcomes:**
{% for outcome in feature.desired_outcomes.user_outcomes.items %}
- {{ outcome }}
{% endfor %}

**Business outcomes:**
{% for outcome in feature.desired_outcomes.business_outcomes.items %}
- {{ outcome }}
{% endfor %}

**Scope boundaries:**
{% for item in feature.scope_boundaries.items %}
- {{ item }}
{% endfor %}

**Assumptions:**
{% for item in feature.assumptions.items %}
- {{ item }}
{% endfor %}

**Dependencies:**
{% for item in feature.dependencies.items %}
- {{ item }}
{% endfor %}

**Constraints:**
{% for item in feature.constraints.items %}
- {{ item }}
{% endfor %}

**Acceptance criteria:**
{% for item in feature.acceptance_criteria.items %}
- {{ item }}
{% endfor %}

The target codebase is mounted read-only at `/workspace/codebase/`.

## Your output

Write the design document at `/workspace/documents/design.md`. It must
match this structure exactly:

{{ render_template(DesignDocument) }}

The placeholder comments describe what each section is for.

## How to investigate

Build an understanding of the current state relevant to this feature
before drafting the design.

**Delegate broad surveys.** When you want to explore a subsystem,
discover patterns across many files, or map relationships between
modules, use an Explore subagent via the Agent tool and consume
its summary. Do not read many files directly — delegation keeps
your own context focused on synthesis.

Use Read, Grep, Glob, and LSP tools directly only for narrow,
targeted lookups — confirming a function signature, reading one
specific file you already know matters, checking a single symbol's
references.

As a starter for what to investigate, consider:
- Package structure around areas this feature touches.
- Public interfaces and conventions in those areas.
- Patterns already established for similar concerns.
- Test conventions and fixtures available.

Use judgment. Skip items that don't apply; add investigations the
list doesn't cover.

When you have enough context, write a short investigation summary
(what you learned; what's still uncertain) before drafting. Do not
begin the design before this checkpoint.

## How to design

Design for the target state — the ideal shape of the feature once
complete. Do not design for incremental shippability; how the work
is sliced into change sets is handled downstream.

### Design principles

Good design produces software that is **easy to understand, easy to
change, easy to test and debug, and easy to extend**. These are the
qualities implementers, reviewers, debuggers, and future changers
will depend on — and the qualities a future Critic agent will judge
your design against.

Modularity is the primary means to those ends. A system properly
modularized is comprehensible, testable, and safe to change. The
principles below are either constituents of good modularity, or
consequences that good modularity enables, or disciplines that keep
modular designs honest.

**Modularity done well rests on:**

- **Separation of concerns.** Each component owns one concern;
  unrelated concerns live in different components.
- **Cohesion.** Pieces within a component belong together; they
  serve its single concern.
- **Loose coupling.** Components depend on stable interfaces, not
  each other's internals. A change inside one component should
  not ripple.
- **Abstraction and information hiding.** Interfaces expose what
  callers need; implementation detail stays hidden behind them.

**What modularity done well enables:**

- **Composition over inheritance.** Well-modularized pieces combine
  through composition. Inheritance creates tight coupling between
  base and derived; composition keeps seams clean.
- **Explicit dependencies.** A component's dependencies appear in
  its signature — no hidden globals, no implicit reads. Explicit
  dependencies are what make collaboration injectable.
- **Testability.** Injectable collaborators, pure functions where
  practical, deterministic behavior where the domain allows.
  Well-modularized code is testable almost by definition.

**Support disciplines:**

- **Strong typing.** Use the target language's type system to make
  design contracts visible and enforceable. Boundary types,
  discriminated unions, and named enumerations (rather than raw
  strings or dicts) turn contracts into navigable code that resists
  drift.
- **Observability.** Design so runtime behavior is inspectable:
  meaningful names, structured events at boundaries, errors that
  carry context. Good module boundaries are natural observation
  points.

### Avoid over-engineering

Do not add abstractions, flags, extension points, or plumbing for
hypothetical future needs. Design for the current target state;
generalize later when a second real use case emerges. Don't
premature-optimize — design for clarity first, tune when a real
bottleneck is found.

### Follow project-specific conventions

Read `/workspace/codebase/CLAUDE.md` early in investigation (if
present) for project-specific conventions — type conventions,
framework choices, naming patterns — and respect them. If your
design would require changing a convention, surface that in
`risks_and_open_items` rather than making the change silently.

### Respect the feature's boundaries

Your design must stay within the feature's declared scope boundaries,
satisfy every declared constraint, and be consistent with its
declared dependencies. If any of these are in tension with a design
choice, pull back the design or surface the conflict in
`risks_and_open_items`.

### Resolve every input assumption explicitly

For every assumption in the feature definition, decide its
disposition (accepted, refined, promoted to constraint, or
contradicted) and record it in `resolved_assumptions`. Record any
new assumptions you introduce during design in the same section.

### Surface uncertainty

Anything the design leaves uncertain — bets you're making, decisions
you deferred, places where later stages will need judgment — belongs
in `risks_and_open_items`.

### Clarification vs. risk

If a design decision materially depends on information you lack, and
no reasonable bet can substitute, emit `clarification_needed` with
the specific question. Otherwise, make the bet and record it as a
risk.

### Completeness

Fill every section of the design document meaningfully. If a section
truly doesn't apply, write "none" with reasoning rather than leaving
it empty.

## Output protocol

When you complete the design, emit a **success** outcome with:
- `design_document`: path to the design doc
  (`/workspace/documents/design.md`).

Before emitting success, verify the design doc exists at the expected
path and has every required section filled meaningfully.

If you need specific information that a reasonable bet cannot
substitute for, emit **clarification_needed** with:
- `question`: the specific question to answer.
- `context`: enough background that the answerer can respond without
  re-reading the whole design.

If you need a permission you don't currently have (network access to
an external resource, a tool not currently available), emit
**permission_needed** with:
- `action`: what you want to do.
- `reason`: why it's needed for the design.

If you hit an unrecoverable error — the workspace is broken, inputs
are malformed, tools repeatedly fail — emit **failed** with:
- `reason`: what went wrong.
```

- [ ] **Step 4: Run test, confirm passes**

Run: `pdm run pytest tests/archipelago/agents/designer/test_instructions_template.py -xvs`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/archipelago/agents/designer/instructions_template.md tests/archipelago/agents/designer/test_instructions_template.py
git commit -m "$(cat <<'EOF'
feat(agents-designer): add Jinja-templated Designer instructions

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4.3: Designer callables

**Files:**
- Create: `src/archipelago/agents/designer/callables.py`
- Create: `tests/archipelago/agents/designer/test_callables.py`

**Dependencies:** Tasks 4.1, 4.2.

- [ ] **Step 1: Write failing test**

Create `tests/archipelago/agents/designer/test_callables.py`:

```python
"""Tests for Designer prompt_builder and instructions_provider."""

from __future__ import annotations

from pathlib import Path

from archetype.markdown import template_fields
from archetype.templating import resolve

from archipelago.actions import WorkspaceHandle
from archipelago.agents.designer.callables import (
    designer_instructions_provider,
    designer_prompt_builder,
)
from archipelago.agents.designer.models import DesignerInput
from archipelago.models import DesignDocument, FeatureDefinition


def _state(minimal_feature_definition) -> DesignerInput:
    return DesignerInput(
        workspace_handle=WorkspaceHandle(
            volume_name="v",
            root="/workspace",
            documents_path="/workspace/documents",
            codebase_path="/workspace/codebase",
            feature_definition_path="/workspace/documents/feature_definition.md",
            codebase_source_ref="main",
            codebase_resolved_sha="a" * 40,
        ),
        feature_definition=minimal_feature_definition,
    )


class TestDesignerPromptBuilder:
    def test_given_state_when_prompt_builder_then_returns_non_empty_string(
        self, minimal_feature_definition
    ):
        result = designer_prompt_builder(_state(minimal_feature_definition))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_given_state_when_prompt_builder_then_mentions_workspace_root(
        self, minimal_feature_definition
    ):
        result = designer_prompt_builder(_state(minimal_feature_definition))
        assert "/workspace" in result

    def test_given_state_when_prompt_builder_then_references_instructions_or_design(
        self, minimal_feature_definition
    ):
        result = designer_prompt_builder(_state(minimal_feature_definition))
        assert "instructions" in result.lower() or "design" in result.lower()


class TestDesignerInstructionsProvider:
    def test_given_state_when_instructions_provider_then_matches_manual_resolve(
        self, minimal_feature_definition
    ):
        state = _state(minimal_feature_definition)
        result = designer_instructions_provider(state)

        template_path = (
            Path(__file__).resolve().parents[4]
            / "src" / "archipelago" / "agents" / "designer" / "instructions_template.md"
        )
        expected = resolve(
            template_path.read_text(encoding="utf-8"),
            feature=state.feature_definition,
            FeatureDefinition=FeatureDefinition,
            DesignDocument=DesignDocument,
        )
        assert result == expected

    def test_given_state_when_instructions_provider_then_contains_structural_markers(
        self, minimal_feature_definition
    ):
        state = _state(minimal_feature_definition)
        result = designer_instructions_provider(state)
        for field in template_fields(FeatureDefinition):
            assert field.heading in result
        for field in template_fields(DesignDocument):
            assert f"## {field.heading}" in result
```

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/agents/designer/test_callables.py -xvs`
Expected: `ModuleNotFoundError: No module named 'archipelago.agents.designer.callables'`.

- [ ] **Step 3: Write implementation**

Create `src/archipelago/agents/designer/callables.py`:

```python
"""Designer callables — prompt_builder and instructions_provider.

Both take DesignerInput so templating can inline per-run state.
Instructions are loaded from the bundled template file and resolved
via archetype.templating.resolve.
"""

from __future__ import annotations

from pathlib import Path

from archetype.templating import resolve

from archipelago.agents.designer.models import DesignerInput
from archipelago.models import DesignDocument, FeatureDefinition

_TEMPLATE_PATH = Path(__file__).parent / "instructions_template.md"


def designer_prompt_builder(state: DesignerInput) -> str:
    return (
        f"The workspace is mounted at {state.workspace_handle.root}. "
        f"Follow your instructions to produce the design document."
    )


def designer_instructions_provider(state: DesignerInput) -> str:
    template_text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return resolve(
        template_text,
        feature=state.feature_definition,
        FeatureDefinition=FeatureDefinition,
        DesignDocument=DesignDocument,
    )
```

- [ ] **Step 4: Run test, confirm passes**

Run: `pdm run pytest tests/archipelago/agents/designer/test_callables.py -xvs`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/archipelago/agents/designer/callables.py tests/archipelago/agents/designer/test_callables.py
git commit -m "$(cat <<'EOF'
feat(agents-designer): add prompt_builder and instructions_provider

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4.4: `designer` `AgentAction` primitive

**Files:**
- Create: `src/archipelago/agents/designer/primitive.py`
- Create: `tests/archipelago/agents/designer/test_primitive.py`

**Dependencies:** Task 4.3.

**Important:** before writing the test, grep `agent-foundry/src/agent_foundry/primitives/models.py` for the actual field names on `AgentAction`. The design doc §6.1 uses `visible_dirs`, `writable_dirs`, `reuse_policy`, `timeout_seconds`, `skip_permissions` — confirm these match. If agent-foundry uses different names, adjust both test and implementation. Also note: `timeout_seconds` is stored on the primitive but **not enforced** by `run_primitive_plan` in the current orchestration layer — it's a declaration only. Phase 2 accepts this gap.

- [ ] **Step 1: Write failing test**

Create `tests/archipelago/agents/designer/test_primitive.py`:

```python
"""Tests for the Designer AgentAction primitive config."""

from __future__ import annotations

from agent_foundry.orchestration.container_executor import run_agent_in_container
from agent_foundry.primitives.models import AgentAction, ContainerReusePolicy

from archipelago.agents.designer.callables import (
    designer_instructions_provider,
    designer_prompt_builder,
)
from archipelago.agents.designer.primitive import designer


class TestDesignerPrimitiveConfig:
    def test_given_designer_when_inspected_then_is_agent_action(self):
        assert isinstance(designer, AgentAction)

    def test_given_designer_when_inspected_then_name_is_designer(self):
        assert designer.name == "designer"

    def test_given_designer_when_inspected_then_callables_wired(self):
        assert designer.prompt_builder is designer_prompt_builder
        assert designer.instructions_provider is designer_instructions_provider

    def test_given_designer_when_inspected_then_executor_is_run_agent_in_container(self):
        assert designer.executor is run_agent_in_container

    def test_given_designer_when_inspected_then_dir_policy_matches_design(self):
        assert designer.visible_dirs == ["/workspace"]
        assert designer.writable_dirs == ["/workspace/documents"]

    def test_given_designer_when_inspected_then_reuse_policy_is_new_session(self):
        assert designer.reuse_policy is ContainerReusePolicy.REUSE_NEW_SESSION

    def test_given_designer_when_inspected_then_timeout_is_30_minutes(self):
        assert designer.timeout_seconds == 1800

    def test_given_designer_when_inspected_then_skip_permissions_is_true(self):
        assert designer.skip_permissions is True
```

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/agents/designer/test_primitive.py -xvs`
Expected: `ModuleNotFoundError: No module named 'archipelago.agents.designer.primitive'`.

- [ ] **Step 3: Write implementation**

Create `src/archipelago/agents/designer/primitive.py`:

```python
"""Designer AgentAction declaration.

Container config per design §6.1:
- /workspace visible (codebase read-only + documents writable via chmod).
- Only /workspace/documents/ writable.
- REUSE_NEW_SESSION reuse policy.
- 30-minute timeout (declaration only — not enforced by the
  orchestrator in Phase 2; Designer can run longer in practice).
"""

from __future__ import annotations

from agent_foundry.orchestration.container_executor import run_agent_in_container
from agent_foundry.primitives.models import AgentAction, ContainerReusePolicy

from archipelago.agents.designer.callables import (
    designer_instructions_provider,
    designer_prompt_builder,
)
from archipelago.agents.designer.models import DesignerInput, DesignerOutput

designer = AgentAction[DesignerInput, DesignerOutput](
    name="designer",
    prompt_builder=designer_prompt_builder,
    instructions_provider=designer_instructions_provider,
    executor=run_agent_in_container,
    reuse_policy=ContainerReusePolicy.REUSE_NEW_SESSION,
    timeout_seconds=1800,
    visible_dirs=["/workspace"],
    writable_dirs=["/workspace/documents"],
    skip_permissions=True,
)
```

- [ ] **Step 4: Run test, confirm passes**

Run: `pdm run pytest tests/archipelago/agents/designer/test_primitive.py -xvs`
Expected: 8 passed. If agent-foundry's `AgentAction` uses different field names, adjust test and implementation together in this step before re-running.

- [ ] **Step 5: Commit**

```bash
git add src/archipelago/agents/designer/primitive.py tests/archipelago/agents/designer/test_primitive.py
git commit -m "$(cat <<'EOF'
feat(agents-designer): declare designer AgentAction primitive

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4.5: Public API

**Files:**
- Modify: `src/archipelago/agents/designer/__init__.py`
- Modify: `src/archipelago/agents/__init__.py`
- Create: `tests/archipelago/agents/designer/test_public_api.py`

**Dependencies:** Task 4.4.

- [ ] **Step 1: Write failing test**

Create `tests/archipelago/agents/designer/test_public_api.py`:

```python
"""Public API surface for archipelago.agents.designer and archipelago.agents."""

from __future__ import annotations

import archipelago.agents as agents_pkg
import archipelago.agents.designer as designer_pkg


class TestDesignerPackageAPI:
    def test_given_designer_package_when_imported_then_all_matches_expected(self):
        assert set(designer_pkg.__all__) == {
            "designer",
            "DesignerInput",
            "DesignerOutput",
        }

    def test_given_all_names_when_accessed_then_importable(self):
        for name in designer_pkg.__all__:
            assert hasattr(designer_pkg, name)


class TestAgentsPackageAPI:
    def test_given_agents_package_when_imported_then_designer_reachable(self):
        assert "designer" in agents_pkg.__all__
        assert hasattr(agents_pkg, "designer")
```

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/agents/designer/test_public_api.py -xvs`
Expected: `AssertionError: set() != {...}`.

- [ ] **Step 3: Write implementation**

Replace `src/archipelago/agents/designer/__init__.py`:

```python
"""Designer agent — Cluster A in the Phase 2 tensions analysis.

Reads a FeatureDefinition + target codebase and produces a DesignDocument.
"""

from __future__ import annotations

from archipelago.agents.designer.models import (
    DesignerInput,
    DesignerOutput,
)
from archipelago.agents.designer.primitive import designer

__all__ = [
    "DesignerInput",
    "DesignerOutput",
    "designer",
]
```

Replace `src/archipelago/agents/__init__.py`:

```python
"""Archipelago agents package. Public entry points for agent primitives."""

from __future__ import annotations

from archipelago.agents.designer import designer

__all__ = ["designer"]
```

- [ ] **Step 4: Run test, confirm passes**

Run: `pdm run pytest tests/archipelago/agents/ -xvs`
Expected: all Slice 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/archipelago/agents/designer/__init__.py src/archipelago/agents/__init__.py tests/archipelago/agents/designer/test_public_api.py
git commit -m "$(cat <<'EOF'
feat(agents-designer): expose public API for designer and agents packages

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Slice 4 — Verification

- [ ] `pdm test-unit tests/archipelago/agents/` green.
- [ ] Instructions template resolves against `minimal_feature_definition` without error.
- [ ] Every Designer primitive config field matches Phase 2 design §6.1.
- [ ] `pdm lint` / `pdm typecheck` green.

---

# Slice 5 — Design Pipeline + CLI + First E2E

**Goal:** Compose `workspace_bootstrap → designer` into `design_pipeline: Sequence[DesignPipelineState, DesignPipelineState]`. Wire `run_design_pipeline(feature_definition, codebase_source) -> DesignPipelineState` that generates the volume name, constructs the `PrimitivePlan`, supplies all four required kwargs to `run_primitive_plan` (`artifacts_dir`, `workspace_volume`, `base_image_tag`, `responder_provider`), and threads the volume name into the initial `DesignPipelineState` so `bootstrap_fn` uses the same name. Provide a CLI at `scripts/run_design_pipeline.py`. Run the first real end-to-end test against `examples/features/run-observability.md` targeting agent-foundry. When Slice 5 passes, Phase 2 is complete.

**Depends on:** Slices 2, 3, 4.

---

## Task 5.1: `DesignPipelineState` + volume-name helper

**Files:**
- Create: `src/archipelago/systems/__init__.py`
- Create: `src/archipelago/systems/design_pipeline.py` (state model + helper only)
- Create: `tests/archipelago/systems/__init__.py`
- Create: `tests/archipelago/systems/test_design_pipeline_state.py`

**Dependencies:** Slices 2, 3, 4 merged.

- [ ] **Step 1: Scaffold**

```bash
mkdir -p src/archipelago/systems tests/archipelago/systems
```

Create `src/archipelago/systems/__init__.py`:

```python
"""Runnable Archipelago systems — compositions of primitives.

`design_pipeline` is the Phase 2 pipeline: workspace_bootstrap → designer.
Given a feature definition and a target codebase, it produces a design
document.
"""
```

Create `tests/archipelago/systems/__init__.py` (empty).

- [ ] **Step 2: Write failing test**

Create `tests/archipelago/systems/test_design_pipeline_state.py`:

```python
"""Tests for DesignPipelineState and the volume-name helper."""

from __future__ import annotations

import re

from archipelago.actions import WorkspaceHandle
from archipelago.agents.designer import DesignerOutput
from archipelago.models import CodebaseSource
from archipelago.systems.design_pipeline import DesignPipelineState, generate_volume_name


def _handle() -> WorkspaceHandle:
    return WorkspaceHandle(
        volume_name="v",
        root="/workspace",
        documents_path="/workspace/documents",
        codebase_path="/workspace/codebase",
        feature_definition_path="/workspace/documents/feature_definition.md",
        codebase_source_ref="main",
        codebase_resolved_sha="a" * 40,
    )


class TestDesignPipelineState:
    def test_given_required_fields_when_constructed_then_optionals_default_to_none(
        self, minimal_feature_definition
    ):
        state = DesignPipelineState(
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(repo_url="u", ref="r"),
            volume_name="archipelago-ws-demo-1",
        )
        assert state.workspace_handle is None
        assert state.designer_output is None

    def test_given_all_fields_when_constructed_then_fields_populated(
        self, minimal_feature_definition
    ):
        state = DesignPipelineState(
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(repo_url="u", ref="r"),
            volume_name="archipelago-ws-demo-1",
            workspace_handle=_handle(),
            designer_output=DesignerOutput(design_document="/workspace/documents/design.md"),
        )
        assert state.workspace_handle is not None
        assert state.designer_output is not None


class TestGenerateVolumeName:
    def test_given_slug_when_generate_then_name_matches_expected_pattern(self):
        name = generate_volume_name("run-observability")
        assert re.match(r"^archipelago-ws-run-observability-\d{19}$", name), name

    def test_given_slug_with_unsafe_chars_when_generate_then_sanitized(self):
        name = generate_volume_name("my weird/slug!")
        assert re.match(r"^archipelago-ws-[a-zA-Z0-9._-]+-\d{19}$", name), name

    def test_given_two_calls_when_generate_then_names_differ(self):
        # time_ns() suffix makes same-second collisions astronomically rare.
        a = generate_volume_name("demo")
        b = generate_volume_name("demo")
        assert a != b


class TestStateFieldInvariants:
    """Compile-time invariants: each step's input-type fields must be a
    subset of DesignPipelineState fields, so the compiler's state-extraction
    pass finds every field it needs."""

    def test_given_bootstrap_input_when_inspected_then_fields_subset_of_pipeline_state(self):
        from archipelago.actions import BootstrapInput

        assert set(BootstrapInput.model_fields.keys()) <= set(
            DesignPipelineState.model_fields.keys()
        )

    def test_given_designer_input_when_inspected_then_fields_subset_of_pipeline_state(self):
        from archipelago.agents.designer import DesignerInput

        # DesignerInput needs workspace_handle (from BootstrapOutput's
        # unpacking) + feature_definition (from the initial state).
        # Both must be keys of DesignPipelineState.
        expected_subset = set(DesignerInput.model_fields.keys())
        available = set(DesignPipelineState.model_fields.keys())
        assert expected_subset <= available, (
            f"DesignerInput fields not in DesignPipelineState: "
            f"{expected_subset - available}"
        )
```

- [ ] **Step 3: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/systems/test_design_pipeline_state.py -xvs`
Expected: `ModuleNotFoundError: No module named 'archipelago.systems.design_pipeline'`.

- [ ] **Step 4: Write minimal implementation**

Create `src/archipelago/systems/design_pipeline.py`:

```python
"""Design pipeline — Phase 2's runnable system.

Given a feature definition and a target codebase, compose workspace
bootstrap + Designer into a Sequence and run it to produce a design
document.
"""

from __future__ import annotations

import re
import time

from pydantic import BaseModel

from archipelago.actions import WorkspaceHandle
from archipelago.agents.designer import DesignerOutput
from archipelago.models import CodebaseSource, FeatureDefinition


# Base image for AgentAction containers. Hardcoded for Phase 2; sourced
# from Phase 3's published image once that ships. If the tag needs to
# change, update here and redeploy.
BASE_IMAGE_TAG = "agent-worker:latest"


_VOLUME_NAME_UNSAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def generate_volume_name(feature_slug: str) -> str:
    """Produce a unique Docker-volume name for one pipeline run.

    Form: `archipelago-ws-{sanitized-slug}-{unix_nanoseconds}`. The
    nanosecond suffix makes same-second collisions astronomically rare
    (no observed collisions in practice at this resolution). The caller
    (run_design_pipeline) passes this name into both the container
    registry and bootstrap_fn so they agree on it.
    """
    sanitized = _VOLUME_NAME_UNSAFE.sub("-", feature_slug).strip("-") or "unnamed"
    return f"archipelago-ws-{sanitized}-{time.time_ns()}"


class DesignPipelineState(BaseModel):
    """State that flows through the design pipeline Sequence.

    `feature_definition`, `codebase_source`, and `volume_name` are
    populated at pipeline entry. `workspace_handle` is filled by
    `workspace_bootstrap`. `designer_output` is filled by `designer`.
    """

    feature_definition: FeatureDefinition
    codebase_source: CodebaseSource
    volume_name: str
    workspace_handle: WorkspaceHandle | None = None
    designer_output: DesignerOutput | None = None
```

- [ ] **Step 5: Run test, confirm passes**

Run: `pdm run pytest tests/archipelago/systems/test_design_pipeline_state.py -xvs`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add src/archipelago/systems/ tests/archipelago/systems/__init__.py tests/archipelago/systems/test_design_pipeline_state.py
git commit -m "$(cat <<'EOF'
feat(systems): add DesignPipelineState and volume-name helper

generate_volume_name() centralizes volume-name generation so the
container registry and bootstrap_fn agree on the name. time_ns()
suffix prevents same-second collisions.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5.2: `design_pipeline` Sequence

**Files:**
- Modify: `src/archipelago/systems/design_pipeline.py` (append)
- Create: `tests/archipelago/systems/test_sequence_composition.py`

**Dependencies:** Task 5.1.

- [ ] **Step 1: Write failing test**

Create `tests/archipelago/systems/test_sequence_composition.py`:

```python
"""Tests for the design_pipeline Sequence composition."""

from __future__ import annotations

from agent_foundry.primitives.models import Sequence

from archipelago.actions import workspace_bootstrap
from archipelago.agents.designer import designer
from archipelago.systems.design_pipeline import DesignPipelineState, design_pipeline


class TestDesignPipelineSequence:
    def test_given_pipeline_when_inspected_then_is_sequence(self):
        assert isinstance(design_pipeline, Sequence)

    def test_given_pipeline_when_inspected_then_steps_are_bootstrap_then_designer(self):
        assert design_pipeline.steps == [workspace_bootstrap, designer]

    def test_given_pipeline_when_inspected_then_step_order_preserved(self):
        first, second = design_pipeline.steps[0], design_pipeline.steps[1]
        assert first is workspace_bootstrap
        assert second is designer
```

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/systems/test_sequence_composition.py -xvs`
Expected: `ImportError: cannot import name 'design_pipeline' from 'archipelago.systems.design_pipeline'`.

- [ ] **Step 3: Append implementation**

Append to `src/archipelago/systems/design_pipeline.py`:

```python
from agent_foundry.primitives.models import Sequence

from archipelago.actions import workspace_bootstrap
from archipelago.agents.designer import designer


design_pipeline = Sequence[DesignPipelineState, DesignPipelineState](
    steps=[workspace_bootstrap, designer],
)
```

- [ ] **Step 4: Run test, confirm passes**

Run: `pdm run pytest tests/archipelago/systems/test_sequence_composition.py -xvs`
Expected: 3 passed. If the `Sequence[I, O](steps=...)` form doesn't match agent-foundry's actual API, adjust the declaration (and test assertions) accordingly.

- [ ] **Step 5: Commit**

```bash
git add src/archipelago/systems/design_pipeline.py tests/archipelago/systems/test_sequence_composition.py
git commit -m "$(cat <<'EOF'
feat(systems): compose design_pipeline Sequence (bootstrap → designer)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5.3: `run_design_pipeline` orchestrator

**Files:**
- Modify: `src/archipelago/systems/design_pipeline.py` (append)
- Create: `tests/archipelago/systems/test_run_design_pipeline.py`

**Dependencies:** Task 5.2.

`run_design_pipeline` is the async entry point. It generates the volume name once, constructs the initial `DesignPipelineState` with that name (so `bootstrap_fn` uses it), and calls `run_primitive_plan(PrimitivePlan(root=design_pipeline), initial_state=..., artifacts_dir=..., workspace_volume=<same name>, base_image_tag=BASE_IMAGE_TAG, responder_provider=static_provider(StdinResponder()))`.

- [ ] **Step 1: Verify agent-foundry's `run_primitive_plan` signature**

Run: `pdm run python -c "from agent_foundry.orchestration import run_primitive_plan; import inspect; print(inspect.signature(run_primitive_plan))"`
Expected: confirms signature — `(plan: PrimitivePlan, *, initial_state, artifacts_dir, workspace_volume, base_image_tag, responder_provider, run_id=None)`.

- [ ] **Step 2: Write failing test**

Create `tests/archipelago/systems/test_run_design_pipeline.py`:

```python
"""Tests for run_design_pipeline (run_primitive_plan + executor patched)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from archipelago.agents.designer import DesignerOutput
from archipelago.models import CodebaseSource
from archipelago.systems.design_pipeline import (
    BASE_IMAGE_TAG,
    DesignPipelineState,
    run_design_pipeline,
)


@pytest.fixture
def patched_runner():
    with patch(
        "archipelago.systems.design_pipeline.run_primitive_plan",
        new_callable=AsyncMock,
    ) as mock:
        yield mock


class TestRunDesignPipeline:
    @pytest.mark.asyncio
    async def test_given_inputs_when_run_then_plan_invoked_with_initial_state(
        self, patched_runner, minimal_feature_definition
    ):
        cs = CodebaseSource(repo_url="u", ref="r")
        final = DesignPipelineState(
            feature_definition=minimal_feature_definition,
            codebase_source=cs,
            volume_name="archipelago-ws-demo-1",
            designer_output=DesignerOutput(design_document="/workspace/documents/design.md"),
        )
        patched_runner.return_value = final

        result = await run_design_pipeline(
            feature_definition=minimal_feature_definition,
            codebase_source=cs,
        )

        assert result is final
        patched_runner.assert_called_once()
        kwargs = patched_runner.call_args.kwargs

        # initial_state carries the generated volume_name.
        initial_state = kwargs["initial_state"]
        assert isinstance(initial_state, DesignPipelineState)
        assert initial_state.feature_definition is minimal_feature_definition
        assert initial_state.codebase_source is cs
        assert initial_state.volume_name.startswith("archipelago-ws-")
        assert initial_state.workspace_handle is None
        assert initial_state.designer_output is None

        # workspace_volume kwarg passed to run_primitive_plan equals the
        # volume_name in initial_state — they must agree.
        assert kwargs["workspace_volume"] == initial_state.volume_name

        # base_image_tag from the module constant.
        assert kwargs["base_image_tag"] == BASE_IMAGE_TAG

        # responder_provider is a zero-arg callable that returns a
        # StdinResponder instance.
        from agent_foundry.responders.stdin import StdinResponder

        responder = kwargs["responder_provider"]()
        assert isinstance(responder, StdinResponder)

        # artifacts_dir is a Path under cwd/runs/ with a timestamp name.
        artifacts_dir = kwargs["artifacts_dir"]
        assert isinstance(artifacts_dir, Path)
        assert artifacts_dir.parent.name == "runs"
        # YYYY-MM-DD-HH-MM-SS — second-resolution timestamp.
        import re
        assert re.match(r"^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}$", artifacts_dir.name), (
            artifacts_dir.name
        )

    @pytest.mark.asyncio
    async def test_given_plan_raises_when_run_then_error_propagates(
        self, patched_runner, minimal_feature_definition
    ):
        patched_runner.side_effect = RuntimeError("bootstrap exploded")
        with pytest.raises(RuntimeError, match="bootstrap exploded"):
            await run_design_pipeline(
                feature_definition=minimal_feature_definition,
                codebase_source=CodebaseSource(repo_url="u", ref="r"),
            )
```

- [ ] **Step 3: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/systems/test_run_design_pipeline.py -xvs`
Expected: `ImportError: cannot import name 'run_design_pipeline' from 'archipelago.systems.design_pipeline'`.

- [ ] **Step 4: Append implementation**

Append to `src/archipelago/systems/design_pipeline.py`:

```python
import datetime
from pathlib import Path

from agent_foundry.orchestration import run_primitive_plan
from agent_foundry.primitives.plan import PrimitivePlan
from agent_foundry.responders.protocol import static_provider
from agent_foundry.responders.stdin import StdinResponder


def _artifacts_dir_for_run() -> Path:
    """`cwd/runs/<YYYY-MM-DD-HH-MM-SS>/` — second-resolution timestamp
    makes per-run directories sortable and human-readable without the
    visual noise of nanoseconds."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    return Path.cwd() / "runs" / ts


async def run_design_pipeline(
    *,
    feature_definition: FeatureDefinition,
    codebase_source: CodebaseSource,
) -> DesignPipelineState:
    """Run the design pipeline and return the final state.

    Generates the workspace-volume name once and threads it into both
    the initial state (for bootstrap_fn) and the run_primitive_plan
    workspace_volume kwarg (for the container registry), so both sides
    agree on the name of the Docker volume the designer container will
    mount.
    """
    volume_name = generate_volume_name(feature_definition.frontmatter.feature_slug)
    initial_state = DesignPipelineState(
        feature_definition=feature_definition,
        codebase_source=codebase_source,
        volume_name=volume_name,
    )
    return await run_primitive_plan(
        PrimitivePlan(root=design_pipeline),
        initial_state=initial_state,
        artifacts_dir=_artifacts_dir_for_run(),
        workspace_volume=volume_name,
        base_image_tag=BASE_IMAGE_TAG,
        responder_provider=static_provider(StdinResponder()),
    )
```

- [ ] **Step 5: Run test, confirm passes**

Run: `pdm run pytest tests/archipelago/systems/test_run_design_pipeline.py -xvs`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/archipelago/systems/design_pipeline.py tests/archipelago/systems/test_run_design_pipeline.py
git commit -m "$(cat <<'EOF'
feat(systems): add run_design_pipeline orchestrator

Generates the workspace-volume name once and threads it into both the
initial state (for bootstrap_fn) and run_primitive_plan's
workspace_volume kwarg so the container registry mounts the same
volume bootstrap creates. Artifacts land in cwd/runs/<timestamp>/,
the base image tag is module-hardcoded, and StdinResponder handles
clarification/permission requests.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5.4: CLI — `scripts/run_design_pipeline.py`

**Files:**
- Create: `scripts/run_design_pipeline.py`
- Create: `tests/archipelago/scripts/__init__.py`
- Create: `tests/archipelago/scripts/test_run_design_pipeline_cli.py`

**Dependencies:** Task 5.3.

CLI wraps `asyncio.run(run_design_pipeline(...))` in `try/except` for `AgentFailedError` (designer failed — exit 1 with the reason in the message) and `RuntimeError` (bootstrap failed — exit 1 with the reason). Input-parse errors produce exit 2 with the parser message. Success exits 0 and prints the design document path + volume name.

- [ ] **Step 1: Write failing test**

```bash
mkdir -p scripts tests/archipelago/scripts
```

Create `tests/archipelago/scripts/__init__.py` (empty).

Create `tests/archipelago/scripts/test_run_design_pipeline_cli.py`:

```python
"""Tests for the run_design_pipeline CLI."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from agent_foundry.orchestration.errors import AgentFailedError

from archipelago.agents.designer import DesignerOutput
from archipelago.models import CodebaseSource
from archipelago.systems.design_pipeline import DesignPipelineState


@pytest.fixture
def cli_module():
    path = (
        Path(__file__).resolve().parents[3] / "scripts" / "run_design_pipeline.py"
    )
    spec = importlib.util.spec_from_file_location("run_design_pipeline_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_design_pipeline_script"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def run_pipeline_mock():
    with patch(
        "run_design_pipeline_script.run_design_pipeline",
        new_callable=AsyncMock,
    ) as mock:
        yield mock


class TestCLISuccess:
    def test_given_all_flags_when_main_then_success(
        self, cli_module, run_pipeline_mock, tmp_path, capsys, minimal_feature_definition
    ):
        repo_root = Path(__file__).resolve().parents[3]
        text = (repo_root / "examples" / "features" / "run-observability.md").read_text(encoding="utf-8")
        feature_file = tmp_path / "feature.md"
        feature_file.write_text(text, encoding="utf-8")

        run_pipeline_mock.return_value = DesignPipelineState(
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(repo_url="u", ref="r"),
            volume_name="archipelago-ws-demo-1",
            designer_output=DesignerOutput(design_document="/workspace/documents/design.md"),
        )
        # Populate workspace_handle to exercise the success-print path.
        from archipelago.actions import WorkspaceHandle
        run_pipeline_mock.return_value = run_pipeline_mock.return_value.model_copy(
            update={
                "workspace_handle": WorkspaceHandle(
                    volume_name="archipelago-ws-demo-1",
                    root="/workspace",
                    documents_path="/workspace/documents",
                    codebase_path="/workspace/codebase",
                    feature_definition_path="/workspace/documents/feature_definition.md",
                    codebase_source_ref="r",
                    codebase_resolved_sha="a" * 40,
                )
            }
        )

        result = cli_module.main([
            "--feature", str(feature_file),
            "--repo", "https://github.com/730alchemy/agent-foundry.git",
            "--ref", "main",
        ])
        assert result == 0
        run_pipeline_mock.assert_called_once()
        out, _ = capsys.readouterr()
        assert "/workspace/documents/design.md" in out
        assert "archipelago-ws-demo-1" in out


class TestCLIArgValidation:
    def test_given_missing_required_flags_when_main_then_nonzero_exit(self, cli_module):
        with pytest.raises(SystemExit) as exc:
            cli_module.main(["--feature", "/tmp/x.md"])
        assert exc.value.code != 0

    def test_given_missing_feature_file_when_main_then_exit_2(self, cli_module, capsys):
        result = cli_module.main([
            "--feature", "/does/not/exist.md",
            "--repo", "u",
            "--ref", "r",
        ])
        assert result == 2
        _, err = capsys.readouterr()
        assert "/does/not/exist.md" in err

    def test_given_unparseable_feature_when_main_then_exit_2(self, cli_module, tmp_path, capsys):
        bad = tmp_path / "bad.md"
        bad.write_text("garbage without structure", encoding="utf-8")
        result = cli_module.main([
            "--feature", str(bad),
            "--repo", "u",
            "--ref", "r",
        ])
        assert result == 2
        _, err = capsys.readouterr()
        assert "parse" in err.lower() or "validation" in err.lower()


class TestCLIFailures:
    def test_given_designer_failure_when_main_then_exit_1(
        self, cli_module, run_pipeline_mock, tmp_path, capsys
    ):
        repo_root = Path(__file__).resolve().parents[3]
        text = (repo_root / "examples" / "features" / "run-observability.md").read_text(encoding="utf-8")
        feature_file = tmp_path / "feature.md"
        feature_file.write_text(text, encoding="utf-8")
        run_pipeline_mock.side_effect = AgentFailedError("designer emitted failed: reason=X")

        result = cli_module.main([
            "--feature", str(feature_file),
            "--repo", "u",
            "--ref", "r",
        ])
        assert result == 1
        _, err = capsys.readouterr()
        assert "designer" in err.lower()
        assert "reason=X" in err

    def test_given_bootstrap_failure_when_main_then_exit_1(
        self, cli_module, run_pipeline_mock, tmp_path, capsys
    ):
        repo_root = Path(__file__).resolve().parents[3]
        text = (repo_root / "examples" / "features" / "run-observability.md").read_text(encoding="utf-8")
        feature_file = tmp_path / "feature.md"
        feature_file.write_text(text, encoding="utf-8")
        run_pipeline_mock.side_effect = RuntimeError("git clone failed for repo=...")

        result = cli_module.main([
            "--feature", str(feature_file),
            "--repo", "u",
            "--ref", "r",
        ])
        assert result == 1
        _, err = capsys.readouterr()
        assert "bootstrap" in err.lower() or "git clone" in err.lower()
```

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/scripts/test_run_design_pipeline_cli.py -xvs`
Expected: `FileNotFoundError: .../scripts/run_design_pipeline.py`.

- [ ] **Step 3: Write implementation**

Create `scripts/run_design_pipeline.py`:

```python
"""Archipelago design-pipeline CLI.

Reads a feature-definition markdown file, invokes the design pipeline
against the named repo + ref, and prints the produced design document's
path. Exit codes:
  0 — success.
  1 — pipeline runtime failure (bootstrap or designer).
  2 — input-parse or argument error.

Usage:
    python scripts/run_design_pipeline.py \\
        --feature examples/features/run-observability.md \\
        --repo https://github.com/730alchemy/agent-foundry.git \\
        --ref main
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from agent_foundry.orchestration.errors import AgentFailedError
from archetype.markdown import MarkdownValidationError, validate_markdown

from archipelago.models import CodebaseSource, FeatureDefinition
from archipelago.systems.design_pipeline import run_design_pipeline


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_design_pipeline",
        description="Run the Archipelago design pipeline (bootstrap → designer).",
    )
    parser.add_argument("--feature", required=True, help="Path to a feature-definition markdown file.")
    parser.add_argument("--repo", required=True, help="Git URL of the target codebase.")
    parser.add_argument("--ref", required=True, help="Git ref (commit SHA, branch, or tag).")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    feature_path = Path(args.feature)
    if not feature_path.exists():
        print(f"error: feature file not found: {feature_path}", file=sys.stderr)
        return 2

    try:
        text = feature_path.read_text(encoding="utf-8")
        feature = validate_markdown(text, FeatureDefinition)
    except MarkdownValidationError as exc:
        print(f"error: failed to parse feature: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 — surface any parse error
        print(f"error: unexpected parse error: {exc}", file=sys.stderr)
        return 2

    source = CodebaseSource(repo_url=args.repo, ref=args.ref)

    try:
        final = asyncio.run(
            run_design_pipeline(feature_definition=feature, codebase_source=source)
        )
    except AgentFailedError as exc:
        print(f"error: designer failed: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        # bootstrap_fn wraps docker / git errors as RuntimeError with
        # descriptive messages.
        print(f"error: bootstrap failed: {exc}", file=sys.stderr)
        return 1

    # AgentFilePath verification guarantees designer_output when the
    # agent emits success, but print defensively and surface the
    # volume name so the user can inspect the workspace.
    if final.designer_output is not None:
        print(f"Design document: {final.designer_output.design_document}")
    if final.workspace_handle is not None:
        print(f"Workspace volume: {final.workspace_handle.volume_name}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
```

- [ ] **Step 4: Run test, confirm passes**

Run: `pdm run pytest tests/archipelago/scripts/test_run_design_pipeline_cli.py -xvs`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_design_pipeline.py tests/archipelago/scripts/__init__.py tests/archipelago/scripts/test_run_design_pipeline_cli.py
git commit -m "$(cat <<'EOF'
feat(scripts): add run_design_pipeline CLI

Wraps run_design_pipeline in try/except that distinguishes bootstrap
failure (RuntimeError) from designer failure (AgentFailedError) in
the error message; exits 1 for either. Input-parse errors exit 2.
Success prints the design document path and workspace volume name.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5.5: End-to-end integration test

**Files:**
- Create: `tests/archipelago/systems/test_design_pipeline_integration.py`

**Dependencies:** Task 5.4.

Full pipeline against real infrastructure. Skip-if gates: Docker, network, `ANTHROPIC_API_KEY`. Timeout via `pytest-timeout` (configured in Task 2.1) bounds the test process; the designer's internal timeout is declaration-only.

- [ ] **Step 1: Write test**

Create `tests/archipelago/systems/test_design_pipeline_integration.py`:

```python
"""Full end-to-end test: bootstrap → designer → design.md.

Marked `integration`; skipped when Docker, network, or claude-code
authentication is unavailable. Phase 2's completion criterion.
"""

from __future__ import annotations

import os
from pathlib import Path

import docker
import pytest
from archetype.markdown import validate_markdown

from archipelago.models import CodebaseSource, DesignDocument, FeatureDefinition
from archipelago.systems.design_pipeline import run_design_pipeline

pytestmark = pytest.mark.integration

REPO_URL = "https://github.com/730alchemy/agent-foundry.git"
REF = "main"


def _docker_available() -> bool:
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


def _claude_auth_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"))


@pytest.fixture
def docker_and_auth_client():
    if not _docker_available():
        pytest.skip("Docker daemon not reachable")
    if not _claude_auth_available():
        pytest.skip("ANTHROPIC_API_KEY / CLAUDE_CODE_OAUTH_TOKEN not set")
    return docker.from_env()


@pytest.fixture
def cleanup_volumes(docker_and_auth_client, archipelago_volume_registry):
    created: list[str] = []
    try:
        yield created
    finally:
        for name in created:
            archipelago_volume_registry.add(name)
            try:
                docker_and_auth_client.volumes.get(name).remove(force=True)
            except Exception:
                pass


class TestDesignPipelineEndToEnd:
    @pytest.mark.asyncio
    @pytest.mark.timeout(1800)
    async def test_given_run_observability_when_pipeline_then_design_document_produced(
        self, docker_and_auth_client, cleanup_volumes, repo_root: Path
    ):
        feature_text = (repo_root / "examples" / "features" / "run-observability.md").read_text(encoding="utf-8")
        feature = validate_markdown(feature_text, FeatureDefinition)
        source = CodebaseSource(repo_url=REPO_URL, ref=REF)

        final = await run_design_pipeline(
            feature_definition=feature,
            codebase_source=source,
        )
        assert final.workspace_handle is not None
        cleanup_volumes.append(final.workspace_handle.volume_name)
        assert final.designer_output is not None

        # Read the produced design.md out of the volume.
        design_text = docker_and_auth_client.containers.run(
            "alpine:3.20",
            command=["cat", final.designer_output.design_document],
            volumes={final.workspace_handle.volume_name: {"bind": "/workspace", "mode": "ro"}},
            remove=True,
        ).decode("utf-8", errors="replace")

        # Parseable as a DesignDocument.
        design = validate_markdown(design_text, DesignDocument)

        # Every section has non-trivial content.
        MIN_CHARS = 40
        for name, value in [
            ("summary", design.summary),
            ("current_state_context", design.current_state_context),
            ("components", design.components),
            ("architecture", design.architecture),
            ("acceptance_criteria", design.acceptance_criteria),
            ("test_strategy", design.test_strategy),
            ("risks_and_open_items", design.risks_and_open_items),
            ("resolved_assumptions", design.resolved_assumptions),
        ]:
            assert len(value.strip()) >= MIN_CHARS, (
                f"section {name!r} too short: {len(value)} chars"
            )

        assert "Run Observability" in design_text
```

- [ ] **Step 2: Run integration test**

Run: `pdm test-integration tests/archipelago/systems/test_design_pipeline_integration.py -xvs`
Expected on a fully provisioned host: `1 passed` (5–30 min; a real Designer runs).
Expected on a host without Docker / auth: `1 skipped`.

- [ ] **Step 3: Human review**

If the test passed, read the produced design by hand:

```bash
docker run --rm -v <volume>:/workspace alpine:3.20 cat /workspace/documents/design.md > /tmp/design.md
less /tmp/design.md
```

Evaluate subjectively: does the design respect the feature's scope boundaries, resolve every assumption, and propose something coherent? Note flaws for Phase 3 iteration.

- [ ] **Step 4: Commit**

```bash
git add tests/archipelago/systems/test_design_pipeline_integration.py
git commit -m "$(cat <<'EOF'
test(systems): add design-pipeline end-to-end integration test

Phase 2's completion criterion — full pipeline against agent-foundry's
main at archipelago-agent-worker:latest, produces a parseable
DesignDocument with all eight sections filled.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5.6: Public API for `archipelago.systems`

**Files:**
- Modify: `src/archipelago/systems/__init__.py`
- Create: `tests/archipelago/systems/test_public_api.py`

**Dependencies:** Tasks 5.1, 5.2, 5.3.

- [ ] **Step 1: Write failing test**

Create `tests/archipelago/systems/test_public_api.py`:

```python
"""Public API surface for archipelago.systems."""

from __future__ import annotations

import archipelago.systems as systems_pkg


class TestPublicAPI:
    def test_given_systems_package_when_imported_then_all_matches_expected(self):
        assert set(systems_pkg.__all__) == {
            "BASE_IMAGE_TAG",
            "DesignPipelineState",
            "design_pipeline",
            "generate_volume_name",
            "run_design_pipeline",
        }

    def test_given_all_names_when_accessed_then_importable(self):
        for name in systems_pkg.__all__:
            assert hasattr(systems_pkg, name)
```

- [ ] **Step 2: Run test, confirm fails**

Run: `pdm run pytest tests/archipelago/systems/test_public_api.py -xvs`
Expected: `AssertionError: set() != {...}`.

- [ ] **Step 3: Write implementation**

Replace `src/archipelago/systems/__init__.py`:

```python
"""Runnable Archipelago systems — compositions of primitives.

`design_pipeline` is the Phase 2 pipeline: workspace_bootstrap → designer.
Given a feature definition and a target codebase, it produces a design
document.
"""

from __future__ import annotations

from archipelago.systems.design_pipeline import (
    BASE_IMAGE_TAG,
    DesignPipelineState,
    design_pipeline,
    generate_volume_name,
    run_design_pipeline,
)

__all__ = [
    "BASE_IMAGE_TAG",
    "DesignPipelineState",
    "design_pipeline",
    "generate_volume_name",
    "run_design_pipeline",
]
```

- [ ] **Step 4: Run test, confirm passes**

Run: `pdm run pytest tests/archipelago/systems/ -xvs -m 'not integration'`
Expected: all Slice 5 unit tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/archipelago/systems/__init__.py tests/archipelago/systems/test_public_api.py
git commit -m "$(cat <<'EOF'
feat(systems): expose public API for archipelago.systems

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Slice 5 — Verification (Phase 2 completion)

- [ ] `pdm test-unit` green across all of archipelago.
- [ ] `pdm test-integration` green on a host with Docker + network + claude auth; skips cleanly otherwise.
- [ ] E2E integration test has run against real infrastructure at least once with a human-reviewed passing design doc.
- [ ] CLI exit codes: 0 on success, 1 on pipeline runtime failure (bootstrap or designer), 2 on input-parse / argument error.
- [ ] `pdm lint` / `pdm typecheck` green.

---

# Phase 2 Completion Checklist

When Slice 5 lands:

- [ ] Slices 2–5 all merged to `main`.
- [ ] `pdm test-all` green in archipelago.
- [ ] E2E integration test has run against real infrastructure at least once; the produced `design.md` was human-reviewed and is coherent.
- [ ] `temp/2026-04-21-cs7-plan4-phase2-slice{2,3,4,5}-*.md` draft plans are removed (superseded by this consolidated plan) — the user is handling this cleanup.
- [ ] Memory `project_review_feedback_loop.md` updated: Phase 2 complete; point at the next unit of work (Decomposer agent, Design-Critic experiment, or Phase 3 iteration).

---

# Out-of-Scope (Deferred Past Phase 2)

Per Phase 2 design §12:
- Decomposer (Cluster B) and Planner (Cluster C) agents.
- Reviewer, Integrator, Dispatcher agents.
- `CommitAction`, `SubmitPRAction` function actions.
- Design-Critic debate experiment.
- Instruction-appendix auto-generation.
- Semantic (LLM-checked) validation of produced documents.
- Workspace-volume cleanup automation (the session-scoped autouse fixture added in Task 2.1 removes test-created volumes; production cleanup is a future function action).
- **Bootstrap partial-failure orphan cleanup at the registry level.** `bootstrap_fn` now removes its own volume on post-create-volume failure, but if the Docker daemon itself fails mid-cleanup, a stray volume may persist. A future cleanup function action or admin script will sweep stale `archipelago-ws-*` volumes beyond what the per-run cleanup covers.
- **Non-interactive / CI clarification handling.** `StdinResponder` returns empty strings when stdin is a closed pipe (typical CI), consuming up to 20 responder turns before surfacing `AgentFailedError`. A `FailFastResponder` that raises immediately on any clarification/permission request is deferred; the 20-turn cap is a shared budget across clarifications and permissions.
- **Structural validation of produced `design.md`.** `AgentFilePath` verifies the file exists and is within the declared size bound, but does not parse the content as a `DesignDocument`. A zero-byte or structurally-empty design can pass verification and exit the pipeline with code 0. Structural validation is deferred to Phase 3.
- **Designer timeout enforcement.** `timeout_seconds=1800` on the primitive is a declaration; `run_primitive_plan` does not wrap the execution in `asyncio.wait_for`. A runaway Designer can run longer than 30 minutes. The pytest-timeout mark on the E2E test bounds the test process but not a production run. Enforcement lives in a future agent-foundry change.

---

# Self-Review Notes

This section records the self-review pass per `jig:plan` §Self-Review:

1. **Spec coverage.** Every item from Phase 2 design §§2, 4, 5, 6, 7, 8, 9 maps to a task in this plan. Design §7 shipped in Slice 1. Design §10 (first E2E feature) maps to Task 5.5.

2. **Placeholder scan.** No "TBD", "implement later", or "similar to Task N" phrases. Every code block is complete and runnable. The only content gaps are:
   - Task 3.8 — the integration test's `PINNED_SHA` is a literal `<resolved-sha-from-step-1>` placeholder deliberately marked for the implementer to fill in; Step 1 of that task instructs them how.

3. **Type consistency.** Cross-referenced across tasks: `WorkspaceHandle`, `BootstrapInput`, `BootstrapOutput`, `FeatureDefinition`, `CodebaseSource`, `DesignerInput`, `DesignerOutput`, `DesignPipelineState`, `design_pipeline`, `run_design_pipeline`, `BASE_IMAGE_TAG`, `generate_volume_name` — all used identically everywhere they appear.

4. **Dependency ordering.** Topology: Task 2.0 → 2.1 → Slice 2 body → { Slice 3 body, Slice 4 (with 4.1 depending on 3.1) } → Slice 5 → Phase 2 complete. No cycles. Cross-slice fixture sharing (`minimal_feature_definition`) is via a pytest fixture in `tests/archipelago/conftest.py` (created in Task 2.1), not a cross-test import.

5. **Command accuracy.** Test commands use `pdm run pytest` and `pdm test-unit` / `pdm test-integration`. `PYTHONPATH` is handled by pdm's script definitions; `pythonpath = ["src", "."]` is set explicitly in `pyproject.toml` in Task 2.1 so `tests.*` imports resolve.

**Known fragile points — verify at task time:**
- **`AgentAction` field names** (Task 4.4). The design doc uses `visible_dirs`, `writable_dirs`, `reuse_policy`, `timeout_seconds`, `skip_permissions`. Grep agent-foundry's `src/agent_foundry/primitives/models.py` for the current names and adjust test + implementation together if they differ.
- **`Sequence[I, O](steps=...)` parameterization** (Task 5.2). If the actual form differs, adjust the declaration and the `isinstance(design_pipeline, Sequence)` test.
- **`run_primitive_plan` signature** (Task 5.3 Step 1). Confirmed 2026-04-21: `(plan: PrimitivePlan, *, initial_state, artifacts_dir, workspace_volume, base_image_tag, responder_provider, run_id=None)`. Re-confirm at task time in case the signature has changed.
- **`BASE_IMAGE_TAG` value** (Task 5.1). Defaults to `agent-worker:latest`. Update if Phase 3's published tag differs.

**Addressed review-swarm findings.** This plan explicitly resolves the following blocking/major findings from the plan-review swarm run 2026-04-21:
- **Legacy `archipelago.models` shadow** → Task 2.0 deletes it up front (plan-logic-reviewer, blocking).
- **`tests/__init__.py` missing** → created in Task 2.1 (task-dependency, critical).
- **`run_primitive_plan` signature mismatch** → Task 5.3 wires all four required kwargs (blast-radius + state-completeness + task-dependency, blocking).
- **`workspace_volume` chicken-and-egg** → `run_design_pipeline` generates the name once and threads it into both the plan invocation and the `BootstrapInput` (blast-radius, blocking).
- **`run-observability.md` heading case** → resolved upstream: agent-foundry commit `dfb757f` added case-insensitive heading matching to the projector. Task 2.6 is now a straightforward round-trip (blast-radius + plan-logic-reviewer, blocking).
- **`clarification_needed` / `permission_needed` unhandled** → `run_design_pipeline` wires `StdinResponder`; the CLI's `try/except AgentFailedError` path covers terminal `failed` outcomes separately (state-completeness, major).
- **Bootstrap `.git/` chmod breaks git** → `chmod_tree_excluding_git` prunes `.git/`; Task 3.8 has a regression test that runs `git log -1` post-bootstrap (plan-logic, major).
- **`/workspace/documents/` unwritable** → `prepare_documents_dir` chmods it `0775` before the feature-def write; Task 3.8 verifies (plan-logic, major).
- **Task 4.1 hidden Slice-3 dep** → declared explicitly as "Task 3.1 merged" (task-dependency, major).
- **`pytest-timeout` + `asyncio_mode`** → both added in Task 2.1 (task-dependency, major).
- **Volume-name collision** → `time.time_ns()` suffix, sanitization of slug characters (migration-safety, major).
- **Docker image lazy-pull orphans** → `pull_image` runs before `create_volume` (migration-safety, major).
- **`cleanup_volumes` fixture on no-Docker host** → skip check inside `docker_client` fixture, `cleanup_volumes` depends on it (migration-safety, major).
- **Session-end volume safety net** → autouse session fixture in Task 2.1 (state-completeness, major).
- **Test 3.5 IndexError** → rewritten to extract `command` via `kwargs.get` (plan-logic, major).
- **Task 5.3 test kwargs vs args** → test now asserts on `call.kwargs["initial_state"]` (blast-radius, high).
- **Dead `designer_output is None` branch** → CLI's success-print path guards on both optional fields defensively; failure paths are explicit `except` clauses (state-completeness, minor).
- **`model_copy` deep-copy fragility** → not applicable in the revised plan; Task 3.6 no longer uses `model_copy` for test fixtures.

---

# Change Log

- **2026-04-21 (revision)** — Applied 11 fixes from the second plan-review swarm: Optional frontmatter annotations (Tasks 2.4, 2.5); CLI mock patches script-module binding (Task 5.4); Task 3.1 stub exports `WorkspaceHandle` early; `BASE_IMAGE_TAG = "agent-worker:latest"` (Task 5.1); `GIT_IMAGE = "alpine/git:v2.47.2"` (Task 3.2); `chmod_tree_excluding_git` rstrips trailing slashes (Task 3.4); `bootstrap_fn` cleans up its own volume on post-create failure (Task 3.6); session-scoped cleanup switched to opt-in registry (Task 2.1); Task 5.5 fixture renamed to `docker_and_auth_client`; `DesignerSlice` collapsed into `DesignerOutput` (Tasks 4.1, 4.4, 4.5); `ConfigDict(extra="ignore")` on boundary input types + new subset-invariant test (Tasks 3.1, 4.1, 5.1); new Out-of-Scope notes for bootstrap orphan-volume registry, CI clarification handling, and structural design.md validation.
- **2026-04-21** — Initial consolidated plan via `jig:plan`. Covers Phase 2 Slices 2–5. Renames the pipeline from `phase_2`/`run_phase2`/`Phase2State` to `design_pipeline`/`run_design_pipeline`/`DesignPipelineState` throughout. Incorporates fixes for all blocking and major findings from the 2026-04-21 plan-review swarm. Archetype commit `dfb757f` (case-insensitive heading matching) shipped in agent-foundry before this plan was finalized, removing the need for a heading-rename fallback in Task 2.6.
