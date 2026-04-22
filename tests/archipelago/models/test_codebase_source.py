"""Tests for CodebaseSource."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from archipelago.models.codebase_source import CodebaseSource


class TestCodebaseSource:
    def test_given_https_url_and_ref_when_constructed_then_fields_populated(self):
        source = CodebaseSource(
            repo_url="https://github.com/730alchemy/agent-foundry.git",
            ref="main",
        )
        assert source.repo_url == "https://github.com/730alchemy/agent-foundry.git"
        assert source.ref == "main"

    def test_given_ssh_url_when_constructed_then_stored_opaquely(self):
        source = CodebaseSource(
            repo_url="git@github.com:730alchemy/agent-foundry.git",
            ref="abc1234",
        )
        assert source.repo_url.startswith("git@github.com:")
        assert source.ref == "abc1234"

    def test_given_missing_repo_url_when_constructed_then_validation_error(self):
        with pytest.raises(ValidationError):
            CodebaseSource(ref="main")  # type: ignore[call-arg]

    def test_given_missing_ref_when_constructed_then_validation_error(self):
        with pytest.raises(ValidationError):
            CodebaseSource(repo_url="https://example.com/repo.git")  # type: ignore[call-arg]
