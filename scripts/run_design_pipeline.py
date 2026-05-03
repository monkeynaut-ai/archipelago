"""Archipelago design-pipeline CLI.

Reads a feature-definition markdown file, invokes the design pipeline
against the named repo + ref, and prints the produced design document's
path. Exit codes:
  0 — success.
  1 — pipeline runtime failure (bootstrap or designer).
  2 — input-parse or argument error.

Usage:
    python scripts/run_design_pipeline.py \\
        --feature examples/features/run-observability.md \\
        --repo https://github.com/730alchemy/agent-foundry.git \\
        --ref main
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from agent_foundry.orchestration.errors import AgentFailedError
from archetype.markdown import MarkdownValidationError, validate_markdown
from dotenv import load_dotenv

from archipelago.models import CodebaseSource, FeatureDefinition
from archipelago.systems.design_pipeline import run_design_pipeline


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_design_pipeline",
        description="Run the Archipelago design pipeline (bootstrap → designer).",
    )
    parser.add_argument(
        "--feature", required=True, help="Path to a feature-definition markdown file."
    )
    parser.add_argument("--repo", required=True, help="Git URL of the target codebase.")
    parser.add_argument("--ref", required=True, help="Git ref (commit SHA, branch, or tag).")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to a dotenv file to load into the process environment "
        "(default: .env in cwd). Provides CLAUDE_CODE_OAUTH_TOKEN / "
        "ANTHROPIC_API_KEY for the designer and GITHUB_TOKEN for private clones.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Load dotenv FIRST so downstream env reads (agent-foundry's
    # CLAUDE_CODE_OAUTH_TOKEN forwarding, bootstrap_fn's GITHUB_TOKEN
    # lookup) see the values. override=False — explicit exports from
    # the parent shell win.
    load_dotenv(args.env_file, override=False)

    feature_path = Path(args.feature)
    if not feature_path.exists():
        print(f"error: feature file not found: {feature_path}", file=sys.stderr)
        return 2

    try:
        text = feature_path.read_text(encoding="utf-8")
        feature = validate_markdown(text, FeatureDefinition)
    except MarkdownValidationError as exc:
        print(f"error: failed to parse feature: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"error: unexpected parse error: {exc}", file=sys.stderr)
        return 2

    source = CodebaseSource(repo_url=args.repo, ref=args.ref)

    try:
        final = asyncio.run(run_design_pipeline(feature_definition=feature, codebase_source=source))
    except AgentFailedError as exc:
        print(f"error: designer failed: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        # bootstrap_fn wraps docker / git errors as RuntimeError with
        # descriptive messages.
        print(f"error: bootstrap failed: {exc}", file=sys.stderr)
        return 1

    # AgentFilePath verification guarantees designer_output when the
    # agent emits success, but print defensively and surface the
    # volume name so the user can inspect the workspace.
    if final.designer_output is not None:
        print(f"Investigation summary: {final.designer_output.investigation_summary}")
        print(f"Design document: {final.designer_output.design_document_path}")
    if final.workspace_handle is not None:
        print(f"Workspace volume: {final.workspace_handle.volume_name}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
