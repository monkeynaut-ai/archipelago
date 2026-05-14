# Run Report — MCP tools postmortem

**Feature:** `examples/features/mcp_tools.md`
**Target codebase:** `730alchemy/agent-foundry`, ref `enable-mcp-tools`
**Date:** 2026-05-12

---

## Issue 1: Only change set 1 was delivered despite all four being planned

### Situation

A complete Archipelago run for the "Enable MCP tools" feature produced a PR ([#31](https://github.com/730alchemy/agent-foundry/pull/31)) containing only change set 1 — the MCP server configuration data models. The three remaining change sets (MCP config JSON serializer, `AgentAction.mcp_servers` field and validator, container executor integration) were planned by the TDD planner, tested and implemented by tester and implementer agents that each reported success, and yet produced no code. The run lasted 4 hours and 21 minutes. The `enable-mcp-tools` branch contains exactly one feature commit (`9d48bca`), instead of the nine or more expected.

The change set planner produced a correct four-change-set decomposition. The TDD planner correctly generated detailed, self-contained plans for all four change sets at distinct workspace paths (`/workspace/documents/change-sets/{slug}/tdd_plan.md`). The orchestrator invoked the tester 12 times and the implementer 12 times, covering all four change sets' tasks in the correct order. Every agent reported success. And yet three quarters of the feature never landed. The failure was not in what the orchestrator did — it was in what the agents understood they were supposed to do.

### What went wrong

- **Agent instructions (CLAUDE.md) are written once at container startup and contain change-set-specific context.** The tester and implementer each run in a single container for the duration of the run. At container startup, CLAUDE.md is written with the first change set's specification baked in — including the change set title, the TDD plan file path (`/workspace/documents/change-sets/1-mcp-server-configuration-data-models-and-public-api/tdd_plan.md`), and the acceptance criteria. Those instructions do not change when the container is re-invoked for change sets 2, 3, and 4.

- **The tester and implementer receive no change-set context in their per-invocation prompts.** Every tester invocation — all 12 of them — received the identical prompt: "Follow your instructions to write the failing tests." Every implementer invocation received: "Follow your instructions to implement the change set." With no change set name and no TDD plan path in the prompt, both agents fell back to their CLAUDE.md, which said change set 1. The tdd_planner's prompt correctly includes the change set name ("Plan TDD steps for change set '2. MCP config JSON serializer'"), so it can do the right thing. The tester and implementer have no equivalent signal.

- **The consequence: all twelve later invocations worked on change set 1.** The tester for invocation 2 (intended for change set 1, task 2) read the CS1 TDD plan, found `test_mcp_models.py` already written and the implementation already present, and emitted `clarification_needed`: "The tests I wrote are passing rather than failing as the plan predicts — should I proceed with tasks 2–4 even though implementation already exists?" Invocation 5 (intended for change set 2) asked the same question in slightly different words. Invocation 9 asked again. The pattern repeated across all twelve invocations. Each time, the user answered ("verify green path; if green, exit successfully"), the tester reported success, and the orchestrator moved to the next task — which was still change set 1.

- **The TDD plans for change sets 2–4 exist but were never consumed.** The tdd_planner correctly produced complete, high-quality plans for all four change sets at their respective workspace paths. The plans for CS2–CS4 specify new files to create, complete test code, exact commands, and commit messages. None of that work was attempted because no agent ever read those paths. The artifacts at `runs/2026-05-12-15-52-22/tdd_planner/turns/{2,3,4}/collected_files/tdd_plan.md` are fully actionable but unused.

- **Empty `output.json` files made the failure invisible.** Every tester and implementer turn that reported success produced an empty `{}` as its structured output payload. There is no record of which change set each agent thought it was working on, which tests it ran, or what commits it made. The orchestrator received a stream of successes and had no way to detect that nine of them were vacuous.

- **Human responders treated each clarification as a one-off.** Over 12 tester invocations, 12 separate clarification_needed requests were filed and answered, each with some variant of "verify and exit." No one connected the repetition to a structural problem — that the same question was being asked because the tester was always looking at the same change set.

### Recommended fixes

**Pass change-set context in the per-invocation prompt.** This is the highest-leverage single fix. The orchestrator already injects the change set name into the tdd_planner prompt. It must do the same for the tester and implementer. At minimum, the prompt should include the change set slug and the TDD plan path. A concrete form: `"Plan/test/implement change set '2. MCP config JSON serializer'. TDD plan: /workspace/documents/change-sets/2-mcp-config-json-serializer/tdd_plan.md. Follow your instructions."` This makes each invocation self-contained regardless of what is in CLAUDE.md.

**Separate static role instructions from dynamic run context in CLAUDE.md.** The current CLAUDE.md mixes two distinct lifetimes: role instructions (valid for the container's lifetime) and change-set context (valid for one invocation). The change-set title, file list, TDD plan path, and acceptance criteria should never appear in CLAUDE.md. Those belong in the prompt. CLAUDE.md should say: "Read the current change set from your prompt before acting."

**Add a completion-verification step after each change set.** After the implementer reports success on a change set, the orchestrator (or a lightweight verifier function) should check that the acceptance criteria are objectively satisfied: do the expected files exist, do the unit tests pass, and does the git log show the expected commits? A change set is not done until this check passes — an agent's word is not sufficient. This is the "harness competing tensions" principle applied directly: the verifier is adversarial to the implementer's self-report.

**Add a Critic agent to each change-set loop.** After the implementer completes a change set, a Critic agent reviews the diff against the change set's acceptance criteria and the design document. It has two outcomes: approved (the work is correct and complete) or rejected (with a specific description of what is missing or wrong, routed back to the implementer). The Critic creates the competing force that the current pipeline lacks: every agent currently operates unchallenged. A Critic that can reject work prevents vacuous successes from propagating. The Critic should also check that the implemented scope matches the planned scope — not more, not less.

**Emit meaningful structured output from tester and implementer.** The current success payload is `{}`. It should include: which change set was worked on, which tasks were completed, which files were modified, which test commands were run, and how many tests passed. This structured output serves two purposes: it lets the orchestrator verify change-set identity (if the implementer says it worked on CS1 when CS2 was expected, the orchestrator can catch the mismatch and re-invoke with correct context), and it builds an audit trail.

**Detect and escalate repeated clarification patterns.** When the same agent emits `clarification_needed` with the same or semantically similar question on successive invocations, the responder should treat it as a structural problem rather than a one-off question. An automated responder could detect repetition and escalate to a human with the full pattern, rather than answering the twelfth instance of "should I proceed with change set 1 even though it's already done?" the same way it answered the first.

---

## Issue 2: Stuck agent during change set 1

### Situation

During the run, change set 1 completed successfully in terms of code — all models were implemented correctly, all 25 new tests passed, and the workspace was clean — but the orchestration framework never received the implementer agent's success response. The run stalled for roughly 15 minutes after the commit landed. Investigation revealed that the tester agent had written all four tasks' worth of tests in a single shot rather than incrementally, which forced the implementer to collapse four planned commits into one with a combined message. The monitoring script inside the container was polling a task output file for the exact commit message the TDD plan had prescribed for Task 1; since the actual commit used a different message, the polling loop never exited. The run was unblocked by injecting the expected trigger string into the output file, after which the agent emitted its success response and the run continued.

### What went wrong

- **The tester wrote all four tasks' tests upfront.** Instead of writing only Task 1's tests and stopping, it produced the complete final test file covering all four tasks. This violated the incremental TDD contract the plan was built around.

- **The monolithic import block made partial commits impossible.** Because the test file imported all four symbols at the top level, any state where fewer than four were implemented caused a collection error at pre-commit time. The implementer couldn't commit Task 1's work without also having Tasks 2–4 in place.

- **Four commits collapsed into one.** The plan specified four commits with four distinct messages. The implementer produced one, with a combined message. The granular per-task red-green history was lost.

- **The commit message diverged from the plan.** The monitoring script was polling for `"feat(primitives): add MCPTransportKind"`. The actual commit used `"feat(primitives): add MCP server configuration models and public API exports"`. The trigger string never appeared, and the monitor got stuck.

- **`"Aborting commit."` was never written to the output file.** The first commit attempt failed at the pre-commit hook, but the abort message wasn't captured in the task output file the monitor was watching. So even the failure signal never fired.

- **The `python` executable wasn't on PATH.** The `py-compile` pre-commit hook uses `python -m py_compile` but the container only has `python3` and the venv's `python` on the system path. Every commit attempt failed this hook until the implementer learned to prepend the venv's `bin` to `PATH`.

- **The pre-commit stash behavior caused a false failure.** On one commit attempt, the implementer staged `mcp.py` and the test file but not `__init__.py`. Pre-commit stashes unstaged changes before running hooks, so `TestPublicAPIExports` failed even though all tests passed in the working tree.

### Recommended fixes

**Scope the tester to one task at a time.** The tester's prompt currently receives the full TDD plan. It should receive only the current task's spec plus the existing test file as written so far. With no visibility into future tasks, it cannot write ahead. This is the highest-leverage fix — problems 1–4 all flow from the tester's boundary violation.

**Add a post-tester scope gate.** After the tester produces output, attempt to import the test file against the current codebase state (`pdm test-unit <test_file> --collect-only`). If collection fails with an `ImportError` on a symbol not introduced by the current task, reject the output and retry. This is an objective, cheap check that catches the boundary violation before the implementer ever runs.

**Add an explicit early-exit to the implementer for the collapsed-test case.** Instruct the implementer: before running any tests, check whether the test file imports symbols that don't yet exist in the codebase. If it does, emit `clarification_needed` immediately rather than implementing all tasks in one shot. The agents identified this pattern themselves and wrote it into `lessons-learned.md`; it should be in the implementer's instructions.

**Replace commit-message polling with `git log` inspection.** The monitoring loop fails whenever the agent deviates from the plan's exact commit wording. A more robust signal: after the agent process exits (or after a timeout), inspect `git log` to check whether a commit covering the expected files landed since the session started. Exit code + file presence is stable; commit message strings are not.

**Capture stderr to the task output file.** Pre-commit writes `"Aborting commit."` to stderr. If the output file only captures stdout, the failure signal is invisible to any monitor that watches that file. Redirecting both streams (`2>&1`) removes this blind spot regardless of what monitoring strategy is in use.

**Add a `python` symlink to the Docker image.** The `py-compile` pre-commit hook requires `python` on the system PATH, but the container only provides `python3`. Add `RUN ln -s $(which python3) /usr/local/bin/python` to the Dockerfile. One line, eliminates a hook failure that burned multiple 2-minute pre-commit runs.

**Instruct the implementer to stage all co-required files together.** The plan's `git add` steps already list the files, but the agent staged them selectively on one attempt. Make the instruction explicit: "if your tests depend on changes across multiple source files, stage all of them in a single `git add` before committing — pre-commit stashes unstaged changes and will test the partial state."

**Add prior-completion detection to the implementer.** At session start, the implementer should scan `gitStatus` for a recent commit whose message or scope matches the current change set. If the implementation files already exist and all targeted tests pass, emit `success` without re-running the full task sequence. This prevents redundant work when the orchestrator re-invokes the implementer on already-completed work.

## Notes

- Implementation agent must return feedback that can affect orchestration, e.g. not continue with tasks in change set if that change set is already successfully completed.
