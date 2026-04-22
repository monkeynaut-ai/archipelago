"""Archipelago function-action primitives.

A function action executes deterministic Python — no LLM, no container.
`workspace_bootstrap` provisions the shared Docker volume that every
Archipelago run operates on.
"""

from __future__ import annotations

from archipelago.actions.workspace_bootstrap import WorkspaceHandle

__all__ = ["WorkspaceHandle"]
