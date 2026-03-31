"""Domain type aliases for the Archipelago pipeline.

These aliases document intent and enable LSP-based refactoring across the
codebase. At runtime they are plain strings/primitives — the value is in
readability, grep-ability, and future-proofing for when a type needs to
become a richer object.
"""

type WorkSpace = str
"""Docker volume name, e.g. ``"archipelago-1711234567"``."""

type CommitHash = str
"""Git SHA, e.g. ``"abc123def456"``."""

type RepoUrl = str
"""Git remote URL, e.g. ``"https://github.com/org/repo"``."""

type RepoRef = str
"""Branch or tag, e.g. ``"main"``."""

type Objective = str
"""Human-readable job objective describing what the pipeline should achieve."""
