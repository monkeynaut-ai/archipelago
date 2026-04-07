"""Integration tests: WorkerInput → env builder → container lockdown enforcement.

Verifies that when a WorkerInput is configured with acp_hidden_dirs or
acp_readonly_dirs, the resulting environment variables cause the in-container
lockdown script to actually prevent filesystem access at the OS level.

Originally in tests/archipelago/integration/test_config_to_lockdown.py as
part of a full plan → compiler → env → container pipeline test. The
plan/compiler half depended on GraphWiringPlan and compile_plan from
agent_foundry, both removed in agent-foundry CS3. CS5 re-creates the
security-critical half (env → container lockdown) here, constructing
WorkerInput directly. The pipeline-to-env half is deferred to CS10's
runner rewrite — tracked in the CS5 plan's deferred requirements.

Requires: Docker daemon + acp-cc-worker:latest image (pdm docker-base).
"""

import pytest
from conftest import run_in_container

from archipelago.docker_worker.env import build_container_env
from archipelago.docker_worker.models import WorkerCommitSpec, WorkerConstraints, WorkerInput


def _worker_input(
    *,
    hidden_dirs: list[str] | None = None,
    readonly_dirs: list[str] | None = None,
) -> WorkerInput:
    return WorkerInput(
        commit_spec=WorkerCommitSpec(title="test"),
        repo_ref="main",
        constraints=WorkerConstraints(),
        acp_hidden_dirs=hidden_dirs or [],
        acp_readonly_dirs=readonly_dirs or [],
    )


# ── Unit tests: WorkerInput → env dict (no Docker needed) ──


class TestWorkerInputToEnv:
    """build_container_env emits the right ACP_* env vars for lockdown config."""

    def test_given_hidden_dirs_when_env_built_then_acp_hidden_dirs_set(self):
        env = build_container_env(
            _worker_input(hidden_dirs=["/workspace/secrets"]),
            ws_url="ws://host:1234/test",
        )
        assert env["ACP_HIDDEN_DIRS"] == "/workspace/secrets"

    def test_given_readonly_dirs_when_env_built_then_acp_readonly_dirs_set(self):
        env = build_container_env(
            _worker_input(readonly_dirs=["/workspace/tests"]),
            ws_url="ws://host:1234/test",
        )
        assert env["ACP_READONLY_DIRS"] == "/workspace/tests"

    def test_given_multiple_hidden_dirs_when_env_built_then_comma_separated(self):
        env = build_container_env(
            _worker_input(hidden_dirs=["/workspace/secrets", "/workspace/keys"]),
            ws_url="ws://host:1234/test",
        )
        # Value should include both paths (exact separator is build_lockdown_env's concern)
        assert "/workspace/secrets" in env["ACP_HIDDEN_DIRS"]
        assert "/workspace/keys" in env["ACP_HIDDEN_DIRS"]

    def test_given_no_lockdown_config_when_env_built_then_keys_absent_or_empty(self):
        env = build_container_env(
            _worker_input(),
            ws_url="ws://host:1234/test",
        )
        # build_lockdown_env should omit or leave empty the ACP_*_DIRS keys when
        # nothing is configured. Either absence or empty string is acceptable —
        # the lockdown script treats both the same.
        assert env.get("ACP_HIDDEN_DIRS", "") == ""
        assert env.get("ACP_READONLY_DIRS", "") == ""


# ── Integration tests: env vars → real container lockdown enforcement ──


@pytest.mark.integration
class TestDockerWorkerLockdown:
    """Run a real container with lockdown env vars and verify OS-level enforcement."""

    def test_given_hidden_dirs_env_when_container_runs_lockdown_then_dir_inaccessible(
        self, docker_client, worker_image, container_cleanup
    ):
        env = build_container_env(
            _worker_input(hidden_dirs=["/workspace/secrets"]),
            ws_url="ws://host:1234/test",
        )

        # Create a secret file, source the lockdown script, then try to read
        # the file as the claude user. The lockdown should block the read.
        script = """
            mkdir -p /workspace/secrets
            echo "secret-data" > /workspace/secrets/key.txt
            . /home/claude/lockdown.sh
            gosu claude sh -c 'cat /workspace/secrets/key.txt 2>&1'
        """
        exit_code, output = run_in_container(
            docker_client, worker_image, script, env=env, cleanup_list=container_cleanup
        )
        assert exit_code != 0, f"Expected non-zero exit; got 0 with output: {output}"
        assert "secret-data" not in output, f"Secret leaked through lockdown: {output}"

    def test_given_readonly_dirs_env_when_container_runs_lockdown_then_reads_ok_writes_fail(
        self, docker_client, worker_image, container_cleanup
    ):
        env = build_container_env(
            _worker_input(readonly_dirs=["/workspace/config"]),
            ws_url="ws://host:1234/test",
        )

        # Create a config file, source lockdown, then read it (should succeed)
        # and try to write to the directory (should fail).
        script = """
            mkdir -p /workspace/config
            echo "setting: true" > /workspace/config/app.yaml
            chown -R claude:claude /workspace/config
            . /home/claude/lockdown.sh
            gosu claude sh -c 'cat /workspace/config/app.yaml && echo READ_OK'
            gosu claude sh -c 'touch /workspace/config/new.txt 2>&1'
        """
        exit_code, output = run_in_container(
            docker_client, worker_image, script, env=env, cleanup_list=container_cleanup
        )
        assert "READ_OK" in output, f"Expected read to succeed; output: {output}"
        assert exit_code != 0, (
            f"Expected non-zero exit from write attempt; got 0 with output: {output}"
        )
