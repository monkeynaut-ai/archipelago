# Run Observability — design pipeline run comparison

**Feature:** `examples/features/run-observability.md`
**Target codebase:** `730alchemy/agent-foundry`, ref `main`
**Pipeline:** `scripts/run_design_pipeline.py` (Phase 2 design pipeline)

Compares two end-to-end designer runs across a sequence of fixes shipped between them. Structured so the per-metric deltas are evidence for which fixes paid off and which need follow-up.

## Runs compared

| Field | Prev | New |
|---|---|---|
| Run timestamp | 2026-04-22 15:51 | 2026-04-25 16:58 |
| Stream JSONL | `runs/2026-04-22-15-51-12/39b6016cdaa5457189b9113a931426d0/designer/turns/0/stream.jsonl` | `runs/2026-04-25-16-58-39/b99556aed6104d219d7c3cccfbcc6363/designer/turns/0/stream.jsonl` |
| Stream size | 780,151 bytes | 648,764 bytes |

## What changed between the two runs

| Change | Where | PR(s) |
|---|---|---|
| `StructuredOutput` injection unblocked (strip `x-agent-file-path` from sanitized schema) | agent-foundry | #14 |
| `AGENT_USER_UID` / `AGENT_USER_GID` exposed as importable constants | agent-foundry | #15 |
| `_default_artifacts_dir` writes to `<cwd>/.tmp/` instead of `/tmp/` | agent-foundry | #16 |
| Designer instructions: feature values de-inlined from CLAUDE.md | archipelago | #8 |
| Designer instructions: delegation-first investigation, LSP override | archipelago | #8 |
| Designer instructions: hard investigation-summary gate (`AgentFilePath`) | archipelago | #8 |
| `_workspace_ops.prepare_documents_dir` chowns to `AGENT_USER_UID:GID` | archipelago | #8 |

## Headline numbers

| Metric | Prev | New | Delta |
|---|---:|---:|---|
| Wall-time duration | 762 s | 378 s | **−50%** |
| Total cost (USD) | $1.5950 | $0.9199 | **−42%** |
| Logical turns | 41 | 31 | −24% |
| Run's `num_turns` | 34 | 18 | −47% |
| `input_tokens` | 3,948 | 7,780 | +97% |
| `cache_read_input_tokens` | 1,480,763 | 414,359 | **−72%** |
| `cache_creation_input_tokens` | 103,451 | 61,745 | −40% |
| `output_tokens` | 36,906 | 17,526 | −53% |

## Tool-call distribution

| Tool | Prev | New | Notes |
|---|---:|---:|---|
| `StructuredOutput` | 0 | **1** | agent-foundry #14 fix verified end-to-end |
| Read | 37 | 39 | delegation push didn't reduce direct reads |
| Grep | 1 | 7 | |
| Glob | 3 | 5 | |
| Agent (Explore subagent) | 1 | 3 | modest movement |
| Bash | 26 | 1 | agent stopped using shell as a side-channel |
| Write | 2 | 2 | one each for `investigation.md` and `design.md` (new run) |
| ToolSearch | 2 | 2 | |
| Skill | 0 | 1 | |
| LSP | 0 | 0 | LSP override held |

## Wins

- **`StructuredOutput` end-to-end.** Schema sanitation (agent-foundry #14) restored tool injection. The agent emitted a structured envelope rather than relying on the text-fallback parser.
- **De-inlining feature values reduced context overhead.** `cache_read_input_tokens` dropped 72%; total run cost halved. CLAUDE.md is now role-defining instead of feature-specific, and the agent reads the feature definition from the workspace file.
- **Bash side-channel went away.** 26 → 1. The previous run was leaning on shell scripts to probe the codebase; the new run isn't.
- **LSP-first override held.** Zero LSP calls in the designer role even though the agent-worker preamble's LSP-first rule still applies elsewhere.
- **Investigation-summary gate works.** `investigation.md` was written; `AgentFilePath` verification accepted the run.
- **Docs dir ownership fix worked.** Designer wrote `design.md` to `/workspace/documents/design.md` directly (no fallback to `/workspace/output/`).

## Concerns

- **Delegation barely moved.** Read 37 → 39, Agent 1 → 3. The "default to delegation, >2 files = delegate" wording reads as preference, not directive. Read-to-Agent ratio is still ~13:1. Two paths forward:
  1. **Stronger wording:** make it imperative ("Direct file reads are forbidden for codebase investigation; use Agent.").
  2. **Tool restriction:** remove Read from the designer's tool allowlist when agent-foundry supports per-primitive allowlists. Forces compliance.
- **`input_tokens` doubled** (3.9K → 7.8K) while cache reads dropped. Suggests cache hit rate per call shifted (more uncached prompt content per turn). Not a cost regression — total cost dropped — but worth understanding why.
- **Investigation summary substance not yet verified.** Confirmed the file exists; not yet checked whether it's substantive (what was learned, what's uncertain) versus a placeholder satisfying the gate.
- **Design quality not yet evaluated.** Final `design.md` hasn't been read to judge whether the Read-heavy investigation produced a worse design than fewer-Read+more-Agent would have.

## Open hypotheses for the next iteration

- If we tighten the delegation directive (option 1 above) and run again, expect Read to drop and Agent to rise. If Read stays high, the wording isn't the lever — the agent's heuristic about delegation cost vs. inline read is what dominates.
- If `input_tokens` per turn keeps rising, we may want to look at what's getting added to context turn-over-turn. Investigation summary written into the workspace doesn't get auto-loaded into the prompt, but maybe other artifacts are.

## Inspection commands

```bash
# Re-derive the headline numbers
python3 scripts/inspect_stream.py --summary \
    runs/2026-04-25-16-58-39/b99556aed6104d219d7c3cccfbcc6363/designer/turns/0/stream.jsonl

# Pull the agent's text-block reasoning (no tool payloads)
python3 scripts/inspect_stream.py --text-only \
    runs/2026-04-25-16-58-39/b99556aed6104d219d7c3cccfbcc6363/designer/turns/0/stream.jsonl

# Pull the StructuredOutput envelope
python3 scripts/inspect_stream.py --envelope \
    runs/2026-04-25-16-58-39/b99556aed6104d219d7c3cccfbcc6363/designer/turns/0/stream.jsonl

# Read investigation summary and design from the volume
docker run --rm -v archipelago-ws-run-observability-<...>:/workspace alpine:3.20 \
    cat /workspace/documents/investigation.md
docker run --rm -v archipelago-ws-run-observability-<...>:/workspace alpine:3.20 \
    cat /workspace/documents/design.md
```
