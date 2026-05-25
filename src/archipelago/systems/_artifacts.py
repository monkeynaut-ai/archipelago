"""Shared artifacts-directory helper for runnable Archipelago systems.

Runnable systems land per-run artifacts under
`cwd/runs/<YYYY-MM-DD-HH-MM-SS>/`. Centralizing here keeps the layout
consistent across pipelines so a developer can grep `runs/` confidently.
The leading-underscore module name marks this as intra-package shared
machinery, not a public surface.
"""

from __future__ import annotations

import datetime
from pathlib import Path


def run_artifacts_layout() -> tuple[Path, str]:
    """Return ``(parent_dir, run_id)`` for ``run_primitive_plan``.

    ``agent_foundry`` always creates ``<parent_dir>/<run_id>/``. Passing
    ``Path.cwd() / "runs"`` as the parent and a second-resolution
    timestamp as the run_id yields a single effective layer:
    ``runs/<YYYY-MM-DD-HH-MM-SS>/``. Second-resolution timestamps make
    per-run directories sortable and human-readable.
    """
    ts = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    return Path.cwd() / "runs", ts
