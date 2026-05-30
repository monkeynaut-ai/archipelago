"""End-to-end bootstrap against a real Docker daemon.

These tests require Docker (skipped if unreachable) and a GitHub token
with read access to the pinned private repo. Set GH_TOKEN or
GITHUB_TOKEN in the environment before running:

    GH_TOKEN=$(gh auth token) pdm test-integration \\
        tests/archipelago/actions/test_bootstrap_integration.py
"""

from __future__ import annotations

import contextlib

import docker
import pytest

from archipelago.actions import BootstrapInput, BootstrapOutput
from archipelago.actions.workspace_bootstrap import bootstrap_fn
from archipelago.constants import (
    FEATURE_DEFINITION_FILENAME,
    GID_CODEBASE,
    GID_TESTS,
    WORKSPACE_CODEBASE_PATH,
    WORKSPACE_DOCUMENTS_PATH,
    WORKSPACE_ROOT,
)
from archipelago.models import CodebaseSource

PINNED_REPO = "https://github.com/730alchemy/agent-foundry.git"
PINNED_SHA = "c8da88e081575bf2b25c85cf1f176d0297700a31"

pytestmark = pytest.mark.integration


def _docker_available() -> bool:
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


@pytest.fixture
def docker_client():
    if not _docker_available():
        pytest.skip("Docker daemon not reachable")
    return docker.from_env()


@pytest.fixture
def cleanup_volumes(docker_client, archipelago_volume_registry):
    created: list[str] = []
    try:
        yield created
    finally:
        for name in created:
            archipelago_volume_registry.add(name)
            with contextlib.suppress(Exception):
                docker_client.volumes.get(name).remove(force=True)


class TestBootstrapIntegration:
    def test_given_real_repo_when_bootstrap_then_volume_populated_correctly(
        self, docker_client, cleanup_volumes, minimal_feature_definition
    ):
        import time

        volume_name = f"archipelago-ws-test-{time.time_ns()}"
        state = BootstrapInput(
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(repo_url=PINNED_REPO, ref=PINNED_SHA),
            volume_name=volume_name,
        )

        result = bootstrap_fn(state)
        cleanup_volumes.append(result.workspace_handle.volume_name)
        assert isinstance(result, BootstrapOutput)

        output = docker_client.containers.run(
            "alpine:3.20",
            command=[
                "sh",
                "-c",
                "ls -la /workspace/documents && "
                f"stat -c '%a %n' {WORKSPACE_DOCUMENTS_PATH}/{FEATURE_DEFINITION_FILENAME} && "
                "stat -c '%a %n' /workspace/documents && "
                "test -d /workspace/codebase/.git && echo '.git present' && "
                "find /workspace/codebase -maxdepth 2 -name pyproject.toml "
                "-exec stat -c '%a %g %n' {} + && "
                # Verify split ownership: codebase root → GID_CODEBASE,
                # tests/ → GID_TESTS, both 775.
                f"stat -c '%a %g {WORKSPACE_CODEBASE_PATH}' {WORKSPACE_CODEBASE_PATH} && "
                f"stat -c '%a %g {WORKSPACE_CODEBASE_PATH}/tests' "
                f"{WORKSPACE_CODEBASE_PATH}/tests && "
                # Verify .git/ is group-writable to GID_CODEBASE so the
                # implementer can run git add / git commit. The setgid
                # bit on the directory shows up as the leading '2' in
                # `stat -c '%a'` (e.g., 2775).
                f"stat -c '%a %g {WORKSPACE_CODEBASE_PATH}/.git' "
                f"{WORKSPACE_CODEBASE_PATH}/.git && "
                # Verify core.fileMode is disabled on the cloned repo so
                # prepare_codebase_tree's chmod doesn't pollute git diff.
                "echo '--- git config ---' && "
                f"cat {WORKSPACE_CODEBASE_PATH}/.git/config",
            ],
            volumes={result.workspace_handle.volume_name: {"bind": WORKSPACE_ROOT, "mode": "ro"}},
            remove=True,
        ).decode("utf-8", errors="replace")

        assert FEATURE_DEFINITION_FILENAME in output
        assert ".git present" in output
        assert f"444 {WORKSPACE_DOCUMENTS_PATH}/{FEATURE_DEFINITION_FILENAME}" in output
        assert f"775 {WORKSPACE_DOCUMENTS_PATH}" in output
        assert f"775 {GID_CODEBASE} {WORKSPACE_CODEBASE_PATH}/pyproject.toml" in output
        assert f"775 {GID_CODEBASE} {WORKSPACE_CODEBASE_PATH}" in output
        assert f"775 {GID_TESTS} {WORKSPACE_CODEBASE_PATH}/tests" in output
        # .git/ is group-writable to GID_CODEBASE with setgid bit set
        # (mode 2775 in stat output: leading 2 = setgid).
        assert f"2775 {GID_CODEBASE} {WORKSPACE_CODEBASE_PATH}/.git" in output
        assert "filemode = false" in output.lower()

    def test_given_real_repo_when_bootstrap_then_git_log_still_works(
        self, docker_client, cleanup_volumes, minimal_feature_definition
    ):
        """Regression guard: .git/ must remain writable so git tooling works."""
        import time

        volume_name = f"archipelago-ws-test-git-{time.time_ns()}"
        state = BootstrapInput(
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(repo_url=PINNED_REPO, ref=PINNED_SHA),
            volume_name=volume_name,
        )
        result = bootstrap_fn(state)
        cleanup_volumes.append(result.workspace_handle.volume_name)

        # Run a git command that writes to .git (commit-graph, reachability cache).
        # entrypoint="" is required: alpine/git:v2.47.2 has `git` as its ENTRYPOINT,
        # so we must override it to use a shell script.
        output = docker_client.containers.run(
            "alpine/git:v2.47.2",
            command=[
                "sh",
                "-c",
                "cd /workspace/codebase && git log -1 --oneline",
            ],
            entrypoint="",
            volumes={result.workspace_handle.volume_name: {"bind": WORKSPACE_ROOT, "mode": "rw"}},
            tmpfs={"/git": ""},
            remove=True,
        ).decode("utf-8", errors="replace")

        assert output.strip(), "git log produced no output"

    def test_given_real_repo_when_bootstrap_then_resolved_sha_is_40_hex(
        self, docker_client, cleanup_volumes, minimal_feature_definition
    ):
        import time

        volume_name = f"archipelago-ws-test-sha-{time.time_ns()}"
        state = BootstrapInput(
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(repo_url=PINNED_REPO, ref=PINNED_SHA),
            volume_name=volume_name,
        )
        result = bootstrap_fn(state)
        cleanup_volumes.append(result.workspace_handle.volume_name)

        sha = result.workspace_handle.codebase_resolved_sha
        assert len(sha) == 40
        assert all(c in "0123456789abcdef" for c in sha)
