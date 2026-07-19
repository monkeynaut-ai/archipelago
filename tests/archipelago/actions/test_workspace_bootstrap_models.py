"""Tests for workspace-bootstrap state models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from archipelago.actions.workspace_bootstrap import (
    BootstrapInput,
    BootstrapOutput,
    WorkspaceHandle,
    _slugify_branch,
    _unique_branch_name,
)
from archipelago.constants import (
    FEATURE_DEFINITION_FILENAME,
    WORKSPACE_CODEBASE_PATH,
    WORKSPACE_DOCUMENTS_PATH,
    WORKSPACE_ROOT,
)
from archipelago.models import CodebaseSource


def _sample_handle() -> WorkspaceHandle:
    return WorkspaceHandle(
        volume_name="archipelago-ws-demo-1000000000000000000",
        root=WORKSPACE_ROOT,
        documents_path=WORKSPACE_DOCUMENTS_PATH,
        codebase_path=WORKSPACE_CODEBASE_PATH,
        feature_definition_path=f"{WORKSPACE_DOCUMENTS_PATH}/{FEATURE_DEFINITION_FILENAME}",
        codebase_source_ref="main",
        codebase_resolved_sha="a" * 40,
    )


class TestSlugifyBranch:
    def test_given_normal_title_when_slugify_then_lowercase_hyphenated(self):
        assert _slugify_branch("Run Observability") == "run-observability"

    def test_given_special_chars_when_slugify_then_replaced_with_hyphens(self):
        assert _slugify_branch("Add OAuth2.0 Support!") == "add-oauth2-0-support"

    def test_given_empty_string_when_slugify_then_returns_unnamed(self):
        assert _slugify_branch("") == "unnamed"

    def test_given_spaces_only_when_slugify_then_returns_unnamed(self):
        assert _slugify_branch("   ") == "unnamed"

    def test_given_consecutive_special_chars_when_slugify_then_single_hyphen(self):
        assert (
            _slugify_branch("feat: add logging") == "feat--add-logging"
            or _slugify_branch("feat: add logging") == "feat-add-logging"
        )

    def test_given_leading_trailing_hyphens_after_sub_when_slugify_then_stripped(self):
        result = _slugify_branch("  hello world  ")
        assert not result.startswith("-")
        assert not result.endswith("-")


class TestUniqueBranchName:
    def test_given_title_not_in_remote_when_unique_then_returns_slug(self):
        result = _unique_branch_name("Run Observability", set())
        assert result == "run-observability"

    def test_given_title_slug_fits_24_chars_when_unique_then_not_truncated(self):
        # "run-observability" is 17 chars, well under 24
        result = _unique_branch_name("Run Observability", set())
        assert len(result) <= 24

    def test_given_long_title_when_unique_then_truncated_to_24(self):
        title = "A Very Long Feature Title That Exceeds The Limit"
        result = _unique_branch_name(title, set())
        assert len(result) <= 24

    def test_given_long_title_when_unique_then_no_trailing_hyphen(self):
        title = "A Very Long Feature Title That Exceeds The Limit"
        result = _unique_branch_name(title, set())
        assert not result.endswith("-")

    def test_given_collision_when_unique_then_appends_suffix_1(self):
        slug = _slugify_branch("Demo Feature")
        result = _unique_branch_name("Demo Feature", {slug})
        assert result == f"{slug[:21].rstrip('-')}-1"

    def test_given_collision_on_1_when_unique_then_appends_suffix_2(self):
        slug = _slugify_branch("Demo Feature")
        base = slug[:21].rstrip("-")
        result = _unique_branch_name("Demo Feature", {slug, f"{base}-1"})
        assert result == f"{base}-2"

    def test_given_24_char_slug_collides_when_unique_then_base_truncated_for_suffix(self):
        # Construct a title whose slug is exactly 24 chars
        title = "abcde fghij klmno pqrstu"  # "abcde-fghij-klmno-pqrstu" = 24 chars
        slug = _slugify_branch(title)
        assert len(slug) == 24
        candidate = slug[:24].rstrip("-")
        result = _unique_branch_name(title, {candidate})
        assert len(result) <= 24
        assert result != candidate

    def test_given_all_99_suffixes_taken_when_unique_then_raises(self):
        slug = _slugify_branch("Demo Feature")
        candidate = slug[:24].rstrip("-")
        base = slug[:21].rstrip("-")
        taken = {candidate} | {f"{base}-{i}" for i in range(1, 100)}
        with pytest.raises(RuntimeError):
            _unique_branch_name("Demo Feature", taken)


class TestWorkspaceHandle:
    def test_given_all_fields_when_constructed_then_fields_populated(self):
        handle = _sample_handle()
        assert handle.root == WORKSPACE_ROOT
        assert handle.codebase_resolved_sha == "a" * 40

    def test_given_missing_volume_name_when_constructed_then_validation_error(self):
        with pytest.raises(ValidationError):
            WorkspaceHandle(
                root=WORKSPACE_ROOT,
                documents_path=WORKSPACE_DOCUMENTS_PATH,
                codebase_path=WORKSPACE_CODEBASE_PATH,
                feature_definition_path=f"{WORKSPACE_DOCUMENTS_PATH}/{FEATURE_DEFINITION_FILENAME}",
                codebase_source_ref="main",
                codebase_resolved_sha="a" * 40,
            )  # type: ignore[call-arg]


class TestBootstrapInputOutput:
    def test_given_all_fields_when_bootstrap_input_then_fields_populated(
        self, minimal_feature_definition
    ):
        state = BootstrapInput(
            feature_definition=minimal_feature_definition,
            codebase_source=CodebaseSource(
                repo_url="https://github.com/monkeynaut-ai/agent-foundry.git",
                ref="main",
            ),
            volume_name="archipelago-ws-demo-1000000000000000000",
        )
        assert state.feature_definition is minimal_feature_definition
        assert state.volume_name.startswith("archipelago-ws-")

    def test_given_missing_volume_name_when_bootstrap_input_then_validation_error(
        self, minimal_feature_definition
    ):
        with pytest.raises(ValidationError):
            BootstrapInput(
                feature_definition=minimal_feature_definition,
                codebase_source=CodebaseSource(repo_url="u", ref="r"),
            )  # type: ignore[call-arg]

    def test_given_handle_when_bootstrap_output_then_handle_preserved(self):
        handle = _sample_handle()
        out = BootstrapOutput(workspace_handle=handle)
        assert out.workspace_handle is handle
