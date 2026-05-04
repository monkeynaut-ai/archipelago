---
feature_slug: fix-summary
created_at: 2026-04-20
---

# Run Observability

## Problem statement

`src/agent_foundry/orchestration/summary.py` reads record.get("agent") when analyzing lifecycle.json for data to include in summary.txt. However, creators of lifecycle events, such as `src/agent_foundry/orchestration/container_executor.py` use "agent_name" when constructing events. An example of an existing event construction is

```python
    lifecycle.append(
        LifecycleEvent.AGENT_INVOCATION_STARTED,
        agent_name=agent_name,
        invocation=invocation,
    )
```

The end result is that when summary.txt is created it does not include any summary of agent activity. Compounding this problem is the fact that ``tests/agent_foundry/orchestration/test_summary.py` codifies this bug by incorrectly constructing a fixture that defines the field "agent" instead of "agent_name" (see `tests/agent_foundry/orchestration/test_summary.py`)

## Feature intent

When a run completes, the summary.txt file written to the artifacts dir must contain a summary for each invoked agents.

Tests construct a fixture that is typed correctly, reflecting the true shape of lifecycle events

## Desired outcomes

### User outcomes

- Sees a summary.txt file that includes agent summaries
- At a glance the user knows if any agent failed during a run
- At a glance the user knows the amount of time an agent spent running

### Business outcomes

- Identify failing agents
- Identify agents that take longer than expected to execute

## Scope boundaries

- No additional metrics or information in the summary. Just fix the visibility problem (agent summaries being skipped).

## Assumptions

- none

## Dependencies

- skip

## Constraints

- No new runtime dependencies

## Acceptance criteria

- Summary.txt file, generated in the artifacts directory at the end of a run contains a summary for each agent invoked during the run
- If an agent is invoked more than once, the summary includes only one summary line for the agent
- If two agents are invoked, the summary includes a summary line for each agent
- The agent summary line includes agent name, total number of invocations, number of successful invocations, number of failed invocations, and average invocation time
