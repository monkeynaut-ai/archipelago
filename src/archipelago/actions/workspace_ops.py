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

from archipelago.constants import GID_CODEBASE, GID_DOCUMENTS, GID_TESTS, WORKSPACE_ROOT

GIT_IMAGE = "alpine/git:v2.47.2"
ALPINE_IMAGE = "alpine:3.20"

_GITHUB_HTTPS_PREFIX = "https://github.com/"


def _decode_container_stderr(exc: docker.errors.ContainerError) -> str:
    """docker-py types ContainerError.stderr as str | None but populates
    it with bytes at runtime. Normalize to str for error messages."""
    stderr = exc.stderr
    if stderr is None:
        return str(exc)
    if isinstance(stderr, bytes):
        return stderr.decode("utf-8", errors="replace")
    return stderr


def _with_github_token(repo_url: str, github_token: str | None) -> str:
    """Inject x-access-token auth into an HTTPS GitHub URL. No-op for
    other URL shapes (SSH, non-github hosts, tokenless case)."""
    if not github_token or not repo_url.startswith(_GITHUB_HTTPS_PREFIX):
        return repo_url
    tail = repo_url[len(_GITHUB_HTTPS_PREFIX) :]
    return f"https://x-access-token:{github_token}@github.com/{tail}"


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
    codebase_path: str,
    github_token: str | None = None,
) -> str:
    """Clone repo_url into /workspace/codebase inside volume_name, check
    out ref, and return the resolved commit SHA.

    Uses a throwaway alpine/git container mounting the volume at
    /workspace. .git/ is preserved for Designer's git log / git blame.

    Sets ``core.fileMode = false`` on the cloned repo so the workspace's
    permission setup (``prepare_codebase_tree`` runs ``chmod 775`` over
    the tree, which flips the executable bit on every regular file)
    doesn't pollute every agent-side ``git diff`` with mode-only noise.

    If github_token is provided and repo_url is an HTTPS GitHub URL, the
    URL is rewritten to use x-access-token auth for private-repo cloning.
    The original repo_url (without token) is used in error messages.
    """
    effective_url = _with_github_token(repo_url, github_token)
    script = (
        f"set -e && "
        f"git clone {effective_url} {codebase_path} && "
        f"git -C {codebase_path} checkout {ref} && "
        f"git -C {codebase_path} config core.fileMode false && "
        f"git -C {codebase_path} rev-parse HEAD"
    )
    try:
        raw = client.containers.run(
            GIT_IMAGE,
            command=["sh", "-c", script],
            entrypoint="",
            volumes={volume_name: {"bind": WORKSPACE_ROOT, "mode": "rw"}},
            remove=True,
            stdout=True,
            stderr=False,
        )
    except docker.errors.ContainerError as exc:
        stderr = _decode_container_stderr(exc)
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
            volumes={volume_name: {"bind": WORKSPACE_ROOT, "mode": "rw"}},
            remove=True,
        )
    except docker.errors.ContainerError as exc:
        stderr = _decode_container_stderr(exc)
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
            volumes={volume_name: {"bind": WORKSPACE_ROOT, "mode": "rw"}},
            remove=True,
        )
    except docker.errors.ContainerError as exc:
        stderr = _decode_container_stderr(exc)
        raise RuntimeError(f"chmod {mode} {path!r} failed: {stderr}") from exc


DOCUMENTS_DIR_MODE = "775"


def prepare_codebase_tree(client: DockerClient, *, volume_name: str, codebase_path: str) -> None:
    """Set up codebase ownership and permissions after the clone.

    Splits write privileges along the standard layout:

    - Everything under ``codebase_path`` (excluding ``.git/``) is chowned to
      ``root:GID_CODEBASE`` and chmodded ``775`` so an agent holding
      ``GID_CODEBASE`` can write source files. Read access for others
      stays at ``r-x`` so agents without the GID can still read.
    - ``codebase_path/tests/`` (if it exists) is then re-chowned to
      ``root:GID_TESTS`` so an agent holding ``GID_TESTS`` (and not
      ``GID_CODEBASE``) can write tests but cannot modify source.
    - ``.git/`` is chowned to ``root:GID_CODEBASE`` and made
      group-writable, with the setgid bit on directories so that
      objects/refs/logs git creates later inherit ``GID_CODEBASE``
      rather than the agent's primary group. The implementer needs
      this to run ``git add`` / ``git commit``; agents without
      ``GID_CODEBASE`` can still read via the "other" ``r-x`` bits.
    """
    codebase_path = codebase_path.rstrip("/")
    tests_path = f"{codebase_path}/tests"
    git_path = f"{codebase_path}/.git"
    script = (
        f"set -e && "
        f"find {codebase_path} -path '{git_path}' -prune -o "
        f"-exec chown root:{GID_CODEBASE} {{}} + && "
        f"find {codebase_path} -path '{git_path}' -prune -o "
        f"-exec chmod 775 {{}} + && "
        f"if [ -d {tests_path} ]; then chown -R root:{GID_TESTS} {tests_path}; fi && "
        # .git/: implementer (GID_CODEBASE) needs write for git add/commit.
        # Setgid on directories so newly-created refs/objects/logs inherit
        # GID_CODEBASE instead of the agent's primary group.
        f"chown -R root:{GID_CODEBASE} {git_path} && "
        f"chmod -R g+w {git_path} && "
        f"find {git_path} -type d -exec chmod g+s {{}} +"
    )
    try:
        client.containers.run(
            ALPINE_IMAGE,
            command=["sh", "-c", script],
            volumes={volume_name: {"bind": WORKSPACE_ROOT, "mode": "rw"}},
            remove=True,
        )
    except docker.errors.ContainerError as exc:
        stderr = _decode_container_stderr(exc)
        raise RuntimeError(f"prepare_codebase_tree failed for {codebase_path!r}: {stderr}") from exc


def prepare_documents_dir(client: DockerClient, *, volume_name: str, path: str) -> None:
    """mkdir -p `path`, chown to root:GID_DOCUMENTS, chmod 775.

    Group ownership + mode 775 lets any agent holding GID_DOCUMENTS write
    there; all others get r-x (read-only).
    """
    script = f"mkdir -p {path} && chown root:{GID_DOCUMENTS} {path} && chmod 775 {path}"
    try:
        client.containers.run(
            ALPINE_IMAGE,
            command=["sh", "-c", script],
            volumes={volume_name: {"bind": WORKSPACE_ROOT, "mode": "rw"}},
            remove=True,
        )
    except docker.errors.ContainerError as exc:
        stderr = _decode_container_stderr(exc)
        raise RuntimeError(f"prepare_documents_dir failed: {stderr}") from exc


def read_file(
    client: DockerClient,
    *,
    volume_name: str,
    path: str,
) -> str:
    """Read a UTF-8 text file from inside the workspace volume.

    Spawns a throwaway alpine container that mounts the volume read-only
    and `cat`s the file. Used by Loop's `over` lambdas to parse markdown
    documents written by upstream agents — host-side composition needs
    a bridge to in-volume content.
    """
    try:
        output = client.containers.run(
            ALPINE_IMAGE,
            command=["cat", path],
            volumes={volume_name: {"bind": WORKSPACE_ROOT, "mode": "ro"}},
            detach=False,
            remove=True,
        )
    except docker.errors.ContainerError as exc:
        stderr = _decode_container_stderr(exc)
        raise RuntimeError(f"read_file({path}) failed: {stderr}") from exc
    return output.decode("utf-8")


def make_change_sets_dir(client: DockerClient, *, volume_name: str, path: str) -> None:
    """mkdir -p `path`, chown root:GID_DOCUMENTS, chmod 775.

    Created at bootstrap time so per-CS subdirs inherit the correct ownership.
    """
    script = f"mkdir -p {path} && chown root:{GID_DOCUMENTS} {path} && chmod 775 {path}"
    try:
        client.containers.run(
            ALPINE_IMAGE,
            command=["sh", "-c", script],
            volumes={volume_name: {"bind": WORKSPACE_ROOT, "mode": "rw"}},
            remove=True,
        )
    except docker.errors.ContainerError as exc:
        stderr = _decode_container_stderr(exc)
        raise RuntimeError(f"make_change_sets_dir failed: {stderr}") from exc


def make_change_set_subdir(
    client: DockerClient, *, volume_name: str, slug: str, parent_dir: str
) -> str:
    """mkdir -p `parent_dir/{slug}`, chown root:GID_DOCUMENTS, chmod 775.

    Returns the in-container path.
    """
    cs_path = f"{parent_dir}/{slug}"
    script = f"mkdir -p {cs_path} && chown root:{GID_DOCUMENTS} {cs_path} && chmod 775 {cs_path}"
    try:
        client.containers.run(
            ALPINE_IMAGE,
            command=["sh", "-c", script],
            volumes={volume_name: {"bind": WORKSPACE_ROOT, "mode": "rw"}},
            remove=True,
        )
    except docker.errors.ContainerError as exc:
        stderr = _decode_container_stderr(exc)
        raise RuntimeError(f"make_change_set_subdir({slug}) failed: {stderr}") from exc
    return cs_path


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
        volumes={volume_name: {"bind": WORKSPACE_ROOT, "mode": "rw"}},
    )
    try:
        helper.put_archive(directory, tar_bytes)
    finally:
        helper.remove()

    if mode is not None:
        chmod_path(client, volume_name=volume_name, path=path, mode=mode)
