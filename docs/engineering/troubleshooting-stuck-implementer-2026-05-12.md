# Troubleshooting: Stuck Implementer Agent (2026-05-12)

An implementer agent inside a Docker container completed its work and committed code, but
the orchestration framework never received the success response. This documents the
investigation and fix.

---

## (a) Troubleshooting Steps

### Step 1 — Identify which containers are running

**Question:** Which containers from the `agent-worker-foundry-dev:latest` image are running, and what is their health?

**Command:**
```bash
docker ps --filter "ancestor=agent-worker-foundry-dev:latest" \
  --format "table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.RunningFor}}"
```
Lists all containers from the image with status and uptime.

**Learned:** 5 containers running, all healthy, ages 30 minutes to ~1 hour.

---

### Step 2 — Check resource usage

**Question:** Are any containers under memory pressure or abnormally busy?

**Command:**
```bash
docker stats --no-stream --format \
  "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}\t{{.PIDs}}" \
  $(docker ps --filter "ancestor=agent-worker-foundry-dev:latest" -q)
```
Snapshots current CPU, memory, I/O, and PID counts for all containers.

**Learned:** `interesting_mahavira` was the clear outlier — 159.6 MiB RAM (vs 3–7 MiB for
the others), 20 PIDs (vs 1–3), and 2.19 GB / 1.53 GB block I/O. The other four containers
were effectively idle.

---

### Step 3 — Inspect processes inside the active container

**Question:** What is `interesting_mahavira` actually doing?

**Command:**
```bash
docker top interesting_mahavira
```
Lists every process running inside the container with its PID, parent PID, and full command.

**Learned:** Three meaningful processes:
- A `claude` implementer agent invoked with `--output-format stream-json`
- A Pyright LSP server (Python + Node processes)
- A bash polling loop watching a task output file for the strings
  `"feat(primitives): add MCPTransportKind"`, `"failed"`, or `"Aborting commit"`

---

### Step 4 — Read the task output file

**Question:** What has the agent written to its output file so far?

**Command:**
```bash
docker exec interesting_mahavira \
  cat /tmp/claude-1000/-workspace-codebase/.../tasks/b12u9ohp0.output | tail -50
```
Shows the last 50 lines of the file the bash monitor is watching.

**Learned:** The file contained output from a failed `git commit`: the `py_compile`
pre-commit hook failed (`python` executable not found), and the `pytest-unit` hook failed
with `ImportError: cannot import name 'MCPServerConfig' from agent_foundry.primitives.mcp`.
719 tests passed, 1 collection error.

---

### Step 5 — Count lines, check git log, search for trigger strings

**Question:** Is the file complete? Has the target commit been made? Do any polling trigger
strings appear?

**Commands:**
```bash
docker exec interesting_mahavira grep -c "" .../tasks/b12u9ohp0.output
docker exec interesting_mahavira git -C /workspace/codebase log --oneline -10
docker exec interesting_mahavira grep -a \
  "Aborting commit\|feat(primitives): add MCPTransportKind\|\"failed\"\|\"success\"" \
  .../tasks/b12u9ohp0.output | tail -20
```
Counts lines; shows recent commits; searches the file for all polling trigger strings.

**Learned:** The file had 59 lines. A commit named
`feat(primitives): add MCP server configuration models and public API exports` (`9d48bca`)
existed. None of the trigger strings appeared in `b12u9ohp0.output`.

---

### Step 6 — Read the full output file and list all task files

**Question:** What exactly is in the file? Are there other task output files with more
information?

**Commands:**
```bash
docker exec interesting_mahavira cat .../tasks/b12u9ohp0.output
docker exec interesting_mahavira ls -la .../tasks/
```
Reads the complete file; shows all task output files with sizes and timestamps.

**Learned:** The file only contained the failed pre-commit output (written at 21:37). Two
other task files existed: `bopa9ujxf.output` (21:36, 442 bytes) and `bjc9ti27m.output`
(21:49, 1396 bytes) — both written after `b12u9ohp0.output`.

---

### Step 7 — Read the other task output files

**Question:** What do the newer task files contain?

**Commands:**
```bash
docker exec interesting_mahavira cat .../tasks/bjc9ti27m.output
docker exec interesting_mahavira cat .../tasks/bopa9ujxf.output
```
Reads both files.

**Learned:** `bjc9ti27m.output` showed a clean pytest run at 21:49 — **744 tests passing**,
up from 719 at 21:37 (25 new tests added). `bopa9ujxf.output` was empty except for locale
warnings.

---

### Step 8 — Confirm "Aborting commit" is truly absent

**Question:** Could grep have missed the trigger string due to encoding or partial match?

**Command:**
```bash
docker exec interesting_mahavira grep -c "Aborting" .../tasks/b12u9ohp0.output
```
Counts all lines containing "Aborting" in the file.

**Learned:** Zero matches. The string was never written to the file.

---

### Step 9 — Check current git status

**Question:** Is the workspace clean? Did the agent leave uncommitted work?

**Commands:**
```bash
docker exec interesting_mahavira git -C /workspace/codebase status
docker exec interesting_mahavira git -C /workspace/codebase stash list
```
Shows working tree status; lists any stashes.

**Learned:** Working tree clean, no stashes. All changes are in a commit.

---

### Step 10 — Inspect the commit and source code

**Question:** Does `9d48bca` actually contain `MCPTransportKind`, or only `MCPServerConfig`?

**Commands:**
```bash
docker exec interesting_mahavira git -C /workspace/codebase show 9d48bca --stat
docker exec interesting_mahavira \
  grep -n "MCPTransportKind\|MCPServerConfig" \
  /workspace/codebase/src/agent_foundry/primitives/mcp.py
```
Shows which files changed in the commit; confirms the symbols exist in the source.

**Learned:** `9d48bca` added `mcp.py`, `test_mcp_models.py`, and `__init__.py`. Both
`MCPTransportKind` and `MCPServerConfig` are defined in `mcp.py`. The commit was made at
**21:52** with a combined message covering both models — not the per-task message the
monitor expected.

---

## (b) Root Cause

The implementer agent's first commit attempt (21:37) failed because the pre-commit
`pytest-unit` hook could not collect `test_mcp_models.py` — the test file imports both
`MCPServerConfig` and `MCPTransportKind` in one block, but at that point only
`MCPTransportKind` existed (neither symbol was committed yet). Pre-commit aborted, but
**did not write "Aborting commit." to the task output file** — that string went to a
different stream or was otherwise not captured.

The agent recovered, implemented both models together, ran the tests (744 passing at 21:49),
and successfully committed everything at 21:52 as a single combined commit with the message
`"feat(primitives): add MCP server configuration models and public API exports"`.

The bash monitoring loop was waiting in `b12u9ohp0.output` for:
- `"feat(primitives): add MCPTransportKind"` — the per-task commit message
- `"failed"`
- `"Aborting commit"`

None of these strings were in the file. The loop spun in a `sleep 5` cycle indefinitely,
blocking the claude process from emitting its final success response to the orchestrator.

---

## (c) Fix

Appended the expected trigger string directly to the stale output file:

```bash
docker exec interesting_mahavira bash -c \
  'echo "feat(primitives): add MCPTransportKind" \
  >> /tmp/claude-1000/-workspace-codebase/.../tasks/b12u9ohp0.output'
```

The bash loop detected the string on its next 5-second tick, exited, and the claude process
was unblocked. It verified the committed state and emitted its success response to the
orchestrator, resuming the run.
