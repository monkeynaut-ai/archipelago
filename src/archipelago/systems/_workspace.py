"""Shared workspace-provisioning constants for runnable systems.

Holds the base container image tag and the Docker-volume name generator.
Both are run-provisioning concerns shared by any pipeline that mounts a
workspace volume; the leading-underscore module name marks this as
intra-package shared machinery, not a public surface.
"""

from __future__ import annotations

import re
import time

# Base image for AgentAction containers. Hardcoded for Phase 2; sourced
# from Phase 3's published image once that ships. If the tag needs to
# change, update here and redeploy.
BASE_IMAGE_TAG = "agent-worker-foundry-dev:latest"


_VOLUME_NAME_UNSAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def generate_volume_name(feature_slug: str) -> str:
    """Produce a unique Docker-volume name for one pipeline run.

    Form: `archipelago-ws-{sanitized-slug}-{unix_nanoseconds}`. The
    nanosecond suffix makes same-second collisions astronomically rare
    (no observed collisions in practice at this resolution). The caller
    passes this name into both the container registry and bootstrap_fn
    so they agree on it.
    """
    sanitized = _VOLUME_NAME_UNSAFE.sub("-", feature_slug).strip("-") or "unnamed"
    return f"archipelago-ws-{sanitized}-{time.time_ns()}"
