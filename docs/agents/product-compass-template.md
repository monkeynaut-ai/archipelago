# Product Compass Template

## 0. AI Parsing Rules

These rules make the document reliably machine-readable for agents.

- Use the headings as written; do not rename sections.
- Prefer short paragraphs and bullet lists over long prose (except **2.4 Transformation Story**).
- One concept per bullet.
- When creating IDs, use stable tokens:
    - Problems: `P-001`, `P-002`, ...
    - Assumptions: `A-001`, `A-002`, ...
    - Features (when referenced here): `F-001`, `F-002`, ...
- Keep scoring fields numeric and explicit (no ranges, no words):
    - Severity/Impact/Alignment/Effort/Risk: integers 1–5
    - Confidence: one of `0.5`, `0.8`, `1.0`
    - Reach: either a number with unit (e.g. `200 users/week`) or integer 1–5
- Put constraints and non-goals in their dedicated sections; do not bury them in narrative.
- If something is unknown, write `Unknown` (do not guess).
- For assumptions, always include a falsifier (“what would disconfirm it?”).

---

## 1. Product Identity

**Product Name:**

**One-Sentence Description:**

Clear, precise articulation of what the product _is_.

**Category / Domain:**

Market or conceptual category.

---

## 2. Beacon

**Long-Term Aspiration (3–5+ years):**

What becomes true if this product fully succeeds?

**Transformation Statement:**

Before → After transformation for the primary user.

**Non-Compromise Principles:**

Values that must not be violated.

### 2.1 Desired Outcome and Business Goals

Outcome-focused: the measurable change in the world we want this product to cause.

- **Primary Desired Outcome (1 sentence):**
- **Business Goals (ordered):**
    - Goal 1 (with rough target if possible)
    - Goal 2

### 2.2 Customer Promise (Working-Backwards Snapshot)

One paragraph written from the customer’s perspective:

- What problem disappears?
- What becomes easier / faster / safer / cheaper?
- Why now?

### 2.3 FAQs (for alignment)

Short list of questions stakeholders and builders will ask:

- Who is this _for_ (and not for)?
- What must be true for this to work?
- What’s the simplest version that still delivers the promise?
- What would make this a bad idea to build?

### 2.4 Transformation Story (Day-in-the-Life)

Write 1–2 pages (or ~500–1200 words) that make the transformation concrete.

**Format:**

- **Before:** What a normal day/workflow looks like today (pain, friction, risks, workarounds).
- **After:** What the same day/workflow looks like after adoption (new capabilities, confidence, speed, joy).

**Requirements:**

- Use a specific archetype from **4.1 Primary User Archetype**.
- Include at least 3 concrete moments where the product changes an outcome.
- Explicitly show what disappears (tasks, anxiety, delays, errors) and what becomes possible.
- Avoid marketing language; write as plain narrative.

---

## 3. Problem Landscape

### 3.1 Core Problems

Structured list:

- Problem ID
- Problem Description
- Who experiences it
- Why it matters

### 3.2 Root Causes

Systemic forces behind the problems.

### 3.3 Existing Alternatives

How users currently cope.

---

## 4. Target User Model

### 4.1 Primary User Archetype

- Role
- Goals
- Frustrations
- Environment

### 4.2 Secondary Users (if any)

---

## 5. Value Model (How We Create Value)

Explicit, structured.

### 5.1 Value Equation

Value = (Desired Outcome × Probability of Success) ÷ (Time + Effort + Risk + Cost)

Define:

- What “Desired Outcome” means in this context
- What reduces friction
- What increases success probability

### 5.2 Competitive Advantage Hypothesis

Why we can uniquely deliver this value.

---

## 6. Strategic Focus

### 6.1 What We Are Optimizing For

Examples:

- Speed
- Intelligence
- Precision
- Leverage
- Revenue
- Learning

Rank in priority order.

### 6.2 Explicit Non-Goals

Clear boundaries.

Prevents feature creep.

### 6.3 Key Capabilities (Coarse-Grained)

List the product’s major capabilities (not epics/stories).

- Capability 1 (1–2 sentences)
- Capability 2
- Capability 3

---

## 7. Design Philosophy

Guiding heuristics:

- Simplicity vs power
- Opinionated vs flexible
- Automation vs control
- Transparency vs abstraction

---

## 8. Constraints

Structured for AI interpretability.

### 8.1 Technical Constraints

### 8.2 Resource Constraints

### 8.3 Regulatory / Ethical Constraints

### 8.4 Strategic Constraints

---

## 9. Success Metrics

### 9.1 Leading Indicators

Behavioral metrics.

### 9.2 Lagging Indicators

Revenue, retention, impact.

### 9.3 Qualitative Signals

User sentiment patterns.

---

## 10. Feature Evaluation Framework

Used by humans and AI agents.

### 10.1 Alignment Criteria

A feature must:

- Solve a core problem
- Strengthen competitive advantage
- Improve the value equation
- Respect constraints

### 10.2 Scoring Model (Structured)

For each proposed feature:

- Problem Severity (1–5)
- User Impact (1–5)
- Strategic Alignment (1–5)
- Reach (users/events per time period, or 1–5)
- Confidence (50% / 80% / 100%)
- Effort (1–5)
- Risk (1–5)

Two useful rollups:

- **Compass Score (simple):** (Impact × Alignment × Severity) ÷ (Effort + Risk)
- **RICE Score (option):** (Reach × Impact × Confidence) ÷ Effort

---

## 11. Idea Seeds (Muse Section)

Open-ended prompts to stimulate ideation:

- “If this product were 10× better, what changed?”
- “What would make this indispensable?”
- “What would eliminate 90% of user effort?”
- “What feature would make competitors irrelevant?”

Note: expand these seeds into prompts that tie into our specific problems and capabilities.

This section is inspirational, not binding.

---

## 12. Assumptions, Evidence, and Validation

This document is a living system that should converge toward stability by converting assumptions into evidence.

### 12.1 Critical Assumptions

For each:

- Assumption ID
- Type: Desirability | Viability | Feasibility | Usability
- What would disconfirm it?

### 12.2 Current Evidence

List what you already know (data, interviews, production telemetry, competitive analysis).

### 12.3 Validation Plan

Smallest tests to run next (interviews, prototypes, spikes, A/B tests) and the decision rule for each.

---

## 13. Open Questions

Explicit uncertainties:

- Market
- Technical
- Strategic

Encourages exploration without distorting the core.