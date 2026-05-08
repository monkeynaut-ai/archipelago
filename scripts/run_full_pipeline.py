"""Archipelago full-pipeline CLI.

Reads a feature-definition markdown file, invokes the full working-
session pipeline (workspace_bootstrap → designer → change_set_planner →
outer-loop[prepare → tdd_planner → inner-loop[log]]) against the named
repo + ref, and prints the produced documents' paths. Exit codes:
  0 — success.
  1 — pipeline runtime failure.
  2 — input-parse or argument error.

Usage:
    python scripts/run_full_pipeline.py \\
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
from archipelago.systems.pipeline import run_full_pipeline


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_full_pipeline",
        description=(
            "Run the Archipelago v0.1 working-session pipeline end-to-end "
            "(design + change-set planning + per-CS step planning)."
        ),
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
        "ANTHROPIC_API_KEY for agents and GITHUB_TOKEN for private clones.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

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
        final = asyncio.run(run_full_pipeline(feature_definition=feature, codebase_source=source))
    except AgentFailedError as exc:
        print(f"error: agent failed: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"error: pipeline failed: {exc}", file=sys.stderr)
        return 1

    if final.investigation_summary_path is not None:
        print(f"Investigation summary: {final.investigation_summary_path}")
    if final.design_document_path is not None:
        print(f"Design document: {final.design_document_path}")
    if final.change_sets_document_path is not None:
        print(f"Change-sets document: {final.change_sets_document_path}")
    if final.workspace_handle is not None:
        print(f"Workspace volume: {final.workspace_handle.volume_name}")
    if final.pr_url is not None:
        print(f"Pull request: {final.pr_url}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
