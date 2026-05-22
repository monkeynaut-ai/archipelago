"""Tests for the coordinator that builds extra_env and extra_volumes."""

from __future__ import annotations

import pytest

from archipelago.systems._container_extras import build_extra_env, build_extra_volumes


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "ARCHIPELAGO_PROXY_URL",
        "ARCHIPELAGO_PROXY_CA_PATH",
        "GIT_USER_NAME",
        "GIT_USER_EMAIL",
    ):
        monkeypatch.delenv(var, raising=False)


class TestBuildExtraEnv:
    def test_returns_none_when_no_contributions(self) -> None:
        assert build_extra_env() is None

    def test_returns_only_git_env_when_only_git_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GIT_USER_NAME", "Mark")
        monkeypatch.setenv("GIT_USER_EMAIL", "mark@example.com")
        assert build_extra_env() == {
            "GIT_USER_NAME": "Mark",
            "GIT_USER_EMAIL": "mark@example.com",
        }

    def test_returns_only_proxy_env_when_only_proxy_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ARCHIPELAGO_PROXY_URL", "http://host.docker.internal:8080")
        monkeypatch.setenv("ARCHIPELAGO_PROXY_CA_PATH", "/abs/ca.crt")
        assert build_extra_env() == {
            "HTTPS_PROXY": "http://host.docker.internal:8080",
            "NODE_EXTRA_CA_CERTS": "/etc/archipelago/mitmproxy-ca.crt",
        }

    def test_merges_proxy_and_git_when_both_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARCHIPELAGO_PROXY_URL", "http://host.docker.internal:8080")
        monkeypatch.setenv("ARCHIPELAGO_PROXY_CA_PATH", "/abs/ca.crt")
        monkeypatch.setenv("GIT_USER_NAME", "Mark")

        assert build_extra_env() == {
            "HTTPS_PROXY": "http://host.docker.internal:8080",
            "NODE_EXTRA_CA_CERTS": "/etc/archipelago/mitmproxy-ca.crt",
            "GIT_USER_NAME": "Mark",
        }


class TestBuildExtraVolumes:
    def test_returns_none_when_no_contributions(self) -> None:
        assert build_extra_volumes() is None

    def test_returns_proxy_mount_when_proxy_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ARCHIPELAGO_PROXY_URL", "http://host.docker.internal:8080")
        monkeypatch.setenv("ARCHIPELAGO_PROXY_CA_PATH", "/abs/ca.crt")
        assert build_extra_volumes() == {
            "/abs/ca.crt": {"bind": "/etc/archipelago/mitmproxy-ca.crt", "mode": "ro"}
        }
