"""Private helpers that isolate Docker + git side effects for bootstrap_fn.

Every helper takes an explicit docker.DockerClient — no module-level
client, no ambient state. Image tags used by throwaway containers are
pinned; callers pre-pull them via pull_image so bootstrap_fn fails
fast on network issues before creating a volume.
"""

from __future__ import annotations

import docker.errors
from docker.client import DockerClient
from docker.models.volumes import Volume

GIT_IMAGE = "alpine/git:v2.47.2"
ALPINE_IMAGE = "alpine:3.20"


def pull_image(client: DockerClient, tag: str) -> None:
    """Pull `tag` so that subsequent `containers.run(tag, ...)` calls
    don't hit an inline pull (and its associated failure modes) during
    the critical section of bootstrap_fn."""
    client.images.pull(tag)


def create_volume(client: DockerClient, name: str) -> Volume:
    """Create a Docker volume with the given name.

    Raises docker.errors.APIError on name conflicts or invalid names.
    """
    return client.volumes.create(name=name)


def clone_and_resolve_ref(
    client: DockerClient,
    *,
    volume_name: str,
    repo_url: str,
    ref: str,
) -> str:
    """Clone repo_url into /workspace/codebase inside volume_name, check
    out ref, and return the resolved commit SHA.

    Uses a throwaway alpine/git container mounting the volume at
    /workspace. .git/ is preserved for Designer's git log / git blame.
    """
    script = (
        f"set -e && "
        f"git clone {repo_url} /workspace/codebase && "
        f"git -C /workspace/codebase checkout {ref} && "
        f"git -C /workspace/codebase rev-parse HEAD"
    )
    try:
        raw = client.containers.run(
            GIT_IMAGE,
            command=["sh", "-c", script],
            volumes={volume_name: {"bind": "/workspace", "mode": "rw"}},
            remove=True,
            stdout=True,
            stderr=False,
        )
    except docker.errors.ContainerError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
        raise RuntimeError(f"git clone failed for repo={repo_url!r} ref={ref!r}: {stderr}") from exc

    output = raw.decode("utf-8", errors="replace").strip()
    last_line = next(line.strip() for line in reversed(output.splitlines()) if line.strip())
    return last_line
