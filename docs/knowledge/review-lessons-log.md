# Design Lessons Log

Decisions and principles captured during the review feedback loop implementation (CS1: Primitive Models).

## Principles

**Clarity** — The system is unambiguous about what it is, what it expects, and what it guarantees. Vagueness causes bugs. Types, contracts, and APIs should leave no room for misinterpretation.

**Empathy** — The user's experience matters more than the implementer's convenience. Power without friction. Guardrails should guide, not punish.

**Discipline** — If it matters, enforce it automatically. If it doesn't matter, remove it. Humans forget; machines don't. Every representation must be current or deleted.

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
