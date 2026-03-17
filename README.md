# Archipelago

Autonomous system for software engineering.

## Authentication

Docker worker containers require a Claude Code auth token. Set exactly one of:

**Option 1: OAuth token (Claude Pro/Max subscription)**
```bash
claude setup-token          # generates a long-lived token
export CLAUDE_CODE_OAUTH_TOKEN="sk-ant-oat01-..."
```

**Option 2: API key (API billing)**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

The `ContainerManager` env allowlist passes the token from your host environment into the container automatically. The container entrypoint validates that exactly one auth method is set.
