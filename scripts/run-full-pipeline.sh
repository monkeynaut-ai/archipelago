#!/usr/bin/env bash
# Run the full pipeline against the bundled run-observability feature
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

usage() {
    echo "usage: $(basename "$0") FEATURE [--ref REF]" >&2
    exit 2
}

if [[ $# -lt 1 ]]; then usage; fi
feature="$1"
shift

ref="main"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --ref) [[ $# -ge 2 ]] || usage; ref="$2"; shift 2 ;;
        --ref=*) ref="${1#--ref=}"; shift ;;
        *) echo "unknown argument: $1" >&2; usage ;;
    esac
done

if command -v gh >/dev/null 2>&1 && gh auth token >/dev/null 2>&1; then
    export GITHUB_TOKEN="$(gh auth token)"
fi

PYTHONPATH=src pdm run python scripts/run_full_pipeline.py \
    --feature "$feature" \
    --repo https://github.com/730alchemy/agent-foundry.git \
    --ref "$ref"

