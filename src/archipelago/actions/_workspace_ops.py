"""Private helpers that isolate Docker + git side effects for bootstrap_fn.

Every helper takes an explicit docker.DockerClient — no module-level
client, no ambient state. Image tags used by throwaway containers are
pinned; callers pre-pull them via pull_image so bootstrap_fn fails
fast on network issues before creating a volume.
"""

from __future__ import annotations

import io
import posixpath
import tarfile

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
            entrypoint="",
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


def chmod_tree_excluding_git(
    client: DockerClient,
    *,
    volume_name: str,
    path: str,
    mode: str,
) -> None:
    """Apply chmod `mode` recursively to `path`, pruning .git/ so git
    tooling keeps its write access to index and pack locks."""
    # Strip trailing slash so `{path}/.git` renders without a double
    # slash; find's -path comparison is byte-exact and a double slash
    # would silently fail to match real .git/ and wipe its perms.
    path = path.rstrip("/")
    # `find` with -prune excludes .git/ from the traversal; the
    # alternation runs chmod on everything else.
    script = f"find {path} -path '{path}/.git' -prune -o -exec chmod {mode} {{}} +"
    try:
        client.containers.run(
            ALPINE_IMAGE,
            command=["sh", "-c", script],
            volumes={volume_name: {"bind": "/workspace", "mode": "rw"}},
            remove=True,
        )
    except docker.errors.ContainerError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
        raise RuntimeError(f"chmod -R {mode} {path!r} (excluding .git) failed: {stderr}") from exc


def chmod_path(
    client: DockerClient,
    *,
    volume_name: str,
    path: str,
    mode: str,
) -> None:
    """chmod `path` to `mode` (non-recursive)."""
    try:
        client.containers.run(
            ALPINE_IMAGE,
            command=["sh", "-c", f"chmod {mode} {path}"],
            volumes={volume_name: {"bind": "/workspace", "mode": "rw"}},
            remove=True,
        )
    except docker.errors.ContainerError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
        raise RuntimeError(f"chmod {mode} {path!r} failed: {stderr}") from exc


DOCUMENTS_DIR_MODE = "775"


def prepare_documents_dir(client: DockerClient, *, volume_name: str) -> None:
    """mkdir -p /workspace/documents and chmod it 0775 so a non-root
    designer container can create design.md there.

    Ownership UID is whatever the throwaway container's default is
    (root in alpine), matched by the agent-worker base image running
    with a matching UID. If a future base image uses a different UID,
    add a chown step here.
    """
    script = "mkdir -p /workspace/documents && chmod 775 /workspace/documents"
    try:
        client.containers.run(
            ALPINE_IMAGE,
            command=["sh", "-c", script],
            volumes={volume_name: {"bind": "/workspace", "mode": "rw"}},
            remove=True,
        )
    except docker.errors.ContainerError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
        raise RuntimeError(f"prepare_documents_dir failed: {stderr}") from exc


def write_file(
    client: DockerClient,
    *,
    volume_name: str,
    path: str,
    content: str,
    mode: str | None = None,
) -> None:
    """Write content to path inside volume_name.

    Streams a tar archive into the target directory via put_archive on a
    helper container — atomic, avoids shell-quoting hazards for UTF-8.
    If `mode` is supplied, chmods the file after writing.
    """
    directory, filename = posixpath.split(path)

    tar_buf = io.BytesIO()
    encoded = content.encode("utf-8")
    with tarfile.open(fileobj=tar_buf, mode="w") as tar:
        info = tarfile.TarInfo(name=filename)
        info.size = len(encoded)
        info.mode = 0o644
        tar.addfile(info, io.BytesIO(encoded))
    tar_bytes = tar_buf.getvalue()

    helper = client.containers.create(
        ALPINE_IMAGE,
        command=["true"],
        volumes={volume_name: {"bind": "/workspace", "mode": "rw"}},
    )
    try:
        helper.put_archive(directory, tar_bytes)
    finally:
        helper.remove()

    if mode is not None:
        chmod_path(client, volume_name=volume_name, path=path, mode=mode)
