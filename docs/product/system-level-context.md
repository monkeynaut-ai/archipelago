# System-Level Context Strategy — Potential Value for Archipelago

*Assessment of whether Agent Foundry's candidate focus — system-level context strategy as a swappable, comparable variable — would be useful for Archipelago, how, and how much value it could add.*

*Source brief: `~/engineering/professional-notes/research/topics/system-level-context-strategy-research-brief.md`.*

*Date: 2026-07-04.*

---

Yes — and Archipelago is arguably a stronger fit for this capability than the brief itself lets on, because Archipelago has already produced the exact failure the capability exists to prevent.

## Archipelago already has a context strategy — hand-built, hardcoded, and it has already failed

The 2026-05-12 MCP run postmortem is a textbook instance of the pain the brief hypothesizes: the run delivered only CS1 of 4 because the tester and implementer CLAUDE.md files were hardcoded to CS1 and re-invocation prompts carried no change-set context. That's not a prompt bug — it's a **provisioning-at-dispatch defect**: context was provisioned statically at build time when it needed to be parameterized per invocation. Archipelago is a live confirmation of the brief's demand hypothesis ("cross-agent context is a real, felt pain"), from inside the house.

Also notable: workspace-mediated communication (vision §3.2) *is* a cross-agent context strategy — agents read/write artifacts at known paths. But it was chosen once, by hand, as a principle. It's one point in the design space, never compared against alternatives. So Archipelago also confirms the brief's other hypothesis: "everyone hand-builds one strategy."

## How it would be useful

**1. Per-invocation context slicing — the immediate, concrete win.** Planner runs once per change set; implementer/tester get re-invoked per CS and per retry. Each invocation needs a different slice: the job spec, *its* change set, a summary of prior CS outcomes, current review feedback — not everything, and not CS1's context forever. Today that slicing lives ad hoc in role markdown, baked CLAUDE.md, and prompt assembly. A first-class strategy seat ("this AgentAction gets scoped-slice with carry-forward summaries") turns the postmortem's failure class into a configuration choice instead of scattered handwritten plumbing.

**2. It converts context into an experiment axis — which is what Archipelago says it is.** The tertiary north star (vision §3.4): every axis is a parameter; if experimenting with an axis is expensive, the architecture has failed. Context is currently the *least* swappable axis in the system — entangled across role markdown, container config, and workspace layout. Topology got construct trees; data models got single-source-of-truth; context got nothing. This capability fills the one axis where Archipelago currently violates its own philosophy.

**3. The tension-analysis method already generates heterogeneous context needs.** Cluster A (Designer) wants breadth — whole-codebase context. Cluster C (Planner) wants a narrow slice — one change set, discipline, nothing else. Cluster B sits between. §3.1 derives agents with *structurally different* context appetites, which is precisely what a per-agent context strategy layer serves. Without it, every agent gets whatever the hand-built plumbing happens to provide.

**4. Archipelago is the natural flagship demo for AF's comparability bet.** "Sweep N strategies, measure outcome + token cost" needs a real multi-agent workload with real outcome metrics. Archipelago has them: change sets delivered, tests passing, review-loop iterations, tokens burned. Run the same job spec under full-inherit vs. scoped-slice vs. summarized-handoff and the comparison is legible. Value flows both directions — Archipelago validates AF's focus; AF's capability de-risks Archipelago's runs.

## How much value

- **High and immediate** for the re-invocation/provisioning half. It addresses a demonstrated run-killing failure mode, and AF's container substrate (provisioning into CLAUDE.md, workspace paths — the agent's native locations) is exactly the mechanism Archipelago's containerized agents already ride on. The brief's "defensible seam" (provisioning-at-dispatch) is also the seam Archipelago needs most, since agents are ephemeral containers per invocation — a clean alignment.
- **Moderate and compounding** for the comparability half. The first sweep won't change what ships, but it operationalizes the experimentation north star for the one axis that currently has no lever.
- **Lower urgency** for evolution-during-run (mid-loop retrieval, compaction). Archipelago's ephemeral-container model mostly sidesteps it — though cross-run knowledge carry-forward (`docs/knowledge`, run reports feeding future runs) will eventually want it.

Two honest caveats. First, **separability isn't free here**: context is currently interwoven with role markdown and workspace-path conventions, so adopting the capability means extraction work in Archipelago, not just consuming a new AF API. Second, **§3.2 partially occupies the space** — the workspace-mediated principle already answers "how do agents share context" at the artifact level; the AF capability has to compose with it (strategy decides *which* artifacts/slices an invocation sees) rather than replace it, or the two layers will fight.

Net: for Archipelago specifically, this is plausibly the highest-leverage capability AF could add next — it fixes the last postmortem's root-cause class *and* unlocks the experiment axis the project's philosophy demands but doesn't yet have.

---

# Trying to Realize the Potential

*Based on the research report (`~/engineering/professional-notes/research/topics/system-level-context-strategy-research-report.md`, 2026-07-04), read with the lens: how do we actually derive the potential in real life — what Agent Foundry would need to implement, and how Archipelago would use it.*

The report's implementation sketch (its §9) maps almost one-to-one onto Archipelago's needs — but working it through "in real life" surfaces one gap the report doesn't name, one cost problem it names but Archipelago makes worse, and a natural sequencing where Archipelago gets paid before the thesis is even tested.

## The striking alignment: G2 *is* the postmortem

Report gap G2 — "instructions are provisioned once-at-creation; on container REUSE new instructions are not re-injected" (`registry.py:209-215`) — is the exact mechanism behind the 2026-05-12 failure (tester/implementer CLAUDE.md frozen at CS1 across re-invocations). And the report's incidental finding that the executor seam *already* receives `instructions` + `run_ctx` per invocation means it's a write-timing fix, not new plumbing. So its Step 3 (re-provisioning executor) isn't speculative platform investment for Archipelago — it's the fix for a known run-killing bug, delivered as a platform capability. That's the cleanest "derive the potential in real life" entry point there is.

## What Agent Foundry would need to implement

Taking the report's four steps and asking "what does Archipelago actually consume":

1. **`ContextStrategy` collaborator (report Step 1, closes G1)** — the seam itself. For Archipelago the migration is mechanical: current `prompt_builder`/`instructions_provider` callables become the "hand-written default" strategy, zero behavior change, then per-agent strategies get swapped in. This is the prerequisite for everything else.

2. **Per-invocation re-provisioning executor (report Step 3, closes G2)** — the postmortem fix. Implementer/tester re-invoked at CS3 get CS3's instructions. Archipelago wants this *regardless* of whether the comparability thesis pans out.

3. **`ProcessTarget` eval variant (report Step 4, closes G4)** — needed for any sweep, since Archipelago's unit of outcome is a process run (change sets delivered, tests pass), not a single AgentAction.

4. **The gap the report doesn't name: workspace-view scoping.** This is the real-life wrinkle. The report celebrates the typed boundary as honest scoped-slice provisioning — true *at the state layer*. But Archipelago's §3.2 principle means state carries thin pointers; the actual payload lives in the shared workspace volume, and `runner.py` mounts **one volume for every agent in the run**. So today, every strategy is full-inherit *at the filesystem layer* no matter what the typed slice says. A "scoped-slice" strategy that only controls which paths the prompt mentions is weak isolation — the agent can still wander the whole workspace. For strategies to genuinely differ in Archipelago, `ContextStrategy` needs a workspace-provisioning element: which artifacts get copied/mounted into *this* agent's view, not just which get named in the prompt. AF owns the container substrate, so this is reachable — but it's a fifth gap, and without it the Archipelago sweep would be comparing prompt-assembly variants while the filesystem quietly full-inherits underneath. This is exactly the report's separability risk (its §10e) in concrete form.

## How Archipelago would use it

**Per-agent strategy assignment falls straight out of the tension clusters.** The vision §3.1 method already derived heterogeneous context appetites, so the assignment is almost dictated:

- **Designer** (Cluster A, breadth) — full-inherit or retrieved-at-dispatch over the repo; it's *supposed* to see everything.
- **Decomposer** (Cluster B) — scoped-slice: design artifacts + job spec, not raw exploration transcripts.
- **Planner** (Cluster C, per-CS) — narrow scoped-slice: one change set, its AC, nothing else.
- **Implementer/Tester** — scoped-slice + summarized carry-forward: current CS spec + plan + a compact summary of prior CS outcomes + live review feedback. This is the re-invocation fix expressed as a strategy choice.
- **Future Reviewer** — a genuinely open choice (diff-only vs. diff+design vs. full-inherit), i.e. the first place a *sweep* answers a question Archipelago doesn't already know the answer to.

**The sweep — where real life bites.** The report's noise floor (2–6 pp single-run swings at temp 0; multi-run + power analysis mandatory) collides with Archipelago's economics: a full feature run is hours and many dollars, and multi-agent runs at ~15× chat tokens. `invocations_per_case ≥ 3–5` across N strategies on full feature jobs is not a casual experiment. Realistic mitigations: (a) sweep on **single-change-set jobs**, not full features — smaller, still exercises every boundary; (b) lean on the token-cost-as-proxy finding (~80% of outcome variance) so cost, which is cheap to measure precisely, does double duty; (c) treat the first sweep as the report's own recommended **separability probe** (its open question 2) — swap only the strategy, hold everything constant, and check whether outcomes move coherently at all before scaling up.

## The sequencing that de-risks everything

What's attractive here is that the value doesn't depend on the thesis being right:

1. **AF Steps 1 + 2** (strategy seam, scoped-slice on the typed boundary) → Archipelago migrates to the default strategy. Pure refactor, no behavior change, extraction work done.
2. **AF Step 3** → Archipelago fixes the CS-hardcoding failure class. **Payoff banked here**, before any experimentation claim is tested.
3. **Workspace-view scoping** (the unnamed gap) → strategies become genuinely distinct in Archipelago's workspace-mediated world.
4. **AF Step 4 + first sweep** on a single-CS job, N≥3 runs → this *is* the separability probe the report says to run before committing AF's focus, and Archipelago is the natural bed for it.

So the honest read: steps 1–2 are cheap insurance, step 3 pays for itself outright, and only steps 4+ carry the thesis risk (demand, separability, noise) — by which point Archipelago has already extracted the operational value and generated the evidence AF needs for its focus decision. The two projects fund each other's uncertainty.

---

# Research Topics

*Topics that would help realize the potential, ordered roughly by how much they de-risk before code gets written.*

1. **Separability in practice** — the load-bearing untested assumption (report risk §10e). Can you swap only the context strategy while holding prompt/tools/topology constant and get coherent outcome movement, or does context entangle with the reasoning that produced it (Cognition's "actions carry implicit decisions" argument)? Research design: minimal controlled experiment on a single-CS Archipelago job. This is the one topic worth resolving *before* committing AF's focus.

2. **Workspace-view scoping mechanics** — the gap the report doesn't name. How to give each containerized agent a scoped filesystem view of a shared workspace: per-agent volume mounts vs. copy-in/copy-out manifests vs. overlay filesystems vs. convention-plus-audit. Includes prior art (how Anthropic's research system, Devin, and CI systems scope worker filesystems) and the git-versioned-workspace endgame.

3. **Summarized carry-forward design** — the strategy Archipelago's implementer/tester re-invocations need most. What makes a good inter-change-set summary: what to preserve (decisions, deviations from plan, gotchas) vs. drop (transcript detail); who writes it (the outgoing agent, a dedicated summarizer AICall, deterministic extraction from artifacts); and how summary quality degrades across CS chains (error accumulation — the Cognition failure mode).

4. **Cheap, credible comparison signal for process-level sweeps** — how to get statistically defensible strategy comparisons when one run costs hours/dollars. Covers the agent-eval-noise literature (multi-run, power analysis, pass@k), whether the token-cost-as-proxy claim (~80% of outcome variance) holds for context-strategy variation specifically, and what minimal benchmark task set (single-CS jobs) gives signal without feature-scale cost.

5. **Cross-agent context strategy taxonomy completion** — the report's coverage holes: CrewAI, AutoGen/AG2, Pydantic AI, LlamaIndex Workflows, Semantic Kernel, mem0/Zep/LangMem/Cognee. Two payoffs: confirms the whitespace (nobody ships strategies as swappable units) and harvests strategy designs worth putting in AF's named library.

6. **Direct demand harvesting** — the report's weakest dimension (low–medium). GitHub issues, postmortems, practitioner talks on cross-agent context pain in real multi-agent deployments — not maintainer acknowledgments. Determines whether AF's positioning targets a felt pain or a niche elegance.

7. **Per-invocation instruction re-provisioning semantics** — narrower and more engineering-flavored: what should change between invocations of a reused container (instructions, MCP config, workspace deltas), what must stay stable (identity, accumulated scratch state), and where exactly the AF-lane/harness-lane boundary sits (per-invocation vs. mid-turn). Feeds directly into AF Step 3's design.

If only three can be funded: **1, 2, 4** — separability decides whether the thesis holds, workspace scoping decides whether strategies can genuinely differ in Archipelago, and comparison signal decides whether the flagship demo can be believed.

---

# Research Methodology for Topics 1, 2, and 4

Each wants a different method — 1 is an experiment, 2 is prior-art survey + spike, 4 is literature + a variance pilot. And there's a sequencing trick: 4's pilot and 1's experiment can share the same runs.

## Topic 1 — Separability: a controlled experiment, not literature

This can't be answered by reading; it's an empirical claim about our own system (falsification-gate discipline: reproduction beats inference).

- **Rig**: don't wait for the AF `ContextStrategy` seam. Hand-roll it — the seam already exists de facto as `prompt_builder`/`instructions_provider`. Write 3 strategy variants as alternative callables: full-inherit, scoped-slice, summarized-handoff.
- **Task**: one single-CS job on a small, real repo (not a toy — the entanglement risk lives in real codebase context). Freeze everything else: same job spec, same agents, same model, same tools, same topology.
- **Runs**: N≥5 per strategy (15 runs total at single-CS scale is affordable).
- **Measure**: quantitative — tests pass, CS delivered, review iterations, tokens; qualitative — read trajectories for entanglement signatures: does the scoped-slice agent burn turns re-deriving context it wasn't given? Does the summary-fed agent act on stale implicit decisions? Entanglement shows up as *compensating behavior*, not just as score deltas.
- **Verdict criterion**: strategy effect is "coherent" if direction is consistent across runs and magnitude exceeds the run-to-run noise floor (which topic 4 gives us). If effects are incoherent or the qualitative read shows strategies leaking into agent reasoning, separability fails — a disconfirmation worth having before AF commits its focus.

## Topic 2 — Workspace scoping: prior-art survey, then a spike

Two-phase, mostly desk research first.

- **Phase A — survey** (good fit for the deep-research workflow): how existing systems give workers scoped filesystem views. Concrete targets: Bazel/Buck sandboxing (the most mature "declared inputs only" filesystem model), GitHub Actions/CI workspace scoping, git `sparse-checkout` + worktrees (directly relevant to the git-versioned-workspace endgame), Docker mount options (subpath mounts, read-only mounts, overlayfs), Anthropic's research-system writeup and any Devin/Cognition material on worker isolation. Output: a mechanism catalog scored on isolation strength (advisory vs. enforced), setup cost per invocation, compatibility with container REUSE, and path to the git endgame.
- **Phase B — spike in AF**: prototype the top two mechanisms against the real `runner.py` volume handling. Likely candidates: (i) copy-in manifest — strategy declares artifact paths, they're copied into a per-agent volume (strong isolation, cost = copy time); (ii) read-only full mount + declared writable subtree (weak read isolation, cheap, halfway house). Measure setup latency per invocation, since it multiplies across every dispatch.
- **Deliverable**: decision matrix + measured spike numbers, feeding directly into the fifth-gap design.

## Topic 4 — Comparison signal: literature verification, then a variance-baseline pilot

- **Phase A — verify the two load-bearing claims** (both currently inferred-from-fetch): read arXiv 2602.07150 properly and extract its actual recommended protocol (how many runs, what statistical test, pass@k vs. mean); trace Anthropic's "token usage explains ~80% of variance" claim to its source and its scope — it was measured on *research* tasks, and whether it transfers to code-generation outcomes is exactly what we can't assume.
- **Phase B — variance-baseline pilot**: before sweeping anything, run *one* configuration (current hand-built strategy) N=5–8 times on the same single-CS job and measure run-to-run variance on our actual metrics. This is the number everything else hangs on: it tells us the minimum detectable effect size, and therefore whether a 3-strategy × 5-run sweep can say anything at all.
- **Phase C — power analysis**: given observed variance, compute the N needed to detect a plausible strategy effect (say 10–20 pp on CS-success). If the answer is N=40, the sweep design changes (more/smaller tasks, or lean harder on token cost as the primary signal, which has far lower measurement noise).
- Also test the proxy hypothesis on our own data: within the pilot runs, does token spend correlate with outcome? If yes, cost becomes both axes and the sweep gets much cheaper.

## The sequencing trick

Run 4B first — its repeated same-config runs *are* the noise floor that topic 1's verdict criterion needs. Then topic 1's experiment adds the other strategy arms to an already-measured baseline: 4B's five runs become the full-inherit arm of 1's experiment. One combined campaign, roughly: 5 baseline runs → power check → 10 more runs across two alternative strategies → separability verdict + comparison-signal design, both from the same ~15-run budget. Topic 2 proceeds in parallel as desk research since it shares no runs.
