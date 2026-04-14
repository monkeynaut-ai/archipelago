# Design Lessons Log

Decisions and principles captured during the review feedback loop implementation.

## Principles

**Clarity** — The system is unambiguous about what it is, what it expects, and what it guarantees — in its APIs and its implementation. Vagueness causes bugs. Types, contracts, and code structure should leave no room for misinterpretation.

**Empathy** — The user's experience matters more than the implementer's convenience. Power without friction. Guardrails should guide, not punish.

**Discipline** — If it matters, enforce it automatically. If it doesn't matter, remove it. Humans forget; machines don't. Every representation must be current or deleted.

**Coherence** — Decisions compound. An architectural choice in one layer should simplify — not complicate — decisions in adjacent layers. If a downstream choice requires fighting an upstream decision, one of them is wrong.

**Surface, verify, encode** — Assumptions rot; constraints endure. At every boundary — between the LLM and the platform, between repos, between a test and the code it guards — actively surface what you're assuming, validate it empirically or analytically, adjust the design when the assumption is wrong, and encode the corrected assumption as a type, assertion, or schema invariant. What remains implicit is what breaks next. The cycle: (1) surface — ask "what are we assuming here?" at each boundary and design decision; (2) verify — test the assumption via empirical spike, analytical trace, or structural read; (3) adjust — when the assumption is wrong, change the design, don't patch around it; (4) encode — lock the corrected assumption into a type shape, test assertion, schema constraint, or convention that the system enforces automatically. Unencoded assumptions are correct today and wrong tomorrow. Emerged during CS6/CS6.5 planning when six separate assumptions were surfaced via direct questions or empirical spikes, each changing the design direction: `--json-schema` availability on Pro subscriptions, `$defs`/`$ref` incompatibility with Claude Code, StrEnum discriminator rejection by Pydantic 2.12, PlannerOutput conflating LLM-emittable and runner-assembled fields, the role spec harness accepting typos via subset checks, and text markers being unnecessary under `-p` mode structured output.

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

### Subgraph state accumulates like a repository, not a pipeline
**Principle:** Coherence

Real-world testing exposed three requirements the pipeline model couldn't meet: (1) functions in FunctionActions must be reusable — not forced to accept the full composite input type just because they're the first step; (2) all fields in the composite's accumulated state must be available to every step, not just the previous step's output; (3) the composite output is assembled from the full accumulated state, not just the last step's output. The initial compiler treated data flow as a unix pipe (step N output → step N+1 input), forcing every step to explicitly forward fields it didn't use. The correct model: subgraph state accumulates like a git repository. Each step reads what it needs from the accumulated state, writes what it produces back, and the state grows. The composite's scope-out selects which fields leave. This enables function reusability — a step only declares the fields it needs, independent of where it sits in the sequence.

### Test-driven discovery vs test-driven verification
**Principle:** Discipline

Tests we wrote ourselves during TDD caught implementation bugs against our own intent. Tests the user wrote as a real consumer of the package caught *design* bugs we hadn't anticipated — the function reusability problem, the pipeline model flaw. These are different kinds of value: TDD verifies the implementation matches the design; real-world usage verifies the design matches the need. Both are necessary; neither is sufficient. Plan to do both — write your TDD tests, then build something real with the result and let the friction tell you what's wrong.

### Iteration earned the design
**Principle:** Coherence

The accumulated state model wasn't in any plan or design doc. It emerged mid-conversation when a user testing a Sequence found that step functions couldn't be reused without artificially declaring fields they didn't need. Good designs often look obvious in hindsight but are reached through iteration, not foresight. Don't try to plan your way to the right answer on day one — plan a reasonable starting point, build it, test it under real conditions, and let the friction tell you what to fix. Iteration is not a sign of poor planning; it's how good design happens.

### Plan agents reason from prompts, not running code
**Principle:** Discipline

The Plan subagent designed the original pipeline-based compiler. It didn't catch the flat-state isolation problem because it doesn't execute code or run tests — it synthesizes from text. Plan agents are useful for breaking down structure and exploring alternatives, but they're not oracles. The only ground truth is running the code against real requirements. Use plan agents to scaffold and explore; verify with execution.

### The cost of cleanup is paid now or later, not avoided
**Principle:** Discipline

CS3 deleted ~6,500 lines of dead code (old compiler, planner, registry, role specs, demo). Leaving it would have been easier in the moment, but every day that code lived in the repo it polluted searches, generated warnings, confused future readers, and made every grep more expensive. The initial argument for keeping it ("CS5-8 might need it") was speculative — the cost of removing it later, after it had been re-read and re-considered dozens of times, would have been higher than removing it now. Defer-and-forget is rarely cheaper than do-it-now; the cost compounds invisibly.

### StrEnum over Literal for LSP-navigable symbols
**Principle:** Coherence

LSP operations like `findReferences`, `goToDefinition`, `rename`, and `workspaceSymbol` depend on the target being a symbol — a named definition with a declaration site. `StrEnum` members are symbols: `Severity.MUST_FIX` has an authoritative declaration LSP can anchor to. `Literal` string values are not symbols; the string *is* the value, with no declaration to find. In a codebase committed to LSP-first navigation (per the user global CLAUDE.md rule), using `Literal` for enumerated values silently breaks the workflow. `findReferences` on a routing value returns nothing, rename refactors fall back to text search (which can't distinguish the routing literal from a random docstring mention), and an agent following the "check `findReferences` before declaring anything unused" rule cannot tell "genuinely unused" apart from "LSP can't see it." The uniform StrEnum policy added during CS5 planning isn't just an ergonomic preference — it keeps the data model layer and the navigation layer coherent. A choice in one layer (use `Literal` for enum-like values) contradicted a choice in another (navigate by LSP operations), and one of them had to give. We chose the layer that runs every day.

### Deletion discipline: categorize by behavior, not by import health
**Principle:** Clarity, Discipline

During CS5 cleanup, two files were deleted based on broken imports without inspecting their content.

### Schema is the load-bearing contract
**Principle:** Clarity, Surface/verify/encode

When the agent boundary moved from text parsing to `--json-schema` structured output, schema tests went from "proves Pydantic works" (low value — testing the framework) to "guards the agent boundary" (load-bearing — testing our contract). The JSON schema injected into the LLM via `--json-schema` IS the API contract: the literal bytes in the LLM's context determine what it emits, and the same schema (via `model_json_schema()`) determines what Pydantic accepts on return. Drift between the two is a silent failure — the LLM emits data that looks right but doesn't match the model, or vice versa. Treat schema generation as a first-class concern with its own helper (`to_claude_code_schema`), its own tests (schema shape assertions per model), and its own documented quirks (Claude Code silently disables on `discriminator`, fails retries on `$defs`/`$ref`). Discovered during CS6 when we trimmed per-model tests down to two effective tests each — the schema test was the one that earned its place because it's the only thing preventing the LLM from silently emitting wrong data.

### Collapse signal mechanisms, don't multiply them
**Principle:** Discipline

Before CS6.5, agent turns signaled completion via three mechanisms: text markers (`ARCHIPELAGO_TASK_COMPLETE`) matched by regex, exit codes from the CLI process, and the `result` event's `is_error` field in stream-json. Each mechanism had its own code path in the adapter, its own failure modes, and its own tests. When two mechanisms both fired on the same turn (the `result` event and the text marker), the adapter emitted duplicate status messages — caught by the CS6.5 review swarm (finding C1). The fix: one mechanism (Claude Code's synthetic `StructuredOutput` tool call) carries all four outcome kinds (success, clarification_needed, permission_needed, failed) via a discriminated union. Text markers become dead code. The four-outcome taxonomy emerged from questioning a false assumption: "clarification and permission are mid-stream signals." Under `-p` mode, every signal is turn-final — the process exits after each turn. Once that assumption was surfaced and verified, all signals collapsed into a single structured payload at turn-end. Fewer mechanisms = fewer code paths = fewer ways for signals to diverge or duplicate.

### Don't categorize until you have field data
**Principle:** Discipline, Surface/verify/encode

During CS6.5 design, `FailureOutcome` was initially given a five-variant `FailureCategory` StrEnum: `TASK_INFEASIBLE`, `ENVIRONMENT_BROKEN`, `GAVE_UP`, `REFUSED`, `UNKNOWN`. The categories looked reasonable in the abstract. They were dropped to a free-form `reason: str` on the principle that premature categorization locks in a taxonomy before you understand the distribution. No agent has emitted a `FailureOutcome` yet — the five categories were invented from zero data. The Archipelago team will monitor `reason` text in production and promote patterns to an enum later if the data justifies it. The temptation to categorize is especially strong when designing discriminated unions, where the pattern itself invites "enumerate all variants." Resist: enumerate variants when the domain is well-understood (success/clarification/permission/failed — those are genuinely complete terminal states of an agent turn); use free-form text when the domain is unexplored (failure reasons — we don't yet know what agents will actually say when they give up).

### Platform separation follows dependency flow
**Principle:** Coherence

No explicit platforming effort was made during CS6/CS6.5. But the generic pieces — schema flattener (`to_claude_code_schema`), protocol types (`StructuredOutputMessage`), adapter plumbing (`_build_claude_cmd` with `json_schema` param), stderr-on-error path — all landed in agent-foundry. The domain-specific pieces — `AgentTurnEnvelope[T]`, `ReviewerPayload`, role spec YAMLs, `build_outcome_schema` wrapper — all stayed in Archipelago. This happened without a planning decision because the cross-repo dependency constraint (Archipelago depends on agent-foundry, never the reverse) naturally pushes generic infrastructure downward and domain specifics upward. The `AgentTurnEnvelope[T]` type contains nothing Archipelago-specific — it's a generic four-outcome discriminated union parameterized by the success payload. It lives in Archipelago because that's where it was born, but it's one "second consumer" away from promotion to agent-foundry. Don't plan a platform; let the dependency direction reveal it. When generic code keeps landing in the same downstream repo, that's the signal to promote it. When domain code keeps trying to creep into the upstream repo, that's the signal to push it back. The platform boundary is wherever the dependency arrow points.

### Encode assumptions about external interfaces as integration tests
**Principle:** Surface/verify/encode

The adapter pattern-matches on Claude Code's stream-json event shape — `event.type == "assistant"`, `block.name == "StructuredOutput"`, `result.stop_reason`, `result.structured_output`. All unencoded assumptions about an external system's output format. If Anthropic changes any of these, the adapter breaks silently — it stops capturing structured output and falls into the retry path, which also fails, producing a confusing "no structured output" error that looks like a schema problem rather than an interface change. The fix: an integration test (`test_claude_code_stream_shape.py`) that runs the real `claude` CLI with `--json-schema` and asserts every shape the adapter depends on. The test runs on every `pdm run test-integration` and fails loudly with a specific message about which field or event type changed. General lesson: when your code pattern-matches on an external system's output, that's an assumption about the external interface. Unit tests with synthetic fixtures verify your logic but not the assumption. Only an integration test against the real system encodes the assumption as a constraint.

### Security-relevant config: doing nothing must never reduce safety
**Principle:** Discipline, Empathy

When a configuration field governs access, permissions, visibility, or any security-relevant behavior, the absence of configuration must never increase risk. If missing config could mean "unrestricted access" OR "no access," default to no access. The user must explicitly opt IN to each grant.

Emerged during CS7 Plan 1 design of `AgentAction`'s filesystem lockdown. The initial design had `hidden_dirs: list[str]` and `readonly_dirs: list[str]`, both defaulting to empty. Empty meant "hide nothing, make nothing read-only" — an agent with no lockdown configured had full access to everything in `/workspace`. The inversion: rename to `visible_dirs` and `writable_dirs`, both defaulting to empty, now meaning "see nothing, modify nothing" under `/workspace`. Forgetting to configure no longer grants access — it denies it.

This is distinct from "fail-fast." Fail-fast surfaces errors loudly when they happen. Safe-by-default prevents the error from being a silent grant of authority in the first place. Misconfiguration produces visible failures (e.g., the agent reports "permission denied") rather than invisible exposure. General rule: for any field where one end of the range is "grant" and the other is "deny," default to deny — force the authorizing choice to be explicit.

### TDD difficulty is a design signal, not a testing problem
**Principle:** Clarity, Discipline

When tests require elaborate setup — monkeypatching, fixture gymnastics, mocking internal implementation details, setting up global state — the friction is the design telling you the code has a hidden coupling or wrong dependency shape. The test's difficulty is not a quality bar to clear; it's diagnostic feedback about the code under test.

Emerged during CS7 Plan 1 review of the `AgentAction` compiler. Tests required `monkeypatch.setattr(agent_runner, "run_agent_in_container", stub)` because the compiler imported the runner as a module-level global. The monkeypatch was a red flag — the compiler had an implicit dependency on a specific module, not an explicit collaborator. The fix was architectural: make the executor an explicit field on `AgentAction` (`executor: Callable[...]`). Tests then construct the primitive with their stub; no patching needed. This also solved the strategy-extensibility question (container vs. SDK vs. API) — different executors are just different callables.

General rule: treat test friction as a first-class design signal. When a test needs patching to set up, ask "what implicit dependency is forcing this?" The answer is usually a missing constructor argument, a missing interface, or an unstated coupling. Fix the design; the test simplifies as a side effect. Conversely, tests that set up naturally with explicit construction are evidence that dependencies are visible and collaborators are injectable — the design is honest about what it needs.

### Product declares behavior; platform provides mechanism
**Principle:** Coherence

Agent Foundry is a declarative platform. The product's declaration of an agent (or any primitive) should be the *complete* specification of what that agent is and how it runs — prompt logic, instructions, response channel, and execution strategy. The platform provides mechanism — compilation, lifecycle, execution strategies as library capabilities — but does not bake in defaults that the product hasn't chosen. Nothing load-bearing about an agent's behavior should live implicitly in platform code.

Emerged during CS7 Plan 1 design of `AgentAction`. The initial design had the compiler call `agent_runner.run_agent_in_container` as a hardcoded module-level dependency — the platform was silently deciding "this agent runs in a container." Moving execution strategy onto `AgentAction` as `executor: Callable[["AgentAction", str], BaseModel]` made it a product decision. The compiler calls `action.executor(...)` — it runs what the primitive says to run. The platform ships container, SDK, and (future) API executors as callable capabilities; each product picks per agent.

This pattern generalizes beyond execution strategy. Response channel, prompt construction, instruction assembly, filesystem access — all are product concerns. The platform's job is to run a declarative specification, not to enforce policy through defaults. A product reading an `AgentAction` should be able to answer "what does this agent do and how does it run?" purely from the declaration, without needing to know what the platform does by default.

General rule: when the platform appears to be making a decision on the product's behalf ("this will run in a container," "this will use JSON schema output," "this will have these dirs visible"), ask whether that decision belongs on the primitive. If two agents in the same system might legitimately choose differently, the decision is a product concern and must be declared. If the platform offers multiple ways to accomplish a thing, every way is a library capability — none of them should be "the default."

### Parse external output into typed models at the boundary
**Principle:** Clarity, Surface/verify/encode

The adapter scattered `event.get("type")`, `block.get("name")`, `msg.get("content")` throughout its code — each access an implicit dependency on Claude Code's wire shape. Adding a new field access meant adding another untracked assumption. The fix: parse raw JSON into typed Pydantic models (`SystemInitEvent`, `AssistantEvent`, `ResultEvent`, `ErrorEvent`) at the first moment the data enters our code — the `for line in proc.stdout` loop. Everything downstream works with typed objects; no more dict access. If the wire shape changes, the parse fails at ONE point with a clear Pydantic validation error, instead of propagating as `None` or `KeyError` deep in the event loop. To adapt to upstream changes: update the model, Pydantic tells you everywhere downstream that breaks via type errors. Constants the adapter depends on (`STRUCTURED_OUTPUT_TOOL_NAME`, `NON_RECOVERABLE_STOP_REASONS`) live in the same module as the single source of truth. General lesson: when your code consumes an external system's output, parse it into typed models at the entry point. Every subsequent line of code gets type safety for free, and the adaptation surface for upstream changes shrinks to one file. `cli.py` had broken runner imports at the top but contained a standalone `configure_logging()` function with no dead dependencies — extraction would have preserved it. `test_config_to_lockdown.py` had broken compiler imports but contained lockdown enforcement tests whose value was OS-level behavior verification — the compiler step was ceremonial; the security properties were the real test. Both were caught in PR #2 review and fixed in follow-up commits (`160c8ba`, `63ea6d0`, `740936f`). The lesson: when deleting a file, the unit of analysis is the individual definition, not the file as a whole. Broken imports at the top of a file do not imply broken content inside it. For any non-trivial file, audit each top-level definition: is it standalone? Is what it provides still needed? Where does the behavior it implements live after deletion? Only delete whole files when every top-level definition is genuinely dead. For test files specifically, classify by what's being tested before deleting: correctness tests are replaceable; security/safety tests must be preserved, migrated to a new test that exercises the same property, or explicitly deferred with a tracked requirement in a roadmap or plan document. Losing coverage of a security property silently is a regression even when the production code didn't change.
