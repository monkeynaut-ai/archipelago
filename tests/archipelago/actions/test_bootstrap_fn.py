"""Tests for bootstrap_fn orchestration (helpers patched)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from archetype.markdown import render_instance

from archipelago.actions.workspace_bootstrap import (
    BootstrapInput,
    BootstrapOutput,
    bootstrap_fn,
)
from archipelago.constants import (
    FEATURE_DEFINITION_FILENAME,
    WORKSPACE_CODEBASE_PATH,
    WORKSPACE_DOCUMENTS_PATH,
)
from archipelago.models import CodebaseSource


@pytest.fixture(autouse=True)
def _clear_github_tokens(monkeypatch):
    """Default bootstrap_fn tests to a token-free environment so assertions
    about github_token=None hold regardless of the developer's shell env.
    Tests that exercise the token-passthrough path (below) opt in with
    monkeypatch.setenv."""
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)


@pytest.fixture
def patched_ops():
    with (
        patch("archipelago.actions.workspace_bootstrap._ops") as ops_mod,
        patch("archipelago.actions.workspace_bootstrap.docker.from_env") as from_env,
    ):
        client = MagicMock()
        from_env.return_value = client
        ops_mod.clone_and_resolve_ref.return_value = "f" * 40
        ops_mod.create_volume.return_value = MagicMock(name="volume")
        ops_mod.list_remote_branches.return_value = set()
        ops_mod.GIT_IMAGE = "alpine/git:v2.47.2"
        ops_mod.ALPINE_IMAGE = "alpine:3.20"
        yield ops_mod, client


def _input(minimal_feature_definition, volume_name="archipelago-ws-demo-1") -> BootstrapInput:
    return BootstrapInput(
        feature_definition=minimal_feature_definition,
        codebase_source=CodebaseSource(repo_url="https://example.com/repo.git", ref="main"),
        volume_name=volume_name,
    )


class TestBootstrapFn:
    def test_given_input_when_bootstrap_then_helpers_called_in_order(
        self, patched_ops, minimal_feature_definition
    ):
        ops_mod, client = patched_ops
        result = bootstrap_fn(_input(minimal_feature_definition))

        assert isinstance(result, BootstrapOutput)

        # 1. Images pulled before volume creation.
        pull_calls = ops_mod.pull_image.call_args_list
        assert {c.args[1] for c in pull_calls} == {"alpine/git:v2.47.2", "alpine:3.20"}

        # 2. Volume created with the passed name.
        ops_mod.create_volume.assert_called_once_with(client, "archipelago-ws-demo-1")

        # 3. Clone against the passed name.
        ops_mod.clone_and_resolve_ref.assert_called_once_with(
            client,
            volume_name="archipelago-ws-demo-1",
            repo_url="https://example.com/repo.git",
            ref="main",
            codebase_path=WORKSPACE_CODEBASE_PATH,
            github_token=None,
        )

        # 4. prepare_codebase_tree splits ownership: GID_CODEBASE for the
        # bulk, GID_TESTS for tests/, .git/ untouched, mode 775.
        ops_mod.prepare_codebase_tree.assert_called_once_with(
            client,
            volume_name="archipelago-ws-demo-1",
            codebase_path=WORKSPACE_CODEBASE_PATH,
        )

        # 5. Documents dir prepared.
        ops_mod.prepare_documents_dir.assert_called_once_with(
            client, volume_name="archipelago-ws-demo-1", path=WORKSPACE_DOCUMENTS_PATH
        )

        # 6. write_file on feature_definition.md with mode 444.
        ops_mod.write_file.assert_called_once()
        kwargs = ops_mod.write_file.call_args.kwargs
        assert kwargs["path"] == f"{WORKSPACE_DOCUMENTS_PATH}/{FEATURE_DEFINITION_FILENAME}"
        assert kwargs["mode"] == "444"

    def test_given_input_when_bootstrap_then_feature_def_rendered_via_render_instance(
        self, patched_ops, minimal_feature_definition
    ):
        ops_mod, _ = patched_ops
        bootstrap_fn(_input(minimal_feature_definition))

        kwargs = ops_mod.write_file.call_args.kwargs
        assert kwargs["content"] == render_instance(minimal_feature_definition)

    def test_given_input_when_bootstrap_then_handle_records_ref_and_resolved_sha(
        self, patched_ops, minimal_feature_definition
    ):
        ops_mod, _ = patched_ops
        ops_mod.clone_and_resolve_ref.return_value = "d" * 40
        state = BootstrapInput(
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(repo_url="u", ref="v1.2.3"),
            volume_name="archipelago-ws-demo-1",
        )

        result = bootstrap_fn(state)
        assert result.workspace_handle.codebase_source_ref == "v1.2.3"
        assert result.workspace_handle.codebase_resolved_sha == "d" * 40
        assert result.workspace_handle.volume_name == "archipelago-ws-demo-1"

    def test_given_pull_failure_when_bootstrap_then_create_volume_not_called(
        self, patched_ops, minimal_feature_definition
    ):
        ops_mod, _ = patched_ops
        ops_mod.pull_image.side_effect = RuntimeError("network error")
        with pytest.raises(RuntimeError, match="network error"):
            bootstrap_fn(_input(minimal_feature_definition))
        ops_mod.create_volume.assert_not_called()

    def test_given_clone_failure_when_bootstrap_then_chmod_and_write_skipped(
        self, patched_ops, minimal_feature_definition
    ):
        ops_mod, _ = patched_ops
        ops_mod.clone_and_resolve_ref.side_effect = RuntimeError("clone failed")
        with pytest.raises(RuntimeError, match="clone failed"):
            bootstrap_fn(_input(minimal_feature_definition))
        ops_mod.prepare_codebase_tree.assert_not_called()
        ops_mod.prepare_documents_dir.assert_not_called()
        ops_mod.write_file.assert_not_called()

    def test_given_post_create_failure_when_bootstrap_then_volume_is_removed(
        self, patched_ops, minimal_feature_definition
    ):
        ops_mod, client = patched_ops
        ops_mod.clone_and_resolve_ref.side_effect = RuntimeError("clone failed")
        state = BootstrapInput(
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(repo_url="u", ref="r"),
            volume_name="archipelago-ws-demo-cleanup",
        )

        with pytest.raises(RuntimeError, match="clone failed"):
            bootstrap_fn(state)

        # Volume removed via client.volumes.get(name).remove(force=True).
        client.volumes.get.assert_called_with("archipelago-ws-demo-cleanup")
        client.volumes.get.return_value.remove.assert_called_with(force=True)

    def test_given_gh_token_env_when_bootstrap_then_token_passed_to_clone(
        self, patched_ops, minimal_feature_definition, monkeypatch
    ):
        monkeypatch.setenv("GH_TOKEN", "env-token")
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        ops_mod, _ = patched_ops
        bootstrap_fn(_input(minimal_feature_definition))
        call = ops_mod.clone_and_resolve_ref.call_args
        assert call.kwargs["github_token"] == "env-token"

    def test_given_github_token_env_when_bootstrap_then_token_passed_to_clone(
        self, patched_ops, minimal_feature_definition, monkeypatch
    ):
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.setenv("GITHUB_TOKEN", "fallback-token")
        ops_mod, _ = patched_ops
        bootstrap_fn(_input(minimal_feature_definition))
        call = ops_mod.clone_and_resolve_ref.call_args
        assert call.kwargs["github_token"] == "fallback-token"

    def test_given_no_token_env_when_bootstrap_then_token_is_none(
        self, patched_ops, minimal_feature_definition, monkeypatch
    ):
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        ops_mod, _ = patched_ops
        bootstrap_fn(_input(minimal_feature_definition))
        call = ops_mod.clone_and_resolve_ref.call_args
        assert call.kwargs["github_token"] is None


class TestBootstrapFnBranchCheckout:
    def test_given_input_when_bootstrap_then_list_remote_branches_called_after_clone(
        self, patched_ops, minimal_feature_definition
    ):
        ops_mod, _ = patched_ops
        bootstrap_fn(_input(minimal_feature_definition))

        ops_mod.list_remote_branches.assert_called_once()
        call = ops_mod.list_remote_branches.call_args
        assert call.kwargs["volume_name"] == "archipelago-ws-demo-1"

    def test_given_clean_remote_when_bootstrap_then_branch_named_from_title(
        self, patched_ops, minimal_feature_definition
    ):
        # "Demo Feature" → "demo-feature"
        ops_mod, _ = patched_ops
        ops_mod.list_remote_branches.return_value = set()

        bootstrap_fn(_input(minimal_feature_definition))

        call = ops_mod.create_and_checkout_branch.call_args
        assert call.kwargs["branch_name"] == "demo-feature"

    def test_given_input_when_bootstrap_then_create_branch_called_with_correct_name(
        self, patched_ops, minimal_feature_definition
    ):
        ops_mod, _ = patched_ops
        ops_mod.list_remote_branches.return_value = set()

        bootstrap_fn(_input(minimal_feature_definition))

        ops_mod.create_and_checkout_branch.assert_called_once()
        call = ops_mod.create_and_checkout_branch.call_args
        assert call.kwargs["branch_name"] == "demo-feature"
        assert call.kwargs["volume_name"] == "archipelago-ws-demo-1"

    def test_given_collision_on_base_when_bootstrap_then_branch_gets_suffix(
        self, patched_ops, minimal_feature_definition
    ):
        ops_mod, _ = patched_ops
        ops_mod.list_remote_branches.return_value = {"demo-feature"}

        bootstrap_fn(_input(minimal_feature_definition))

        call = ops_mod.create_and_checkout_branch.call_args
        assert call.kwargs["branch_name"] == "demo-feature-1"

    def test_given_branch_failure_when_bootstrap_then_volume_cleaned_up(
        self, patched_ops, minimal_feature_definition
    ):
        ops_mod, client = patched_ops
        ops_mod.create_and_checkout_branch.side_effect = RuntimeError("branch failed")

        with pytest.raises(RuntimeError, match="branch failed"):
            bootstrap_fn(_input(minimal_feature_definition))

        client.volumes.get.return_value.remove.assert_called_with(force=True)
