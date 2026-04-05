# Design Lessons Log

Decisions and principles captured during the review feedback loop implementation.

## Principles

**Clarity** — The system is unambiguous about what it is, what it expects, and what it guarantees — in its APIs and its implementation. Vagueness causes bugs. Types, contracts, and code structure should leave no room for misinterpretation.

**Empathy** — The user's experience matters more than the implementer's convenience. Power without friction. Guardrails should guide, not punish.

**Discipline** — If it matters, enforce it automatically. If it doesn't matter, remove it. Humans forget; machines don't. Every representation must be current or deleted.

**Coherence** — Decisions compound. An architectural choice in one layer should simplify — not complicate — decisions in adjacent layers. If a downstream choice requires fighting an upstream decision, one of them is wrong.

## Decisions

### Remove names from primitives
**Principle:** Clarity, Discipline

Names existed for YAML string-based references. In Python, composition is by direct object reference — names are redundant. Diagnostic labels can be inferred from class names via introspection. We removed `name` as a required field and eliminated all string-based references. Removing what isn't needed reduces the surface for confusion.

### Type callable signatures
**Principle:** Clarity

The `Conditional` docstring stated that `condition` returns a boolean, but the type annotation was bare `Callable` — no enforcement. We tightened all callable fields to declare their return types: `Callable[[I], bool]` for conditions, `Callable[[I], list]` for `over`, `Callable[[I], O]` for action functions. The system should not claim what it doesn't enforce.

### Use generics for callable parameter types
**Principle:** Clarity

The initial proposal used `Callable[..., bool]` — typed return but untyped parameters. Generics exist precisely to express "this callable takes an instance of whatever type the primitive is parameterized with." We adopted PEP 695 generics so Pyright can verify callable signatures end-to-end. Don't settle for a weaker representation when a precise one exists.

### Eliminate type redundancy
**Principle:** Clarity, Discipline

With generics, types appeared twice: as generic params and as `input`/`output` fields. Two sources for the same fact risks them disagreeing. We removed the fields entirely — type information comes solely from the generic parameters, accessible at runtime via `get_type_args()`. Every fact stated exactly once.

### Require parameterization at construction
**Principle:** Empathy

Generics allow unparameterized construction (`Loop()` instead of `Loop[In, Out]()`), which silently creates an instance that fails later during compilation. We added a model validator that fails immediately with a clear error message. Users should get actionable feedback at the point of mistake, not downstream.

### Add pytest to pre-commit hook
**Principle:** Discipline

The pre-commit hook ran lint and syntax checks but not tests. If tests matter for correctness — and they do — they must be enforced automatically. We added pytest as a pre-commit gate so broken tests can't be committed.

### Keep docs in sync with implementation
**Principle:** Discipline

After removing names from the implementation, the design doc, roadmap, and CS1 plan still referenced names and string-based composition. Stale docs are worse than no docs — they actively mislead. We updated all documents and marked the CS1 plan's code blocks as stale with pointers to the actual source.

### Remove get_type_args from public API
**Principle:** Discipline

`get_type_args` wraps access to Pydantic's internal `__pydantic_generic_metadata__`. The only consumer is the compiler, which lives inside Agent Foundry. Product developers building on Agent Foundry should never need it. Don't expose what consumers don't need — it creates implicit contracts that constrain future changes.

### Chaining vs containment are different composition modes
**Principle:** Discipline

The initial validator plan treated all primitive composition the same: "output of one must match input of the next." But chaining (Sequence steps) and containment (Loop/Retry/Conditional wrapping a body) have different type contracts. A Loop body's input may legitimately differ from the loop's input — the loop injects an item and the body may need parent context (a joined scope). Validating `body.I == Loop.I` would reject valid compositions. Loop body type validation was deferred to the compiler. Meanwhile, Retry has a unique re-entry constraint (`body.O` must be compatible with `body.I`) that the initial plan missed entirely. Validating the wrong thing is worse than not validating at all — it creates false confidence. Understand what you're validating before you validate it.

### Exact type matching at state boundaries
**Principle:** Coherence

The initial validator plan used `issubclass` checks with covariance/contravariance rules for type boundaries between primitives. The directionality was wrong in some cases, and the variance rules added real complexity. The turning point was a deliberate architectural decision: mandate composition over inheritance for state models. That single choice eliminated subtype relationships between Pydantic state types entirely, which made the downstream validator design trivially obvious — replace all `issubclass` checks with identity checks (`is`), delete every subtype test case. The variance machinery was solving a problem that the architecture now prohibited. One upstream decision dissolved an entire category of downstream complexity.

### Conditional without else is a detour, not a fork
**Principle:** Clarity

A `Conditional` with no `else_branch` has two paths: execute `then_branch`, or skip it. If the condition is false, the input passes through as output unchanged. This means `Conditional.I` must equal `Conditional.O` — and `then_branch` must accept and return the same type. All four types identical. The initial plan allowed `Conditional[A, B]` with no else branch, which would silently produce an `A` where a `B` is expected when the condition is false. If you genuinely need diverging paths, that's a `Fork` primitive (which doesn't exist yet). Don't let a missing abstraction corrupt an existing one.

### Plan tests must reflect plan constraints
**Principle:** Discipline

After adding the no-else detour constraint, two existing plan test cases (`test_then_input_mismatch`, `test_then_output_mismatch`) used no-else Conditionals with mismatched I/O types. They hit the new constraint before reaching the check they were testing. The plan's tests became stale the moment we added a new rule. When you change a contract, audit every test that touches it — not just the tests you're adding.

### Don't deduplicate different semantics
**Principle:** Clarity

The Conditional validator's no-else path and with-else path had similar-looking type checks, but different meanings: the no-else path enforces a detour constraint (all types identical), while the with-else path validates independent branch boundaries. Extracting a shared helper would save ~10 lines but obscure *why* the checks exist. Code that looks the same but means different things should stay separate — deduplication is a lie when the semantics diverge.

### Gate is an action variant, not a structural primitive
**Principle:** Coherence

Gate was modeled as a structural primitive with a `condition` field that decides whether to block. But the blocking decision is made by the *parent* — a Retry exhausts, a Conditional checks the state, and routes to the Gate. The Gate's `condition` duplicated routing logic that belongs upstream. Removing it and reclassifying Gate as `GateAction` (a leaf primitive like `FunctionAction`) simplified both the primitive taxonomy and the compiler: control flow primitives structure the graph, action primitives do work at the leaves. Each category has one job.

### Retry doesn't own its exhaustion routing
**Principle:** Coherence

Retry's `on_exhausted: str` field was a destination name — telling the compiler where to route when attempts ran out. But this is a cross-scope reference: the Retry names a destination it can't see. The parent should make this decision. When Retry exhausts, it exits normally — the domain state (e.g., `done=False`) carries the signal implicitly. The parent reads that state and routes via a Conditional. Removing `on_exhausted` eliminated a cross-scope coupling and kept the tree model self-contained.

### No untyped state at public boundaries
**Principle:** Discipline

The initial compiler plan used `dict[str, Any]` for input/output and smuggled internal bookkeeping (`__exhausted_action`, `__cond_result`) through the state as hard-coded string keys. This violates the typing guarantees of the primitive system. The fix: `run_primitive_plan(plan, input: I) -> O` accepts and returns Pydantic models. LangGraph's dict internals are encapsulated within the compiler. Internal signals (like routing decisions) use closures or conditional edges, never state pollution.

### Design for platform extensibility from the start
**Principle:** Discipline

The compiler initially used `isinstance` dispatch to resolve primitive types — simple, but requires modifying core code for every new type. Agent Foundry is a platform: users (including Archipelago) will define custom primitive types. A compiler registry (`dict[type[Primitive], CompilerFn]`) costs the same as isinstance dispatch but is open for extension. When a design choice is equally simple either way, choose the one that supports the platform's extensibility contract. Don't wait for the third user to justify a registry.

### Probe fundamental assumptions before detailed planning
**Principle:** Discipline

We spent 3 hours refining CS3 task details — test code, commit messages, task dependencies — before discovering that the compiler's flat shared state contradicted a requirement in the design doc: "anything not in output is discarded when the primitive completes." The fix (subgraph-based state isolation) restructured every composite primitive's compilation. Verify that the architecture satisfies the design's foundational requirements before planning tasks. "How does state flow?" should be the first question, not the last.

### One probing question can cascade into multiple design corrections
**Principle:** Clarity

"What happens when should_block is True?" revealed that Gate's `condition` duplicated routing that belongs upstream. Removing it led to reclassifying Gate as an action variant (GateAction), which led to renaming Action to FunctionAction, which led to removing `on_exhausted` from Retry (same cross-scope coupling), which led to the typed public API (no more dict smuggling). Each fix was small, but the cascade revealed that the original design conflated control flow with leaf actions. Ask "what exactly happens here?" at every boundary.

### Don't let implementation convenience shape the public API
**Principle:** Clarity

LangGraph uses `dict[str, Any]` internally, so the initial compiler plan exposed dicts in the public API: `graph.invoke({"key": "value"})`. This leaked an implementation detail into the contract users depend on. The fix — `run_primitive_plan(plan, input: I) -> O` — required bridging work (model_dump/model_validate) but gave users the typed guarantees the primitive system promises. The internal representation is not the public interface.

### Exhaustion is a routing signal, not runtime state
**Principle:** Coherence

Retry's `on_exhausted: "escalate"` was a cross-scope reference — the Retry named a destination it couldn't see. And `__exhausted_action` smuggled framework bookkeeping through domain state as a hard-coded string key. Both violated the tree model's self-containment. The fix: remove `on_exhausted` entirely. When Retry exits with `done=False`, the parent reads that domain state and routes via Conditional. The domain data is the signal — no framework plumbing needed.

### YAGNI doesn't apply when the need is visible in the current roadmap
**Principle:** Discipline

The compiler used `isinstance` dispatch. The argument for keeping it: "add a registry when we need it." But Archipelago's agents (CS5-8) will be custom primitive types — the registry is a near-term requirement, not speculative. YAGNI protects against imagined futures, not documented ones. When the roadmap shows the need within a few change sets, build the extensibility now.
