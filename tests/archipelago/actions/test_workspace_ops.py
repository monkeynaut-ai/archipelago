"""Tests for the private _workspace_ops helpers.

Docker client is patched — these are unit tests. Integration against a
real daemon lives in test_bootstrap_integration.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from archipelago.actions import _workspace_ops as ops


class TestPullImage:
    def test_given_client_when_pull_image_then_images_pull_called_with_tag(self):
        client = MagicMock()
        ops.pull_image(client, "alpine/git:v2.47.2")
        client.images.pull.assert_called_once_with("alpine/git:v2.47.2")

    def test_given_pull_error_when_pull_image_then_error_propagated(self):
        import docker.errors

        client = MagicMock()
        client.images.pull.side_effect = docker.errors.APIError("pull failed")
        with pytest.raises(docker.errors.APIError):
            ops.pull_image(client, "alpine/git:v2.47.2")


class TestCreateVolume:
    def test_given_client_when_create_volume_then_volumes_create_called_with_name(self):
        client = MagicMock()
        ops.create_volume(client, "archipelago-ws-demo-1")
        client.volumes.create.assert_called_once_with(name="archipelago-ws-demo-1")

    def test_given_client_when_create_volume_then_returns_client_result(self):
        client = MagicMock()
        expected = MagicMock()
        client.volumes.create.return_value = expected
        result = ops.create_volume(client, "archipelago-ws-demo-1")
        assert result is expected

    def test_given_conflict_when_create_volume_then_api_error_propagated(self):
        import docker.errors

        client = MagicMock()
        client.volumes.create.side_effect = docker.errors.APIError("conflict")
        with pytest.raises(docker.errors.APIError):
            ops.create_volume(client, "dup")


class TestCloneAndResolveRef:
    def test_given_client_when_clone_then_containers_run_mounts_volume_at_workspace(self):
        client = MagicMock()
        client.containers.run.return_value = b"a" * 40 + b"\n"

        sha = ops.clone_and_resolve_ref(
            client,
            volume_name="ws",
            repo_url="https://example.com/repo.git",
            ref="main",
        )

        call = client.containers.run.call_args
        assert call.args[0] == ops.GIT_IMAGE
        assert call.kwargs["volumes"]["ws"]["bind"] == "/workspace"
        assert call.kwargs.get("remove") is True
        assert sha == "a" * 40

    def test_given_repo_and_ref_when_clone_then_command_contains_both(self):
        client = MagicMock()
        client.containers.run.return_value = b"b" * 40 + b"\n"

        ops.clone_and_resolve_ref(
            client,
            volume_name="ws",
            repo_url="https://example.com/repo.git",
            ref="abc123",
        )

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        assert "https://example.com/repo.git" in rendered
        assert "abc123" in rendered
        assert "/workspace/codebase" in rendered
        assert "rev-parse HEAD" in rendered

    def test_given_trailing_whitespace_when_clone_then_sha_stripped(self):
        client = MagicMock()
        client.containers.run.return_value = b"  " + b"c" * 40 + b"\r\n"
        sha = ops.clone_and_resolve_ref(client, volume_name="ws", repo_url="u", ref="r")
        assert sha == "c" * 40

    def test_given_container_error_when_clone_then_informative_error_raised(self):
        import docker.errors

        client = MagicMock()
        client.containers.run.side_effect = docker.errors.ContainerError(
            container=MagicMock(),
            exit_status=128,
            command="git clone ...",
            image="alpine/git",
            stderr=b"fatal: repository not found",
        )
        with pytest.raises(RuntimeError) as exc:
            ops.clone_and_resolve_ref(
                client, volume_name="ws", repo_url="https://example.com/x.git", ref="main"
            )
        assert "https://example.com/x.git" in str(exc.value)
        assert "main" in str(exc.value)
