# Archipelago Vision

*Status: living document. Revised as understanding deepens. Not a specification; not a plan. The frame the rest of the project sits inside.*

*Last revised: 2026-04-20.*

---

## 1. What Archipelago is

Archipelago is a **system of agents** — AI models, humans, services, programs — that collaborate to do real software engineering work, autonomously where possible, with human involvement only where the work genuinely needs it.

**Inputs it accepts** (and will accept more of over time):

- A specific issue or bug to resolve.
- A large feature to implement.
- An architectural or design change (e.g., refactor a package for cohesion).
- An optimization request.
- A security or correctness audit.

**Outputs it produces:** committed code, tests, documentation, and (eventually) opened PRs or merged changes, produced by coordinated agents working over a shared workspace.

**What it is not:**

- Not a single monolithic agent prompted with "please implement X." Archipelago's bet is that coordinated specialist agents beat one generalist.
- Not a frozen pipeline. Every agent, every boundary, every instruction is treated as an experimental variable; the architecture is shaped to make experimentation cheap.
- Not a chatbot. Agents communicate through structured artifacts in a shared workspace, not through conversation turns.

---

## 2. North stars

**Primary — autonomous software engineering.** The long-term goal is to do real software engineering work with minimal human involvement. Progress is measured by how much work Archipelago handles end-to-end without intervention, and at what quality.

**Secondary — excellence on the mother lode.** Large feature implementation is the hardest input class and the one with the highest payoff — economically and intellectually. Other input classes (bug fixes, audits, optimizations) are solved well enough by ad-hoc scripted systems today. Feature implementation is the open frontier, and Archipelago's design pivots around getting this case right.

**Tertiary — compound experimentation.** Archipelago's value accrues over time only if experimenting with agent design is *cheap*. Every architectural choice is evaluated against: does it make the next experiment easier, or harder?

**Others**

- for now humans are the bottleneck, especially human code/design/architecture reviews. Archipelago must make reviews simple. For example, providing sequence and component diagrams. Visual information carries a lot more information. Keep them up to date
- minimize document and knowledge pain. Keep docs uptodate. Preferring using code to document (e.g. how-to's as tests). After each PR merge, purge + merge + clean documentation.

---

## 3. Operating philosophy

The principles that shape every design decision. Each is load-bearing: if you remove it, the architecture changes shape.

### 3.1 Harness competing tensions

**Belief.** Good software emerges from opposing objectives held in *productive conflict*, not from collapsing or ignoring the tension. Any nontrivial software-engineering task has multiple pulls — elegance wants one thing, shippability another; optimism ("this will work") wants one thing, pessimism ("what will break") another. A single mind (or agent) trying to satisfy all pulls simultaneously produces watered-down output where each pull weakens the others. Separating the pulls into distinct actors, each with a *coherent* objective, lets each objective reach its full strength — and the results combine through structured exchange.

**Method.** Four steps, applied recursively at any level (pipeline, agent, function, field):

1. **Enumerate functions.** List the logical things that must happen between the input and the output. Don't assume they map one-to-one to agents.
2. **Map each function's natural pull.** What does it optimize for? What does it treat as primary? What stance does it take (synthesis vs. analysis, forward vs. backward, creator vs. critic, optimist vs. pessimist)?
3. **Cluster by pull-compatibility.** Group functions whose pulls *reinforce* each other — same time horizon, same mode, same stance. Split functions whose pulls *undermine* each other.
4. **Assign each cluster to one agent** (or component, or phase — the method is level-agnostic). The cluster's shared pull becomes the agent's coherent objective.

**Consequence.** Agents in Archipelago are derived from tension analysis, not imported from industry convention. If "Designer" and "Planner" exist as separate agents, it's because the tensions between their functions are strong enough that one agent fighting itself would produce worse output than two agents each pulling cleanly.

#### Worked example — deriving the feature-implementation middle layer

*Setup.* A job specification (objectives, constraints, acceptance criteria, assumptions) enters on one side. An implementation kernel (test agent + implementation agent) is on the other. What goes in between?

*Step 1 — functions.*

1. Codebase context gathering — understand current state.
2. Design — target state: components, capabilities, interfaces, data flow, control flow.
3. AC handling — refine fuzzy "done" into concrete, testable criteria.
4. Test strategy — what to test, at what level, with what fixtures.
5. Decomposition — break the feature into shippable change sets.
6. Sequencing — order change sets by dependency.
7. Step planning — within one change set, the TDD red/green/refactor sequence.

*Step 2 — pulls.*

| Function | Natural pull |
|---|---|
| Context gathering | absorb current state; breadth |
| Design | coherence, elegance, the *whole* target state |
| AC handling | concreteness, adversarial edge cases |
| Test strategy | verifiability, risk coverage |
| Decomposition | shippability, incremental value, slices that stand alone |
| Sequencing | dependency logistics |
| Step planning | micro-rhythm discipline: one thing at a time |

*Step 3 — tensions.*

- **Coherence (Design) vs. shippability (Decomposition) — severe.** One agent doing both fights itself: either elegance wins and change sets don't stand alone, or shippability wins and the design hollows out.
- **Forward synthesis (Design) vs. backward analysis (Context gathering) — mild.** Different time direction but both synthesis-minded; compatible in one agent.
- **Zoom level — severe within one agent.** Decomposition thinks in slices; step planning thinks in TDD cycles. Holding both scales at once is how humans lose track; agents will too.
- **Optimism vs. pessimism (and its ladder)**. Test strategy isn't one job; it's three, each paired to its partner.
  - Feature rung: pessimism = "what could break end-to-end, integration risks" → partners with Design (testability is a design property, shapes architecture).
  - Change-set rung: pessimism = "what fixtures/mocks/seams does this slice need" → partners with Decomposer.
  - Step rung: pessimism = "this assert before this line of impl" → partners with Planner.
- **Creator (Design) vs. critic (rigorous AC / tests) — real but deferrable.** Can be separated now (critic agent) or deferred to a later Reviewer.

*Step 4 — harmony clusters.*

| Cluster | Mode | Horizon | Functions |
|---|---|---|---|
| A — Understand + envision | synthesis | feature | context gathering, design, feature-level AC refinement, feature-level test strategy |
| B — Slice + order | pragmatic shipping | change-set | decomposition, sequencing, CS-level AC, CS-level test-strategy hints |
| C — Verify + execute rigor | discipline | step | step planning, step-level AC, step-level test strategy |

*Result.* Three agents:

- **Designer** owns Cluster A.
- **Decomposer** owns Cluster B.
- **Planner** owns Cluster C, invoked once per change set.

Every split is justified by a tension severe enough that collapsing it would degrade output. Every grouping is justified by pulls that reinforce.

### 3.2 Workspace-mediated communication

Agents exchange work through structured artifacts in a shared workspace (currently a Docker volume; eventually a git-versioned repo), not through direct typed RPC. Each artifact is rendered from, and parsed back into, a Pydantic model that serves as its template.

**Why it's a principle, not a detail.** It trades schema rigidity for experimentation velocity. Splitting one agent into two means both read and write additional files, not a schema migration. A new agent in the middle means new files in the workspace, not rewiring the boundary types of existing agents.

Full argument: `docs/plans/2026-04-03-review-feedback-loop-design.md`; locked decisions in the design doc's "inter-agent communication model" section.

### 3.3 Single-source-of-truth data models

One change to a Pydantic model — a field rename, a new field, a constraint tweak — propagates without any other edits to every artifact derived from it: rendered markdown templates, parsers, validators, JSON schemas, instruction appendices, generated skeletons, prompts (eventually), and downstream typed consumers. The architectural bet is that *this* is what makes the experimentation north star affordable.

Mechanism and roadmap: `agent-foundry/docs/architecture/adr_markdown_template_model_shape.md` (ADR), with the gap list — currently uncovered touchpoints — carried in the parent plan `docs/plans/2026-04-17-cs7-plan4-archipelago-agents-plan.md`.

### 3.4 Experimentation-first

Every architectural axis — topology, instructions, division of tasks, I/O shape, prompts, data flow, control flow — is treated as a parameter to experiment with, not a default to lock. If experimenting with a given axis is expensive, the architecture has failed, regardless of how well the current configuration works.

Full framing: the "this is an experimentation platform, not a frozen pipeline" section of `docs/plans/2026-04-17-cs7-plan4-archipelago-agents-plan.md`.

### 3.5 [Further principles as they emerge]

---

## 4. How philosophy shapes the architecture

*This section bridges principles (§3) to concrete design decisions. Each principle should point to the choices it produced; if it can't, either the principle isn't load-bearing or the design hasn't absorbed it yet — both worth knowing.*

- **3.1 (tensions)** → Designer / Decomposer / Planner split for the feature-implementation middle layer (see worked example above). Further applications TBD as other pipelines are designed.
- **3.2 (workspace-mediated)** → Agents consume markdown documents from known workspace paths and emit markdown to known workspace paths; envelopes are thin pointers, not payloads. Applied in Reviewer design in parent plan.
- **3.3 (single source of truth)** → Agent Foundry `markdown` package: annotation-driven domain models that derive template, parser, validator, and (Phase 2) JSON schema + instruction appendix from one Pydantic class.
- **3.4 (experimentation-first)** → Construction tiers (0: raw → 3: generated) are first-class in Agent Foundry. Swapping tiers for a single agent is a first-class experiment, not a rewrite.

*Populated incrementally as each principle accumulates concrete consequences.*

---

## 5. Current shape (pointer index — not content)

### Agent roster

**Designed, under active brainstorm:**

- **Designer** — Cluster A. Feature-level understanding and design.
- **Decomposer** — Cluster B. Feature → ordered change sets with CS-level AC.
- **Planner** — Cluster C. Per-change-set TDD step plan.

**Planned, design not yet started:**

- Reviewer — change-set-level code review (feedback-loop closing).
- Integrator — merge/integrate change-set outputs.
- Dispatcher — route work to agents.
- `CommitAction` / `SubmitPRAction` — function actions for git operations.

**Shipped in Archipelago:** none yet.

### Platform (Agent Foundry) capabilities

- CS1–CS3 primitives (models, validators, compiler) — shipped.
- CS5 data-model layer — shipped.
- CS6 / CS6.5 agent output models + structured-output protocol — shipped.
- CS7 Plan 1 `AgentAction` primitive — shipped.
- CS7 Plan 2 lifecycle orchestration — shipped.
- CS7 Plan 3 base image — shipped.
- CS7 Plan 4 Phase 1 markdown machinery — shipped (`agent_foundry.markdown` package).

### Active design docs

- `docs/plans/2026-04-03-review-feedback-loop-design.md`
- `docs/plans/2026-04-03-review-feedback-loop-roadmap.md`
- `docs/plans/2026-04-17-cs7-plan4-archipelago-agents-plan.md`
- `docs/plans/2026-04-17-cs7-plan4-phase1-markdown-machinery-design.md`
- `docs/plans/2026-04-17-cs7-plan4-phase1-implementation-plan.md`
- `agent-foundry/docs/architecture/adr_markdown_template_model_shape.md`

---

## 6. Open threads

- **Designer / Decomposer / Planner I/O shapes.** Under active brainstorm. Next up after vision doc lands.
- **Codebase context: separate Investigator agent, or a tool Designer wields?** Open. Leaning tool-for-Designer at Archipelago-scale targets.
- **Design-critic loop: now or later?** Leaning later — the creator-vs-critic tension (§3.1) is naturally served by the future Reviewer agent, not a separate critic in this phase.
- **AC ladder.** Tentatively: feature-level AC lives in the job spec (input); change-set-level AC emerges from Decomposer; step-level AC emerges from Planner. Confirm during I/O design.
- **Test-strategy ladder.** Tentatively: feature-level in Designer; CS-level in Decomposer; step-level in Planner. Confirm during I/O design.
- **Agent Foundry Phase 2 scope.** Driven by Designer agent's concrete platform needs, not pre-scoped.
- **Experimental-tier platform couplings.** Agent Foundry's public-API policy (its `docs/reference/public-api.md`) marks `agent_foundry.agents` (incl. `ContainerConfig`), `orchestration.run_agent_in_container`, run-hook event types, and `mlflow_adapter` as Experimental — importable but liable to change pre-1.0. Archipelago's containerized-agent path depends on all of these; expect re-migrations on future syncs. A ruff banned-api guard keeps imports on the sanctioned facades so a shape change surfaces in one place.

---

## 7. Glossary

- **Feature** — a cohesive unit of capability to add to the system. Usually requires multiple change sets.
- **Change set** — a shippable slice of a feature. Independently valuable and testable. Archipelago's vocabulary matches its own development: this project's own roadmap is organized as CS1, CS2, ....
- **Step** — a single red/green/refactor cycle within a change set.
- **Agent** — an actor (AI model, human, service, program) that performs work in the system.
- **Action / primitive** — a unit of work an agent can execute. `AgentAction` (LLM-driven) and `FunctionAction` (code-driven) are the two types in Agent Foundry.
- **Workspace** — the shared substrate (file system, mounted volume, eventually a git-versioned repo) through which agents communicate.
- **Harmony cluster** — a set of functions whose natural pulls reinforce rather than undermine, grouped into one agent per §3.1's method.
- **Construction tier** — a level of platform support for building an agent, from Tier 0 (raw callables) to Tier 3 (objective-driven, generated). See `docs/plans/2026-04-17-cs7-plan4-archipelago-agents-plan.md`.

---

## 8. Change log

- **2026-04-20** — Initial draft. Vision framing, north stars, "harness competing tensions" principle articulated with worked example (Designer / Decomposer / Planner derivation). Other principles (§3.2–§3.4) stubbed with pointers to existing design docs and ADR. Current-shape index and open-threads list populated from active design state.
