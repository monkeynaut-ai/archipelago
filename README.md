# Archipelago

A system of agents — AI models, humans, services, programs — that collaborate to do
real software engineering work, autonomously where possible, with human involvement
only where the work genuinely needs it.

> **Status: experimental.** Archipelago is a pre-1.0 research project and an active
> experiment, not a product. Interfaces, topology, and agent roster change without
> notice or deprecation cycles. There is no support commitment: issues and pull
> requests may go unanswered. Runs invoke LLMs and execute agent-authored code inside
> Docker containers — assume it will cost money, and read [Safety](#safety) before
> pointing it at a repository you care about.

## What it does

You give Archipelago a feature definition and a target repository. It runs a pipeline
of specialist agents that design the change, review that design, decompose it into
shippable change sets, plan each change set as a sequence of TDD steps, write the
tests, write the implementation, and open a pull request.

The pipeline's current shape:

```
workspace bootstrap
  └─ designer                      produce a design for the feature
       └─ design review            correctness + quality reviewers, retried until
          (retry, with operator    they pass; on exhaustion the operator is asked
           intervention)           to accept, abort, or retry with guidance
            └─ change-set planner  design → ordered, shippable change sets
                 └─ for each change set
                      ├─ TDD planner         change set → ordered tasks
                      │    └─ for each task
                      │         ├─ tester        write the failing test
                      │         └─ implementer   make it pass
                      └─ PR creator
```

Agents do not talk to each other. They exchange work through structured markdown
artifacts in a shared workspace, each rendered from and parsed back into a Pydantic
model. Splitting one agent into two means new files in the workspace, not a schema
migration — which is the point.

## Why it is shaped this way

Archipelago's central bet is that **coordinated specialist agents beat one generalist**,
and that the split points should be derived rather than borrowed from industry job
titles. The method — "harness competing tensions" — separates functions whose natural
pulls undermine each other (design coherence vs. shippable slicing) and groups
functions whose pulls reinforce.

The second bet is that this only compounds if **experimentation is cheap**. Topology,
instructions, task division, I/O shape, prompts, and control flow are all treated as
parameters to vary, not defaults to lock in.

Both bets, the north stars they serve, and the open questions they leave are argued in
full in [`docs/product/archipelago-vision.md`](docs/product/archipelago-vision.md).
Read that first if you want to understand the project rather than just run it.

## Requirements

- Python 3.14
- [PDM](https://pdm-project.org/)
- Docker — agents run in containers
- A Claude Code auth token (see [Authentication](#authentication))
- A GitHub token with access to the target repository

## Install

Archipelago builds on [Agent Foundry](https://github.com/monkeynaut-ai/agent-foundry), a
typed framework for declaring and running agentic systems. Agent Foundry is currently
consumed as a **sibling checkout**, so clone both into the same parent directory:

```bash
git clone https://github.com/monkeynaut-ai/agent-foundry.git
git clone https://github.com/monkeynaut-ai/archipelago.git
cd archipelago
pdm install
```

## Authentication

Worker containers require a Claude Code auth token. Set exactly one of:

**Option 1 — OAuth token (Claude Pro/Max subscription)**

```bash
claude setup-token          # generates a long-lived token
export CLAUDE_CODE_OAUTH_TOKEN="sk-ant-oat01-..."
```

**Option 2 — API key (API billing)**

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

The container entrypoint validates that exactly one auth method is set; an explicit
env allowlist passes the token from your host environment into the container.

You also need `GITHUB_TOKEN` set to a token that can clone the target repository and
open pull requests against it. Copy [`.env.example`](.env.example) to `.env` and fill
it in — the CLI loads `.env` itself.

## Run

A run takes a feature definition (markdown) and a target repository:

```bash
PYTHONPATH=src pdm run python scripts/run_full_pipeline.py \
    --feature examples/features/run-observability.md \
    --repo https://github.com/your-org/your-repo.git \
    --ref main
```

Bundled feature definitions live in [`examples/features/`](examples/features/).

Expect a run to take a long time and consume a substantial number of tokens. Runs emit
telemetry through MLflow when `AF_MLFLOW_BASE_URL` is configured.

## Safety

Archipelago executes LLM-authored code and git operations against a real repository.

- Agents run in Docker containers, but they are handed a clone of your target
  repository and a token that can write to it. **Point it at a repository you are
  willing to have modified**, and prefer a scratch fork while you are learning what it
  does.
- Scope `GITHUB_TOKEN` to the target repository only. A broadly scoped token gives a
  misbehaving run a correspondingly broad blast radius.
- Agent containers are not network-isolated. They reach the model provider and GitHub
  by design.

## Development

```bash
pdm test-unit          # everything except integration, benchmark, e2e
pdm test-integration   # integration only — needs Docker
pdm test-all           # the commit/PR gate
pdm test-e2e           # hits real LLMs; minutes per run; explicit invocation only
pdm lint               # ruff
pdm format             # ruff format
pdm typecheck          # pyright
```

Run tests through the `pdm` scripts — they set `PYTHONPATH=src`, so a bare `pytest`
will not resolve the `archipelago` package.

See [CONTRIBUTING.md](CONTRIBUTING.md) for conventions and workflow.

## Documentation

| Document | What it covers |
|---|---|
| [`docs/product/archipelago-vision.md`](docs/product/archipelago-vision.md) | The canonical frame: vision, north stars, operating philosophy, open threads |
| [`docs/engineering/`](docs/engineering/) | Development workflow and engineering notes |
| [`docs/architecture-wins.md`](docs/architecture-wins.md) | Architectural decisions that paid off |
| [`docs/run-reports/`](docs/run-reports/) | Postmortems from real pipeline runs |

## License

Apache-2.0 — see [LICENSE](LICENSE).
