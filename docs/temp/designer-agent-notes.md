# Notes on Designer Agent

## Open

- modularity is the king. Done properly it makes design comprehensible and safer to change. How is modularity done properly? Through abstraction, information hiding, loose coupling, cohesion, separation of concerns. Modularity is waht allows composition. It makes code more testable by enabling injection

## Can Claude Code balance investigation ↔ design?

Capable — but balance comes from how we instruct the Designer, not from raw tool capability.

Claude Code gives Designer good investigation primitives:

- Read, Grep, Glob for source exploration.
- LSP (findReferences, goToDefinition, documentSymbol, workspaceSymbol) for symbol-level navigation.
- Agent tool for delegating — Designer can spawn an Explore subagent to survey a subsystem and return a summary, keeping its own context focused on synthesis.
- Web fetch/search for external context.

What the tools don't solve:

- Rabbit-holing. Left unstructured, Designer can burn budget on investigation and never synthesize — or prematurely synthesize before understanding.
- Budgeted stopping. No built-in "investigation budget" — has to be encoded in instructions or platform scaffolding.
- Right-sizing context. Breadth of investigation vs. depth of design is judgment; prompt discipline carries the load.

Three likely mitigations for Designer v1, ordered cheapest-first:

1. Phased instructions. "First, investigate [specific questions]. Then, write the design." Structure forces the transition.
2. Delegated investigation. Designer spawns an Explore subagent whose only job is to return a codebase_context.md. Designer reads it, then designs. Maps cleanly

- Rabbit-holing. Left unstructured, Designer can burn budget on investigation and never synthesize — or prematurely synthesize before understanding.
- Budgeted stopping. No built-in "investigation budget" — has to be encoded in instructions or platform scaffolding.
- Right-sizing context. Breadth of investigation vs. depth of design is judgment; prompt discipline carries the load.

Three likely mitigations for Designer v1, ordered cheapest-first:

1. Phased instructions. "First, investigate [specific questions]. Then, write the design." Structure forces the transition.
2. Delegated investigation. Designer spawns an Explore subagent whose only job is to return a codebase_context.md. Designer reads it, then designs. Maps cleanly
onto the workspace substrate.
3. Platform-enforced checkpoints. A Phase-2 platform feature that forces a synthesis checkpoint after N investigation calls. Add only if v1 rabbit-holes.

My lean for Designer v1: (1) + optional (2). Add (3) if it proves needed.

## Designer ↔ Critic ↔ Judge debate

Yes — this is exactly the kind of experiment the "experimentation-first" north star exists for. The tensions method justifies it cleanly:

- Designer: creator-optimist (Cluster A stance).
- Critic: critic-pessimist (our deferred tension #4, now externalized instead of suppressed).
- Judge: synthesizer — a new meta-stance that resolves the dialectic.

Three coherent roles; three distinct stances. Workspace-mediated fit is natural: design_v1.md → critique_v1.md → design_v2.md → critique_v2.md → ... →
final_design.md. Every round is an observable, replayable artifact — this is ideal territory for the template machinery to prove itself on.

Real design questions this opens:

- Termination. Fixed N rounds? Convergence detection (diffs shrinking)? Judge-interrupts?
- Judge scope. Sees all rounds, or only final positions? Writes a new synthesis, or picks a side?
- Critic stance. Generic "find flaws" — or specific lenses (security, testability, simplicity, maintainability) rotated across rounds?
- When to invoke. Every design, or gated on feature complexity / explicit request?

Risks to name:

- Defensiveness loops. Designer digs in under attack rather than improves. Detect via cross-round diff convergence.
- Judge is the choke point. Weak Judge = adversarial labor wasted.
- Cost. N × 2 turns + Judge ≈ 3–5× single Designer. Worth measuring.

Sequencing recommendation.

Don't fold into Phase 2, but design for it. Two reasons:

1. Phase 2 needs a shipped Designer first. Without a baseline, Critic doesn't know what to attack, and there's nothing to compare the debate variant against. The
right experiment is "Designer alone vs. Designer-Critic-Judge on the same spec" — that requires Designer alone to exist.
2. The debate variant deserves its own phase (CS7 Plan 5, say) so the experiment has clean framing, clean fixtures, and clean measurements.

What we can do in Phase 2 to make this cheap later:

- Designer's output must be a complete markdown artifact that a future Critic can read and attack — no privileged internal state.
- Designer's input shape must be reproducible, so the same input can be run through Designer-alone and Designer-debate variants.
- Workspace layout leaves room for design_v{N}.md / critique_v{N}.md naming.

If these three hold, the debate experiment slots in cleanly as a later phase without re-shaping Phase 2.

Does this sequencing sit right — Phase 2 builds Designer (with hooks for later debate), Phase 3+ runs the debate experiment? Or do you want to push harder and
include it in Phase 2?

(a) Protocol vs. checklist — what's the actual difference?

You're right to probe. For a sophisticated LLM, the differences are thinner than the labels suggest. Real distinctions:

- Compliance pressure. "First do X. Then Y." creates stronger implicit "must execute every step in order" pressure than "Consider looking at: X, Y, Z." LLMs treat
numbered imperatives as contracts.
- Order sensitivity. Protocol implies sequence; checklist doesn't.
- Completeness expectation. Protocol enumerates what must happen. Checklist enumerates what might be useful and (implicitly or explicitly) permits additions.
- Error behavior. Protocol step that fails creates "am I violating the spec" tension. Checklist item that doesn't apply, the LLM just skips.

But the deepest difference is where judgment lives:

- Protocol: spec author owns completeness. LLM executes.
- Checklist (explicit-judgment-clause): shared. LLM decides whether the list is enough and supplements.
- Free-form: LLM owns completeness. Prone to cold-start drift.

So "protocol vs. checklist" is really a judgment-placement decision dressed up as phrasing. Word choice ("first do X" vs. "consider X") matters less than whether
the instruction frames Designer as an executor or a thinker.