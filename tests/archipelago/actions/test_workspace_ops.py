"""Tests for the private _workspace_ops helpers.

Docker client is patched — these are unit tests. Integration against a
real daemon lives in test_bootstrap_integration.py.
"""

from __future__ import annotations

import io
import tarfile
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

    def test_given_client_when_clone_then_entrypoint_overridden_to_empty(self):
        """Regression guard: alpine/git has `git` as entrypoint, so the shell
        command must override it or git interprets 'sh' as a subcommand."""
        client = MagicMock()
        client.containers.run.return_value = b"a" * 40 + b"\n"

        ops.clone_and_resolve_ref(client, volume_name="ws", repo_url="u", ref="r")

        call = client.containers.run.call_args
        assert call.kwargs.get("entrypoint") == ""

    def test_given_github_token_and_github_url_when_clone_then_url_rewritten_with_auth(self):
        client = MagicMock()
        client.containers.run.return_value = b"a" * 40 + b"\n"

        ops.clone_and_resolve_ref(
            client,
            volume_name="ws",
            repo_url="https://github.com/owner/repo.git",
            ref="main",
            github_token="secret-token",
        )

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        assert "x-access-token:secret-token@github.com/owner/repo.git" in rendered

    def test_given_github_token_and_non_github_url_when_clone_then_url_unchanged(self):
        client = MagicMock()
        client.containers.run.return_value = b"a" * 40 + b"\n"

        ops.clone_and_resolve_ref(
            client,
            volume_name="ws",
            repo_url="https://gitlab.com/owner/repo.git",
            ref="main",
            github_token="secret-token",
        )

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        assert "secret-token" not in rendered
        assert "https://gitlab.com/owner/repo.git" in rendered

    def test_given_no_token_when_clone_then_url_unchanged(self):
        client = MagicMock()
        client.containers.run.return_value = b"a" * 40 + b"\n"

        ops.clone_and_resolve_ref(
            client,
            volume_name="ws",
            repo_url="https://github.com/owner/repo.git",
            ref="main",
        )

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        assert "x-access-token" not in rendered

    def test_given_container_error_when_clone_then_original_url_in_message_not_token(self):
        import docker.errors

        client = MagicMock()
        client.containers.run.side_effect = docker.errors.ContainerError(
            container=MagicMock(),
            exit_status=128,
            command="git clone ...",
            image="alpine/git",
            stderr=b"fatal: auth failed",
        )
        with pytest.raises(RuntimeError) as exc:
            ops.clone_and_resolve_ref(
                client,
                volume_name="ws",
                repo_url="https://github.com/owner/repo.git",
                ref="main",
                github_token="secret-token",
            )
        # The original URL appears; the token does not leak into error logs.
        assert "https://github.com/owner/repo.git" in str(exc.value)
        assert "secret-token" not in str(exc.value)


class TestChmodTreeExcludingGit:
    def test_given_path_when_chmod_tree_excluding_git_then_find_excludes_dot_git(self):
        client = MagicMock()
        client.containers.run.return_value = b""

        ops.chmod_tree_excluding_git(
            client, volume_name="ws", path="/workspace/codebase", mode="555"
        )

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        # Implementation uses `find ... -path */.git -prune` so .git/ stays writable.
        assert "/workspace/codebase" in rendered
        assert ".git" in rendered
        assert "555" in rendered
        assert call.kwargs["volumes"]["ws"]["bind"] == "/workspace"
        assert call.kwargs.get("remove") is True

    def test_given_container_error_when_chmod_tree_then_runtime_error_raised(self):
        import docker.errors

        client = MagicMock()
        client.containers.run.side_effect = docker.errors.ContainerError(
            container=MagicMock(),
            exit_status=1,
            command="find ...",
            image="alpine",
            stderr=b"find: cannot access /workspace/nowhere",
        )
        with pytest.raises(RuntimeError) as exc:
            ops.chmod_tree_excluding_git(
                client, volume_name="ws", path="/workspace/nowhere", mode="555"
            )
        assert "/workspace/nowhere" in str(exc.value)

    def test_given_trailing_slash_path_when_chmod_tree_then_no_double_slash_in_command(self):
        client = MagicMock()
        client.containers.run.return_value = b""

        ops.chmod_tree_excluding_git(
            client, volume_name="ws", path="/workspace/codebase/", mode="555"
        )

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        # Defensive rstrip means no `//` sequence appears in the script.
        assert "//" not in rendered, rendered


class TestChmodPath:
    def test_given_mode_when_chmod_path_then_chmod_command_runs(self):
        client = MagicMock()
        client.containers.run.return_value = b""

        ops.chmod_path(
            client,
            volume_name="ws",
            path="/workspace/documents/feature_definition.md",
            mode="444",
        )

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        assert "chmod 444 /workspace/documents/feature_definition.md" in rendered


class TestPrepareDocumentsDir:
    def test_given_volume_when_prepare_documents_then_mkdir_chown_chmod_called(self):
        from agent_foundry.agents import AGENT_USER_GID, AGENT_USER_UID

        client = MagicMock()
        client.containers.run.return_value = b""

        ops.prepare_documents_dir(client, volume_name="ws")

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        assert "mkdir -p /workspace/documents" in rendered
        assert f"chown {AGENT_USER_UID}:{AGENT_USER_GID} /workspace/documents" in rendered
        assert "chmod 775 /workspace/documents" in rendered

    def test_given_volume_when_prepare_documents_then_chown_runs_before_chmod(self):
        """Chmod after chown so the bits land on the new ownership; if
        the order swaps, root-owned dirs end up 775 before chown — fine
        but unintentional. Pin the order."""
        client = MagicMock()
        client.containers.run.return_value = b""

        ops.prepare_documents_dir(client, volume_name="ws")

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        chown_idx = rendered.index("chown")
        chmod_idx = rendered.index("chmod 775")
        assert chown_idx < chmod_idx


class TestWriteFile:
    def test_given_content_when_write_file_then_put_archive_called(self):
        client = MagicMock()
        helper = MagicMock()
        client.containers.create.return_value = helper

        ops.write_file(
            client,
            volume_name="ws",
            path="/workspace/documents/feature_definition.md",
            content="# hello\n",
        )

        assert client.containers.create.called
        assert helper.put_archive.called
        call = helper.put_archive.call_args
        assert call.args[0] == "/workspace/documents"
        tar_bytes = call.args[1]
        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r") as tar:
            members = tar.getmembers()
            assert len(members) == 1
            assert members[0].name == "feature_definition.md"
            extracted = tar.extractfile(members[0])
            assert extracted is not None
            assert extracted.read() == b"# hello\n"

    def test_given_mode_when_write_file_then_chmod_path_invoked_after_write(self):
        client = MagicMock()
        helper = MagicMock()
        client.containers.create.return_value = helper

        ops.write_file(
            client,
            volume_name="ws",
            path="/workspace/documents/feature_definition.md",
            content="content",
            mode="444",
        )
        # chmod_path dispatches through containers.run with a chmod command.
        chmod_calls = [
            c
            for c in client.containers.run.call_args_list
            if "chmod"
            in (
                " ".join(c.kwargs.get("command", []))
                if isinstance(c.kwargs.get("command"), list)
                else str(c.kwargs.get("command", ""))
            )
        ]
        assert chmod_calls, "chmod container call was not made"

    def test_given_helper_container_when_write_file_then_helper_removed(self):
        client = MagicMock()
        helper = MagicMock()
        client.containers.create.return_value = helper

        ops.write_file(
            client,
            volume_name="ws",
            path="/workspace/documents/feature_definition.md",
            content="content",
        )
        assert helper.remove.called
