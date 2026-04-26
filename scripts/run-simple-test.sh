#!/usr/bin/env bash
# Run the design pipeline against the bundled run-observability feature
# definition, targeting agent-foundry's main branch.
#
# Auth:
#   CLAUDE_CODE_OAUTH_TOKEN: must be in .env (the CLI loads .env itself).
#   GITHUB_TOKEN: this script prefers `gh auth token` (the host's
#     credentials, which have access to private 730alchemy repos) over
#     whatever is in .env, since .env tokens have historically been
#     stale or under-scoped for the private clone path. Falls back to
#     whatever the CLI loads from .env if `gh` isn't authenticated.

set -euo pipefail

cd "$(dirname "$0")/.."

if command -v gh >/dev/null 2>&1 && gh auth token >/dev/null 2>&1; then
    export GITHUB_TOKEN="$(gh auth token)"
fi

PYTHONPATH=src pdm run python scripts/run_design_pipeline.py \
    --feature examples/features/run-observability.md \
    --repo https://github.com/730alchemy/agent-foundry.git \
    --ref main
