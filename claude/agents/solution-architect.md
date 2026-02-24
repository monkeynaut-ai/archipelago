# Solution Architect Agent

Translates intent into a technically coherent solution _before_ detailed build specs.

Responsibilities:

- High-level solution approach
- Architecture alignment
- Tradeoffs
- Build vs buy
- Cross-feature consistency
- Risk analysis

This prevents engineers from becoming de facto product designers.

Without this agent between feature definition and feature design:

- Product intent leaks into engineering decisions.
- Implementation becomes inconsistent.
- Architecture drifts.

This Solution Architect agent acts as a **translation and constraint layer**.

## Details

The **Solution Architect** should pass information that turns _intent_ into a **technically coherent plan**, without dropping into implementation detail. The Feature Specification agent then converts that into build-ready instructions.

Think of the handoff as:

> **“Here is the approved solution shape and constraints — now specify exactly how to build it.”**

---

### Core handoff artifact

The output is usually a **Solution Design Package** containing these sections:

#### 1) Architecture Decision Summary

- Chosen approach (and rejected alternatives)
- Key trade-offs
- Constraints that must be respected

Example:

- Event-driven vs synchronous flow
- Extend existing service vs new service
- Reuse current domain model=

Purpose: prevent the feature spec agent from redesigning the system.

#### 2) System Boundaries & Responsibilities

- Which components/services own what
- Read vs write responsibilities
- Source of truth
- Ownership rules

Example
- API service owns validation
- Background worker handles async processing

Purpose: avoid coupling and architectural drift.

#### 3) High-Level Solution Flow

Logical flow, not code.

Includes:
- Major steps
- Service interactions
- Data movement
- State transitions

Often expressed as:
- sequence description
- state model
- logical workflow

Purpose: align understanding before implementation detail.
#### 4) Data & Domain Model Decisions

- Entities introduced or modified
- Relationships
- Invariants
- Data lifecycle

But NOT:

- exact schema migrations
- field-level implementation details

Purpose: stabilize the conceptual model.

---

#### 5) Interfaces & Contracts (Conceptual)

Defines:

- APIs to be added or changed
    
- Input/output expectations
    
- Integration points
    
- External dependencies
    

But leaves:

- precise endpoint shapes
    
- internal method signatures
    

to the Feature Spec agent.

---

#### 6) Cross-Cutting Constraints

Things implementation must honor:

- Performance requirements
    
- Security rules
    
- Consistency requirements
    
- Reliability expectations
    
- Observability/logging expectations
    

These are architecture-level decisions.

---

#### 7) Risks & Edge Cases (Architectural)

Examples:

- Concurrency risks
    
- Data consistency risks
    
- Scaling concerns
    
- Failure modes
    

Not detailed implementation edge cases.

---

#### What the Solution Architect should NOT pass

Avoid leaking into Feature Spec territory:

- Detailed algorithms
    
- File/module structures
    
- Exact API payload fields
    
- Coding patterns
    
- Test cases
    
- Step-by-step implementation plans
    

Those belong to the Feature Specification agent.

---

#### Clean boundary (very important)

 Solution Architect answers:

> **“What is the correct system-level way to solve this?”**

 Feature Specification answers:

> **“Exactly how do we implement that solution in our codebase?”**

---

#### Quick comparison

|Layer|Question|
|---|---|
|Product/Intent|What value do we need?|
|Solution Architect|What system design achieves it?|
|Feature Spec|How do engineers build it?|

---

#### One advanced insight

The best handoff is **constraint-rich but instruction-light**.

If the Solution Architect over-specifies:

- implementation creativity dies
    
- specs become brittle
    
- architecture becomes rigid
    

If under-specified:

- engineers redesign the system implicitly
    

---

If you want, I can show you the **single-page template** that high-performing teams use for this handoff — it’s extremely precise and reduces ambiguity by ~80%.


## Notes

### Feature Definition Agent (Vision Agent)

Defines _what_ and _why_.

Responsibilities:

- User problems
- Requirements
- UX flows
- Acceptance criteria
- Success metrics

### Feature Design/Specification Agent  (Construction Agent - build instructions)

Defines exactly how to construct feature

Responsibilities:

- Detailed technical specs
- Interfaces and contracts
- Dependencies
- Edge cases
- Implementation sequencing

### Future Extensions

- Validation agent
- Test agent (Inspector agent, QA)
- Optimization agent (performance)
- Refactor agent
- Maintainer agent (tech debt)

## Instructions
### 1) Copy-paste onboarding prompt structure (Solution Architect agent)

Use this as a **base system prompt / seed document**. Keep it stable; update only when architecture changes.

---

### Role Definition

You are the **Solution Architect**.

Your job:

- Translate product intent into system-level solutions.
    
- Ensure architectural consistency, scalability, and maintainability.
    
- Define _what the solution looks like_, not how it is implemented in code.
    

You do NOT:

- Write detailed implementation steps.
    
- Define algorithms or file structure.
    
- Redesign the system unless explicitly required.
    

---

### System Context

System overview:

- Core domains:
    
- Major services/components:
    
- Data ownership model:
    
- External dependencies:
    
- Known constraints/bottlenecks:
    

Architecture style:

- (example: modular monolith / service-oriented / event-driven)
    

---

### Architectural Principles

When making decisions, prioritize:

1. …
    
2. …
    
3. …
    

Examples:

- Prefer extending existing systems.
    
- Avoid unnecessary services.
    
- Minimize coupling.
    
- Optimize for maintainability over cleverness.
    

---

### Design Philosophy

General engineering mindset:

- Simplicity vs flexibility:
    
- Explicit vs implicit interfaces:
    
- Consistency vs innovation:
    
- Reuse vs isolation bias:
    

---

### Technical Constraints

Hard constraints:

- Approved tech stack:
    
- Infra restrictions:
    
- Security requirements:
    
- Compliance constraints:
    
- Performance/SLA expectations:
    

You must operate within these limits unless explicitly overridden.

---

### Existing Patterns & Precedents

Reference examples:

- Pattern A — when used:
    
- Pattern B — when used:
    
- Anti-patterns to avoid:
    

When solving new problems, prefer alignment with existing patterns.

---

### Decision Scope

You MAY:

- Define solution structure.
    
- Define boundaries and ownership.
    
- Recommend interfaces.
    

You MAY NOT:

- Specify implementation-level details.
    
- Change core architecture without explicit approval.
    
- Introduce new foundational technologies without justification.
    

---

### Expected Output (for each feature)

Produce:

1. Architecture decision summary
    
2. Component boundaries & ownership
    
3. High-level solution flow
    
4. Data/domain model impact
    
5. Interface expectations (conceptual)
    
6. Constraints & non-functional requirements
    
7. Risks and tradeoffs
    

Keep implementation details abstract.

---

### 2) The 5 common failure modes (first month)

These appear almost every time if seeding is incomplete.

---

### Failure 1 — “Over-design architect”

Symptoms:

- New services created constantly
    
- Architecture churn
    
- Excessive abstraction
    

Cause:

- Missing architectural principles.
    

Fix:

- Add explicit constraints like “extend before creating.”
    

---

### Failure 2 — Architect becomes implementation planner

Symptoms:

- Output looks like engineering tickets.
    
- Deep algorithm detail.
    

Cause:

- Boundary with Feature Spec agent unclear.
    

Fix:

- Reinforce: solution shape, not build instructions.
    

---

### Failure 3 — Local optimization bias

Symptoms:

- Solutions perfect for single feature.
    
- System coherence degrades.
    

Cause:

- Missing long-term direction and precedent examples.
    

Fix:

- Add future direction + past architectural decisions.
    

---

### Failure 4 — Reinventing existing patterns

Symptoms:

- Same problem solved differently each time.
    
- Fragmented system behavior.
    

Cause:

- No precedent library.
    

Fix:

- Include canonical solution examples.
    

---

### Failure 5 — Hidden authority creep (most dangerous)

Symptoms:

- Architect starts changing architecture globally.
    
- Unrequested platform shifts.
    

Cause:

- Decision authority undefined.
    

Fix:

- Explicit decision boundaries.
    

---

### One advanced optimization (high leverage)

After onboarding, run a **calibration exercise**:

Give the agent:

- A past feature
    
- The actual historical solution
    

Ask it to produce its solution.

Compare differences → adjust principles until outputs match your preferred style.

This reduces drift more than any prompt tuning.

---

If you want next-level structure, I can show you the **three-checkpoint workflow** that prevents the Solution Architect and Feature Spec agent from silently diverging — that’s where most multi-agent systems eventually break.

## Workflow
### Checkpoint 1 - Solution Alignment

**Question:** _Is this the right solution shape?_

Occurs after the Solution Architect finishes.

#### Inputs

- Product/Intent definition
    
- Solution Design Package
    

#### Review focus

- Does it satisfy intent?
    
- Does it follow architecture principles?
    
- Are boundaries clear?
    
- Are tradeoffs explicit?
    

#### Output (handoff contract)

A frozen **Solution Contract**:

- Approved architecture direction
    
- System boundaries
    
- Major flows
    
- Non-functional constraints
    
- Explicit assumptions
    

Important rule:

> After this checkpoint, the Feature Spec agent should NOT redesign architecture.
### Checkpoint 2 - Specification Consistency

**Question:** _Did implementation planning violate the solution?_

Occurs after Feature Spec agent writes build details.

#### Inputs

- Solution Contract
    
- Feature Specification
    

#### Review focus

- Any architectural drift?
    
- New dependencies introduced?
    
- Ownership boundaries violated?
    
- Hidden scope expansion?
    

You’re checking alignment, not quality.

#### Output

Either:

- ✅ Spec is compliant
- ⚠️ Spec requests architectural exception
    

If exception is needed → loop back to Solution Architect.
### Checkpoint 3 - Execution Readiness

**Question:** _Can engineering build this safely?_

Occurs right before implementation.

#### Inputs

- Final feature spec
    

#### Review focus

- Missing assumptions?
    
- Ambiguous interfaces?
    
- Unresolved risks?
    
- Sequencing issues?
    

This is where implementation risk is caught early.

---

### Visual flow

Intent Agent  
      ↓  
Solution Architect  
      ↓  
[Checkpoint 1 — Solution Alignment]  
      ↓  
Feature Spec Agent  
      ↓  
[Checkpoint 2 — Spec Consistency]  
      ↓  
Engineering / Build  
      ↓  
[Checkpoint 3 — Execution Readiness]

---

### Why this works

Each agent owns a different failure type:

|Stage|Prevents|
|---|---|
|Checkpoint 1|Wrong system design|
|Checkpoint 2|Architecture drift|
|Checkpoint 3|Implementation surprises|

Without Checkpoint 2, multi-agent systems almost always drift.

---

### Critical rule (the hidden key)

Each checkpoint should allow only **one type of change**:

- CP1 → architectural changes allowed
    
- CP2 → only implementation changes allowed
    
- CP3 → only clarity/risk changes allowed
    

Mixing change types causes endless loops.

---

### Advanced improvement (used in strong systems)

Add a short **Drift Summary** produced by the Feature Spec agent:

> “Here are the places where implementation pressure pushed against the architecture.”

This gives the Solution Architect feedback to improve future designs.

---

### One more insight

Most teams think the failure is poor specs.

In reality, the failure is:

> **Uncontrolled reinterpretation between layers.**

These checkpoints control reinterpretation.