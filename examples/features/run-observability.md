---
feature_slug: run-observability
created_at: 2026-04-20
---

# Run Observability

## Problem statement

Archipelago runs are opaque. We have no structured view of what agents do during a run: how much time they spend, how many tool calls they make, how many tokens they consume, how they terminate, whether they retry. Without this visibility, tuning agent instructions, diagnosing pathologies (rabbit-holing, retry loops, excessive token burn), and comparing agent behavior across runs rely on scattered logs and guesswork. The longer Archipelago operates without first-class observability, the harder it becomes to evaluate whether changes to agents and the platform are improvements.

## Feature intent

Establish a first-class observability layer for Archipelago agent runs. Each run produces a structured record of per-turn metrics for every `AgentAction` that executes. The record lives on the host filesystem, is inspectable immediately (streamed during the run), and is accompanied by a simple summary tool so humans can see totals without hand-parsing. Future observability layers (run-level, primitive-level, cross-run aggregation) build on this foundation; this feature establishes the mechanism and the persistence abstraction they will share.

## Desired outcomes

### User outcomes

- After every run, Archipelago developers can inspect what each agent did: time per turn, tool calls, tokens consumed, terminal outcome.
- When an agent misbehaves (rabbit-holes, retries excessively, times out), the observability data identifies where and how.
- Archipelago developers can compare metrics across runs to judge whether changes to instructions or tools improved agent behavior.
- For long or crashed runs, developers can see what the agent was doing at the moment of interruption.

### Business outcomes

- Agent tuning becomes evidence-driven instead of guess-driven.
- Token costs are visible and can be controlled by architectural changes.
- Pathological agent behaviors are detectable early, not after months of accumulated inefficiency.
- The observability abstraction establishes a foundation for future run-level, primitive-level, and cross-run tooling without re-architecting.

## Scope boundaries

- Not a real-time dashboard — inspection is post-run, via files on disk.
- Not cross-run aggregation or querying — each run is inspected individually in v1.
- Not a visualization layer — humans read JSONL or the summary text; no charts or UI.
- Not a retention or cleanup policy — observability files accumulate on disk; users manage their own cleanup.
- Not run-level or primitive-level observability — v1 is agent-turn-level only; other layers are deferred.

## Assumptions

- Runs are bounded in duration — they complete in minutes to low hours, not days, so per-run file sizes stay manageable.
- The host running Archipelago has sufficient disk space for per-run observability files.
- Claude Code's stream-json output exposes per-turn metrics (tool calls, token usage, stop reasons) in a parseable form.
- Concurrent runs are rare enough in v1 experimentation that simple file-per-run isolation is adequate — no need for write locks or explicit coordination.

## Dependencies

- Agent Foundry's lifecycle emission mechanism from CS7 Plan 2 — the observability sink consumes events the runtime already emits.
- Claude Code's stream-json output format — the source of per-turn metrics.

## Constraints

- No new runtime dependencies — use the Python standard library plus existing project dependencies. Adding a new PyPI dep (e.g. structlog, OpenTelemetry) introduces weight Agent Foundry's minimal-dep ethos does not accept.

## Acceptance criteria

- Each agent turn produces an event record with these fields: `turn_index`, `started_at`, `ended_at`, `duration_s`, `tool_calls_by_tool`, `tokens` (input, output, cache_read, cache_write), `subagent_spawns`, `stop_reason`, `outcome_kind`, `resume_retries`, `model`.
- Events are persisted on the host filesystem at a path rooted in the current working directory.
- Events are streamed — written as they occur during the run, not batched at run end.
- If a run crashes mid-execution, events emitted before the crash are preserved on disk.
- Concurrent runs each preserve their observability data in isolation — no collisions, overwrites, or data loss — regardless of how many runs execute simultaneously.
- A per-run summary helper, invocable from the command line with a run ID, produces totals: total duration, tool-call breakdown, aggregated token usage, terminal outcome.
- Persistence is implemented behind an abstraction — changing from JSONL files to an alternate mechanism (SQLite, external DB) requires no changes to event emission or consumer tooling.
