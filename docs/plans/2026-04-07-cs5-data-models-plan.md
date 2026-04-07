# CS5: New and Modified Data Models — Implementation Plan

> **Design:** docs/plans/2026-04-03-review-feedback-loop-design.md
> **Roadmap:** docs/plans/2026-04-03-review-feedback-loop-roadmap.md
> **Scope:** Archipelago repo. Broader than the roadmap's original CS5 — absorbs transition cleanup that was originally deferred to CS11.

**Goal:** Install the new data models for the review feedback loop (`ChangeSetStep`, `ReviewFinding`, new `ImplementationTask`, `DispatchedFinding`, new `DispatcherOutput`, `IntegratorOutput`), restructure `ChangeSet` and `JobSpecification`, and remove the dead code that no longer compiles or has no transition value.

**Context — why the scope is broader than the roadmap:**

The Archipelago package is already non-functional as a runtime:
- `runner.py` imports `agent_foundry.compiler.compiler.run_plan` and `agent_foundry.planner.wiring_plan.GraphWiringPlan` — both modules were **deleted in agent-foundry CS3**. `runner.py` doesn't import successfully.
- `cli.py` depends on `runner.py` → also broken.
- Five test files (`test_archipelago_checkpoint.py`, `test_archipelago_e2e.py`, `test_archipelago_pipeline_plan.py`, `test_docker_worker_e2e.py`, `tests/integration/test_config_to_lockdown.py`) import from the deleted `agent_foundry.compiler`/`agent_foundry.planner` modules → all broken.
- `archipelago_system.json` is the old JSON pipeline-plan format; CS9 will replace it with a Python `System` definition built from primitives.
- `models_v0.1.py` is a parallel snapshot with zero imports.

Since there is no user of Archipelago and no backward-compatibility requirement, CS5 removes this dead code wholesale. The decomposer/dispatcher/evaluator agents (identified as having no transition value) are removed with their role YAMLs and tests. The code_writer / unit_test_writer / software_reviewer agents are kept verbatim as transition references — they still compile because they depend only on `CurrentTask`, `CodeReview*`, and `AgentWorkerResult`, all of which remain in `models.py`.

**Compliance with Data Model Conventions:** All models added or modified by CS5 follow the rules in `CLAUDE.md § Data Model Conventions`. Those conventions (StrEnum for routing keys, free `str` for informational labels, tagged discriminated unions, no `Literal` for enumerated values, agent boundaries use JSON schema injection) were drafted and committed during CS5 planning and are the authoritative reference.

**Guiding decisions (confirmed):**

- **Single `models.py`** — no `models_v2.py`. New models are added alongside kept models; removed models are deleted outright.
- **`ChangeSet` restructured in place** — new fields replace old fields. Docker worker's dependency on the old shape is quarantined via a local `WorkerCommitSpec` model in `docker_worker/models.py`.
- **`ReviewFinding.category`** — free `str` with a suggested taxonomy in the field description. Category is an informational/audit field only — nothing downstream pattern-matches on it. The Dispatcher routes by semantic fit (LLM judgment on description/suggested_resolution against change set intent), the Planner reads the finding text when handling fix cycles, and the post-job report and human escalation UIs just display the label. A closed `Literal` would add retry cost at the agent boundary with zero downstream benefit.
- **`ReviewFinding.severity`** — `Severity(StrEnum)` with members `MUST_FIX = "must_fix"` and `CAN_DEFER = "can_defer"`. Unlike category, severity **is** a routing key: `must_fix` drives the review-fix cycle, `can_defer` drives the post-PR Dispatcher path. The design doc's control flow branches on it explicitly, so strict typing is load-bearing. `StrEnum` (chosen over `Literal`) gives upstream Python code an importable, refactor-safe symbol (`Severity.MUST_FIX`) and avoids string duplication at every call site; Pydantic serializes members to plain JSON strings, so the agent boundary still works via JSON schema injection (see "Agent Boundary Sync" below). Agents receive `"enum": ["must_fix", "can_defer"]` in the prompt schema and Pyright exhaustiveness still works in `match` statements.
- **`DispatchedFinding.disposition`** — `Disposition(StrEnum)` with members `ROUTE_TO_CHANGE_SET`, `DEFER_TO_POST_JOB`, `ESCALATE`. Same reasoning as severity: disposition is a routing key consumed by the Integrator (`routed_findings`), the post-job report writer (`deferred_findings`), and human escalation (`escalations`). `StrEnum` gives the Dispatcher agent handler, the Integrator's scheduling code, and the post-job report writer a single importable taxonomy.
- **Discriminator tags on `StepOrigin` / `FindingOrigin`** — `OriginKind(StrEnum)` with members `STEP = "step"` and `FINDING = "finding"`. Each wrapper class defaults its `kind` field to its specific enum member (`kind: OriginKind = OriginKind.STEP` on `StepOrigin`, etc.). Pydantic 2.x supports `StrEnum`-typed discriminator fields; if the pinned Pydantic version does not, fall back to `kind: Literal[OriginKind.STEP] = OriginKind.STEP` form, which still gives us the importable symbol. The uniform StrEnum policy keeps CS5's model layer free of hardcoded string literals everywhere a value belongs to a known set — no "why is this one different?" questions for future readers.
- **Uniform StrEnum policy (no Literals)** — every field whose values come from a known, finite set is a `StrEnum`. Open text stays as `str`. The CS5 model layer has zero hardcoded string literals for enumerated values.
- **`ImplementationTask.origin`** — discriminated union via tagged wrapper types (`StepOrigin`, `FindingOrigin`) that carry an `OriginKind`-typed `kind` field, with Pydantic `Field(discriminator="kind")` for unambiguous parsing. See the `OriginKind` bullet above for the discriminator-field typing choice.
- **`ChangeSetStep.acceptance_criteria_addressed`** — `list[str]` holding copies of the parent criterion text. Simple, self-contained, no cross-reference ID scheme.
- **Kept agents untouched** — `code_writer.py`, `unit_test_writer.py`, `software_reviewer.py` and their entries in `io_models.py` are not modified by CS5. Their tests (`test_code_writer.py`, `test_unit_test_writer.py`, `test_software_reviewer.py`) are not modified by CS5.
- **Kept docker-worker code untouched except for the ChangeSet quarantine** — `docker_worker/*` otherwise stays intact.

**Tech Stack:** Python 3.14, Pydantic >=2.12.5, pytest

---

## File Structure

All paths relative to `/home/markn/engineering/jig-archipelago/archipelago/`.

### Delete

| File | Reason |
|------|--------|
| `src/archipelago/models_v0.1.py` | Orphaned — zero imports anywhere in the repo |
| `src/archipelago/runner.py` | Broken imports (deleted agent-foundry modules); will be rebuilt in CS10 |
| `src/archipelago/cli.py` | Depends on broken `runner.py`; will be rebuilt in CS10 |
| `src/archipelago/__main__.py` | Depends on `cli.py`; will be rebuilt in CS10 |
| `src/archipelago/archipelago_system.json` | Old JSON pipeline format; CS9 replaces with Python `System` definition |
| `src/archipelago/agents/decomposer.py` | No transition value |
| `src/archipelago/agents/dispatcher.py` | No transition value |
| `src/archipelago/agents/evaluator.py` | No transition value |
| `src/archipelago/roles/decompose_job_specification.yaml` | Role for deleted agent |
| `src/archipelago/roles/dispatch_commit.yaml` | Role for deleted agent |
| `src/archipelago/roles/evaluate_commit.yaml` | Role for deleted agent |
| `tests/archipelago/unit/test_archipelago_checkpoint.py` | Imports from deleted agent-foundry modules |
| `tests/archipelago/unit/test_archipelago_e2e.py` | Imports from deleted agent-foundry modules |
| `tests/archipelago/unit/test_archipelago_pipeline_plan.py` | Imports from deleted agent-foundry modules |
| `tests/archipelago/unit/test_docker_worker_e2e.py` | Imports from deleted agent-foundry modules |
| `tests/archipelago/integration/test_config_to_lockdown.py` | Imports from deleted agent-foundry modules |
| `tests/archipelago/unit/test_runner.py` | Tests the deleted runner |
| `tests/archipelago/unit/test_cli.py` | Tests the deleted cli |

### Modify

| File | Change |
|------|--------|
| `src/archipelago/models.py` | Remove `Step`, `UnitTestUpdates`, old `ImplementationTask`, `KernelState`. Restructure `ChangeSet`. Add `test_paths` to `JobSpecification`. Add `Severity` (StrEnum), `Disposition` (StrEnum), `OriginKind` (StrEnum), `ChangeSetStep`, `ReviewFinding`, `StepOrigin`, `FindingOrigin`, `TaskOrigin`, new `ImplementationTask`, `DispatchedFinding`, `DispatcherOutput`, `IntegratorOutput`. Add `from enum import StrEnum` and `from typing import Annotated` to imports |
| `src/archipelago/agents/io_models.py` | Remove `DecomposerOutput`, old `DispatcherOutput`, `EvaluatorOutput`. Drop corresponding imports from `archipelago.models` (specifically `CurrentTask` stays because `UnitTestWriterOutput`/`CodeWriterOutput`/`SoftwareReviewerOutput` do not use it — only the deleted `DispatcherOutput` did) |
| `src/archipelago/docker_worker/models.py` | Add `WorkerCommitSpec` (local copy of the old `ChangeSet` shape). Change `WorkerInput.commit_spec: ChangeSet` → `WorkerInput.commit_spec: WorkerCommitSpec`. Drop `from archipelago.models import ChangeSet` |
| `tests/archipelago/unit/test_archipelago_models.py` | Remove test classes for deleted models (`Step`, `UnitTestUpdates`, old `ImplementationTask`, `KernelState`). Update `ChangeSet` tests for the new shape. Update `JobSpecification` tests for `test_paths`. Add test classes for all six new models |
| `tests/archipelago/unit/test_io_models.py` | Remove tests for `DecomposerOutput`, old `DispatcherOutput`, `EvaluatorOutput` |
| `tests/archipelago/unit/test_docker_worker_models.py` | Update `WorkerInput` tests to construct `WorkerCommitSpec` instead of `ChangeSet` |

### Create

None. All new models land inside the existing `models.py`.

---

## Task Ordering

Deletes come first to reduce noise and avoid churn in files that will be torn out anyway. Additive TDD tasks come last, in dependency order.

1. **Task 1** — Delete dead runtime code (`runner.py`, `cli.py`, `__main__.py`, `archipelago_system.json`, `models_v0.1.py`, and their tests)
2. **Task 2** — Delete unused agents and their role YAMLs, io_models entries, and test references
3. **Task 3** — Delete removed models from `models.py` and their test classes
4. **Task 4** — Quarantine `WorkerCommitSpec` inside `docker_worker/models.py` (decouples docker_worker from `ChangeSet` before we restructure it)
5. **Task 5** — Restructure `ChangeSet` and add `JobSpecification.test_paths` (TDD)
6. **Task 6** — Add `ChangeSetStep` and `ReviewFinding` (TDD, leaf models)
7. **Task 7** — Add new `ImplementationTask` (TDD, depends on Task 6)
8. **Task 8** — Add `DispatchedFinding` and new `DispatcherOutput` (TDD, depends on Task 6)
9. **Task 9** — Add `IntegratorOutput` (TDD, depends on Task 6)
10. **Task 10** — Full suite, lint, format, final verification

One commit per task. Each task leaves the tree green (`pdm test-unit` passes, `pdm run lint` clean) before the commit lands.

---

### Task 1: Delete Dead Runtime Code

**Files:**
- Delete: `src/archipelago/runner.py`
- Delete: `src/archipelago/cli.py`
- Delete: `src/archipelago/__main__.py`
- Delete: `src/archipelago/archipelago_system.json`
- Delete: `src/archipelago/models_v0.1.py`
- Delete: `tests/archipelago/unit/test_runner.py`
- Delete: `tests/archipelago/unit/test_cli.py`
- Delete: `tests/archipelago/unit/test_archipelago_checkpoint.py`
- Delete: `tests/archipelago/unit/test_archipelago_e2e.py`
- Delete: `tests/archipelago/unit/test_archipelago_pipeline_plan.py`
- Delete: `tests/archipelago/unit/test_docker_worker_e2e.py`
- Delete: `tests/archipelago/integration/test_config_to_lockdown.py`
- Modify: `pyproject.toml` (if it has a `[project.scripts]` entry pointing to `archipelago.__main__` or `archipelago.cli`, remove it)

**Dependencies:** None

- [ ] **Step 1: Verify impact**
  - Grep the repo for any remaining imports of `archipelago.runner`, `archipelago.cli`, or `archipelago.__main__` outside the deletion list. There should be none. If there are, add them to the deletion list or flag them in the task.
  - Grep the repo for any imports of `archipelago.models_v0` — should be none (confirmed during planning).
  - Confirm no test depends on `archipelago_system.json` as a data fixture.

- [ ] **Step 2: Delete files**

- [ ] **Step 3: Remove entry points**
  - Check `pyproject.toml` for `[project.scripts]` entries referencing `archipelago.__main__:main`, `archipelago.cli:main`, or similar. Remove them.

- [ ] **Step 4: Run full suite**
  - Run: `pdm test-unit`
  - Expected: all remaining tests pass (the previously-broken tests are gone; the kept tests don't depend on deleted modules).
  - Run: `pdm run lint`
  - Expected: clean. If there are lint errors from orphaned imports elsewhere, fix them.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
chore: delete dead runtime code (runner, cli, system.json, v0.1 models, broken tests)

These files already fail to import after agent-foundry CS3 deleted the
old GraphWiringPlan compiler and planner modules. The runtime will be
rebuilt in CS10 on top of the primitive compiler. models_v0.1.py is an
orphaned snapshot with zero imports.

Part of CS5 (review feedback loop data models).
EOF
)"
```

---

### Task 2: Delete Unused Agents and Supporting Artifacts

**Files:**
- Delete: `src/archipelago/agents/decomposer.py`
- Delete: `src/archipelago/agents/dispatcher.py`
- Delete: `src/archipelago/agents/evaluator.py`
- Delete: `src/archipelago/roles/decompose_job_specification.yaml`
- Delete: `src/archipelago/roles/dispatch_commit.yaml`
- Delete: `src/archipelago/roles/evaluate_commit.yaml`
- Modify: `src/archipelago/agents/io_models.py` — remove `DecomposerOutput`, old `DispatcherOutput`, `EvaluatorOutput`, plus any now-unused imports
- Modify: `tests/archipelago/unit/test_io_models.py` — remove test classes for the three deleted output models

**Dependencies:** Task 1 (keeps repo clean; no hard dependency)

**Note on `agents/io_models.py` imports:** after deleting the three output classes, check whether `CurrentTask` is still used by the remaining output models (`UnitTestWriterOutput`, `CodeWriterOutput`, `SoftwareReviewerOutput`, `EvaluatorOutput` ← being deleted, `DecomposerOutput` ← being deleted, `DispatcherOutput` ← being deleted). Based on current content, only the deleted `DispatcherOutput` imports `CurrentTask`. After deletion, remove `CurrentTask` from the `from archipelago.models import AgentWorkerResult, CurrentTask` line. Keep `AgentWorkerResult`.

- [ ] **Step 1: Delete files**
  - Delete the three agent files, the three YAML role files.

- [ ] **Step 2: Prune `io_models.py`**
  - Remove `DecomposerOutput`, `DispatcherOutput`, `EvaluatorOutput` classes.
  - Update `from archipelago.models import AgentWorkerResult, CurrentTask` → `from archipelago.models import AgentWorkerResult` (confirm `CurrentTask` has no remaining use in this file).
  - Remove any unused imports from `archipelago.types` that were only used by the deleted classes.

- [ ] **Step 3: Prune `test_io_models.py`**
  - Remove any test classes / imports for `DecomposerOutput`, `DispatcherOutput`, `EvaluatorOutput`.

- [ ] **Step 4: Verify no dangling references**
  - Grep for `DecomposerOutput`, `DispatcherOutput`, `EvaluatorOutput`, `from archipelago.agents.decomposer`, `from archipelago.agents.dispatcher`, `from archipelago.agents.evaluator`. All hits should be inside deleted files or already gone. If any remain in source, they likely belong to the deletion set and should be addressed.
  - If `src/archipelago/agents/__init__.py` re-exports any of these, remove the exports.

- [ ] **Step 5: Run full suite**
  - Run: `pdm test-unit`
  - Expected: pass.
  - Run: `pdm run lint`
  - Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
chore: delete decomposer, dispatcher, evaluator agents and their role specs

These agents have no transition value — the new pipeline (CS7+) uses a
different agent architecture (Planner, Reviewer, new Dispatcher,
Integrator). Removing them now unblocks the ChangeSet restructuring and
data model work in CS5.

code_writer, unit_test_writer, and software_reviewer remain in place as
transition references for the new agent implementations.

Part of CS5 (review feedback loop data models).
EOF
)"
```

---

### Task 3: Delete Removed Models from `models.py`

**Files:**
- Modify: `src/archipelago/models.py` — delete `Step`, `UnitTestUpdates`, old `ImplementationTask`, `KernelState`
- Modify: `tests/archipelago/unit/test_archipelago_models.py` — delete test classes for the four removed models and drop them from imports

**Dependencies:** Tasks 1–2 (removed references to the deleted agents first)

- [ ] **Step 1: Delete model classes**
  - In `models.py`, delete `Step`, `UnitTestUpdates`, `ImplementationTask` (old), `KernelState`. Leave `FeatureDefinition`, `JobSpecification`, `ChangeSet` (will be restructured in Task 5), `CurrentTask`, `TestResults`, `AgentWorkerResult`, and all `CodeReview*` classes intact.

- [ ] **Step 2: Update test file**
  - In `test_archipelago_models.py`, drop `KernelState`, `Step`, `UnitTestUpdates`, old `ImplementationTask` from the imports at the top of the file.
  - Delete test classes / test functions that exercise those four models (`TestKernelState`, any class that asserts on `ImplementationTask.unit_test_changes`, etc.).

- [ ] **Step 3: Verify no dangling references**
  - Grep for `KernelState`, `UnitTestUpdates`, `\bStep\b`, `ImplementationTask` under `src/` and `tests/`.
  - `ImplementationTask` hits in `docs/`, `models.py` (being deleted), and `test_archipelago_models.py` (being updated) are expected. No live source should still reference the old version.
  - `Step` is a common word — use word-boundary grep and visually filter to confirm only comments/docs remain.

- [ ] **Step 4: Run full suite**
  - Run: `pdm test-unit`
  - Expected: pass.
  - Run: `pdm run lint`
  - Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/archipelago/models.py tests/archipelago/unit/test_archipelago_models.py
git commit -m "$(cat <<'EOF'
refactor(models): remove Step, UnitTestUpdates, old ImplementationTask, KernelState

These models are replaced by the review feedback loop design:
- Step → ChangeSetStep (added in a later task)
- old ImplementationTask → new ImplementationTask with origin/interface_specifications
- KernelState → replaced by the primitive compiler's derived state types
- UnitTestUpdates → collapsed into ImplementationTask.unit_test_changes as list[str]

ChangeSet restructuring and new model additions come in subsequent tasks.

Part of CS5 (review feedback loop data models).
EOF
)"
```

---

### Task 4: Quarantine `WorkerCommitSpec` in `docker_worker/models.py`

**Files:**
- Modify: `src/archipelago/docker_worker/models.py`
- Modify: `tests/archipelago/unit/test_docker_worker_models.py` (if it constructs `WorkerInput.commit_spec` from a `ChangeSet`)

**Dependencies:** Task 3

**Rationale:** docker_worker currently reads the old `ChangeSet` fields (`title`, `acceptance_criteria`, `test_focus`, `implementation_focus`). Task 5 restructures `ChangeSet` into an incompatible new shape. Before that destructive change, we decouple docker_worker by giving it its own local copy of the fields it needs. This also reflects the reality that docker_worker's future is TBD — it should not block model work upstream.

- [ ] **Step 1: Write a failing test for `WorkerCommitSpec`**

In `tests/archipelago/unit/test_docker_worker_models.py`, add (or adapt an existing test) to construct `WorkerInput` using a `WorkerCommitSpec` instance with the four old-shape fields. The test should fail because `WorkerCommitSpec` does not yet exist.

```python
def test_given_worker_input_with_commit_spec_when_constructed_then_fields_roundtrip(self):
    spec = WorkerCommitSpec(
        title="Add models",
        acceptance_criteria=["Model exists"],
        test_focus="unit tests",
        implementation_focus="Pydantic models",
    )
    wi = WorkerInput(
        commit_spec=spec,
        repo_ref="main",
        constraints=WorkerConstraints(),
    )
    assert wi.commit_spec.title == "Add models"
    assert wi.commit_spec.acceptance_criteria == ["Model exists"]
```

- [ ] **Step 2: Run the test — confirm red**
  - `pdm test-unit -- tests/archipelago/unit/test_docker_worker_models.py`
  - Expected: ImportError or NameError on `WorkerCommitSpec`.

- [ ] **Step 3: Add `WorkerCommitSpec` and switch `WorkerInput`**

In `docker_worker/models.py`:
- Add a new `WorkerCommitSpec(BaseModel)` class with fields `title: str`, `acceptance_criteria: list[str] = Field(default_factory=list)`, `test_focus: str = ""`, `implementation_focus: str = ""`. Match the docstring and field descriptions of the old `ChangeSet` so the semantics are preserved.
- Change `WorkerInput.commit_spec: ChangeSet` → `WorkerInput.commit_spec: WorkerCommitSpec`.
- Remove `from archipelago.models import ChangeSet`. (If `ChangeSet` was only used here, the import disappears.)

- [ ] **Step 4: Run the test — confirm green**
  - `pdm test-unit -- tests/archipelago/unit/test_docker_worker_models.py`
  - Expected: pass.

- [ ] **Step 5: Run full suite**
  - `pdm test-unit`
  - Expected: pass.
  - `pdm run lint`
  - Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/archipelago/docker_worker/models.py tests/archipelago/unit/test_docker_worker_models.py
git commit -m "$(cat <<'EOF'
refactor(docker_worker): quarantine WorkerCommitSpec local to docker_worker

docker_worker reads the old ChangeSet shape (title, acceptance_criteria,
test_focus, implementation_focus). CS5 restructures ChangeSet into an
incompatible new shape. Moving these fields into a local
WorkerCommitSpec model decouples docker_worker from the top-level
ChangeSet so the restructure can proceed without touching docker_worker
internals. docker_worker's future is still TBD.

Part of CS5 (review feedback loop data models).
EOF
)"
```

---

### Task 5: Restructure `ChangeSet`, Add `JobSpecification.test_paths` (TDD)

**Files:**
- Modify: `src/archipelago/models.py`
- Modify: `tests/archipelago/unit/test_archipelago_models.py`

**Dependencies:** Task 4 (docker_worker no longer depends on `ChangeSet`)

**New `ChangeSet` shape:**
```python
class ChangeSet(BaseModel):
    name: str = Field(description="Short title — used as the PR title")
    intent: str = Field(description="Purpose and motivation for this change set")
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Success conditions for this change set",
    )
    interface_specifications: list[str] | None = Field(
        default=None,
        description="Contracts (signatures, data shapes) this change set introduces or modifies",
    )
    steps: list[ChangeSetStep] = Field(
        default_factory=list,
        description="Ordered list of change set steps — populated before execution",
    )
```

Note: `steps` references `ChangeSetStep`, which is added in Task 6. To keep this task self-contained, define `steps: list[ChangeSetStep]` using a forward reference string and call `ChangeSet.model_rebuild()` after `ChangeSetStep` is defined in Task 6. **Alternative (simpler):** temporarily type `steps: list[Any] = Field(default_factory=list)` in Task 5, and tighten to `list[ChangeSetStep]` in Task 6 when the type exists. **Use the alternative** — it keeps each task's diff focused and avoids forward-reference gymnastics.

**Note on Pyright strictness during the transition:** `list[Any]` is weakly typed and Pyright in `strict` mode will flag it. Before implementing Task 5, check `pyproject.toml` for Pyright's configured strictness level:
- If Pyright is in `basic` mode (or not configured), `list[Any]` passes without complaint. Proceed as planned.
- If Pyright is in `strict` mode, `list[Any]` will fail the lint gate when Task 5 is committed alone (before Task 6 tightens it). In that case, either (a) add a targeted `# pyright: ignore[reportGeneralTypeIssues]` comment on the `steps` line with a `# Tightened in Task 6` hint, OR (b) promote `ChangeSetStep` into Task 5 so `steps: list[ChangeSetStep]` is typed from the start. Option (b) is preferred because it's cleaner; option (a) preserves the intended task boundary if you want to keep Task 5 narrow.

The `list[Any]` → `list[ChangeSetStep]` tightening in Task 6 is intentional and reviewable regardless of which approach Task 5 takes.

**New `JobSpecification` field:**
```python
test_paths: list[str] = Field(
    default_factory=list,
    description="Directories containing test code (for write-permission enforcement). "
                "Will move to a repo-level Archipelago config in a future version.",
)
```

- [ ] **Step 1: Write the failing tests**

Replace existing `TestChangeSet` and update `TestJobSpecification` in `test_archipelago_models.py`:

```python
class TestChangeSet:
    def test_given_minimum_fields_when_instantiated_then_defaults_applied(self):
        cs = ChangeSet(name="Add data models", intent="Install new review loop types")
        assert cs.name == "Add data models"
        assert cs.intent == "Install new review loop types"
        assert cs.acceptance_criteria == []
        assert cs.interface_specifications is None
        assert cs.steps == []

    def test_given_all_fields_when_json_round_tripped_then_no_field_loss(self):
        cs = ChangeSet(
            name="Add data models",
            intent="Install new review loop types",
            acceptance_criteria=["Models exist", "Tests pass"],
            interface_specifications=["ImplementationTask.origin is a tagged union"],
            steps=[],
        )
        reconstructed = ChangeSet.model_validate_json(cs.model_dump_json())
        assert reconstructed == cs

    def test_given_missing_name_when_instantiated_then_validation_error(self):
        with pytest.raises(ValidationError):
            ChangeSet(intent="no name")

    def test_given_missing_intent_when_instantiated_then_validation_error(self):
        with pytest.raises(ValidationError):
            ChangeSet(name="no intent")


class TestJobSpecification:
    def test_given_valid_job_when_instantiated_then_test_paths_defaults_empty(self):
        job = JobSpecification(
            objective="Add auth",
            repo_url="https://github.com/org/repo",
            change_sets=[{"name": "Add models", "intent": "install types"}],
        )
        assert job.test_paths == []

    def test_given_test_paths_when_instantiated_then_stored(self):
        job = JobSpecification(
            objective="Add auth",
            repo_url="https://github.com/org/repo",
            test_paths=["tests/", "src/archipelago/tests/"],
            change_sets=[{"name": "Add models", "intent": "install types"}],
        )
        assert job.test_paths == ["tests/", "src/archipelago/tests/"]

    def test_given_job_with_changes_when_round_tripped_then_no_field_loss(self):
        job = JobSpecification(
            objective="Add auth",
            repo_url="https://github.com/org/repo",
            repo_ref="main",
            constraints=["no new deps"],
            test_paths=["tests/"],
            change_sets=[
                {"name": "Add models", "intent": "install types"},
                {"name": "Wire runner", "intent": "build the executor"},
            ],
        )
        reconstructed = JobSpecification.model_validate_json(job.model_dump_json())
        assert reconstructed == job
```

- [ ] **Step 2: Run the tests — confirm red**
  - `pdm test-unit -- tests/archipelago/unit/test_archipelago_models.py::TestChangeSet tests/archipelago/unit/test_archipelago_models.py::TestJobSpecification`
  - Expected: failures on the new fields.

- [ ] **Step 3: Restructure `ChangeSet` in `models.py`**
  - Delete the old `ChangeSet` class body.
  - Add the new `ChangeSet` with `name`, `intent`, `acceptance_criteria`, `interface_specifications`, and `steps: list[Any] = Field(default_factory=list)` (temporary — tightened in Task 6).
  - The type annotation order in the file: `ChangeSet` must be declared before `JobSpecification` uses it. The existing forward reference style in `models.py` handles this.

- [ ] **Step 4: Add `test_paths` to `JobSpecification`**
  - Add `test_paths: list[str] = Field(default_factory=list, description=...)` to `JobSpecification`. Keep all existing fields.

- [ ] **Step 5: Run the tests — confirm green**
  - `pdm test-unit -- tests/archipelago/unit/test_archipelago_models.py`
  - Expected: pass.

- [ ] **Step 6: Run full suite**
  - `pdm test-unit`
  - Expected: pass.
  - `pdm run lint`
  - Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add src/archipelago/models.py tests/archipelago/unit/test_archipelago_models.py
git commit -m "$(cat <<'EOF'
feat(models): restructure ChangeSet, add JobSpecification.test_paths

ChangeSet new shape: name (PR title), intent, acceptance_criteria,
interface_specifications (optional), steps (typed loosely until
ChangeSetStep lands). Old fields (title, test_focus, implementation_focus)
are removed — docker_worker already quarantined its copy in Task 4.

JobSpecification.test_paths carries the test directory list used for
write-permission enforcement by the Implementer agent (CS8).

Part of CS5 (review feedback loop data models).
EOF
)"
```

---

### Task 6: Add `ChangeSetStep` and `ReviewFinding` (TDD)

**Files:**
- Modify: `src/archipelago/models.py`
- Modify: `tests/archipelago/unit/test_archipelago_models.py`

**Dependencies:** Task 5

**Model definitions:**

```python
class ChangeSetStep(BaseModel):
    """An atomic unit of work inside a ChangeSet."""

    description: str = Field(description="What to do in this step")
    acceptance_criteria_addressed: list[str] = Field(
        default_factory=list,
        description="Copies of the parent ChangeSet acceptance criteria this step addresses",
    )


class Severity(StrEnum):
    """Review finding severity — drives review-fix cycle routing."""

    MUST_FIX = "must_fix"
    CAN_DEFER = "can_defer"


class ReviewFinding(BaseModel):
    """A single finding produced by the Reviewer agent."""

    description: str = Field(description="What the issue is")
    severity: Severity = Field(
        description="must_fix = blocks merge and enters the review-fix cycle; "
                    "can_defer = routed post-PR by the Dispatcher",
    )
    category: str = Field(
        description="Short category label for the finding. Prefer one of: "
                    "design_quality, code_quality, test_complexity, naming. "
                    "Use a different label only if none of these fit.",
    )
    affected_files_and_locations: list[str] = Field(
        default_factory=list,
        description="Where in the code the finding applies (file:line or file:symbol)",
    )
    suggested_resolution: str = Field(
        default="",
        description="What the Reviewer proposes changing to resolve the finding",
    )
    source_commit_hashes: list[str] = Field(
        default_factory=list,
        description="Commits that introduced the issue",
    )
```

After adding `ChangeSetStep`, tighten the `ChangeSet.steps` annotation from `list[Any]` to `list[ChangeSetStep]`.

- [ ] **Step 1: Write failing tests**

```python
class TestChangeSetStep:
    def test_given_description_only_when_instantiated_then_defaults_applied(self):
        step = ChangeSetStep(description="Add the ReviewFinding model")
        assert step.description == "Add the ReviewFinding model"
        assert step.acceptance_criteria_addressed == []

    def test_given_all_fields_when_round_tripped_then_no_field_loss(self):
        step = ChangeSetStep(
            description="Add the ReviewFinding model",
            acceptance_criteria_addressed=["New models exist", "Tests pass"],
        )
        assert ChangeSetStep.model_validate_json(step.model_dump_json()) == step


class TestReviewFinding:
    def test_given_enum_severity_when_instantiated_then_fields_stored(self):
        finding = ReviewFinding(
            description="Function name is ambiguous",
            severity=Severity.CAN_DEFER,
            category="naming",
        )
        assert finding.severity is Severity.CAN_DEFER
        assert finding.category == "naming"
        assert finding.affected_files_and_locations == []
        assert finding.suggested_resolution == ""
        assert finding.source_commit_hashes == []

    def test_given_string_severity_when_instantiated_then_coerced_to_enum(self):
        # Agent output arrives as JSON strings — Pydantic must coerce.
        finding = ReviewFinding(
            description="Function returns wrong type",
            severity="must_fix",
            category="code_quality",
        )
        assert finding.severity is Severity.MUST_FIX

    def test_given_invalid_severity_when_instantiated_then_validation_error(self):
        with pytest.raises(ValidationError):
            ReviewFinding(
                description="x",
                severity="critical",  # not a Severity member
                category="code_quality",
            )

    def test_given_nonstandard_category_when_instantiated_then_accepted(self):
        # category is a free str — the Reviewer can invent labels if needed
        finding = ReviewFinding(
            description="x",
            severity=Severity.CAN_DEFER,
            category="accessibility",
        )
        assert finding.category == "accessibility"

    def test_given_severity_when_dumped_to_json_then_serializes_as_string(self):
        finding = ReviewFinding(
            description="x",
            severity=Severity.MUST_FIX,
            category="code_quality",
        )
        dumped = finding.model_dump_json()
        assert '"severity":"must_fix"' in dumped

    def test_given_all_fields_when_round_tripped_then_no_field_loss(self):
        finding = ReviewFinding(
            description="Function name is ambiguous",
            severity=Severity.CAN_DEFER,
            category="naming",
            affected_files_and_locations=["src/foo.py:42"],
            suggested_resolution="Rename `process` to `compile_primitive`",
            source_commit_hashes=["abc123"],
        )
        assert ReviewFinding.model_validate_json(finding.model_dump_json()) == finding


class TestChangeSetStepsTightening:
    def test_given_change_set_with_steps_when_instantiated_then_steps_typed(self):
        step = ChangeSetStep(description="Add models")
        cs = ChangeSet(name="CS5", intent="data models", steps=[step])
        assert isinstance(cs.steps[0], ChangeSetStep)

    def test_given_change_set_with_dict_step_when_instantiated_then_coerced(self):
        cs = ChangeSet(
            name="CS5",
            intent="data models",
            steps=[{"description": "Add models"}],
        )
        assert isinstance(cs.steps[0], ChangeSetStep)
        assert cs.steps[0].description == "Add models"
```

- [ ] **Step 2: Run the tests — confirm red**

- [ ] **Step 3: Add `ChangeSetStep`, `Severity`, and `ReviewFinding` to `models.py`**
  - Add `from enum import StrEnum` to imports.
  - Declare `ChangeSetStep` before `ChangeSet` so the tightened annotation resolves.
  - Declare `Severity(StrEnum)` and `ReviewFinding` near `ChangeSetStep` (they are siblings in the domain).
  - Tighten `ChangeSet.steps: list[Any]` → `list[ChangeSetStep]`.
  - Update `test_archipelago_models.py` imports to include `ChangeSetStep`, `Severity`, `ReviewFinding`.

- [ ] **Step 4: Run the tests — confirm green**

- [ ] **Step 5: Full suite + lint**

- [ ] **Step 6: Commit**

```bash
git add src/archipelago/models.py tests/archipelago/unit/test_archipelago_models.py
git commit -m "$(cat <<'EOF'
feat(models): add ChangeSetStep and ReviewFinding

ChangeSetStep is the unit of work the Planner consumes (forward-looking)
and the Integrator inserts/modifies (backward-looking). Its
acceptance_criteria_addressed field holds text copies of parent criteria
rather than ID references — simple and self-contained.

ReviewFinding is the Reviewer output unit. severity is a Severity
StrEnum (MUST_FIX, CAN_DEFER) — a routing key consumed by the
review-fix cycle and the post-PR Dispatcher path. StrEnum (over
Literal) gives upstream Python code an importable, refactor-safe
symbol while Pydantic still serializes to plain JSON strings at the
agent boundary. category is a free str with suggested taxonomy in
the field description — nothing downstream pattern-matches on it.

ChangeSet.steps is now tightened from list[Any] to list[ChangeSetStep].

Part of CS5 (review feedback loop data models).
EOF
)"
```

---

### Task 7: Add New `ImplementationTask` with Discriminated `origin` (TDD)

**Files:**
- Modify: `src/archipelago/models.py`
- Modify: `tests/archipelago/unit/test_archipelago_models.py`

**Dependencies:** Task 6

**Model definitions (discriminated union via tagged wrappers):**

```python
from enum import StrEnum
from typing import Annotated
from pydantic import Field


class OriginKind(StrEnum):
    """Tag identifying which origin variant wraps an ImplementationTask source."""

    STEP = "step"
    FINDING = "finding"


class StepOrigin(BaseModel):
    kind: OriginKind = OriginKind.STEP
    step: ChangeSetStep


class FindingOrigin(BaseModel):
    kind: OriginKind = OriginKind.FINDING
    finding: ReviewFinding


TaskOrigin = Annotated[
    StepOrigin | FindingOrigin,
    Field(discriminator="kind"),
]


class ImplementationTask(BaseModel):
    """Planner output — the unit of work consumed by the Test Agent and Implementer."""

    origin: TaskOrigin = Field(description="Either a ChangeSetStep or a ReviewFinding")
    interface_specifications: list[str] = Field(
        default_factory=list,
        description="Function signatures, data shapes, contracts introduced or modified",
    )
    unit_test_changes: list[str] = Field(
        default_factory=list,
        description="Test behaviors to add or remove, each mapped to an acceptance criterion",
    )
    implementation_change: str = Field(
        description="Behavioral description of the software change needed",
    )
```

Notes:
- The old `ImplementationTask` was deleted in Task 3. This task introduces the new one with the same name — no coexistence conflict.
- **Pydantic version check**: before writing code, verify that the pinned Pydantic 2.x accepts a `StrEnum`-typed discriminator field (`kind: OriginKind = OriginKind.STEP`). Quick way: write a scratch file with the definitions above and call `ImplementationTask.model_validate({"origin": {"kind": "step", "step": {"description": "x"}}, "implementation_change": "y"})`. If it parses without error, proceed. If Pydantic complains that the discriminator field must be a single-value `Literal`, fall back to `kind: Literal[OriginKind.STEP] = OriginKind.STEP` on each wrapper (keeps the importable symbol; restores the single-value Literal Pydantic wants). Record the outcome in the commit message so future maintainers know which path we took.

- [ ] **Step 1: Write failing tests**

```python
class TestImplementationTask:
    def test_given_step_origin_when_instantiated_then_origin_is_step(self):
        task = ImplementationTask(
            origin=StepOrigin(step=ChangeSetStep(description="Add models")),
            implementation_change="Add pydantic classes to models.py",
        )
        assert task.origin.kind is OriginKind.STEP
        assert task.origin.step.description == "Add models"

    def test_given_finding_origin_when_instantiated_then_origin_is_finding(self):
        finding = ReviewFinding(
            description="Ambiguous name",
            severity=Severity.MUST_FIX,
            category="naming",
        )
        task = ImplementationTask(
            origin=FindingOrigin(finding=finding),
            implementation_change="Rename `process` to `compile_primitive`",
        )
        assert task.origin.kind is OriginKind.FINDING
        assert task.origin.finding.severity is Severity.MUST_FIX

    def test_given_dict_with_kind_step_when_parsed_then_discriminated_to_step(self):
        data = {
            "origin": {"kind": "step", "step": {"description": "Add models"}},
            "implementation_change": "Add pydantic classes",
        }
        task = ImplementationTask.model_validate(data)
        assert isinstance(task.origin, StepOrigin)

    def test_given_dict_with_kind_finding_when_parsed_then_discriminated_to_finding(self):
        data = {
            "origin": {
                "kind": "finding",
                "finding": {
                    "description": "x",
                    "severity": "must_fix",
                    "category": "naming",
                },
            },
            "implementation_change": "y",
        }
        task = ImplementationTask.model_validate(data)
        assert isinstance(task.origin, FindingOrigin)

    def test_given_missing_kind_discriminator_when_parsed_then_validation_error(self):
        data = {
            "origin": {"step": {"description": "Add models"}},  # no kind
            "implementation_change": "x",
        }
        with pytest.raises(ValidationError):
            ImplementationTask.model_validate(data)

    def test_given_all_fields_when_round_tripped_then_no_field_loss(self):
        task = ImplementationTask(
            origin=StepOrigin(
                step=ChangeSetStep(
                    description="Add models",
                    acceptance_criteria_addressed=["Models exist"],
                )
            ),
            interface_specifications=["ReviewFinding(BaseModel)"],
            unit_test_changes=["add: construction sets defaults"],
            implementation_change="Create pydantic classes",
        )
        assert ImplementationTask.model_validate_json(task.model_dump_json()) == task
```

- [ ] **Step 2: Run the tests — confirm red**

- [ ] **Step 3: Implement in `models.py`**
  - Add `OriginKind(StrEnum)` with `STEP` and `FINDING` members.
  - Add `StepOrigin`, `FindingOrigin`, `TaskOrigin`, new `ImplementationTask`. Place them after `ChangeSetStep` and `ReviewFinding`.
  - Import additions: `Annotated` from `typing` (if not already present). `StrEnum` was already imported in Task 6. Use `StepOrigin | FindingOrigin` (PEP 604) rather than `typing.Union` — Python 3.14 idiom.
  - Update `test_archipelago_models.py` imports to include `OriginKind`, `StepOrigin`, `FindingOrigin`, `ImplementationTask`.

- [ ] **Step 4: Run the tests — confirm green**

- [ ] **Step 5: Full suite + lint**

- [ ] **Step 6: Commit**

```bash
git add src/archipelago/models.py tests/archipelago/unit/test_archipelago_models.py
git commit -m "$(cat <<'EOF'
feat(models): add ImplementationTask, OriginKind, discriminated origin union

origin is a tagged union over StepOrigin (from Change Set Steps,
forward-looking) and FindingOrigin (from Review Findings, backward-looking
fixes). The discriminator is a kind field typed as OriginKind (StrEnum
with STEP and FINDING members), resolved by Pydantic's discriminator
Field option.

[Note to author: if the pinned Pydantic version rejected a plain StrEnum
discriminator and you fell back to Literal[OriginKind.STEP] on each
wrapper, mention it here for future maintainers.]

interface_specifications and unit_test_changes are both list[str] to keep
the boundary simple — agents write natural-language descriptions rather
than structured sub-schemas.

Part of CS5 (review feedback loop data models).
EOF
)"
```

---

### Task 8: Add `DispatchedFinding` and New `DispatcherOutput` (TDD)

**Files:**
- Modify: `src/archipelago/models.py`
- Modify: `tests/archipelago/unit/test_archipelago_models.py`

**Dependencies:** Task 6 (`ReviewFinding` exists)

**Model definitions:**

```python
class Disposition(StrEnum):
    """Dispatcher routing decision for a single review finding."""

    ROUTE_TO_CHANGE_SET = "route_to_change_set"
    DEFER_TO_POST_JOB = "defer_to_post_job"
    ESCALATE = "escalate"


class DispatchedFinding(BaseModel):
    """A routing decision for a single review finding."""

    finding: ReviewFinding
    disposition: Disposition
    target_change_set_name: str | None = Field(
        default=None,
        description="Target change set when disposition is ROUTE_TO_CHANGE_SET",
    )
    rationale: str = Field(description="Why the Dispatcher chose this routing")


class DispatcherOutput(BaseModel):
    """Categorized output from the Dispatcher agent."""

    routed_findings: list[DispatchedFinding] = Field(
        default_factory=list,
        description="Findings routed to specific change sets",
    )
    deferred_findings: list[DispatchedFinding] = Field(
        default_factory=list,
        description="Findings deferred to the post-job report",
    )
    escalations: list[DispatchedFinding] = Field(
        default_factory=list,
        description="Findings requiring human routing decisions",
    )
```

Note: the old `DispatcherOutput` lived in `agents/io_models.py` and was deleted in Task 2. The new `DispatcherOutput` lives in `models.py` alongside the other domain types.

- [ ] **Step 1: Write failing tests**

```python
class TestDispatchedFinding:
    def test_given_route_disposition_when_instantiated_then_target_stored(self):
        df = DispatchedFinding(
            finding=ReviewFinding(
                description="x",
                severity=Severity.CAN_DEFER,
                category="code_quality",
            ),
            disposition=Disposition.ROUTE_TO_CHANGE_SET,
            target_change_set_name="Cleanup Pass",
            rationale="Touches the same subsystem",
        )
        assert df.disposition is Disposition.ROUTE_TO_CHANGE_SET
        assert df.target_change_set_name == "Cleanup Pass"

    def test_given_string_disposition_when_instantiated_then_coerced_to_enum(self):
        df = DispatchedFinding(
            finding=ReviewFinding(
                description="x",
                severity=Severity.CAN_DEFER,
                category="code_quality",
            ),
            disposition="defer_to_post_job",
            rationale="Out of scope",
        )
        assert df.disposition is Disposition.DEFER_TO_POST_JOB
        assert df.target_change_set_name is None

    def test_given_invalid_disposition_when_instantiated_then_validation_error(self):
        with pytest.raises(ValidationError):
            DispatchedFinding(
                finding=ReviewFinding(
                    description="x",
                    severity=Severity.CAN_DEFER,
                    category="code_quality",
                ),
                disposition="ignore",
                rationale="nope",
            )


class TestDispatcherOutput:
    def test_given_empty_when_instantiated_then_all_lists_empty(self):
        out = DispatcherOutput()
        assert out.routed_findings == []
        assert out.deferred_findings == []
        assert out.escalations == []

    def test_given_mixed_dispositions_when_round_tripped_then_no_field_loss(self):
        finding = ReviewFinding(
            description="x",
            severity=Severity.CAN_DEFER,
            category="code_quality",
        )
        out = DispatcherOutput(
            routed_findings=[
                DispatchedFinding(
                    finding=finding,
                    disposition=Disposition.ROUTE_TO_CHANGE_SET,
                    target_change_set_name="CS7",
                    rationale="fits",
                )
            ],
            deferred_findings=[
                DispatchedFinding(
                    finding=finding,
                    disposition=Disposition.DEFER_TO_POST_JOB,
                    rationale="out of scope",
                )
            ],
            escalations=[
                DispatchedFinding(
                    finding=finding,
                    disposition=Disposition.ESCALATE,
                    rationale="ambiguous",
                )
            ],
        )
        assert DispatcherOutput.model_validate_json(out.model_dump_json()) == out
```

- [ ] **Step 2: Run the tests — confirm red**

- [ ] **Step 3: Implement in `models.py`**
  - Add `Disposition(StrEnum)` with `ROUTE_TO_CHANGE_SET`, `DEFER_TO_POST_JOB`, `ESCALATE` members.
  - Add `DispatchedFinding` and `DispatcherOutput`. Place them after `ImplementationTask` and its supporting types.
  - Update `test_archipelago_models.py` imports to include `Disposition`, `DispatchedFinding`, `DispatcherOutput`.

- [ ] **Step 4: Run the tests — confirm green**

- [ ] **Step 5: Full suite + lint**

- [ ] **Step 6: Commit**

```bash
git add src/archipelago/models.py tests/archipelago/unit/test_archipelago_models.py
git commit -m "$(cat <<'EOF'
feat(models): add DispatchedFinding, DispatcherOutput, Disposition enum

DispatchedFinding wraps a single Review Finding with a routing
Disposition (StrEnum: ROUTE_TO_CHANGE_SET, DEFER_TO_POST_JOB, ESCALATE).
Disposition is a routing key — the Integrator consumes routed_findings,
the post-job report writer consumes deferred_findings, and human
escalation UIs consume escalations. StrEnum (over Literal) gives each
consumer an importable, refactor-safe symbol with no string duplication.

DispatcherOutput groups findings into three buckets by disposition.

target_change_set_name is optional — only populated when disposition is
ROUTE_TO_CHANGE_SET. The plan doesn't enforce this pairing at the type
level; validation happens at the Dispatcher agent boundary in CS7.

Part of CS5 (review feedback loop data models).
EOF
)"
```

---

### Task 9: Add `IntegratorOutput` (TDD)

**Files:**
- Modify: `src/archipelago/models.py`
- Modify: `tests/archipelago/unit/test_archipelago_models.py`

**Dependencies:** Task 6 (`ChangeSetStep` exists)

**Model definition:**

```python
class IntegratorOutput(BaseModel):
    """Revised step sequence for a change set after Integrator processing."""

    target_change_set_name: str = Field(description="Which change set was revised")
    revised_steps: list[ChangeSetStep] = Field(
        description="Updated ordered list of Change Set Steps",
    )
    changes_made: list[str] = Field(
        default_factory=list,
        description="Natural-language descriptions of what was inserted, modified, "
                    "reordered, or removed, and why",
    )
```

- [ ] **Step 1: Write failing tests**

```python
class TestIntegratorOutput:
    def test_given_required_fields_when_instantiated_then_changes_made_defaults_empty(self):
        out = IntegratorOutput(
            target_change_set_name="CS7",
            revised_steps=[ChangeSetStep(description="Add a new interface")],
        )
        assert out.target_change_set_name == "CS7"
        assert len(out.revised_steps) == 1
        assert out.changes_made == []

    def test_given_missing_target_when_instantiated_then_validation_error(self):
        with pytest.raises(ValidationError):
            IntegratorOutput(revised_steps=[])

    def test_given_all_fields_when_round_tripped_then_no_field_loss(self):
        out = IntegratorOutput(
            target_change_set_name="CS7",
            revised_steps=[
                ChangeSetStep(description="Add interface A"),
                ChangeSetStep(description="Add interface B"),
            ],
            changes_made=[
                "Inserted step for interface A ahead of existing implementation step",
                "Reworded step 3 to reference new naming",
            ],
        )
        assert IntegratorOutput.model_validate_json(out.model_dump_json()) == out
```

- [ ] **Step 2: Run the tests — confirm red**

- [ ] **Step 3: Implement in `models.py`**
  - Add `IntegratorOutput` after `DispatcherOutput`.
  - Update `test_archipelago_models.py` imports to include `IntegratorOutput`.

- [ ] **Step 4: Run the tests — confirm green**

- [ ] **Step 5: Full suite + lint**

- [ ] **Step 6: Commit**

```bash
git add src/archipelago/models.py tests/archipelago/unit/test_archipelago_models.py
git commit -m "$(cat <<'EOF'
feat(models): add IntegratorOutput

IntegratorOutput is the Integrator agent's output — a revised
ChangeSetStep sequence for a single target change set, plus a
natural-language log of what was inserted, modified, reordered, or
removed. The Integrator handles backward-looking step integration (new
findings into existing plans) while the Planner handles forward-looking
step execution, per the design doc's cohesive-objectives principle.

Part of CS5 (review feedback loop data models).
EOF
)"
```

---

### Task 10: Final Verification

**Files:** None (verification only)

**Dependencies:** Tasks 1–9

- [ ] **Step 1: Full test suite**
  - `pdm test-unit`
  - Expected: all pass.

- [ ] **Step 2: Lint and format**
  - `pdm run lint`
  - Expected: clean.

- [ ] **Step 3: Grep for dangling references**
  - Search source + tests for any lingering reference to deleted symbols: `KernelState`, `UnitTestUpdates`, `DecomposerOutput`, `EvaluatorOutput`, old `DispatcherOutput` in `agents/io_models.py`, `run_archipelago`, `load_archipelago_plan`, `GraphWiringPlan`. Only hits should be in docs.

- [ ] **Step 4: Inventory new public types**
  - Confirm `models.py` exports (via `from archipelago.models import ...`): `FeatureDefinition`, `JobSpecification`, `ChangeSet`, `ChangeSetStep`, `Severity`, `ReviewFinding`, `OriginKind`, `StepOrigin`, `FindingOrigin`, `TaskOrigin`, `ImplementationTask`, `Disposition`, `DispatchedFinding`, `DispatcherOutput`, `IntegratorOutput`, `CurrentTask`, `TestResults`, `AgentWorkerResult`, all `CodeReview*`.
  - Grep `src/archipelago/models.py` for `Literal[` — the only acceptable hit (if any) is the fallback `Literal[OriginKind.STEP] = OriginKind.STEP` form on the discriminator tags, and only if the Pydantic version check in Task 7 required that fallback. Otherwise CS5's model layer should contain zero `Literal` usages.

- [ ] **Step 5: Update memory**
  - Update `project_review_feedback_loop.md` status from "Design approved, high-level implementation roadmap written. No code yet." to reflect CS5 completion.

No commit needed for this task — it is a verification gate only.

---

## Verification Checklist

- [ ] `pdm test-unit` passes with all Task 1 deletions applied
- [ ] `pdm test-unit` passes after each TDD task
- [ ] `pdm run lint` clean at the end
- [ ] No source file imports from `agent_foundry.compiler.compiler`, `agent_foundry.planner.wiring_plan`, or `agent_foundry.registry.registry`
- [ ] No source file references `KernelState`, `UnitTestUpdates`, `DecomposerOutput`, old `DispatcherOutput` shape, `EvaluatorOutput`
- [ ] `docker_worker/models.py` does not import `ChangeSet`
- [ ] All new domain models (`ChangeSetStep`, `ReviewFinding`, `ImplementationTask`, `DispatchedFinding`, `DispatcherOutput`, `IntegratorOutput`), supporting enums (`Severity`, `Disposition`, `OriginKind`), union wrappers (`StepOrigin`, `FindingOrigin`, `TaskOrigin`), the restructured `ChangeSet`, and the extended `JobSpecification` are importable from `archipelago.models`
- [ ] All models comply with the Data Model Conventions in `CLAUDE.md` (StrEnum for routing keys, free `str` for informational labels, discriminated unions via tagged wrappers, no `Literal[...]` for enumerated values except the narrow Pydantic discriminator fallback)
- [ ] `docs/plans/2026-04-03-review-feedback-loop-roadmap.md` CS5 section is still accurate, or has been updated to note the broadened scope

---

## Agent Boundary Sync — Note for CS6/CS7

CS5 defines `severity: Severity` and `disposition: Disposition` as `StrEnum` types because downstream control flow branches on them. Upstream Python code (the review-fix cycle controller, the Dispatcher's filter logic, the Integrator's routing, test fixtures) imports the enum and references members directly — `Severity.MUST_FIX`, `Disposition.ROUTE_TO_CHANGE_SET` — so there's no hardcoded string duplication and rename refactors are single-source. But the Reviewer and Dispatcher agents themselves are LLM subprocesses producing JSON — they don't import Python symbols, they write string values. For the agents to know the valid values without hand-written prompt enumeration, the role handler should inject the Pydantic model's JSON schema into the agent prompt at invocation time:

```python
# Sketch — lands in CS6/CS7, not CS5
schema = ReviewerOutput.model_json_schema()
prompt = f"""
{role_instructions}

Write your output as JSON matching this schema:
```json
{json.dumps(schema, indent=2)}
```
"""
```

Pydantic emits `"severity": {"type": "string", "enum": ["must_fix", "can_defer"]}` automatically — StrEnum serializes to its string values in schemas and JSON output alike. This keeps the enum definition as the single source of truth: when a member is added or renamed, the schema changes, the prompt changes, the agent adapts on the next run. No hand-sync, no drift. Pydantic accepts both the enum member (from Python callers) and the raw string (from LLM agent JSON) when parsing, so both sides of the boundary work without translation code.

**Applies to every `StrEnum` (and any `Literal`) field on agent output models.** When CS6 designs `ReviewerOutput`, `NewDispatcherOutput`, `PlannerOutput`, etc., the role handlers they land in CS7 must use schema injection rather than hand-written prompt enumeration.

---

## Deferred to Later Change Sets

- **CS6**: Agent output models for new agents (`PlannerOutput`, `ReviewerOutput`, etc.) and role YAML specs
- **CS7**: New agent implementations (Planner, Reviewer, new Dispatcher, Integrator, Commit, SubmitPR)
- **CS8**: Evolve kept agents (Test Agent from UnitTestWriter, Implementer from CodeWriter)
- **CS9**: Python `System` definition replacing `archipelago_system.json`
- **CS10**: New runner and CLI on top of `run_primitive_plan`
- **CS11**: Remaining cleanup (remove kept transition-reference agents and models once their replacements are proven)
- **CS12**: Integration tests using `MockClaudeCodeAdapter` (CS4)
- **CS4**: Deferred until CS12 needs it
