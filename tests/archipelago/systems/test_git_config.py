"""Tests for git-identity env-var forwarding."""

from __future__ import annotations

import pytest

from archipelago.systems._git_config import build_git_env


def test_returns_empty_when_both_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GIT_USER_NAME", raising=False)
    monkeypatch.delenv("GIT_USER_EMAIL", raising=False)
    assert build_git_env() == {}


def test_includes_only_name_when_email_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_USER_NAME", "Mark")
    monkeypatch.delenv("GIT_USER_EMAIL", raising=False)
    assert build_git_env() == {"GIT_USER_NAME": "Mark"}


def test_includes_only_email_when_name_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GIT_USER_NAME", raising=False)
    monkeypatch.setenv("GIT_USER_EMAIL", "mark@example.com")
    assert build_git_env() == {"GIT_USER_EMAIL": "mark@example.com"}


def test_includes_both_when_both_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_USER_NAME", "Mark")
    monkeypatch.setenv("GIT_USER_EMAIL", "mark@example.com")
    assert build_git_env() == {"GIT_USER_NAME": "Mark", "GIT_USER_EMAIL": "mark@example.com"}


def test_treats_whitespace_only_values_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_USER_NAME", "   ")
    monkeypatch.setenv("GIT_USER_EMAIL", "")
    assert build_git_env() == {}
