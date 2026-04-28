# CS7 Plan 3 — Base Image Takes Over, Archipelago Image Goes Away

**Roadmap**: `docs/plans/stage1/2026-04-03-review-feedback-loop-roadmap.md` — CS7, Plan 3.
**Branches**:
- Agent Foundry: `feat/cs7-plan3-base-image` (lands first)
- Archipelago: `feat/cs7-plan3-drop-archipelago-image` (lands after)

## Goal

The Agent Foundry base image ships the generic agent brief (`CLAUDE.md`) and the `lessons-learned` skill. The Archipelago Docker image and the `ARCHIPELAGO_*` text-marker protocol are deleted end-to-end. The `acp` name disappears: the package is renamed to `agents`, the image to `agent-worker`, the env vars to `WORKSPACE_HIDDEN_DIRS` / `WORKSPACE_READONLY_DIRS`.

## Scope decisions (locked)

- **Package name**: `agent_foundry.agents` (renamed from `agent_foundry.acp`).
- **Image tag**: `agent-worker:latest` (renamed from `acp-cc-worker:latest`).
- **Env vars**: `WORKSPACE_HIDDEN_DIRS` / `WORKSPACE_READONLY_DIRS` (renamed from `ACP_*`).
- **File rename**: `acp/container.py` → `agents/lifecycle.py`.
- **Keep**: Archipelago's role-specific `CLAUDE-*.md` files on host filesystem (Plan 4 injects at runtime via `write_file_to_container`).
- **Delete from Archipelago**: everything else under `src/archipelago/docker/`, including `v0.1/`.
- **Keep**: Archipelago's `docker_worker/` package (import paths only get updated; CS11 sweeps).
- **Pulled forward from CS11**: marker-config deletion, adapter marker code removal, archipelago image deletion, `ARCHIPELAGO_UPDATE_AVAILABLE` marker drop (no CI pipeline built here — deferred to CS11 proper).

## Base `CLAUDE.md` content (approved)

```markdown
# Agent Worker

You are an agent running in a sandboxed container. Your task is delivered as a prompt; additional role-specific instructions may be appended to this file at container startup.

- **Work in `/workspace`** — do not modify files outside it.
- Additional context files (`CLAUDE-*.md`) in this directory, if present, apply to your specific role.

## Communication protocol

You return results via **structured output**. The host invokes you with a JSON schema (`--json-schema`); you respond by calling the `StructuredOutput` tool exactly once, with a payload matching the schema. The payload is an `AgentTurnEnvelope` with one of four outcomes:

- `success` — task completed, payload contains your result.
- `clarification_needed` — blocked on a question; payload states what you need.
- `permission_needed` — blocked on an action outside your grant; payload states the action and why.
- `failed` — unrecoverable; payload contains `reason`.

Emit the `StructuredOutput` tool call as your final action every turn. Do not rely on free-text signals; the host reads only the structured payload.

## LSP-first code navigation

You have a Pyright LSP server available. Prefer LSP over Grep/Read for:
- Finding references, definitions, implementations
- Hovering for types, listing document or workspace symbols
- Tracing incoming/outgoing calls
- Checking diagnostics after edits

Fall back to Grep/Read only when LSP has no server for the file type.

## lessons-learned skill

When your task completes, invoke the `lessons-learned` skill to log specific, actionable, non-obvious observations to `/workspace/.claude/lessons-learned.md`.
```

---

## PR 1 — Agent Foundry (`feat/cs7-plan3-base-image`)

Work on Agent Foundry. Touches no Archipelago files. Merges first.

### Phase A — Package rename `acp/` → `agents/`

Purely mechanical. No semantic changes.

1. `git mv src/agent_foundry/acp src/agent_foundry/agents`
2. `git mv tests/agent_foundry/acp tests/agent_foundry/agents`
3. Rename test files `test_acp_*.py` → `test_agents_*.py` *only* if the name reads awkwardly (most will; e.g. `test_acp_protocol.py` → `test_agents_protocol.py`). Intent: no file named after the old package name.
4. Global replace across `src/` and `tests/`: `agent_foundry.acp` → `agent_foundry.agents`. Touches:
   - Within moved package: adapter.py, adapters/claude_code.py, agent_runner.py, container.py, protocol.py, recovery.py, role_stack.py, schema_tools.py, session.py, env.py, errors.py, and all tests.
   - Outside moved package: `src/agent_foundry/orchestration/registry.py`, `src/agent_foundry/orchestration/container_executor.py`, `src/agent_foundry/responders/models.py`.
5. Global replace in docs and pyproject: `agent_foundry/acp` → `agent_foundry/agents`, `agent_foundry.acp` → `agent_foundry.agents`.
6. Run `pdm test-all` — must be green before moving on.

### Phase B — Rename `container.py` → `lifecycle.py`

Its role post-CS7-Plan-2 is container-lifecycle orchestration, not abstract container surface.

1. `git mv src/agent_foundry/agents/container.py src/agent_foundry/agents/lifecycle.py`
2. Rename any test files named `test_*container*` that correspond to this module.
3. Global replace: `from agent_foundry.agents.container import` → `from agent_foundry.agents.lifecycle import`. Touches registry.py, container_executor.py, session.py, recovery.py, and their tests.
4. `pdm test-all` green.

### Phase C — Env var rename `ACP_*` → `WORKSPACE_*`

1. Global replace in `src/agent_foundry/agents/docker/entrypoint.sh` and `lockdown.sh`: `ACP_HIDDEN_DIRS` → `WORKSPACE_HIDDEN_DIRS`, `ACP_READONLY_DIRS` → `WORKSPACE_READONLY_DIRS`.
2. Replace in `src/agent_foundry/agents/env.py` and any callers.
3. Replace in tests (test_acp_env.py or successor, test_acp_entrypoint.py, test_acp_container.py, orchestration/test_container_executor.py if applicable).
4. `pdm test-all` green.

### Phase D — Image rename `acp-cc-worker` → `agent-worker`

1. `src/agent_foundry/agents/docker/Dockerfile.base`: update the header comment block and the `docker build -t ...` example.
2. `pyproject.toml`: update `docker-base.cmd`: tag → `agent-worker:latest`; Dockerfile path → `src/agent_foundry/agents/docker/Dockerfile.base`.
3. Replace in source/tests anywhere the image tag is referenced as a string (`grep -r "acp-cc-worker"`).
4. Run `pdm docker-base` locally; confirm image builds under new tag.
5. `pdm test-all` green.

### Phase E — Add generic `CLAUDE.md` to base image

TDD: write the test first.

1. **Test (fails initially)**: `tests/agent_foundry/integration/test_base_image_artifacts.py` — integration test marked `@pytest.mark.integration`, builds the base image (or uses the one from Phase D), runs a container, asserts `/home/claude/.claude/CLAUDE.md` exists and contains the phrase `AgentTurnEnvelope`. Skip gracefully if Docker unavailable.
2. **Implementation**: create `src/agent_foundry/agents/docker/CLAUDE.md` with the approved content (above).
3. **Dockerfile**: add `COPY --chown=claude:claude src/agent_foundry/agents/docker/CLAUDE.md /home/claude/.claude/CLAUDE.md` to `Dockerfile.base`.
4. Rebuild; test passes.

### Phase F — Move `lessons-learned` skill into base image

TDD: extend the artifact test.

1. **Test extension**: in `test_base_image_artifacts.py`, assert `/home/claude/.claude/skills/lessons-learned/SKILL.md` exists.
2. **Implementation**: copy `archipelago/src/archipelago/docker/skills/lessons-learned/SKILL.md` → `agent-foundry/src/agent_foundry/agents/docker/skills/lessons-learned/SKILL.md` verbatim (already generic — verify no product name leaks on read; skill content review before commit).
3. **Dockerfile**: add `COPY --chown=claude:claude src/agent_foundry/agents/docker/skills/lessons-learned/SKILL.md /home/claude/.claude/skills/lessons-learned/SKILL.md`.
4. Rebuild; test passes.

### Phase G — Delete text-marker protocol

This is the widened-scope chunk. Strictly subtractive.

1. **`src/agent_foundry/agents/protocol.py`**: delete `MarkerMapping` class and any marker-related enum/type.
2. **`src/agent_foundry/agents/adapters/claude_code.py`**:
   - Remove import of `MarkerMapping`.
   - Remove `_compiled_markers` field initialization.
   - Remove `_match_marker` method.
   - Remove any call sites of `_match_marker` in `_map_event_to_protocol` (or equivalent); marker-synthesized events go away entirely.
   - Remove constructor params that configured markers, if any.
3. **`src/agent_foundry/agents/role_stack.py`**: remove marker wiring — the import from `protocol.MarkerMapping` and any code that consumes it.
4. **`src/agent_foundry/agents/docker/entrypoint.sh`**: remove the block that copies/handles `marker-config.json` and sets marker-related env vars (if any).
5. **Tests**: delete marker-specific tests in `test_agents_protocol.py`, `test_claude_code_adapter.py`, `test_agents_role_stack.py`. Keep non-marker tests intact. Do NOT delete `test_schema_tools_marker_preserved.py` unless grep confirms its subject is the text-marker protocol — likely unrelated (it's about schema flattening preserving schema-level marker keywords).
6. Pyright clean; `pdm test-all` green.

### Phase H — Verify PR 1

1. `pdm lint` clean.
2. `pdm typecheck` clean.
3. `pdm test-all` green (unit + integration).
4. `pdm docker-base` produces `agent-worker:latest`.
5. Container spot-check: `docker run --rm agent-worker:latest test -f /home/claude/.claude/CLAUDE.md && test -f /home/claude/.claude/skills/lessons-learned/SKILL.md` → exits 0.
6. `grep -r "acp\|ACP" src tests pyproject.toml` — expect zero non-test, non-docs hits. Stray hits get fixed before PR.

### PR 1 deliverables

- Package renamed, tests renamed, imports updated.
- `container.py` → `lifecycle.py` rename.
- Env vars renamed.
- Image tag renamed.
- Base image ships `CLAUDE.md` and `lessons-learned` skill.
- Text-marker protocol deleted (classes, adapter code, entrypoint handling, tests).
- Integration test covers the two new image artifacts.

---

## PR 2 — Archipelago (`feat/cs7-plan3-drop-archipelago-image`)

Opens after PR 1 merges. Archipelago's `file://` dep on agent-foundry picks up the new package name.

### Phase I — Update Archipelago imports

1. Global replace across `src/archipelago/` and `tests/archipelago/`: `from agent_foundry.acp` → `from agent_foundry.agents`, `agent_foundry.acp.` → `agent_foundry.agents.`. Touches ~10 files under `docker_worker/` plus their tests.
2. Replace env-var references in tests: `ACP_HIDDEN_DIRS` → `WORKSPACE_HIDDEN_DIRS`, `ACP_READONLY_DIRS` → `WORKSPACE_READONLY_DIRS`.
3. `pdm test-all` green.

### Phase J — Delete Archipelago Docker image

1. Delete the entire directory: `src/archipelago/docker/v0.1/` (historical snapshot, confirmed unreferenced).
2. Delete files from `src/archipelago/docker/`:
   - `Dockerfile`
   - `CLAUDE.md` (archipelago-specific brief — superseded by base image)
   - `marker-config.json`
   - `product-init.sh`
   - `settings.local.json`
   - `claude.json`
   - `run-interactive.sh`
   - `generate_review_schema.py`
   - `skills/` (lessons-learned moved to agent-foundry in PR 1)
3. **Keep** these files under `src/archipelago/docker/`:
   - `CLAUDE-source-code-writer.md`
   - `CLAUDE-unit-test-writer.md`
   - `CLAUDE-software-review.md`
   - `CLAUDE-test.md`
   Plan 4 injects these at runtime. Consider renaming the directory `src/archipelago/docker/` → `src/archipelago/agent_instructions/` or similar to reflect new purpose — defer to Plan 4 (risk of churn with no consumer yet).
4. `pyproject.toml`: remove scripts `docker-archipelago.composite`, `_docker-build-archipelago`, `generate-review-schema`, and the `generate-review-schema.env` entry.

### Phase K — Clean remaining marker refs in `docker_worker/`

1. `src/archipelago/docker_worker/protocol.py`: remove any residual marker-class usage or references to `MarkerMapping` (it's now gone from agent-foundry). If the module is left with no content, delete it and clean callers.
2. `src/archipelago/docker_worker/models.py`: any `ARCHIPELAGO_*` string literals → delete.
3. `tests/archipelago/unit/test_adapter_protocol_models.py`, `test_docker_worker_interrupts.py`: strip marker cases.
4. `pdm test-all` green. Lint + typecheck clean.

### Phase L — Update roadmap

1. Edit `docs/plans/stage1/2026-04-03-review-feedback-loop-roadmap.md`:
   - Mark CS7 Plan 3 complete.
   - CS11 items now done (strike or mark superseded): marker-config deletion, archipelago image deletion, `ARCHIPELAGO_UPDATE_AVAILABLE` marker deletion. Preserve the CI-pipeline task note for CS11 proper.
2. Commit the roadmap edit with the PR.

### Phase M — Verify PR 2

1. `pdm lint` clean.
2. `pdm typecheck` clean.
3. `pdm test-all` green.
4. `grep -r "acp\|ACP\|ARCHIPELAGO_TASK_COMPLETE\|ARCHIPELAGO_NEED_\|ARCHIPELAGO_UPDATE_AVAILABLE\|marker-config\|acp-cc-worker\|archipelago-cc-worker" src tests pyproject.toml` — zero non-doc, non-historical hits.
5. Confirm `src/archipelago/docker/` contains only the `CLAUDE-*.md` role files.

### PR 2 deliverables

- All `agent_foundry.acp` imports updated to `agent_foundry.agents`.
- All `ACP_*` env-var references updated to `WORKSPACE_*`.
- `src/archipelago/docker/v0.1/` gone.
- Archipelago Docker image files deleted; `CLAUDE-*.md` role files retained.
- `pyproject.toml` docker scripts removed.
- Residual marker references scrubbed from `docker_worker/`.
- Roadmap updated.

---

## Risks and deviations

- **Test files named `test_acp_*`**: renaming them touches collaborator files and widens the diff. Alternative: leave filenames alone. Chosen: rename, because the goal is "acp name disappears" — stopping halfway leaves readers confused.
- **`test_schema_tools_marker_preserved.py`**: name contains "marker" but subject is schema-flattening markers, not text markers. Leave alone unless grep reveals otherwise during Phase G Task 5.
- **`product-init.sh` removal**: the base image's `entrypoint.sh` invokes it at startup. PR 1 must also drop that invocation from `entrypoint.sh` — add to Phase G Task 4. Without this, the base image crashes on startup once PR 2 removes the script.

  *Correction*: this bites during Phase H verification. Fix at Phase G; not during Archipelago PR.
- **Docker image rebuild cadence**: both PRs should be tested against a rebuilt image. Integration tests that need Docker should skip gracefully in CI if Docker unavailable.
- **Cross-repo coordination**: if PR 1 is reverted post-merge, PR 2 can't rebase cleanly. Mitigation: no force-merges; let PR 1 soak for one full test cycle before opening PR 2.

## Definition of done

- Both PRs merged.
- `agent-worker:latest` image builds cleanly and contains generic `CLAUDE.md` + `lessons-learned` skill.
- `agent_foundry.agents` is the only package name; `acp` appears nowhere in code, config, or non-historical docs.
- `ARCHIPELAGO_*` text markers, `MarkerMapping`, `_match_marker`, and `marker-config.json` no longer exist.
- Archipelago's `src/archipelago/docker/` contains only role-specific `CLAUDE-*.md` files.
- Full test suite green in both repos.
- Roadmap reflects completed items.
