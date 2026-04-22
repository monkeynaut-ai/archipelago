"""Archipelago agents package. Public entry points for agent primitives."""

from __future__ import annotations

# Ensure designer submodule is importable by importing it here.
# This makes it available as agents.designer without overwriting the module reference.
import archipelago.agents.designer  # noqa: F401

__all__ = ["designer"]
