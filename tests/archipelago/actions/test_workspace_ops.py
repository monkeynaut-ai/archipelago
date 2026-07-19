"""Tests for the workspace_ops helpers.

Docker client is patched — these are unit tests. Integration against a
real daemon lives in test_bootstrap_integration.py.
"""

from __future__ import annotations

import io
import tarfile
from unittest.mock import MagicMock

import pytest

from archipelago.actions import workspace_ops as ops
from archipelago.constants import (
    CHANGE_SETS_DIR_NAME,
    FEATURE_DEFINITION_FILENAME,
    WORKSPACE_CODEBASE_PATH,
    WORKSPACE_DOCUMENTS_PATH,
    WORKSPACE_ROOT,
)


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
            codebase_path=WORKSPACE_CODEBASE_PATH,
        )

        call = client.containers.run.call_args
        assert call.args[0] == ops.GIT_IMAGE
        assert call.kwargs["volumes"]["ws"]["bind"] == WORKSPACE_ROOT
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
            codebase_path=WORKSPACE_CODEBASE_PATH,
        )

        call = client.containers.run.call_args
        env = call.kwargs["environment"]
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        assert env["AF_REPO_URL"] == "https://example.com/repo.git"
        assert env["AF_GIT_REF"] == "abc123"
        assert env["AF_CODEBASE_PATH"] == WORKSPACE_CODEBASE_PATH
        assert "rev-parse HEAD" in rendered

    def test_given_trailing_whitespace_when_clone_then_sha_stripped(self):
        client = MagicMock()
        client.containers.run.return_value = b"  " + b"c" * 40 + b"\r\n"
        sha = ops.clone_and_resolve_ref(
            client, volume_name="ws", repo_url="u", ref="r", codebase_path=WORKSPACE_CODEBASE_PATH
        )
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
                client,
                volume_name="ws",
                repo_url="https://example.com/x.git",
                ref="main",
                codebase_path=WORKSPACE_CODEBASE_PATH,
            )
        assert "https://example.com/x.git" in str(exc.value)
        assert "main" in str(exc.value)

    def test_given_client_when_clone_then_entrypoint_overridden_to_empty(self):
        """Regression guard: alpine/git has `git` as entrypoint, so the shell
        command must override it or git interprets 'sh' as a subcommand."""
        client = MagicMock()
        client.containers.run.return_value = b"a" * 40 + b"\n"

        ops.clone_and_resolve_ref(
            client, volume_name="ws", repo_url="u", ref="r", codebase_path=WORKSPACE_CODEBASE_PATH
        )

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
            codebase_path=WORKSPACE_CODEBASE_PATH,
            github_token="secret-token",
        )

        call = client.containers.run.call_args
        assert (
            call.kwargs["environment"]["AF_REPO_URL"]
            == "https://x-access-token:secret-token@github.com/owner/repo.git"
        )

    def test_given_github_token_and_non_github_url_when_clone_then_url_unchanged(self):
        client = MagicMock()
        client.containers.run.return_value = b"a" * 40 + b"\n"

        ops.clone_and_resolve_ref(
            client,
            volume_name="ws",
            repo_url="https://gitlab.com/owner/repo.git",
            ref="main",
            codebase_path=WORKSPACE_CODEBASE_PATH,
            github_token="secret-token",
        )

        call = client.containers.run.call_args
        env = call.kwargs["environment"]
        assert "secret-token" not in env["AF_REPO_URL"]
        assert env["AF_REPO_URL"] == "https://gitlab.com/owner/repo.git"

    def test_given_no_token_when_clone_then_url_unchanged(self):
        client = MagicMock()
        client.containers.run.return_value = b"a" * 40 + b"\n"

        ops.clone_and_resolve_ref(
            client,
            volume_name="ws",
            repo_url="https://github.com/owner/repo.git",
            ref="main",
            codebase_path=WORKSPACE_CODEBASE_PATH,
        )

        call = client.containers.run.call_args
        assert "x-access-token" not in call.kwargs["environment"]["AF_REPO_URL"]

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
                codebase_path=WORKSPACE_CODEBASE_PATH,
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
            client, volume_name="ws", path=WORKSPACE_CODEBASE_PATH, mode="555"
        )

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        # Implementation uses `find ... -path */.git -prune` so .git/ stays writable.
        assert WORKSPACE_CODEBASE_PATH in rendered
        assert ".git" in rendered
        assert "555" in rendered
        assert call.kwargs["volumes"]["ws"]["bind"] == WORKSPACE_ROOT
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
        assert "/workspace/nowhere" in str(exc.value)  # arbitrary path, not a constant

    def test_given_trailing_slash_path_when_chmod_tree_then_no_double_slash_in_command(self):
        client = MagicMock()
        client.containers.run.return_value = b""

        ops.chmod_tree_excluding_git(
            client, volume_name="ws", path=f"{WORKSPACE_CODEBASE_PATH}/", mode="555"
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
            path=f"{WORKSPACE_DOCUMENTS_PATH}/{FEATURE_DEFINITION_FILENAME}",
            mode="444",
        )

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        assert f"chmod 444 {WORKSPACE_DOCUMENTS_PATH}/{FEATURE_DEFINITION_FILENAME}" in rendered


class TestPrepareDocumentsDir:
    def test_given_volume_when_prepare_documents_then_mkdir_chown_chmod_called(self):
        from archipelago.constants import GID_DOCUMENTS

        client = MagicMock()
        client.containers.run.return_value = b""

        ops.prepare_documents_dir(client, volume_name="ws", path=WORKSPACE_DOCUMENTS_PATH)

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        assert f"mkdir -p {WORKSPACE_DOCUMENTS_PATH}" in rendered
        assert f"chown root:{GID_DOCUMENTS} {WORKSPACE_DOCUMENTS_PATH}" in rendered
        assert f"chmod 775 {WORKSPACE_DOCUMENTS_PATH}" in rendered

    def test_given_volume_when_prepare_documents_then_chown_runs_before_chmod(self):
        """Pin chown-before-chmod order so bits land on the correct ownership."""
        client = MagicMock()
        client.containers.run.return_value = b""

        ops.prepare_documents_dir(client, volume_name="ws", path=WORKSPACE_DOCUMENTS_PATH)

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        chown_idx = rendered.index("chown")
        chmod_idx = rendered.index("chmod 775")
        assert chown_idx < chmod_idx


class TestMakeChangeSetsDir:
    def test_given_volume_when_make_change_sets_dir_then_mkdir_chown_chmod_called(self):
        from archipelago.constants import GID_DOCUMENTS

        client = MagicMock()
        client.containers.run.return_value = b""

        ops.make_change_sets_dir(
            client, volume_name="ws", path=f"{WORKSPACE_DOCUMENTS_PATH}/{CHANGE_SETS_DIR_NAME}"
        )

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        assert f"mkdir -p {WORKSPACE_DOCUMENTS_PATH}/change-sets" in rendered
        assert f"chown root:{GID_DOCUMENTS} {WORKSPACE_DOCUMENTS_PATH}/change-sets" in rendered
        assert f"chmod 775 {WORKSPACE_DOCUMENTS_PATH}/change-sets" in rendered


class TestMakeChangeSetSubdir:
    def test_given_slug_when_make_change_set_subdir_then_mkdir_chown_chmod_called(self):
        from archipelago.constants import GID_DOCUMENTS

        client = MagicMock()
        client.containers.run.return_value = b""

        path = ops.make_change_set_subdir(
            client,
            volume_name="ws",
            slug="add-login",
            parent_dir=f"{WORKSPACE_DOCUMENTS_PATH}/{CHANGE_SETS_DIR_NAME}",
        )

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        assert f"mkdir -p {WORKSPACE_DOCUMENTS_PATH}/change-sets/add-login" in rendered
        assert (
            f"chown root:{GID_DOCUMENTS} {WORKSPACE_DOCUMENTS_PATH}/change-sets/add-login"
            in rendered
        )
        assert f"chmod 775 {WORKSPACE_DOCUMENTS_PATH}/change-sets/add-login" in rendered
        assert path == f"{WORKSPACE_DOCUMENTS_PATH}/change-sets/add-login"


class TestListRemoteBranches:
    def test_given_standard_output_when_list_remote_then_returns_branch_names(self):
        client = MagicMock()
        ls_output = b"abc123\trefs/heads/main\ndef456\trefs/heads/feat/login\n"
        client.containers.run.return_value = ls_output

        result = ops.list_remote_branches(
            client, volume_name="ws", codebase_path=WORKSPACE_CODEBASE_PATH
        )

        assert result == {"main", "feat/login"}

    def test_given_empty_output_when_list_remote_then_returns_empty_set(self):
        client = MagicMock()
        client.containers.run.return_value = b""

        result = ops.list_remote_branches(
            client, volume_name="ws", codebase_path=WORKSPACE_CODEBASE_PATH
        )

        assert result == set()

    def test_given_container_error_when_list_remote_then_runtime_error_raised(self):
        import docker.errors

        client = MagicMock()
        client.containers.run.side_effect = docker.errors.ContainerError(
            container=MagicMock(),
            exit_status=1,
            command="git ls-remote ...",
            image="alpine/git",
            stderr=b"fatal: remote error",
        )
        with pytest.raises(RuntimeError):
            ops.list_remote_branches(
                client, volume_name="ws", codebase_path=WORKSPACE_CODEBASE_PATH
            )

    def test_given_volume_when_list_remote_then_volume_mounted_at_workspace_root(self):
        client = MagicMock()
        client.containers.run.return_value = b""

        ops.list_remote_branches(client, volume_name="ws", codebase_path=WORKSPACE_CODEBASE_PATH)

        call = client.containers.run.call_args
        assert call.kwargs["volumes"]["ws"]["bind"] == WORKSPACE_ROOT

    def test_given_client_when_list_remote_then_entrypoint_overridden_to_empty(self):
        client = MagicMock()
        client.containers.run.return_value = b""

        ops.list_remote_branches(client, volume_name="ws", codebase_path=WORKSPACE_CODEBASE_PATH)

        call = client.containers.run.call_args
        assert call.kwargs.get("entrypoint") == ""

    def test_given_codebase_path_when_list_remote_then_command_targets_origin(self):
        client = MagicMock()
        client.containers.run.return_value = b""

        ops.list_remote_branches(client, volume_name="ws", codebase_path=WORKSPACE_CODEBASE_PATH)

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        assert WORKSPACE_CODEBASE_PATH in rendered
        assert "ls-remote" in rendered
        assert "origin" in rendered


class TestShellMetacharacterHandling:
    def test_given_ref_with_shell_metacharacters_when_clone_then_not_in_script(self):
        client = MagicMock()
        client.containers.run.return_value = b"a" * 40 + b"\n"
        malicious = "main; touch /tmp/pwned"

        ops.clone_and_resolve_ref(
            client,
            volume_name="ws",
            repo_url="https://example.com/repo.git",
            ref=malicious,
            codebase_path=WORKSPACE_CODEBASE_PATH,
        )

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        assert malicious not in rendered
        assert call.kwargs["environment"]["AF_GIT_REF"] == malicious

    def test_given_branch_with_shell_metacharacters_when_branch_then_not_in_script(self):
        client = MagicMock()
        client.containers.run.return_value = b""
        malicious = "feature; touch /tmp/pwned"

        ops.create_and_checkout_branch(
            client,
            volume_name="ws",
            codebase_path=WORKSPACE_CODEBASE_PATH,
            branch_name=malicious,
        )

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        assert malicious not in rendered
        assert call.kwargs["environment"]["AF_BRANCH_NAME"] == malicious


class TestCreateAndCheckoutBranch:
    def test_given_branch_name_when_create_branch_then_checkout_b_called(self):
        client = MagicMock()
        client.containers.run.return_value = b""

        ops.create_and_checkout_branch(
            client,
            volume_name="ws",
            codebase_path=WORKSPACE_CODEBASE_PATH,
            branch_name="my-feature",
        )

        call = client.containers.run.call_args
        cmd = call.kwargs["command"]
        rendered = " ".join(cmd) if isinstance(cmd, list) else cmd
        env = call.kwargs["environment"]
        assert "checkout" in rendered
        assert "-b" in rendered
        assert env["AF_BRANCH_NAME"] == "my-feature"
        assert env["AF_CODEBASE_PATH"] == WORKSPACE_CODEBASE_PATH

    def test_given_volume_when_create_branch_then_volume_mounted_rw(self):
        client = MagicMock()
        client.containers.run.return_value = b""

        ops.create_and_checkout_branch(
            client,
            volume_name="ws",
            codebase_path=WORKSPACE_CODEBASE_PATH,
            branch_name="feat",
        )

        call = client.containers.run.call_args
        assert call.kwargs["volumes"]["ws"]["bind"] == WORKSPACE_ROOT
        assert call.kwargs["volumes"]["ws"]["mode"] == "rw"

    def test_given_container_error_when_create_branch_then_error_contains_branch_name(self):
        import docker.errors

        client = MagicMock()
        client.containers.run.side_effect = docker.errors.ContainerError(
            container=MagicMock(),
            exit_status=128,
            command="git checkout -b ...",
            image="alpine/git",
            stderr=b"fatal: branch already exists",
        )
        with pytest.raises(RuntimeError) as exc:
            ops.create_and_checkout_branch(
                client,
                volume_name="ws",
                codebase_path=WORKSPACE_CODEBASE_PATH,
                branch_name="my-branch",
            )
        assert "my-branch" in str(exc.value)

    def test_given_client_when_create_branch_then_entrypoint_overridden_to_empty(self):
        client = MagicMock()
        client.containers.run.return_value = b""

        ops.create_and_checkout_branch(
            client,
            volume_name="ws",
            codebase_path=WORKSPACE_CODEBASE_PATH,
            branch_name="feat",
        )

        call = client.containers.run.call_args
        assert call.kwargs.get("entrypoint") == ""


class TestWriteFile:
    def test_given_content_when_write_file_then_put_archive_called(self):
        client = MagicMock()
        helper = MagicMock()
        client.containers.create.return_value = helper

        ops.write_file(
            client,
            volume_name="ws",
            path=f"{WORKSPACE_DOCUMENTS_PATH}/{FEATURE_DEFINITION_FILENAME}",
            content="# hello\n",
        )

        assert client.containers.create.called
        assert helper.put_archive.called
        call = helper.put_archive.call_args
        assert call.args[0] == WORKSPACE_DOCUMENTS_PATH
        tar_bytes = call.args[1]
        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r") as tar:
            members = tar.getmembers()
            assert len(members) == 1
            assert members[0].name == FEATURE_DEFINITION_FILENAME
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
            path=f"{WORKSPACE_DOCUMENTS_PATH}/{FEATURE_DEFINITION_FILENAME}",
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
            path=f"{WORKSPACE_DOCUMENTS_PATH}/{FEATURE_DEFINITION_FILENAME}",
            content="content",
        )
        assert helper.remove.called


class TestGitContainersAvoidAnonymousVolume:
    """alpine/git declares `VOLUME /git`; without an explicit mount over it,
    every `containers.run(..., remove=True)` leaves an anonymous volume behind
    (remove=True reaps the container, not its anonymous volumes). Mounting a
    tmpfs at /git prevents the anonymous volume from ever being created."""

    def test_given_clone_when_run_then_tmpfs_mounts_over_git_volume(self):
        client = MagicMock()
        client.containers.run.return_value = b"a" * 40 + b"\n"
        ops.clone_and_resolve_ref(
            client, volume_name="ws", repo_url="u", ref="r", codebase_path=WORKSPACE_CODEBASE_PATH
        )
        assert client.containers.run.call_args.kwargs.get("tmpfs") == {"/git": ""}

    def test_given_list_remote_branches_when_run_then_tmpfs_mounts_over_git_volume(self):
        client = MagicMock()
        client.containers.run.return_value = b""
        ops.list_remote_branches(client, volume_name="ws", codebase_path=WORKSPACE_CODEBASE_PATH)
        assert client.containers.run.call_args.kwargs.get("tmpfs") == {"/git": ""}

    def test_given_create_branch_when_run_then_tmpfs_mounts_over_git_volume(self):
        client = MagicMock()
        ops.create_and_checkout_branch(
            client, volume_name="ws", codebase_path=WORKSPACE_CODEBASE_PATH, branch_name="b"
        )
        assert client.containers.run.call_args.kwargs.get("tmpfs") == {"/git": ""}
