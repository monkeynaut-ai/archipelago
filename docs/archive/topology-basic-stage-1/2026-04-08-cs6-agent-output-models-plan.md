# CS6: Agent Payload Models and Role Specs Implementation Plan

> **Design:** docs/plans/stage1/2026-04-03-review-feedback-loop-design.md
> **Roadmap:** docs/plans/stage1/2026-04-03-review-feedback-loop-roadmap.md (CS6 section)
> **Related:** docs/plans/stage1/2026-04-08-cs6.5-structured-output-protocol-plan.md (the protocol machinery that consumes these types)
> **Issue:** 730alchemy/archipelago#1
> **For agents:** Use team-dev (parallel) or sdd (sequential) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define the agent-facing domain payload type for the Reviewer agent and register the four new agent role specs (Planner, Reviewer, Dispatcher, Integrator) so CS6.5 can inject their schemas via `--json-schema` and CS7 can implement the agent handlers against stable names.

**Architecture:** Under the CS6.5 structured-output design, each agent's "output" is the typed payload the LLM emits via Claude Code's `--json-schema` — nothing more. Execution metadata (exit code, Docker volume, captured stderr) lives in the adapter layer (`TurnResult`) and the runner state, not in per-agent wrapper models. Three of the four new agents already have suitable payload types from CS5 (`ImplementationTask`, `DispatcherOutput`, `IntegratorOutput`). Only the Reviewer needs a new thin wrapper (`ReviewerPayload`) because the Reviewer emits multiple findings in one turn and the envelope's payload `T` must be a single BaseModel. The role spec YAMLs declare the four new agent handlers by name for the registry; their `module`/`class_name` references point at CS7 work and will be dangling at CS6 merge time — that is expected and acceptable because role specs are lazy-loaded.

**Tech Stack:** Python 3.14, Pydantic v2, PDM, pytest, PyYAML.

---

## Scope Guardrails

**In scope:**
- One new Pydantic payload type in `src/archipelago/models.py`: `ReviewerPayload`.
- Four new role spec YAMLs under `src/archipelago/roles/`: `plan_implementation_task`, `review_change_set`, `dispatch_findings`, `integrate_findings`.
- A small test harness in `tests/archipelago/unit/test_archipelago_role_specs.py` that parses each role spec file and asserts structural schema.

**Out of scope — do NOT touch in CS6:**
- **Do not create any agent class** (e.g. `Planner`, `Reviewer`, `FindingDispatcher`, `Integrator`). These are CS7 work. The role spec `module`/`class_name` references will be dangling at commit time; that is fine because role specs are lazy-loaded.
- **Do not add any "agent wrapper" types** that bundle `worker_result` / `workspace_volume` with a domain payload. The old pattern in `agents/io_models.py` (`CodeWriterOutput`, `UnitTestWriterOutput`, `SoftwareReviewerOutput`) is legacy — CS8 rewrites those agent handlers and CS11 deletes the wrappers. CS6 does not add more of them.
- **Do not touch `agents/io_models.py`.** Everything new goes in `models.py` alongside the other domain types from CS5.
- **Do not invoke or depend on anything from CS6.5** (`turn_outcome.py`, `schema_tools.py`, `build_outcome_schema`). CS6 ships the types; CS6.5 ships the machinery that injects them into `--json-schema`.

---

## Conversation design decisions (load-bearing context)

Locked in during the CS6/CS6.5 planning session. Do not re-litigate:

1. **LLM-facing types are pure domain payloads.** Execution metadata (`worker_result`, `workspace_volume`, exit code, session IDs) is adapter/runner concern, never in the type passed to `build_outcome_schema(...)`.
2. **Planner's payload is `ImplementationTask`** (from CS5 — already in `models.py`). No `PlannerOutput` wrapper.
3. **Reviewer's payload is `ReviewerPayload { findings: list[ReviewFinding] }`** — the only new type CS6 adds. The thin wrapper exists because Pydantic and `--json-schema` require a top-level object, not a bare list.
4. **Dispatcher's payload is `DispatcherOutput`** (from CS5). No new wrapper.
5. **Integrator's payload is `IntegratorOutput`** (from CS5). No new wrapper.
6. **CommitAction and SubmitPRAction are deterministic `FunctionAction` primitives**, not agents. They do not use `--json-schema` and do not need output model types in CS6. CS7 will decide their function signatures directly.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/archipelago/models.py` | Modify | Add `ReviewerPayload` next to `ReviewFinding` |
| `tests/archipelago/unit/test_archipelago_models.py` | Modify | Add construction + schema tests for `ReviewerPayload` |
| `src/archipelago/roles/plan_implementation_task.yaml` | Create | Role spec for the Planner agent |
| `src/archipelago/roles/review_change_set.yaml` | Create | Role spec for the Reviewer agent |
| `src/archipelago/roles/dispatch_findings.yaml` | Create | Role spec for the Dispatcher agent |
| `src/archipelago/roles/integrate_findings.yaml` | Create | Role spec for the Integrator agent |
| `tests/archipelago/unit/test_archipelago_role_specs.py` | Create | Parse each role YAML with PyYAML, assert required keys |

---

## Task 1: `ReviewerPayload` payload type

**Files:**
- Modify: `src/archipelago/models.py`
- Modify: `tests/archipelago/unit/test_archipelago_models.py`

**Dependencies:** none

**Background:** The Reviewer agent emits multiple findings per turn. The envelope `AgentTurnEnvelope[T]` (CS6.5) requires `T` to be a single BaseModel, not a bare `list[...]`. `ReviewerPayload` is a one-field wrapper that satisfies that constraint and gives CS7's handler a stable type to inject as the Reviewer's schema target.

- [ ] **Step 1: Write the failing tests**

  Append to `tests/archipelago/unit/test_archipelago_models.py` (after `TestImplementationTask`, before `TestChangeSetStepsTightening`). First extend the import block at the top of the file to add `ReviewerPayload`:

  ```python
  from archipelago.models import (
      ChangeSet,
      ChangeSetStep,
      # ...existing imports...
      ReviewerPayload,
      ReviewFinding,
      Severity,
      # ...
  )
  ```

  Then add:

  ```python
  class TestReviewerPayload:
      def test_given_empty_when_constructed_then_findings_defaults_to_empty_list(self):
          payload = ReviewerPayload()
          assert payload.findings == []

      def test_given_findings_when_constructed_then_preserved(self):
          findings = [
              ReviewFinding(
                  description="Missing input validation",
                  severity=Severity.MUST_FIX,
                  category="design_quality",
              ),
              ReviewFinding(
                  description="Ambiguous function name",
                  severity=Severity.CAN_DEFER,
                  category="naming",
              ),
          ]
          payload = ReviewerPayload(findings=findings)
          assert payload.findings == findings

      def test_given_instance_when_round_tripped_then_equals(self):
          findings = [
              ReviewFinding(
                  description="x",
                  severity=Severity.MUST_FIX,
                  category="code_quality",
              ),
          ]
          payload = ReviewerPayload(findings=findings)
          assert ReviewerPayload.model_validate_json(payload.model_dump_json()) == payload

      def test_given_payload_when_schema_generated_then_findings_is_array_property(self):
          schema = ReviewerPayload.model_json_schema()
          assert schema["type"] == "object"
          assert "findings" in schema["properties"]
          assert schema["properties"]["findings"]["type"] == "array"
  ```

  **Rationale for the kept tests:** construction smoke + round-trip + schema shape. The schema test is load-bearing — CS7 will inject this schema via CS6.5's `build_outcome_schema(ReviewerPayload)` and a drift here silently breaks the Reviewer agent boundary.

- [ ] **Step 2: Run tests to verify they fail**

  Run: `cd /home/markn/engineering/jig-archipelago/archipelago && pdm run pytest tests/archipelago/unit/test_archipelago_models.py::TestReviewerPayload -x`
  Expected: FAIL with `ImportError: cannot import name 'ReviewerPayload' from 'archipelago.models'`

- [ ] **Step 3: Write the implementation**

  Edit `src/archipelago/models.py`. Add the class immediately after `ReviewFinding` (currently lines 100-124):

  ```python
  class ReviewerPayload(BaseModel):
      """Reviewer agent's structured-output payload.

      Thin wrapper around a list of ReviewFindings. Exists because the
      ``--json-schema`` enforcement path (CS6.5) and Pydantic's
      ``model_json_schema`` both require a top-level object, not a bare
      list. Used by CS7's Reviewer handler as the ``T`` in
      ``AgentTurnEnvelope[T]``.
      """

      findings: list[ReviewFinding] = Field(
          default_factory=list,
          description=(
              "All review findings produced in this review pass — must_fix and "
              "can_defer together. Severity is carried on each finding; the Runner "
              "filters/branches downstream, so the Reviewer does not pre-split them."
          ),
      )
  ```

- [ ] **Step 4: Run tests to verify they pass**

  Run: `cd /home/markn/engineering/jig-archipelago/archipelago && pdm run pytest tests/archipelago/unit/test_archipelago_models.py::TestReviewerPayload -x`
  Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

  ```bash
  cd /home/markn/engineering/jig-archipelago/archipelago
  git add src/archipelago/models.py tests/archipelago/unit/test_archipelago_models.py
  git commit -m "feat(models): add ReviewerPayload wrapper for reviewer agent structured output

  Thin wrapper around list[ReviewFinding]; exists because --json-schema and
  Pydantic both require a top-level object. CS7's Reviewer handler will use
  this as T in AgentTurnEnvelope[T].

  Refs 730alchemy/archipelago#1"
  ```

---

## Task 2: Role spec test harness + `plan_implementation_task` role spec

**Files:**
- Create: `tests/archipelago/unit/test_archipelago_role_specs.py`
- Create: `src/archipelago/roles/plan_implementation_task.yaml`

**Dependencies:** none

**Why bundled:** The first role spec is bundled with the test harness to keep the TDD cycle tight. Subsequent role specs (Tasks 3-5) only append one test method each; they reuse the harness defined here.

- [ ] **Step 1: Write the failing tests**

  Create `tests/archipelago/unit/test_archipelago_role_specs.py`:

  ```python
  """Role spec YAML files — structural validation.

  These tests parse each role spec file directly with PyYAML and assert the
  required schema keys are present with sane values. They do not load the
  Archipelago registry (which lazy-imports agent modules that may not exist
  yet during the CS6 → CS7 transition).
  """

  from pathlib import Path

  import yaml

  ROLES_DIR = (
      Path(__file__).resolve().parents[3] / "src" / "archipelago" / "roles"
  )

  REQUIRED_TOP_LEVEL_KEYS = {
      "name",
      "description",
      "version",
      "implementation",
      "tags",
      "quality_controls",
  }
  REQUIRED_IMPLEMENTATION_KEYS = {"module", "class_name"}
  REQUIRED_QC_KEYS = {"timeout_seconds", "max_retries"}


  def _load(name: str) -> dict:
      path = ROLES_DIR / name
      assert path.is_file(), f"Role spec not found: {path}"
      with path.open() as f:
          return yaml.safe_load(f)


  def _assert_schema(
      spec: dict,
      *,
      expected_name: str,
      expected_module: str,
      expected_class: str,
  ) -> None:
      assert REQUIRED_TOP_LEVEL_KEYS.issubset(spec.keys()), (
          f"Missing top-level keys: {REQUIRED_TOP_LEVEL_KEYS - spec.keys()}"
      )
      assert spec["name"] == expected_name
      assert isinstance(spec["description"], str) and spec["description"]
      assert isinstance(spec["version"], str) and spec["version"]
      impl = spec["implementation"]
      assert REQUIRED_IMPLEMENTATION_KEYS.issubset(impl.keys())
      assert impl["module"] == expected_module
      assert impl["class_name"] == expected_class
      assert isinstance(spec["tags"], list) and len(spec["tags"]) > 0
      qc = spec["quality_controls"]
      assert REQUIRED_QC_KEYS.issubset(qc.keys())
      assert isinstance(qc["timeout_seconds"], int) and qc["timeout_seconds"] > 0
      assert isinstance(qc["max_retries"], int) and qc["max_retries"] >= 0


  class TestExistingSoftwareReviewSpec:
      """Sanity check the harness against an already-present role spec."""

      def test_given_software_review_yaml_when_loaded_then_matches_schema(self):
          spec = _load("software_review.yaml")
          _assert_schema(
              spec,
              expected_name="software_review",
              expected_module="archipelago.agents.software_reviewer",
              expected_class="SoftwareReviewer",
          )


  class TestPlanImplementationTaskSpec:
      def test_given_plan_implementation_task_yaml_when_loaded_then_matches_schema(self):
          spec = _load("plan_implementation_task.yaml")
          _assert_schema(
              spec,
              expected_name="plan_implementation_task",
              expected_module="archipelago.agents.planner",
              expected_class="Planner",
          )
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run: `cd /home/markn/engineering/jig-archipelago/archipelago && pdm run pytest tests/archipelago/unit/test_archipelago_role_specs.py -x`
  Expected: FAIL — `TestExistingSoftwareReviewSpec` passes (it checks the existing file), but `TestPlanImplementationTaskSpec` fails with `AssertionError: Role spec not found: .../plan_implementation_task.yaml`.

- [ ] **Step 3: Create the role spec file**

  Create `src/archipelago/roles/plan_implementation_task.yaml`:

  ```yaml
  name: plan_implementation_task
  description: Synthesizes an ImplementationTask from a ChangeSetStep or ReviewFinding using Claude Code in an ephemeral Docker container
  version: "1.0.0"
  implementation:
    module: archipelago.agents.planner
    class_name: Planner
  tags:
    - archipelago
    - docker-worker
    - planning
  quality_controls:
    timeout_seconds: 3600
    max_retries: 1
  ```

- [ ] **Step 4: Run tests to verify they pass**

  Run: `cd /home/markn/engineering/jig-archipelago/archipelago && pdm run pytest tests/archipelago/unit/test_archipelago_role_specs.py -x`
  Expected: PASS (2 tests — existing and new)

- [ ] **Step 5: Commit**

  ```bash
  cd /home/markn/engineering/jig-archipelago/archipelago
  git add tests/archipelago/unit/test_archipelago_role_specs.py src/archipelago/roles/plan_implementation_task.yaml
  git commit -m "feat(roles): add plan_implementation_task role spec and YAML test harness

  Harness parses each role YAML with PyYAML and asserts structural schema.
  Role spec references archipelago.agents.planner.Planner, which CS7 will
  create; the dangling reference is safe because role specs are lazy-loaded.

  Refs 730alchemy/archipelago#1"
  ```

---

## Task 3: `review_change_set` role spec

**Files:**
- Create: `src/archipelago/roles/review_change_set.yaml`
- Modify: `tests/archipelago/unit/test_archipelago_role_specs.py`

**Dependencies:** Task 2 (harness)

- [ ] **Step 1: Write the failing test**

  Append to `tests/archipelago/unit/test_archipelago_role_specs.py`:

  ```python
  class TestReviewChangeSetSpec:
      def test_given_review_change_set_yaml_when_loaded_then_matches_schema(self):
          spec = _load("review_change_set.yaml")
          _assert_schema(
              spec,
              expected_name="review_change_set",
              expected_module="archipelago.agents.reviewer",
              expected_class="Reviewer",
          )
  ```

- [ ] **Step 2: Run the test to verify it fails**

  Run: `cd /home/markn/engineering/jig-archipelago/archipelago && pdm run pytest tests/archipelago/unit/test_archipelago_role_specs.py::TestReviewChangeSetSpec -x`
  Expected: FAIL with `AssertionError: Role spec not found: .../review_change_set.yaml`

- [ ] **Step 3: Create the role spec file**

  Create `src/archipelago/roles/review_change_set.yaml`:

  ```yaml
  name: review_change_set
  description: Reviews all commits in a change set and categorizes findings as must_fix or can_defer using Claude Code in an ephemeral Docker container
  version: "1.0.0"
  implementation:
    module: archipelago.agents.reviewer
    class_name: Reviewer
  tags:
    - archipelago
    - docker-worker
    - review
  quality_controls:
    timeout_seconds: 7200
    max_retries: 1
  ```

- [ ] **Step 4: Run the test to verify it passes**

  Run: `cd /home/markn/engineering/jig-archipelago/archipelago && pdm run pytest tests/archipelago/unit/test_archipelago_role_specs.py::TestReviewChangeSetSpec -x`
  Expected: PASS

- [ ] **Step 5: Commit**

  ```bash
  cd /home/markn/engineering/jig-archipelago/archipelago
  git add src/archipelago/roles/review_change_set.yaml tests/archipelago/unit/test_archipelago_role_specs.py
  git commit -m "feat(roles): add review_change_set role spec

  Refs 730alchemy/archipelago#1"
  ```

---

## Task 4: `dispatch_findings` role spec

**Files:**
- Create: `src/archipelago/roles/dispatch_findings.yaml`
- Modify: `tests/archipelago/unit/test_archipelago_role_specs.py`

**Dependencies:** Task 2 (harness)

- [ ] **Step 1: Write the failing test**

  Append to `tests/archipelago/unit/test_archipelago_role_specs.py`:

  ```python
  class TestDispatchFindingsSpec:
      def test_given_dispatch_findings_yaml_when_loaded_then_matches_schema(self):
          spec = _load("dispatch_findings.yaml")
          _assert_schema(
              spec,
              expected_name="dispatch_findings",
              expected_module="archipelago.agents.finding_dispatcher",
              expected_class="FindingDispatcher",
          )
  ```

- [ ] **Step 2: Run the test to verify it fails**

  Run: `cd /home/markn/engineering/jig-archipelago/archipelago && pdm run pytest tests/archipelago/unit/test_archipelago_role_specs.py::TestDispatchFindingsSpec -x`
  Expected: FAIL

- [ ] **Step 3: Create the role spec file**

  Create `src/archipelago/roles/dispatch_findings.yaml`:

  ```yaml
  name: dispatch_findings
  description: Routes can_defer review findings to target change sets, post-job deferral, or human escalation using Claude Code in an ephemeral Docker container
  version: "1.0.0"
  implementation:
    module: archipelago.agents.finding_dispatcher
    class_name: FindingDispatcher
  tags:
    - archipelago
    - docker-worker
    - dispatch
  quality_controls:
    timeout_seconds: 3600
    max_retries: 1
  ```

- [ ] **Step 4: Run the test to verify it passes**

  Run: `cd /home/markn/engineering/jig-archipelago/archipelago && pdm run pytest tests/archipelago/unit/test_archipelago_role_specs.py::TestDispatchFindingsSpec -x`
  Expected: PASS

- [ ] **Step 5: Commit**

  ```bash
  cd /home/markn/engineering/jig-archipelago/archipelago
  git add src/archipelago/roles/dispatch_findings.yaml tests/archipelago/unit/test_archipelago_role_specs.py
  git commit -m "feat(roles): add dispatch_findings role spec

  Refs 730alchemy/archipelago#1"
  ```

---

## Task 5: `integrate_findings` role spec

**Files:**
- Create: `src/archipelago/roles/integrate_findings.yaml`
- Modify: `tests/archipelago/unit/test_archipelago_role_specs.py`

**Dependencies:** Task 2 (harness)

- [ ] **Step 1: Write the failing test**

  Append to `tests/archipelago/unit/test_archipelago_role_specs.py`:

  ```python
  class TestIntegrateFindingsSpec:
      def test_given_integrate_findings_yaml_when_loaded_then_matches_schema(self):
          spec = _load("integrate_findings.yaml")
          _assert_schema(
              spec,
              expected_name="integrate_findings",
              expected_module="archipelago.agents.integrator",
              expected_class="Integrator",
          )
  ```

- [ ] **Step 2: Run the test to verify it fails**

  Run: `cd /home/markn/engineering/jig-archipelago/archipelago && pdm run pytest tests/archipelago/unit/test_archipelago_role_specs.py::TestIntegrateFindingsSpec -x`
  Expected: FAIL

- [ ] **Step 3: Create the role spec file**

  Create `src/archipelago/roles/integrate_findings.yaml`:

  ```yaml
  name: integrate_findings
  description: Revises a change set's step sequence to coherently incorporate routed review findings using Claude Code in an ephemeral Docker container
  version: "1.0.0"
  implementation:
    module: archipelago.agents.integrator
    class_name: Integrator
  tags:
    - archipelago
    - docker-worker
    - integration
  quality_controls:
    timeout_seconds: 3600
    max_retries: 1
  ```

- [ ] **Step 4: Run the test to verify it passes**

  Run: `cd /home/markn/engineering/jig-archipelago/archipelago && pdm run pytest tests/archipelago/unit/test_archipelago_role_specs.py::TestIntegrateFindingsSpec -x`
  Expected: PASS

- [ ] **Step 5: Commit**

  ```bash
  cd /home/markn/engineering/jig-archipelago/archipelago
  git add src/archipelago/roles/integrate_findings.yaml tests/archipelago/unit/test_archipelago_role_specs.py
  git commit -m "feat(roles): add integrate_findings role spec

  Refs 730alchemy/archipelago#1"
  ```

---

## Task 6: Full test gate

**Files:** none (verification only)

**Dependencies:** Tasks 1-5

- [ ] **Step 1: Run the full test suite**

  Run: `cd /home/markn/engineering/jig-archipelago/archipelago && pdm test-all`
  Expected: PASS across unit + integration tiers. Integration tests that can't run in the current environment (no Docker daemon) skip gracefully; a failure is not acceptable.

- [ ] **Step 2: Typecheck**

  Run: `cd /home/markn/engineering/jig-archipelago/archipelago && pdm run typecheck`
  Expected: clean (no new errors on modified files).

- [ ] **Step 3: Stop and investigate any failure**

  If any step fails, do not proceed. Read the failure, identify which task introduced the regression, fix it in a new commit before continuing. Never skip the pre-commit/pre-push hooks.

---

## Verification

After all tasks complete:
- `archipelago.models` exports `ReviewerPayload` next to `ReviewFinding`
- Four new YAML files exist under `src/archipelago/roles/`, each loadable by PyYAML with the expected schema
- `tests/archipelago/unit/test_archipelago_role_specs.py` passes all five role spec tests (one existing sanity + four new)
- `pdm test-all` passes end-to-end
- No new code in `agents/io_models.py`
- No agent classes created (CS7 territory)
- No dependency on CS6.5 modules

## Notes for downstream (CS6.5, CS7)

- CS6.5's `build_outcome_schema(ReviewerPayload)` will produce the schema the Reviewer agent handler injects via `--json-schema`.
- CS6.5's `build_outcome_schema(ImplementationTask)` and `build_outcome_schema(DispatcherOutput)` and `build_outcome_schema(IntegratorOutput)` will serve Planner/Dispatcher/Integrator respectively.
- CS7 creates the four agent classes (`Planner`, `Reviewer`, `FindingDispatcher`, `Integrator`) at the module paths the role specs declare. Until CS7 ships, the role specs have dangling implementation references — safe because role specs are lazy-loaded at registry access time, not at module import time.
- `CommitAction` and `SubmitPRAction` are CS7's concern and do not need CS6 payload types — they are deterministic `FunctionAction` primitives whose function signatures will be decided in CS7.
