"""Tests for proxy-wiring env-var translation."""

from __future__ import annotations

import pytest

from archipelago.systems._proxy_config import build_proxy_env, build_proxy_volumes


class TestBuildProxyEnv:
    def test_returns_none_when_both_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ARCHIPELAGO_PROXY_URL", raising=False)
        monkeypatch.delenv("ARCHIPELAGO_PROXY_CA_PATH", raising=False)
        assert build_proxy_env() is None

    def test_returns_none_when_only_url_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARCHIPELAGO_PROXY_URL", "http://host.docker.internal:8080")
        monkeypatch.delenv("ARCHIPELAGO_PROXY_CA_PATH", raising=False)
        assert build_proxy_env() is None

    def test_returns_none_when_only_ca_path_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ARCHIPELAGO_PROXY_URL", raising=False)
        monkeypatch.setenv("ARCHIPELAGO_PROXY_CA_PATH", "/abs/ca.crt")
        assert build_proxy_env() is None

    def test_returns_env_when_both_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARCHIPELAGO_PROXY_URL", "http://host.docker.internal:8080")
        monkeypatch.setenv("ARCHIPELAGO_PROXY_CA_PATH", "/abs/ca.crt")

        assert build_proxy_env() == {
            "HTTPS_PROXY": "http://host.docker.internal:8080",
            "NODE_EXTRA_CA_CERTS": "/etc/archipelago/mitmproxy-ca.crt",
        }


class TestBuildProxyVolumes:
    def test_returns_none_when_both_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ARCHIPELAGO_PROXY_URL", raising=False)
        monkeypatch.delenv("ARCHIPELAGO_PROXY_CA_PATH", raising=False)
        assert build_proxy_volumes() is None

    def test_returns_none_when_only_one_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARCHIPELAGO_PROXY_URL", "http://host.docker.internal:8080")
        monkeypatch.delenv("ARCHIPELAGO_PROXY_CA_PATH", raising=False)
        assert build_proxy_volumes() is None

    def test_returns_mount_when_both_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARCHIPELAGO_PROXY_URL", "http://host.docker.internal:8080")
        monkeypatch.setenv("ARCHIPELAGO_PROXY_CA_PATH", "/abs/ca.crt")

        assert build_proxy_volumes() == {
            "/abs/ca.crt": {"bind": "/etc/archipelago/mitmproxy-ca.crt", "mode": "ro"}
        }
