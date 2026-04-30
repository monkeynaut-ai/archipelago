---
title: Project Check — Archipelago
date: 2026-04-29
scope: src/archipelago, tests/archipelago, scripts/, pyproject.toml
---

# Project Check — Archipelago (2026-04-29)

Source: `src/archipelago/` (1,964 LOC across 31 files), `tests/archipelago/` (2,225 LOC across 26 files), `scripts/` (3 CLIs).

The codebase is at Stage 2 of v0.1 — the design pipeline (Cluster A) is well-tested and architecturally clean; the working-session pipeline (Clusters B & C, plus the Loop topography) was added recently and has substantially less coverage and several rough edges. Most findings below cluster around the seam between "tested Stage 1 surface" and "Stage 2 additions still under construction."

---

## Top 3 Most Egregious Findings — Poor Design

### 1. `archipelago.telemetry.config` is a tangle of init-time side effects, placeholder data, and untyped APIs

**File:** `src/archipelago/telemetry/config.py`

What's wrong:
- Lines 14–15 print `MFLOW_BASE_URL` (with a typo — should be `MLFLOW`) and `MLFLOW_EXPERIMENT_ID` to stdout at module-import time.
- Line 9 calls `load_dotenv()` at module-import time, before the CLI gets a chance to parse `--env-file`.
- Line 50 hard-codes a placeholder `MLflowInput(feature_name="All aboard", target="Crazy Train", quantity=7)` at module scope and then passes it into `enable_mlflow_adapter` as the run's input model — i.e., **every MLflow run logs the same fake metadata**, regardless of which feature was actually run.
- Line 53 declares `def attach_mlflow_adapter(event)` with no type annotation on `event` and no return type. It is wired into `run_full_pipeline` via `on_run_starting=[attach_mlflow_adapter]` (`pipeline.py:245`), so this is a real boundary, not a sketch.
- Module-level `telemetry_configuration = _telemetry_configuration()` means env-var changes after import are invisible. There is no test for this module.

How to improve:
- Replace the module-level instantiation with a `build_telemetry_config(...)` factory and call it from `run_full_pipeline` (or a CLI hook). Move `load_dotenv()` and the prints out of import scope.
- Type `event` against the agent-foundry event type (`RunStartingEvent` or whatever `on_run_starting` callbacks receive) and assert it in tests.
- Either derive `MLflowInput` from the actual `FeatureDefinition` of the run, or — if the adapter does not need it — remove it from the call.
- Add unit tests: factory consumes env vars dynamically; the input model used at attach-time matches the active feature; the typo `"MFLOW_BASE_URL "` is removed.

---

### 2. `_workspace_ops` is "private" but `systems/pipeline.py` reaches into it for Loop callables — interface leak

**Files:** `src/archipelago/actions/_workspace_ops.py`, `src/archipelago/systems/pipeline.py:44, 152, 162`

What's wrong:
- `_workspace_ops` is named with a leading underscore (Python convention for private). Sibling action modules legitimately use it (`workspace_bootstrap.py`, `prepare_change_set_workspace.py`). But `systems/pipeline.py` also imports it (`from archipelago.actions import _workspace_ops as _ops`) and uses `_ops.read_file(...)` inside the `Loop`'s `over` callables. The pipeline now bypasses the typed Action interface and depends on a "private" module.
- Both projection callables (`_change_sets_over`, `_steps_over`) call `docker.from_env()` directly and mix Docker-level I/O into what should be a thin state-projection function. The Docker dependency is invisible at the Loop boundary.
- `_artifacts_dir_for_run` is duplicated identically in `design_pipeline.py:68` and `pipeline.py:208` — symptom of the same "no shared seam between pipelines" problem.

Container-cost note: an earlier draft of this report claimed per-iteration container churn (`N + N×M` alpine spawns). That was wrong. Inspecting agent-foundry's compiler (`primitive_compiler.py:380-396`), the `over` callable is invoked **once per Loop entry**, not per body iteration. Actual reads in `full_pipeline` are `1 + C` (one for the outer Loop, one per change set for the inner Loop). For realistic runs that is a handful of ephemeral containers — pennies. The motivation for fixing this is the interface leak and the cohesion of the projection callables, not container performance.

How to improve:
- Promote `read_file` to the public `actions` namespace and rename `_workspace_ops` → `workspace_ops` (drop the underscore). The convention violation goes away.
- Better: introduce a typed read helper like `archipelago.actions.workspace_io.read_markdown(workspace_handle, path, model_type)` that wraps "spawn container, cat, validate against the document model." Loop projections become small, pure-shaped callables: `lambda state: read_markdown(state.workspace_handle, state.change_sets_document, ChangeSetsDocument).change_sets`. Markdown files remain the inter-agent exchange medium; the orchestrator just gets a cleaner seam to read them through.
- Note: shipping parsed models through agent output (instead of paths) is *not* the right move here. The project deliberately uses markdown files in the shared workspace as the data-exchange medium between agents, because the orchestration-layer typed-output mechanisms (e.g., Claude Code's structured output) are fragile and the file is already there. Keep the file-based exchange.
- Centralize `_artifacts_dir_for_run` into one module shared by both pipelines.

---

### 3. Flat-merge AgentAction outputs push brittle naming coupling and boilerplate onto every consumer

**Files:** `src/archipelago/systems/pipeline.py:67-88`, every `agents/*/models.py`, every `actions/*.py` input model

What's wrong:
- Per the comment block in `pipeline.py:67-78`, "AgentAction outputs are merged FLAT into accumulated state (the AgentAction compiler returns `typed.model_dump()`)". So `DesignerOutput`'s two fields (`investigation_summary`, `design_document`), `ChangeSetPlannerOutput`'s `change_sets_document`, and `TDDPlannerOutput`'s `steps_document` all show up as top-level fields of `FullPipelineState`.
- This creates two coupling problems:
  1. **Name collisions are silent.** If two agents both output a field called `summary`, the second silently shadows the first. Nothing in the type system or tests prevents this.
  2. **Top-level state pollution.** Every new agent forces `FullPipelineState` to gain new `Optional` fields with `None` defaults. The state model bloats with the cluster count.
- Every input model duplicates `model_config = ConfigDict(extra="ignore")` — present 11 times (the four loop states plus seven action/agent input models). The same "why" comment appears verbatim three times.
- `test_design_pipeline_state.TestStateFieldInvariants` checks bootstrap and designer inputs are subsets of `DesignPipelineState` — but there is no equivalent for the four loop-scoped states or the new agent inputs in `full_pipeline`. The asymmetry itself is a smell: the architecture explicitly relies on these subset invariants to keep the compiler well-defined, yet only the older pipeline gets the check.

How to improve:
- Replace flat merge with namespaced merge: each AgentAction's output goes under `state.<agent_name>` (e.g., `state.designer.design_document`). Downstream consumers declare a typed `designer_output: DesignerOutput` field — the type system catches missing data and the field name is unique per agent.
- If flat merge stays, define a single `class AgentInputState(BaseModel): model_config = ConfigDict(extra="ignore")` and have every input model inherit. One place for the rule, one place to comment why.
- Add `TestStateFieldInvariants` analogues for `ChangeSetsLoopState`, `ChangeSetProcessingState`, `StepsLoopState`, `StepProcessingState` and every agent input in `full_pipeline`. The whole architecture rests on this invariant; let CI prove it.

---

## Test-Suite Findings

### Coverage gaps (most serious)

The Designer cluster has 5 dedicated test files (callables, primitive, models, instructions_template, public_api). The other two agents and the new actions have **no equivalent coverage at all**:

| Surface | Test files | Notes |
|---|---|---|
| `agents/change_set_planner/` | 0 | Compare to `designer/` (5 files). |
| `agents/tdd_planner/` | 0 | Same. |
| `actions/prepare_change_set_workspace` | 0 | FunctionAction, 51 LOC. |
| `actions/log_change_set_name` / `log_change_set_step_name` | 0 | Even a trivial print test would catch wiring bugs. |
| `models/change_sets_document.py` | 0 | `ChangeSetRef`, `ChangeSetsDocument`, `slugify` — none. Only listed in `test_public_api.py`'s `__all__` set. |
| `models/steps_document.py` | 0 | Same. |
| `systems/pipeline.py::full_pipeline` | 0 (composition) | No analogue of `test_sequence_composition.py` for the new pipeline. |
| `systems/pipeline.py::_change_sets_over`/`_steps_over` | 0 | Loop `over` callables exercising Docker. |
| `systems/pipeline.py::run_full_pipeline` | 0 | Compare to `test_run_design_pipeline.py`. |
| `systems/pipeline.py::FullPipelineState` (and 4 loop states) | 0 (state shape, invariants) | |
| `scripts/run_full_pipeline.py` | 0 | Compare to `test_run_design_pipeline_cli.py`. |
| `scripts/inspect_stream.py` | 0 | All 4 modes untested. |
| `telemetry/config.py` | 0 | See poor-design finding #1. |
| `logging_config.py::configure_logging` | 0 | Idempotency, JSON-vs-console formatter selection, level fallback — none asserted. |
| `_workspace_ops.read_file` | 0 | |
| `_workspace_ops.make_change_sets_dir` | 0 | |
| `_workspace_ops.make_change_set_subdir` | 0 | |
| `_workspace_ops._decode_container_stderr` | 0 (direct) | Only exercised indirectly through happy/unhappy paths of higher functions. |
| `_workspace_ops._with_github_token` | partial | SSH (`git@github.com:...`) and trailing-`.git`-less GitHub URLs untested. |

The scaffolding directories `tests/archipelago/integration/` and `tests/archipelago/unit/` exist but contain only `__pycache__` — likely planned but never used.

### Edge cases / bad-input cases missing

1. **Shell injection in `clone_and_resolve_ref`**. `f"git -C /workspace/codebase checkout {ref}"` (`_workspace_ops.py:83`) interpolates `ref` into a string passed to `sh -c`. A `ref` containing `; rm -rf /;` would execute. Same hazard for `effective_url`. Even if both come from internal callers in v1, no defensive test asserts the interpolation is safe — and the code does not switch to argv form to avoid the question. Add a test with a mischievous `ref` and decide whether to harden or document the trust boundary.
2. **`generate_volume_name`** has no test for the `or "unnamed"` fallback (input that sanitizes to empty).
3. **`slugify`** — no direct test. The `or "unnamed"` fallback is documented but unverified.
4. **Frontmatter date coercion** — every `coerce_*_to_string` validator is exercised only implicitly through full-document YAML parsing. No test passes a `datetime.datetime` (only `date`); no test passes a string already containing 'T' time portion.
5. **`bootstrap_fn` cleanup error path** — if the post-create cleanup itself raises (`client.volumes.get(name).remove(force=True)`), the `contextlib.suppress(Exception)` is supposed to swallow it. Untested.
6. **Empty/whitespace `github_token`**. `_with_github_token` treats `""` as falsy and returns the URL unchanged — but the boundary isn't asserted.
7. **`write_file` with binary or very-large content** — the tar buffer is built entirely in memory; behavior at multi-MB sizes is unverified.
8. **`prepare_documents_dir` partial-failure** — mkdir/chown/chmod are chained in one `sh -c`. If the chown step fails, the chmod still runs against the previous owner. No test pins this ordering at the integration layer.
9. **CLI `--env-file` flag** in `run_design_pipeline.py` — no test covers a non-default path or a missing file.

### Redundant / overlapping tests

1. `test_workspace_bootstrap_models.py`, `test_design_pipeline_state.py`, `test_designer/test_models.py`, and `test_designer/test_callables.py` all define their own `_sample_handle()` / `_handle()` constructor with copy-pasted field values. Promote a single `sample_workspace_handle` fixture into `conftest.py`.
2. `TestDesignerPromptBuilder` has three tests (`test_returns_non_empty_string`, `test_mentions_workspace_root`, `test_references_instructions_or_design`) that hand-assert independent properties. Replacing them with a single equality check against the expected prompt string is more precise and signals churn faster.
3. The four `test_public_api.py` files (one per package) each enumerate `__all__` against an expected set. They duplicate the same logic and break loudly whenever any export is added or removed. Worth replacing with one parametrized test, or — given that `__all__` is already authoritative — dropping the smoke and trusting `from package import name` failures during integration.

### Tests that don't exercise the path they imply

1. **`test_run_design_pipeline.py`** patches `run_primitive_plan`, so the orchestration is not actually exercised — only the construction of kwargs. The "agent-foundry side" of the contract is verified solely by the e2e test, which is excluded from the default `pdm test-all` run (`addopts = -m 'not benchmark and not e2e'`). A consumer-driven contract test or a fake `run_primitive_plan` that walks the Sequence would close this gap without paying for live LLM calls.
2. **`test_designer/test_primitive.py`** asserts every `AgentAction` config field but never invokes the executor, so a regression in `run_agent_in_container`'s contract would not surface here.
3. **`test_workspace_ops.py::TestPrepareDocumentsDir::test_chown_runs_before_chmod`** uses string-index inspection of the rendered shell command. If the implementation switches from a single `sh -c` to multiple `containers.run` calls, the assertion silently still passes (only one command is inspected). Test the *behavior*, not the *string*.

### Tests for malicious inputs

- **CodebaseSource** validates only structural presence; no test for malformed URLs (by design, but worth a comment in the model docstring).
- **No test for `ref` shell injection** in `clone_and_resolve_ref` (see edge-cases #1).
- **No test for path injection** in `chmod_path`/`chmod_tree_excluding_git` (paths come from internal code; defensive test still warranted).

---

## Top 3 Most Egregious Technical Debts

### 1. Frontmatter date-coercion validators are copy-pasted four times

**Files:** `feature_definition.py:69-80`, `design_document.py:25-37`, `change_sets_document.py:55-60`, `steps_document.py:42-47`

The same `@field_validator(..., mode="after") def coerce_*_to_string(cls, v): if isinstance(v, date): return v.isoformat(); return v` block appears in four frontmatter classes. Three of them have a multi-line docstring explaining "YAML parses unquoted dates as `date` objects."

**Mitigation:** Extract a single function:
```python
def coerce_date_to_iso_string(v: str | date) -> str:
    return v.isoformat() if isinstance(v, date) else v
```
and apply via `field_validator(...)(coerce_date_to_iso_string)` per field, **or** define an `Annotated[str | date, BeforeValidator(coerce_date_to_iso_string)]` type alias and use it on every frontmatter field. The docstring lives in one place and edits propagate.

---

### 2. `_artifacts_dir_for_run`, `docker.from_env()`, and workspace path strings are duplicated across the codebase

- `_artifacts_dir_for_run` is identical in `design_pipeline.py:68` and `pipeline.py:208`.
- `docker.from_env()` is called in 4 places (`workspace_bootstrap.py:82`, `prepare_change_set_workspace.py:37`, `pipeline.py:152`, `pipeline.py:162`) — each a fresh client, no shared lifecycle.
- Workspace path literals (`/workspace`, `/workspace/documents`, `/workspace/codebase`, `feature_definition.md`, `design.md`, `change-sets.md`, `steps.md`) appear scattered across `_workspace_ops.py`, `workspace_bootstrap.py`, `prepare_change_set_workspace.py`, `WorkspaceHandle` properties, and the three instruction-template markdown files.
- `WorkspaceHandle` exposes some paths as typed properties (`design_document_path`, `change_sets_document_path`, `change_sets_dir`) — the right pattern. But `prepare_change_set_workspace_fn` and the agents still hand-assemble `f"{cs_path}/steps.md"`-style paths next to those properties.

**Mitigation:**
- Move `_artifacts_dir_for_run` into `systems/__init__.py` (or a `systems/_artifacts.py`) and import from both pipelines.
- Introduce a single `WorkspaceLayout` (constants module or extension to `WorkspaceHandle`) that owns every well-known path. Stop hand-assembling.
- Threading a `DockerClient` through state (rather than `from_env()` per call) would also eliminate the implicit init-once-per-call cost and make the registry/bootstrap pairing easier to reason about.

---

### 3. Compiler-coupling boilerplate: `model_config = ConfigDict(extra="ignore")` repeated 11 times with a paste-rotting "why" comment

Present in `BootstrapInput`, `DesignerInput`, `ChangeSetPlannerInput`, `TDDPlannerInput`, `PrepareChangeSetWorkspaceInput`, `LogChangeSetNameInput`, `LogChangeSetStepNameInput`, `ChangeSetsLoopState`, `ChangeSetProcessingState`, `StepsLoopState`, `StepProcessingState`. Three of these carry the same multi-line "why" comment ("the compiler passes the full pipeline state into model_validate; extra fields … must be silently dropped"); the others have just the bare line. Adding a new agent or loop body requires copying this rule again.

**Mitigation:** Define `class AgentInputState(BaseModel): model_config = ConfigDict(extra="ignore")` once (in `archipelago.actions` or a small `archipelago.compiler_glue` module) and inherit. The comment lives in one place. Best fix would be upstream in agent-foundry — have the AgentAction compiler tag its input model automatically — but the local mitigation costs nothing.

---

## Other Code-Quality Findings

### Dead / suspicious code

- `MLflowInput(feature_name="All aboard", target="Crazy Train", quantity=7)` (`telemetry/config.py:50`) — placeholder data hardcoded in production code path. Almost certainly a wiring sketch that was never replaced.
- `print("MFLOW_BASE_URL ", MLFLOW_BASE_URL)` (`telemetry/config.py:14`) — debug print at module load with a typo (`MFLOW`).
- `claude/CLAUDE orig.md` (note the space) and `claude/agents/feature-architect.orig.md` — `.orig` files committed to the repo. Likely leftover after edit; remove or move outside the tree.
- `temp/` directory contains `designer-agent-notes.md` and `feature-architect-agent.md` plus a `temp/agents/` subdir — checked-in scratch notes. Should be moved to `docs/` or removed (and added to `.gitignore` if useful locally).
- `lab/` contains shell scripts (`bash-that-volume.sh`, `browse-workspace.sh`, `run-workspace.sh`) and `dev_test_input` / `job_definition` placeholder files. Either promote to `scripts/` with proper docs, or move to `docs/snippets/`.
- `tests/archipelago/integration/` and `tests/archipelago/unit/` are empty (only `__pycache__`). Either populate or remove the empty directories — they imply structure that doesn't exist.
- `pyproject.toml` declares `jsonschema>=4.26.0` and `pexpect>=4.9.0` but **neither is imported anywhere in `src/archipelago/`**. They may be transitive needs of agent-foundry, but if so, they belong on agent-foundry's dependency list, not here.
- `pyproject.toml` declares the `benchmark` pytest marker but no test currently uses it. Either add one or drop the marker.
- `examples/features/run-observability.md` is opened by 4 test files via the `repo_root` fixture; a `run_observability_feature` fixture would be DRYer and pin the location once.

### Hardcoded strings / configuration

- Image tags `"alpine/git:v2.47.2"`, `"alpine:3.20"`, `"agent-worker:latest"` — three locations, no env override. Pin them in a single config module (or accept env var overrides).
- Timeout `1800` (30 minutes) repeated in three agent primitive declarations (`designer/primitive.py:28`, `change_set_planner/primitive.py:34`, `tdd_planner/primitive.py:25`). One named constant.
- File-mode literals `"775"`, `"555"`, `"444"`, `0o644` scattered across `_workspace_ops.py` and `bootstrap_fn`. `DOCUMENTS_DIR_MODE = "775"` exists at `_workspace_ops.py:153` but is not used everywhere it could be.
- The `"unnamed"` fallback string is duplicated in `slugify` and `generate_volume_name`.
- MLflow defaults `"http://localhost:5000"` and experiment ID `"0"` are hardcoded in `telemetry/config.py`.

### Lack of strong typing

- `attach_mlflow_adapter(event)` (`telemetry/config.py:53`) — `event` has no type annotation. Should be `event: RunStartingEvent` (or whichever agent-foundry type it actually receives).
- `coerce_*_to_string(cls, v)` validators (×4) have an untyped `v` parameter. Should be `v: str | date`.
- The three `# type: ignore[arg-type]` comments on `executor=run_agent_in_container` (designer, change_set_planner, tdd_planner primitives) reflect a real type mismatch in agent-foundry's executor signature. Fix upstream rather than suppressing locally.
- Loop `over` callables (`_change_sets_over`, `_steps_over`) read from a private module and a freshly-spawned Docker container; the strong return type (`list[ChangeSetRef]`/`list[StepRef]`) is decorative given the IO-heaviness of the body.

### Overly complex / fragile

- `bootstrap_fn` has a 40-line numbered-step critical section (lines 95–135) where partial-failure cleanup is best-effort. The "5b. Create change-sets/ subdirectory" comment indicates a step inserted post-design — numbered comments rot as steps are added.
- `chmod_tree_excluding_git`'s `find` script interpolates `path` and `mode` directly into a shell string. The `path = path.rstrip("/")` defensive line and accompanying comment ("a double slash would silently fail to match real .git/ and wipe its perms") show that the team has already been bitten — and the underlying shell-string-construction pattern is the root cause.
- `_decode_container_stderr` papers over a docker-py types/runtime inconsistency (typed `str | None` but populated with bytes). Worth filing upstream or vendoring a typed wrapper, rather than carrying the workaround indefinitely.

### Other smells worth a glance

- Logging level fallback `getattr(logging, level.upper(), logging.INFO)` (`logging_config.py:33`) silently swallows typos (`level="WARNIGN"` → INFO). Either validate against `logging.getLevelNamesMapping()` and raise, or document the fallback in the function's contract.
- `pyproject.toml` `addopts = "-m 'not benchmark and not e2e' -n 8"` pins parallelism to 8 — fine for a workstation but brittle in CI environments with different core counts. Consider `-n auto`.

---

## Suggested next moves (in order of leverage)

1. **Fix `telemetry/config.py`** — placeholder MLflowInput, prints at import, untyped event. This is shipping right now and pollutes every run.
2. **Add change_set_planner + tdd_planner test suites** — model parity with Designer. The new agents have no safety net.
3. **Consolidate the boilerplate**: shared `coerce_date_to_iso_string`, shared `AgentInputState`, shared `_artifacts_dir_for_run`. Pure cleanup; small but high-leverage for future agents.
4. **Promote `read_file` out of `_workspace_ops`** (or eliminate it from the Loop callable by shipping content through state). Closes the interface leak and removes per-iteration container churn.
5. **Add `TestStateFieldInvariants` for `full_pipeline`** — proves the subset invariants the architecture rests on.
6. **Argument-list refactor of shell-interpolation sites** in `_workspace_ops.py` (`clone_and_resolve_ref`, `chmod_*`, `make_change_set_subdir`). Defense-in-depth even if internal callers are trusted.
