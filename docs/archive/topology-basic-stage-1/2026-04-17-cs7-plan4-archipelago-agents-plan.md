# CS7 Plan 4 (+ possibly Plan 5): Archipelago Agents & Agent Foundry Construction Capabilities — Design (Living Document)

> **Status:** BRAINSTORM IN PROGRESS. Nothing in this document is locked. Do not implement from this plan yet.
> **Roadmap:** `docs/plans/stage1/2026-04-03-review-feedback-loop-roadmap.md` (Change Set 7, Plan 4)
> **Depends on:** CS7 Plan 1 (AgentAction primitive), CS7 Plan 2 (lifecycle orchestration), CS7 Plan 3 (base image + instructions).
> **Started:** 2026-04-17

## Purpose

Design — from scratch — the four Archipelago agents and two function actions that are the first real product consumers of `AgentAction`. Prior CS5/CS6 model decisions are **not assumed to carry over**; they may be revised or replaced as the design evolves here.

## Framing: this is an experimentation platform, not a frozen pipeline

Agent Foundry exists to make **exploration and experimentation with agent systems simple and fast**. Archipelago is its first application, not a product set in stone. Every design choice here should be evaluated against these experimentation axes — how cheap is it to change:

- **Topology** — how agents connect, split, merge
- **Instructions** — what each agent is told to do
- **Division of tasks** — one agent vs. several; what each owns
- **Inputs and outputs** — data shape at boundaries
- **Prompts** — how input becomes an LLM message
- **Data flow** — what information moves where
- **Control flow** — loops, retries, gates, conditionals

**Implications for this plan:**
- Any agent may split into multiple agents tomorrow. Prefer narrow, composable I/O so splitting is local.
- Data-flow assumptions live in the system-level `PrimitivePlan`, not in individual agents.
- Prefer swappable collaborators (prompt builder, instructions provider, executor) over hardcoded wiring.
- When a primitive seems to do two things, that's a signal to split now — splitting later is harder.
- Nothing in CS5/CS6 is a lock. Re-derive I/O from the agent's current job; revise legacy models if they don't fit.

## North star: autonomous software engineering

The goal of Archipelago — and the reason Agent Foundry exists in this shape — is **autonomous software engineering by agents**, with minimal human involvement. Every design choice here is in service of that. Mark's earlier instinct (fine-grained typed I/O between agents) was an attempt to control behavior tightly enough to remove humans from the loop. The current bet is that **file-sharing through a shared workspace, with structured templates and validator gates between agents, can achieve the same control with more flexibility** and at lower experimentation cost. If that bet is wrong, fine-grained typed I/O remains a fallback.

## Second north star: single-source-of-truth data models

Autonomy is the outcome; **the architectural bet that makes reaching it affordable is this:** one change in a data model — a field rename, a new field, a constraint tweak, a reordering — should propagate, without any other code/config/data edits, to every touchpoint the model participates in. Prompts, instructions, markdown rendering, markdown parsing, validation, JSON-schema emission, generated skeletons, data flow through the run — all derived from the model.

The experimentation platform framing demands this. If changing an agent's output schema requires editing the prompt builder, the instructions file, the parser, the validator, the renderer, the downstream consumer, and the schema export — experimentation is expensive and rare. If it requires editing only the model, experimentation is cheap and frequent.

**Mechanism:** Pydantic domain models, field-level annotations (`AsHeading`, `AsSection`, `AsCodeBlock`, and eventually `AsPromptSection`, `AsInstructionPlaceholder`, `AsInputPath`, ...), and Agent Foundry handlers that read annotations and do the work. See `agent-foundry/docs/architecture/adr_markdown_template_model_shape.md`.

### Touchpoints covered today (by the ADR's machinery)

Each of these updates automatically when the model changes:

- Markdown rendering of a model instance.
- Markdown parsing of the agent's document output.
- Structural + pattern validation with field-localized error reporting.
- JSON schema for `claude --json-schema` (via `to_claude_code_schema`).
- Annotated skeleton template the agent mimics.
- Instruction appendix derived from field descriptions + annotations.
- Downstream code that reads the parsed instance (types flow through LangGraph state).

### Touchpoints NOT yet covered (gap list — each becomes a future annotation + handler)

1. **Prompts.** `prompt_builder` callables are still app-authored Python. A field rename breaks them silently. Closing this needs annotation-driven prompt composition (e.g., `AsPromptSection(...)`), or prompts derived from the model + a rendering style.
2. **Agent instructions (hand-written `.md` files).** The generated appendix stays honest, but the hand-written body may reference field names, concepts, or paths that drift. Closing this needs placeholder substitution resolved at container start, or generating more of the instructions body from the model.
3. **String cross-references inside annotations** (e.g., `language_from="code_language"`). Rename-fragile and invisible to LSP. Closing this means preferring nested typed pairs (`Annotated[CodeSnippet, AsCodeBlock()]`) over string field names.
4. **Standalone validator primitives.** If a post-agent validation primitive is added later, it must read the same annotations; it must not duplicate them.
5. **Workspace path conventions.** Paths currently live as string literals in instructions and prompt builders. Making them model-attached (e.g., `AsInputPath(...)`, `AsOutputPath(...)`) lets a layout change propagate.

### The pattern

Every touchpoint currently handled by hand-authored code or config is a candidate for conversion to **annotation + platform handler**. Each conversion closes one gap. The gap list is the roadmap for reaching the dream fully.

## Inter-agent communication model (locked 2026-04-17)

**Shape: workspace-mediated, file-based, structured-by-template.**

- **Substrate.** A shared Docker volume (likely named `workspace`) accessible to all agents in a run. Files accumulate as upstream work happens. Agents read inputs from known paths and write outputs to known paths.
- **Versioning.** First pass: ephemeral within the run. Future: version the workspace in a git repo so runs are inspectable and replayable.
- **Document structure.** Markdown files have **expected structure / templates**. The template is **a Pydantic model with field descriptions**, treated as the canonical source of truth. The platform derives all artifacts from it:

- **Rendered markdown template** — example/skeleton document the agent mimics (heading per field, description as prose).
- **Instruction appendix** — field-level semantics injected into the agent's instructions (Tier 1 schema-aware instructions).
- **Structural validator** — parse the produced markdown back into the model; failure = structural non-conformance.
- **Optional semantic validator** — an LLM-checked pass that asks, per field, "does the content actually satisfy the field's description?" Optional and per-field-toggleable to control cost.
- **JSON schema** — derived for `--json-schema` if/when an agent's structured envelope payload draws fields from the same model.

This means a single Pydantic model definition (in Archipelago, for domain types; in Agent Foundry, for the template *machinery*) replaces handwriting markdown templates, schemas, and validators separately. Edits to the model propagate to every derived artifact.
- **Document validation is embedded inside the producing agent — not a separate gate.** Before control flows out of an `AgentAction`, the platform validates each declared output document against its template. On failure, the platform issues a bounded correction prompt to the same agent via session `--resume`, asking it to fix the document. This is the natural extension of Plan 2's existing `AgentFilePath` verification (file existence + size budget) — adding template-conformance checks to the same in-loop correction mechanism. No new primitive between agents; validation is a property of the agent that produced the document.
- **Structured envelope at agent boundaries stays minimal.** What flows through `AgentTurnEnvelope[T]` is small: success/fail + the name (path) of the document(s) the agent produced. The document content is in the workspace, not in the envelope. Severity, categorization, routing data — if needed at all — live in the document, not the envelope.
- **Seed inputs at run start.** A small set of inputs (e.g., the feature definition) enters the run from outside. These can be staged via declared input bindings (option A from earlier discussion). Once the run starts, all subsequent inter-agent data is workspace-mediated (option C).

**Why this beats fine-grained typed I/O for experimentation:**
- Splitting one agent into two = both write/read additional files; no schema migration.
- Changing what the Reviewer considers = edit instructions + template; no Pydantic model churn.
- A new agent in the middle = new files in the workspace; existing agents unchanged.
- Validators are decoupled from agents — improving validation doesn't touch the agent.

## Dual focus of this plan

This plan has **two intertwined goals**. The Archipelago agents are not the product — they are **catalysts and beacons** that drive and validate Agent Foundry capability growth.

1. **Agent Foundry — grow the platform's agent-construction capabilities.** The current `AgentAction` primitive is low-level: product supplies raw callables for `prompt_builder` and `instructions_provider`. This plan explores and adds higher-level ways to build agents, so experimenting with agent design is cheap.
2. **Archipelago — land the first four real agents** using whichever construction capabilities fit each agent best. A simple agent might need only handwritten instructions + narrow I/O; a more complex one might benefit from platform-crafted instructions, schema-aware templating, or metadata-driven generation.

This plan may split into **Plan 4 (catalyst agents + minimal platform capabilities)** and **Plan 5 (higher-tier platform capabilities + remaining agents)** once the design clarifies which capabilities are needed up front vs. later.

## Tiers of agent construction (proposed framework — under discussion)

A candidate mental model for organizing Agent Foundry's agent-construction capabilities. Each tier is a level of abstraction; an agent picks its tier based on how much it wants to hand-author vs. delegate to the platform.

- **Tier 0 — Raw.** Product supplies I/O Pydantic types, handwritten `instructions_provider` callable, handwritten `prompt_builder` callable. Full control. Current state of `AgentAction`.
- **Tier 1 — Schema-aware instructions.** Product supplies handwritten instructions + I/O types. Platform auto-generates an "input/output contract" appendix from the Pydantic schemas and injects it into the instructions at container start. Instruction author references *field names and purposes*, not values, and the appendix keeps the contract honest as the schema evolves.
- **Tier 2 — Metadata-driven.** Product supplies structured agent metadata (objective, input-purpose descriptions, output-purpose descriptions, tone hints, constraints, tool hints). Platform renders instructions and prompt scaffolding from the metadata via templates or rule-based composition.
- **Tier 3 — Objective-driven / generated.** Product supplies the minimum: objective + input schema + output schema. Platform generates instructions, prompt scaffolding, and any supporting templates — potentially via an LLM acting as an agent-generator. The generator's output is a concrete agent spec the product can inspect, tweak, and pin.

**Implication for experimentation:** swapping tiers for a single agent becomes a first-class experiment — "Reviewer at Tier 0 vs. Reviewer at Tier 2, compare findings quality." That's the experimentation loop Agent Foundry is meant to support.

**Open questions on tiers:**
- Are these the right tiers, or do they collapse/split differently?
- Is "agent spec" (metadata shape) itself a first-class Pydantic model in Agent Foundry? Versioned, diffable, introspectable?
- Is there a tier-promotion path: start at Tier 0 for a one-off agent; promote to a higher tier once patterns repeat?
- Should Agent Foundry ship an agent generator *as an agent itself* (dogfooding), or is that Tier 3 punted to later?

## Scope

Six primitives and their supporting artifacts:

1. **Reviewer** (`AgentAction`)
2. **Planner** (`AgentAction`)
3. **Integrator** (`AgentAction`)
4. **Dispatcher** (`AgentAction`)
5. **CommitAction** (`FunctionAction`)
6. **SubmitPRAction** (`FunctionAction`)

Each agent needs: input model, output model, instructions file, prompt builder, container config (visible/writable dirs, reuse policy), and tests. Each function action needs: input model, output model, function body, and tests.

## Slicing strategy (agreed 2026-04-17)

Single plan, staged PRs. Sequence: **Reviewer → Planner → Integrator → Dispatcher → CommitAction → SubmitPRAction.** Rationale: Reviewer is the smallest first-real-product-consumer test of `AgentAction` end-to-end; the others share scaffolding.

---

## Design — per primitive

Each subsection below is a placeholder to be filled in during brainstorming. Order matches the implementation sequence, not the priority of questions.

### 1. Reviewer (AgentAction) — first concrete catalyst

**Working name:** `ChangeSetReviewer` (scope is one change set, not one step).

**Purpose:** Review a completed change set as a whole — all commits/steps that fulfill the change set's acceptance criteria, interfaces, assumptions, and constraints. Produce a list of findings to be acted on (routing of must-fix vs. defer is a downstream concern).

**Why change-set-level (not per-step):** prior experimentation (Mark, pre-2026-04-17) showed per-step reviews caused chaos when weaving feedback into ongoing change set work. Change-set-level review fires once, after all steps complete, against a stable set of commits.

**Construction tier:** Tier 1 candidate — handwritten instructions + markdown-file I/O + schema-aware appendix injected by the platform. Tier 0 is the fallback if Tier 1 capabilities don't ship in this plan.

**Input transport: markdown files in the workspace** (first-pass deliberate choice).

Input file categories (each a separate file or a small set of files):

1. **Review target** — identifies what to review. Commit hash range OR a PR reference. Format: small structured header (probably markdown with frontmatter or a tiny structured section).
2. **Feature-level context** — relevant excerpts from the feature definition (or whatever upstream artifact drove this work). Markdown.
3. **Change set spec** — acceptance criteria, interfaces, assumptions, constraints. Markdown.

The prompt itself is minimal: it points the agent at the input files. The instructions file describes the structure and meaning of each input file. The platform (Tier 1) may inject a schema-aware appendix listing input paths and field descriptions.

**Output transport: markdown file** — written by the agent into a known workspace location.

Output structure: a list of findings. Each finding contains:
- **Description** — what the finding is
- **Rationale** — why it's an issue
- **Location** — where in the code/artifacts the issue exists
- **Suggested resolution** — what could be changed to resolve it

(Severity / must-fix vs. defer routing is intentionally not part of the first Reviewer's output — it can be a downstream concern or revisited later. To be confirmed.)

**Structured envelope vs. file:** Plan 2 baseline says every agent emits structured output via `--json-schema`. For a markdown-file-output agent, this resolves cleanly: the structured envelope is a thin pointer (e.g. `findings_path: AgentFilePath`) and the markdown file is the actual deliverable. The platform's `AgentFilePath` verification (Plan 2) confirms the file exists and is within the size budget.

**Container config:**
- `visible_dirs`: workspace (read-only access to commits and input files) — TBD which subpath
- `writable_dirs`: a narrow output directory for the findings markdown — TBD
- `reuse_policy`: probably `REUSE_NEW_SESSION` (each change set is independent; container reuse for warm-start speed) — TBD
- `timeout_seconds`: TBD
- `skip_permissions`: TBD

**Open questions:**
- How are input files placed in the workspace? Written by an upstream `FunctionAction`, by the run setup, or by the platform from declared `AgentAction` input bindings (a new capability)?
- Should the input file structure itself have a Pydantic schema (e.g., parse-on-write to validate before the agent sees them)?
- Should the output markdown have a parseable structure (frontmatter + per-finding sections) so a downstream agent or function can ingest findings programmatically — or stay freeform on first pass?
- Severity / categorization: omit from v1 output, or include from the start? Affects downstream routing topology.
- Does the Reviewer need git tooling inside the container (to navigate diffs and history), or do we pre-compute the diff into a markdown input file?

**Decisions (locked):**
- _None yet._

---

### 2. Planner (AgentAction)

_Placeholder — design after Reviewer is locked._

---

### 3. Integrator (AgentAction)

_Placeholder — design after Planner is locked._

---

### 4. Dispatcher (AgentAction)

_Placeholder — design after Integrator is locked._

---

### 5. CommitAction (FunctionAction)

_Placeholder._

---

### 6. SubmitPRAction (FunctionAction)

_Placeholder._

---

## Cross-cutting open questions

_Questions that span multiple primitives. Populated as they surface._

### Input ↔ instructions relationship (experimentation axes)

This is not a single decision — it's a set of axes, and the right point on each axis varies by agent and by situation. Both Agent Foundry (as a platform) and Archipelago (as an application) need to treat these as parameters to experiment with, not defaults to lock.

**Axis 1 — Input structure.** Free text in the prompt ↔ structured JSON in the prompt ↔ markdown/data files dropped into the workspace ↔ combinations of these. Each has tradeoffs for LLM readability, schema enforcement, versioning, and cross-agent reuse.

**Axis 2 — Input granularity.** One omnibus blob ↔ many narrow fields. Affects how much the instructions can reference specific pieces and how expensive a schema change is.

**Axis 3 — Input transport.** Prompt-embedded (delivered at turn start) ↔ workspace-file-based (instructions tell the agent where to look) ↔ ambient (already in session context from a prior turn). Different transports suit different reuse/resume policies.

**Axis 4 — Instruction ↔ input coupling.** Loose ("all the input information you need is in `abc.md`") ↔ tight ("read `acceptance_criteria`, then verify `test_paths` contains..."). Tight coupling is concrete but fragile when inputs change; loose coupling is resilient but offloads interpretation to the model.

**Capability Agent Foundry may need:** a way for instructions to be **schema-aware without being value-aware** — i.e., instructions can reference the shape of the input (field names, types, constraints) at authoring time, and some platform mechanism keeps instruction text consistent with the Pydantic input model as it evolves. Candidates: templating with schema placeholders, instruction + schema co-validation, auto-generated "input reference" appendix injected into the instruction file at container start.

**Implication for Plan 4:** the input/instruction design for each agent is a choice of coordinates on these axes, not a single answer. Document the coordinates per agent so they can be swapped without reopening the design.

### Other cross-cutting questions

- How do agents that run in containers access the workspace commits produced by FunctionActions running on the host? (Workspace volume lifecycle vs host-side git ops.)
- Should any wrapper types exist, or do agents emit domain types directly as `AgentTurnEnvelope[T]` payloads?
- Which primitives need to emit domain lifecycle events via `runtime.emit(...)`?
- Role granularity: concrete agent per role vs. a review-role-template factory (from 2026-04-17 brainstorm).

---

## Change log

- **2026-04-17** — Document created. Reviewer design initiated from scratch.
- **2026-04-17** — Captured experimentation-platform framing (Agent Foundry's purpose).
- **2026-04-17** — Proposed four tiers of agent construction (Tier 0 raw → Tier 3 generated).
- **2026-04-17** — Reviewer scoped to change-set-level (not per-step). Per-step rejected on prior-experimentation grounds.
- **2026-04-17** — Inter-agent communication model locked: workspace-mediated, file-based, structured-by-template, with embedded validation and minimal envelopes. North star: autonomous SWE.
- **2026-04-17** — Document validation is embedded inside the producing agent (extends Plan 2's `AgentFilePath` mechanism); not a separate validator primitive. Templates: domain content lives in Archipelago, the template *concept* is an Agent Foundry capability.
- **2026-04-17** — **Template source of truth = Pydantic model.** The document template is a Pydantic model (with field descriptions). The platform derives from it: a rendered markdown template (what the agent mimics), a JSON schema (for `--json-schema` when needed), an instruction appendix (field-level semantics), a structural validator (parse markdown → instantiate model), and an optional semantic validator (LLM-checked: does the content satisfy the field description?). One model, many derived artifacts.
- **2026-04-17** — **Template models are built from typed markdown-element classes** — `MarkdownHeading`, `MarkdownSection` (bold title), `MarkdownCodeBlock`, `MarkdownTable`, etc. — via a discriminated-union base with `kind` as the discriminator. The model expresses document structure in terms of markdown elements; validation pipeline is markdown → `markdown-it-py` AST → normalized JSON → Pydantic validation.
- **2026-04-17** — **Layering decision: Option (iii) — annotation-driven domain models.** Applications declare ordinary Pydantic domain models and use `Annotated[T, AsHeading(...)] / AsSection(...) / AsCodeBlock() / ...` annotations to describe how each field renders as markdown. Agent Foundry provides the annotation vocabulary, the rendering engine, and the parsing/validation engine. App writes zero validation code. See ADR: `agent-foundry/docs/architecture/adr_markdown_template_model_shape.md`.
- **2026-04-17** — **Second north star named: single-source-of-truth data models.** One change in a Pydantic model should propagate to every touchpoint (prompts, instructions, rendering, parsing, validation, schemas, skeletons, data flow) without any other edits. Covered touchpoints and the gap list added to the plan as the roadmap beyond the ADR's initial scope.
- **2026-04-17** — **CS7 Plan 4 broken into phases. Phase 1 design drafted:** `docs/plans/stage1/2026-04-17-cs7-plan4-phase1-markdown-machinery-design.md`. Phase 1 builds the platform machinery in agent-foundry (element classes, annotations, `MarkdownDocument` base + meta-validation, renderer, parser/validator, subtree extractor). Subsequent phases will extend the machinery and implement the four Archipelago agents on it.
