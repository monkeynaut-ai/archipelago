# Plan: Analyze run `c94ecba6…` (52m48s, simple fix)

## Context

The user ran the Archipelago pipeline on a small change (rename 2 properties, update 2
tests) and the end-to-end wall clock was **52m48s**. We want to understand **where the
time went** *and* **why** — i.e., not just per-stage timing, but how the system topology,
per-agent instructions, and per-agent configuration contributed to the cost. The
deliverable is an analysis report that pairs each major time expenditure with at least
one plausible causal hypothesis grounded in the topology / instructions / config of the
specific agents involved.

The run artifacts live at:
`runs/2026-05-08-20-10-11/c94ecba6821846fba612d079a7a8765e/`

## What we'll cross-reference

The analysis pulls from three layers and joins them by agent name:

### Layer A — runtime artifacts (the run itself)

- **`lifecycle.jsonl`** — per-event timeline. Has `agent_invocation_started/completed`,
  `turn_started/completed`, `function_action_started/completed`, `agent_container_started`,
  and `responder_requested/answered`. Outcome of each turn is tagged
  (`success` / `clarification_needed` / etc.), which lets us spot rework cycles.
- **`<agent>/turns/<n>/stream.jsonl`** — full Claude SDK stream per turn: every assistant
  message, tool_use, tool_result, thinking block, and a per-message `usage` object with
  `input_tokens` / `output_tokens` / `cache_read_input_tokens` / `cache_creation_input_tokens`.
- **`<agent>/turns/<n>/prompt.txt`** and **`output.json`** — what each agent was asked
  and what it returned (envelope outcome + payload).
- **`<agent>/CLAUDE.md`** — the *baked-in* system prompt for that role on this run
  (template after variable resolution). Lets us tie behavior back to instructions
  exactly as the agent saw them.
- **`<agent>/container.log`** — sandbox stdout / pre- and post-turn hook latency.

### Layer B — system topology (`src/archipelago/systems/pipeline.py`)

The pipeline is a nested Sequence/Loop. Reading `full_pipeline` in `pipeline.py`:

```
workspace_bootstrap
  → designer
  → change_set_planner
  → Loop over change_sets:
      prepare_change_set_workspace
      → log_change_set_name
      → tdd_planner
      → Loop over tasks:
          log_tdd_plan_task
          → tester
          → implementer
  → pr_creator
```

Implications for the analysis:

- The 11 invocations / 13 turns observed are loop iterations of this topology.
  Multiple `tester` / `implementer` invocations are **inner-loop iterations**
  (per-task), not retries — but multiple `tdd_planner` invocations *are* re-entries
  of the per-change-set body, which is anomalous and likely the symptom of upstream
  output being insufficient.
- Sequential dependencies are baked in: tester must finish before implementer
  starts on the same task; the inner loop blocks the outer. Therefore the wall
  clock is roughly the sum of all stages, with no parallelism wins available
  without changing the topology.
- The `responder_provider=static_provider(StdinResponder())` means a
  `clarification_needed` outcome blocks the run on a human at the terminal.
  Any responder-wait gap is purely a process-design cost, not a model cost.

### Layer C — per-agent configuration (`src/archipelago/config.py`, `agents/<role>/primitive.py`)

Pull the model, effort, timeout, container-reuse policy, and gid grants for each role:

| agent | model | effort | reuse policy | timeout | gids |
|---|---|---|---|---|---|
| designer | OPUS_4_7 | HIGH | (read primitive) | (read primitive) | (read primitive) |
| change_set_planner | SONNET_4_6 | HIGH | … | … | … |
| tdd_planner | SONNET_4_6 | (default) | … | … | … |
| tester | HAIKU_4_5 | (default) | REUSE_NEW_SESSION | 1800s | DOCUMENTS, TESTS |
| implementer | SONNET_4_6 | (default) | REUSE_NEW_SESSION | 1800s | DOCUMENTS, CODEBASE |
| pr_creator | HAIKU_4_5 | (default) | … | … | … |

The blank cells get filled in during analysis (one Read per `primitive.py`). This table
is the ground truth for "is this agent slow because the model is big, the effort is high,
or the prompt asked for a lot?"

### Layer D — per-agent instructions

For each role, compare:

- the **template** at `src/archipelago/agents/<role>/instructions_template.md`, and
- the **resolved** copy at `runs/.../<role>/CLAUDE.md` (post variable substitution).

The resolved copy shows exactly what the agent saw — including the change-set blob
(currently a multi-paragraph dump, e.g. ~100 lines for the implementer of this run).
Long, narrative instructions are a hypothesis-rich place to look when an agent
fans out way more than the scope warrants.

The presence of `tdd_planner/instructions_template-orig.md` next to
`instructions_template.md` is a hint that the TDD planner instructions are mid-iteration —
worth noting which version this run used.

## Analysis steps

### Step 1 — Wall-clock timeline (the "where")

Parse `lifecycle.jsonl` and build a per-agent, per-turn Gantt-style timeline. For every
adjacent pair of events, classify the gap as:

- **Agent work** — between `turn_started` and `turn_completed`.
- **Responder wait** — between `responder_requested` and `responder_answered`
  (human-in-the-loop pause after a `clarification_needed` outcome).
- **Container/orchestration** — gap between `agent_invocation_completed` of agent N
  and `agent_invocation_started` of agent N+1; also between `agent_invocation_started`
  and the first `turn_started` (container spin-up vs. session-reuse delta).
- **Other idle** — anything left over.

Output: a table of agent → invocation → wall-clock duration → outcome, plus a category
roll-up (work / responder-wait / container-overhead / other) summing to 52m48s.

### Step 2 — Per-turn fan-out (the "what was the agent doing")

For each `stream.jsonl`, count:

- assistant messages, `tool_use` calls (broken down by tool name), thinking blocks
- total `output_tokens` and total `cache_creation` + `cache_read` input tokens
- the wall-clock duration of the turn (from lifecycle)

Flag turns where tool-call or assistant-message count is wildly disproportionate to
the apparent scope. (Already-visible signal: `implementer/turns/1` has 100 assistant
messages and 58 `Bash` calls in a single turn — the fingerprint of an agent thrashing
or over-exploring.)

For any `Agent` tool calls found, check whether the parent agent's subsequent messages
actually consumed the subagent's summary — look for the subagent result being
referenced in the next assistant message — or whether the parent re-read the same files
independently anyway. A subagent spawn followed by redundant direct reads is wasted
work: the agent paid for delegation and then ignored it.

### Step 3 — Iteration / rework analysis (the "why so many invocations")

The expected happy path through the topology for a single change-set / single-task
rename is:

```
workspace_bootstrap, designer, change_set_planner,
prepare_change_set_workspace, log_change_set_name, tdd_planner,
log_tdd_plan_task, tester, implementer,
pr_creator
```

Compare to actual:

- **11 agent invocations, 13 turns**
- `tdd_planner` invoked twice; `tester` invoked 3× across 5 turns;
  `implementer` invoked 3×

For each *re-entry* or extra turn, identify the trigger:

- For `clarification_needed` outcomes, read the request payload (search
  `lifecycle.jsonl` for `responder_requested.kind` and the matching
  `output.json` of the requesting turn).
- For repeated invocations of the same agent role, read the prior agent's
  output and the next agent's prompt — what handoff broke?

### Step 4 — Token economy / prompt bloat

For each agent invocation, sum input vs output tokens and the cache-read fraction.
Healthy: high cache-read across same-session turns; suspicious: high `cache_creation`
on every turn (prompt rebuilt or workspace context churning). Also compute output
tokens-per-second to flag turns dominated by think-time vs. generation. This catches
inefficiencies invisible in raw timing (e.g., a fast turn that nevertheless burned a
huge prompt).

Compute a cache efficiency ratio per agent:
`cache_read_input_tokens / (cache_read_input_tokens + cache_creation_input_tokens)`.
A ratio below ~0.5 on a multi-turn agent means the agent is paying to build cache but
not reusing it — usually caused by a churning workspace context or a prompt rebuilt
from scratch each turn. Flag agents below 0.4.

For each turn's `result` event, also extract `total_cost_usd` and the per-model
breakdown from `modelUsage`. Sum to a per-agent cost and a run total. This is already
computed by the SDK — no pricing table needed. Flag any agent whose cost fraction is
disproportionate to its share of wall time (cheap model but massive prompt = token-cost
outlier; expensive model on a trivial task = model-selection outlier). Include a cost
column in the per-agent table from Step 1.

### Step 5 — Topology + config + instructions join (the "why")

For each top-N time contributor from Step 1, layer in the matching context from
Layers B/C/D and write a short causal hypothesis. Examples of the kind of joined
finding to produce:

- *"Designer took 3m28s — model is OPUS_4_7 at HIGH effort, the most expensive in the
  pipeline; for a 2-property rename the design step did N tool calls and produced
  M tokens of design doc, suggesting the prompt does not short-circuit on trivial
  scope. Hypothesis: instruction template treats every change as worth full design
  exploration."*
- *"Implementer turn 1 took 10m / 100 messages / 58 Bash calls — model is SONNET_4_6,
  resolved CLAUDE.md is ~100 lines including the full multi-paragraph change-set
  description. Hypothesis: the verbose change-set blob plus open-ended instructions
  invite re-investigation rather than direct edit."*
- *"Tester invocation 2 = 13m07s, of which 10m45s is responder wait. The responder
  payload says `<X>`; the upstream artifact (TDD plan) at the time said `<Y>`.
  Hypothesis: the TDD-planner template's output schema permits ambiguity that
  manifests downstream as a tester clarification."*
- *"Designer spawned N subagents for codebase investigation but then made M direct
  Read/Grep calls covering the same files. If the subagent summaries were sufficient,
  those follow-up reads are redundant. Hypothesis: the investigation instructions say
  'confirm with narrow follow-ups' but the threshold for what counts as narrow is not
  defined, so the designer defaults to re-reading."*

These are the shape of the conclusions, not the conclusions — the analysis is what
turns the placeholders into named, evidenced findings.

### Step 6 — Synthesize the report

Three sections:

1. **Where the 52m48s went** — stacked-bar / table breakdown by agent and by
   category (model work / responder wait / container overhead / rework loops).
2. **Top contributors, ranked** — name the 3–5 biggest time sinks with timestamps,
   a quoted snippet from the relevant turn, and the matching topology / config /
   instruction context that frames the cost.
3. **Recommendations** — for each top contributor, what would have prevented it.
   Distinguish: (a) instruction-template fixes, (b) per-agent config changes
   (e.g., model/effort downgrade), (c) topology changes (e.g., scope-detection
   short-circuit before designer), (d) responder-protocol changes
   (e.g., auto-answer trivial clarifications).

## Initial signals already visible (preview, not the final report)

A first pass on `lifecycle.jsonl` already surfaces three likely dominators — the real
analysis will validate, quantify, and add the why:

- **Tester invocation 2 = 13m07s, the single biggest segment.** ~10m45s of it is a
  responder wait (`01:42:35 → 01:53:20`). The run was *blocked on a human*, not on
  the model. ~20% of total wall clock. Tester is on HAIKU_4_5 so the model itself
  is cheap; the cost is the protocol.
- **Implementer invocation 1 = 10m00s with 100 assistant messages / 58 Bash calls
  in one turn.** Massive fan-out for a 2-property rename. SONNET_4_6 with the long
  resolved instruction template — likely an instruction-template + prompt-bloat
  story.
- **Three implementer × three tester iterations** for a 2-prop / 2-test change.
  Each loop costs both rework and agent re-spin overhead. Plus `tdd_planner` ran
  twice — implies the first TDD plan was insufficient and was re-issued, which
  is a *topology* observation (the inner loop kept re-entering or the change-set
  body was retried).

## Critical files / artifacts

Runtime:
- `runs/2026-05-08-20-10-11/c94ecba6821846fba612d079a7a8765e/lifecycle.jsonl`
- `runs/.../<agent>/turns/<n>/stream.jsonl` — 13 files
- `runs/.../<agent>/turns/<n>/{prompt.txt,output.json}`
- `runs/.../<agent>/CLAUDE.md` — resolved instructions (6 files)

System:
- `src/archipelago/systems/pipeline.py` — topology (`full_pipeline`)
- `src/archipelago/config.py` — per-agent model + effort
- `src/archipelago/agents/<role>/primitive.py` — timeouts, reuse policy, gids
- `src/archipelago/agents/<role>/instructions_template.md` — pre-resolution templates
  (compare to baked CLAUDE.md to see what variables expanded into)

No code in `src/` will be *modified* for the analysis itself. Recommendations from the
report may name changes; those are follow-ups, not part of this work.

## Verification

- Per-agent durations from Step 1 must sum (with overhead) to **52m48s** ±5s
  against `summary.txt`. Mismatch ⇒ lifecycle gap or double-counting.
- Total tool calls counted in Step 2 should match
  `grep -c '"type":"tool_use"' <stream files>` as a cross-check.
- Each `clarification_needed` turn outcome in Step 3 should pair with a matching
  `responder_requested` / `responder_answered` event pair on the same `request_id`.
- The per-agent config table in Layer C must be filled from actual files, not
  guessed — every cell traces to a line in `config.py` or `primitive.py`.

## Out of scope

- Comparing this run to other runs (cross-run trend study is separate).
- Modifying agent prompts, config, or pipeline code. Deliverable is a report;
  fixes are follow-ups.
