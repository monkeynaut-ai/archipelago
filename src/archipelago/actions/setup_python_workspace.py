"""Run `pdm install` once into the workspace volume after bootstrap.

Spawns a throwaway container from the run's base image, mounts the
workspace volume, and runs `pdm install` against the cloned codebase.
Skips silently if the codebase has no `pyproject.toml`, keeping the
pipeline usable for non-Python repos. The resulting `.venv` is written
into the shared volume so every agent container that mounts it later
sees a ready-to-use Python environment without re-bootstrapping.
"""

from __future__ import annotations

import docker
import docker.errors
from agent_foundry.constructs import FunctionAction
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


def setup_python_workspace_fn(
    state: SetupPythonWorkspaceInput,
) -> SetupPythonWorkspaceOutput:
    """Run `pdm install` in the workspace volume's cloned codebase if it
    looks like a Python/pdm project. No-op otherwise."""
    client = docker.from_env()
    volume = state.workspace_handle.volume_name
    image = state.base_image_tag

    # Skip silently for non-Python repos. The pyproject.toml check and the
    # install are combined in one container run: if pyproject.toml is absent
    # the script exits 0 without installing anything.
    #
    # -G :all installs optional dependency groups (e.g. agent-foundry's
    # `mlflow` extra) so agents running the full test suite don't hit
    # ImportError on optional extras.
    #
    # post_install runs `pre-commit install`, which writes .git/hooks/pre-commit
    # so that agent commits are gated by the project's full pre-commit suite.
    # .git/ is owned root:GID_CODEBASE with g+w (set by prepare_codebase_tree),
    # and this container runs with GID_CODEBASE in its supplementary groups,
    # so the write succeeds.
    script = (
        f"test -f {WORKSPACE_CODEBASE_PATH}/pyproject.toml || exit 0"
        f" && git config --global --add safe.directory {WORKSPACE_CODEBASE_PATH}"
        f" && cd {WORKSPACE_CODEBASE_PATH} && pdm install -G :all"
    )
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
            healthcheck={"test": ["NONE"]},
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
