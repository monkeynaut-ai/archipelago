# Architecture Wins: Designing Operator-Guided Retry Cleanly

A record of the design principles that produced a clean solution to operator-guided
retry, and the Agent Foundry properties that made them applicable. Captured from the
design discussion that reframed the `GuidedRetry` primitive as an extension of `Retry`.

## Context

The starting point was a proposed new `GuidedRetry` primitive plus a feature def whose
exhaustion / exception / gating concerns were tangled and brittle. Pulling those concerns
apart led to a design that needs **no new primitive** — only a backwards-compatible
extension of `Retry`. These are the principles that licensed that outcome.

## Design principles that produced the clean solution

**Orthogonality — find the axes, separate them.** The unlock was noticing that "did the
attempt pass," "did the attempt error," and "now what" are three independent axes braided
into two channels. Cleanness came from naming the axes, not from cleverness. Brittleness is
almost always two concerns sharing one mechanism.

**One vocabulary per axis (make the conflation unrepresentable).** Collapsing pass/fail and
clean/errored into a single `AttemptOutcome` (`PASSED | NOT_PASSED | ERRORED`) means an
attempt has exactly one outcome value. The hard cross-cutting question — does an exception
count against the attempt budget, the guided budget, surface to the gate — did not get
*solved*; it became *unsayable*. The best fix to a hard interaction question is a
representation in which the question can't be posed.

**Extend the seat, don't add a parallel structure.** The original design re-grew a loop next
to `Retry`'s loop. The fix routed the new capability through the *existing* extension point
(`on_exhaustion`) plus one new return variant (`CONTINUE`). Prefer a new value in an existing
type over a new type beside it.

**Program to a contract, not a participant (polymorphism at a seam).** `Retry` consults a
resolver that returns a uniform disposition (`STOP | RAISE | CONTINUE`); it stays blind to
whether a human, agent, or function produced it. The "operator is a role, not a species"
requirement fell out of defining one seam carefully rather than special-casing each kind.

**Late binding of authority.** *Who* decides continuation is deferred to runtime
configuration — which primitive fills the resolver seat — not baked into the loop. That is
what yields stdin-vs-Slack-vs-agent for free.

**Meta-principle: harness the competing tensions instead of hard-coding a winner.**
"Automated judgment vs. external judgment" and "stop vs. continue" were being treated as
enumerable special cases. The clean design makes them poles the *same* mechanism spans.

## Agent Foundry properties that made this possible

**Everything is `Primitive[I, O]`, uniformly typed and composable.** Because `body` is
already "any primitive," putting "any primitive" in a resolver seat is the same move the
framework already makes everywhere. The resolver slot isn't a new concept — it's the existing
composition model pointed at a new position.

**State is plain Pydantic passed uniformly between primitives.** An `AttemptOutcome` or a
disposition is just another typed value flowing through state. The framework already treats
every participant's output identically — which is exactly why "operator verdict = automated
verdict, same shape" is free rather than engineered.

**Declarative models separated from the compiler.** Primitives are data; behavior lives in
the compiler. Adding a `CONTINUE` disposition or widening `on_exhaustion` is a model-field
change plus a compiler branch — not a runtime-hook redesign. The feature def's "no new
runtime-level hooks" constraint is satisfiable *because* control flow lives in compiled
primitives, not bespoke runtime machinery.

## What made the operator comm channel (stdin, Slack, …) swappable

Channel-swapping lives one layer down, in `GateAction`'s design:

**Mechanism/transport split.** `GateAction` owns one invariant semantic — *block until
external input arrives, return it as typed state*. The channel that physically delivers the
prompt and collects the reply is a separate concern. Stdin vs Slack changes the transport;
the gate's contract doesn't move. Swapping is possible because the thing that varies
(delivery) was never entangled with the thing that's stable (block-and-resume).

**Indirection by name, not by embedded logic.** The gate references the channel through
`interaction` (a string) and the payload through `prompt_key` (a state-field name) — it
carries no stdin/Slack code itself. Adding Slack is registering a new transport against a new
`interaction` value, not editing the primitive. The primitive names what it needs; resolution
happens outside it.

**Uniform typed boundary.** Every channel resolves to the same shape — a string prompt in, a
validated Pydantic decision out. Because the response is parsed identically regardless of
source, a new channel can't leak channel-specific structure into the loop.

### Does declarativeness drive channel-swapping?

Real but secondary for this axis. The actual swap rides on **named indirection**
(`interaction` string + a transport bound in the compiler); a plain OO object with an
`interaction` field would swap channels just as easily. Where declarativeness still earns its
keep here:

- **Single bind point.** With behavior in the compiler, `interaction → transport` resolves in
  one place. Add Slack once, every `GateAction` in every pipeline gets it.
- **Channel choice is inspectable, serializable data.** `GateAction(interaction="slack")` is a
  value, not a closure — so a pipeline's channel selections can be validated, diffed, or
  generated before anything runs. This matters more for *governing* channels at scale than for
  the swap itself.

Declarativeness is genuinely load-bearing on the *other* axis — evolving `Retry`'s control
flow (`CONTINUE`, richer `on_exhaustion`) without new framework surface.

## The two independent pluggability axes

The design buys two orthogonal axes of extension, each achieved by refusing to let the
variable concern touch the invariant one:

- **Which participant** (gate vs agent vs function) — `Retry` is blind to it; the resolver seat
  carries it.
- **Which channel** (stdin vs Slack) — `GateAction` is blind to it; the transport binding
  carries it.
