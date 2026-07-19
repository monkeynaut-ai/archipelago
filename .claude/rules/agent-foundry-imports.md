---
paths:
  - "**/*.py"
---

# Importing from agent-foundry

agent-foundry exposes a tiered public API. Import symbols from the **package
facade**, never from the deep module that defines them — a ruff `banned-api`
guard (`pyproject.toml`) fails lint on the deep path.

```python
# wrong — banned
from agent_foundry.orchestration.run_outcome import RunOutcome
# right
from agent_foundry.orchestration import RunOutcome
```

Facades to import from: `agent_foundry.constructs`, `agent_foundry.ai_models`,
`agent_foundry.models`, `agent_foundry.agents`, `agent_foundry.compiler`,
`agent_foundry.orchestration`, `agent_foundry.responders`.

If a symbol isn't re-exported by its facade, that's a signal it's Internal-tier
and not meant for use here — don't reach past the facade to get it.
