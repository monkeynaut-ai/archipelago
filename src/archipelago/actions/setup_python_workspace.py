"""Run `pdm install` once into the workspace volume after bootstrap.

Spawns a throwaway container from the run's base image, mounts the
workspace volume, and runs `pdm install` against the cloned codebase.
The resulting `.venv` is written into the shared volume, so every
agent container that mounts it later sees a ready-to-use Python
environment without re-bootstrapping.

Skips silently if the cloned codebase has no `pyproject.toml` — keeps
the pipeline usable for non-Python target repos as a no-op rather
than a failure.
"""

from __future__ import annotations

import docker
import docker.errors
from agent_foundry.primitives.models import FunctionAction
from pydantic import BaseModel

from archipelago.actions.workspace_bootstrap import WorkspaceHandle
from archipelago.actions.workspace_ops import _decode_container_stderr
from archipelago.constants import (
    GID_CODEBASE,
    GID_DOCUMENTS,
    GID_TESTS,
    WORKSPACE_CODEBASE_PATH,
    WORKSPACE_ROOT,
)


class SetupPythonWorkspaceInput(BaseModel):
    workspace_handle: WorkspaceHandle
    base_image_tag: str


class SetupPythonWorkspaceOutput(BaseModel):
    pass


# Supplementary GIDs the throwaway container needs to write into the
# bootstrap-prepared workspace tree. Codebase is mode 775 group-owned by
# GID_CODEBASE; tests/ by GID_TESTS; documents/ by GID_DOCUMENTS. We
# grant all three so pdm install (writes to .venv under codebase) and any
# post-install hooks (could touch tests or docs) succeed without surprise.
_WORKSPACE_GIDS: list[int] = [GID_DOCUMENTS, GID_CODEBASE, GID_TESTS]


def _has_pyproject(client: docker.DockerClient, *, image: str, volume_name: str) -> bool:
    """Return True iff /workspace/codebase/pyproject.toml exists in the volume."""
    try:
        client.containers.run(
            image,
            command=["sh", "-c", f"test -f {WORKSPACE_CODEBASE_PATH}/pyproject.toml"],
            entrypoint="",
            volumes={volume_name: {"bind": WORKSPACE_ROOT, "mode": "ro"}},
            remove=True,
            user="claude",
        )
        return True
    except docker.errors.ContainerError:
        return False


def setup_python_workspace_fn(
    state: SetupPythonWorkspaceInput,
) -> SetupPythonWorkspaceOutput:
    """Run `pdm install` in the workspace volume's cloned codebase if it
    looks like a Python/pdm project. No-op otherwise."""
    client = docker.from_env()
    volume = state.workspace_handle.volume_name
    image = state.base_image_tag

    if not _has_pyproject(client, image=image, volume_name=volume):
        return SetupPythonWorkspaceOutput()

    # Run pdm install. --skip post_install bypasses pdm scripts named
    # post_install — agent-foundry's pyproject.toml defines that as
    # `pre-commit install`, which would try to write `.git/hooks/pre-commit`,
    # but workspace_bootstrap leaves `.git/` root-owned (prepare_codebase_tree
    # explicitly excludes it from chmod), so the claude user can't write
    # there. Pre-commit hooks aren't needed for agent commits; agents run
    # tests directly, not via the human-dev hook chain.
    script = f"cd {WORKSPACE_CODEBASE_PATH} && pdm install --skip post_install"
    try:
        client.containers.run(
            image,
            command=["sh", "-c", script],
            entrypoint="",
            volumes={volume: {"bind": WORKSPACE_ROOT, "mode": "rw"}},
            remove=True,
            user="claude",
            # Grant the workspace GIDs so claude can write into the
            # bootstrap-prepared codebase tree (mode 775, group-owned).
            group_add=_WORKSPACE_GIDS,
        )
    except docker.errors.ContainerError as exc:
        stderr = _decode_container_stderr(exc)
        stdout_attr = getattr(exc, "stdout", None)
        if stdout_attr:
            stdout = (
                stdout_attr.decode("utf-8", errors="replace")
                if isinstance(stdout_attr, bytes)
                else stdout_attr
            )
            stderr = f"{stderr}\n--- stdout ---\n{stdout}"
        raise RuntimeError(f"pdm install failed in workspace volume {volume!r}: {stderr}") from exc

    return SetupPythonWorkspaceOutput()


setup_python_workspace = FunctionAction[SetupPythonWorkspaceInput, SetupPythonWorkspaceOutput](
    function=setup_python_workspace_fn,
)
