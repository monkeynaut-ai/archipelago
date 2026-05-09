"""End-of-run hook that surfaces the workspace's lessons-learned.md.

Agents collaboratively append entries to ``lessons-learned.md`` inside
the workspace volume (per the ``lessons-learned`` skill in the base
agent image). The volume is retained after a run, but the canonical
home for run artifacts is the per-run directory under ``runs/``.
This hook bridges the two: at run-end, it reads the file from the
volume and writes a copy alongside ``lifecycle.jsonl`` and
``summary.txt`` so the lessons are visible without spinning up
``inspect-workspace.sh``.

Built as a factory because the volume name is not on ``RunContext`` —
each pipeline knows it at the call site of ``run_primitive_plan`` and
binds it into the closure here.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import docker

from archipelago.actions import workspace_ops
from archipelago.constants import (
    LESSONS_LEARNED_FILENAME,
    WORKSPACE_DOCUMENTS_PATH,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from agent_foundry.orchestration.run_context import RunEndedEvent

_LESSONS_LEARNED_PATH_IN_VOLUME = f"{WORKSPACE_DOCUMENTS_PATH}/{LESSONS_LEARNED_FILENAME}"

_log = logging.getLogger(__name__)


def make_lessons_learned_hook(volume_name: str) -> Callable[[RunEndedEvent], None]:
    """Return an ``on_run_ended`` hook bound to ``volume_name``.

    The hook reads ``/workspace/documents/lessons-learned.md`` from the
    volume via a throwaway alpine container and writes it to
    ``run_context.artifacts_dir / "lessons-learned.md"``. If the file
    does not exist, the hook silently no-ops — the lessons-learned skill
    instructs agents not to create the file when they have nothing
    useful to log, so absence is normal.
    """

    def hook(event: RunEndedEvent) -> None:
        client = docker.from_env()
        try:
            text = workspace_ops.read_file(
                client,
                volume_name=volume_name,
                path=_LESSONS_LEARNED_PATH_IN_VOLUME,
            )
        except RuntimeError as exc:
            # `read_file` raises RuntimeError on any cat failure —
            # most commonly, the file does not exist (no lessons logged).
            # Log at debug; not an error.
            _log.debug("lessons-learned.md not copied: %s", exc)
            return
        target = event.run_context.artifacts_dir / LESSONS_LEARNED_FILENAME
        target.write_text(text, encoding="utf-8")

    return hook
