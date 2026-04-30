"""Shared artifacts-directory helper for runnable Archipelago systems.

Both `design_pipeline` and `full_pipeline` land per-run artifacts under
`cwd/runs/<YYYY-MM-DD-HH-MM-SS>/`. Centralizing here keeps the layout
consistent across pipelines so a developer can grep `runs/` confidently.
The leading-underscore module name marks this as intra-package shared
machinery, not a public surface.
"""

from __future__ import annotations

import datetime
from pathlib import Path


def artifacts_dir_for_run() -> Path:
    """Return `cwd/runs/<YYYY-MM-DD-HH-MM-SS>/`.

    Second-resolution timestamps make per-run directories sortable and
    human-readable without the visual noise of nanoseconds. The volume
    name handles same-second uniqueness elsewhere.
    """
    ts = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    return Path.cwd() / "runs" / ts
