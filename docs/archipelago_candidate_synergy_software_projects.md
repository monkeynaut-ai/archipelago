# Highest-leverage projects (build these first)

### 1) Evaluation & Regression Harness (“Archipelago Evals”)
**What it is:** A framework that continuously runs realistic tasks end-to-end (idea → spec → PR → deploy → monitor) and scores outcomes (correctness, time, cost, defects, latency, user value proxies). Includes golden tasks, adversarial tasks, and “production replay” tasks.

**Why it’s a lever:** Provides the measurement backbone for safe autonomy increases, prompt/model/tool changes, and refactors.

**Time to build:** Low–medium (start narrow with 20–50 tasks, scale).

**Compounding loop:** Every improvement becomes measurable; regressions get caught automatically.

**Minimum viable version**
- Task runner that spins up ephemeral envs, executes a workflow, collects artifacts.
- Scoring layer: unit test pass rate, lint, security scan, spec completeness checks, human rating hooks.
- Trend dashboards + gating (block merges on eval regressions).

---

### 2) “Spec-to-Tests” Generator + Coverage Guardian
**What it is:** From feature specs, generate executable tests: unit/integration/e2e + property tests + contract tests, then enforce “spec coverage” (every requirement maps to at least one test).

**Why it’s a lever:** Reduces regressions and “done-but-not-done” features; increases confidence for autonomous coding/deploy.

**Time to build:** Medium.

**Compounding loop:** Better specs → better tests → faster iteration → more autonomy.

**Minimum viable version**
- “Requirement ID” system; generate test skeletons keyed to IDs.
- Requirement → code → test traceability.

---

### 3) Architecture & Dependency Risk Analyzer (“Change Impact Radar”)
**What it is:** Builds a living graph of modules, APIs, data flows, and dependencies; predicts impact of a change; proposes test plans and rollout strategies.

**Why it’s a lever:** Prevents expensive incidents and reduces review time by making impacts explicit.

**Time to build:** Medium (start with static analysis + heuristics).

**Compounding loop:** Each repo analyzed improves future planning and refactors.

**MVP**
- Parse imports + build graph + “blast radius” reports for PRs.
- Suggest targeted tests based on impacted nodes.
- Flag cyclic dependencies, unstable interfaces, “hot” modules.

---

### 4) Autonomous “CI Triage & Fix” Agent (with Guardrails)
**What it is:** Diagnoses CI failures, proposes fix PRs, runs targeted re-tests.

**Why it’s a lever:** CI failures block throughput and consume time.

**Time to build:** Low–medium (start with flaky tests, lint, formatting, dependency pinning).

**Compounding loop:** Improves pipeline reliability; builds a failure→fix dataset.

**Guardrails**
- Auto-fix only low-risk categories initially.
- Require approval for non-trivial changes; auto-merge for formatting/lint only.

---

### 5) Production Telemetry → Bug Reproduction Pipeline (“Observability-to-PR”)
**What it is:** Converts incidents into reproducible test cases/minimal failing examples, then proposes fixes.

**Why it’s a lever:** Turns production feedback into engineered learning.

**Time to build:** Medium.

**Compounding loop:** Each incident becomes a regression test; reliability improves nonlinearly.

**MVP**
- Error signature grouping + “repro recipe” generation (env, inputs, version).
- Auto-create failing test in sandbox; attach to ticket/PR.

---

## Next tier (strong levers, slightly longer build)

### 6) Decision Journal + Experiment Engine (Product & Tech)
Log decisions as hypotheses with expected metrics and scheduled follow-ups; integrate A/B and offline evals.

### 7) Prompt/Tool/Workflow Optimizer (“Auto-tune Archipelago”)
Use the eval harness to optimize prompts, tool configs, decomposition strategies, reviewer policies.

### 8) Security & Compliance Autopilot
Threat modeling from architecture/specs; dependency vulnerability mgmt; secrets scanning; least-privilege checks.

---

## “Quick wins” that pay back immediately (build in parallel)

### 9) PR Reviewer Agent with a Hard Checklist
Policy-driven review: correctness, edge cases, perf, security, observability, tests, migrations.

### 10) Repo “Bootstrapper” (Golden Path Templates)
One-command creation of services/features with standard layout, CI, observability hooks, deployment, runbooks.

---

# Highest-leverage “bootstrap” projects given Archipelago’s current gaps

### 1) Workflow Orchestrator MVP (“Control Plane Lite”)
**Goal:** Replace manual control/data flow with a minimal, inspectable execution engine.

**Core features (MVP):**
- DAG of steps (agents + tools) with typed inputs/outputs (JSON schemas).
- Artifact store (specs, plans, diffs, test reports) with versioning.
- “Resume from checkpoint” + rerun only affected nodes.
- Human-in-the-loop gates as explicit nodes.

**Payoff:** Repeatable runs, faster iteration on workflows, easier debugging.

---

### 2) Shared Memory & Artifact Canon (“Single Source of Truth”)
**Goal:** Standardize artifacts and their relationships to prevent drift.

**MVP:**
- Canonical objects: ProductBrief, FeatureArchitecture, FeatureSpec, TestPlan, PRPlan, ReleasePlan, Runbook.
- Requirement IDs and trace links.
- Retrieval API: fetch current spec + tests + deploy notes for a feature.

**Payoff:** Less rework, fewer contradictions, improved autonomy.

---

### 3) “Spec Linter” + Consistency Checker
**Goal:** Automatically flag specs that will fail downstream.

**Checks:**
- Missing acceptance criteria, non-testable requirements, undefined terms, inconsistent constraints.
- Interface mismatches between architecture and spec.
- Missing observability requirements.

**Payoff:** Higher spec quality; reduced churn.

---

### 4) Agent Debugger (“Why did you do that?”)
**Goal:** Make runs inspectable without reading raw logs.

**MVP:**
- Decision trace: inputs → assumptions → outputs.
- Diff of what changed in state/artifacts per step.
- Failure classifier: planning vs context miss vs tool error vs code defect.

**Payoff:** Faster tuning and iteration; failures become structured data.

---

### 5) “Human Review Copilot” for Gates
**Goal:** Speed up and standardize human approvals while workflow is still manual.

**MVP outputs per gate:**
- 1-page summary, risk list, test coverage map, rollout plan, rollback plan.
- Red flags: ambiguous requirements, missing telemetry, migration risks.

**Payoff:** Compresses review time; produces consistent feedback for training.

---

## Projects that create compounding feedback loops (dataset + eval + tuning)

### 6) Failure → Fix Corpus Builder
Automatically capture: prompt, artifacts, diffs, failures, final fix; label root cause + fix type.

### 7) Scenario Bank (“Golden Tasks”) Generator
Turn backlog into eval scenarios + scoring rubrics; include adversarial cases.

### 8) Prompt/Policy Versioning + A/B Harness
Version prompt/policy bundles; run A/B against scenario bank; compare quality/cost/speed.

---

## Software that directly reduces cycle time right now

### 9) CI Triage + Auto-Fix (narrow scope)
Focus on flaky tests, formatting, dependency pinning, fixtures, mocks.

### 10) Repo Bootstrapper (“Golden Path”)
Standard templates for service/module + CI + observability + deployment + runbook.

---

## “Missing parts” you can build as software products (agents-as-products)

### 11) Integration Agent (“Glue Engineer”)
Define schemas/adapters between agents; tool wrappers with predictable IO; checkpoints/gates and error handling.

### 12) Release Engineer Agent
Generate release plan/runbook from spec; execute staged rollout.

### 13) Observability Agent
Emit required metrics/logs/traces/dashboards from spec; verify instrumentation in PR.

---

## Decision-making accelerators

### 14) Roadmap & Constraint Solver
Ingest features, dependencies, risk, confidence; output prioritized plan + what-to-cut under slip.

### 15) Architecture Risk Radar
Flag cross-cutting concerns (auth, migrations, multi-tenancy, rate limits, latency budgets); suggest patterns/tests.

---

## Recommended sequencing (given manual workflow today)
1) Control Plane Lite (orchestrator + artifact store + checkpoints)
2) Artifact Canon + Spec Linter
3) Human Review Copilot
4) Scenario Bank + A/B Harness
5) CI Triage Auto-fix
6) Release Engineer + Observability Agent

