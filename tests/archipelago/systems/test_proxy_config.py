"""Tests for proxy-wiring env-var translation."""

from __future__ import annotations

import pytest

from archipelago.systems._proxy_config import build_proxy_wiring


def test_returns_none_when_both_env_vars_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARCHIPELAGO_PROXY_URL", raising=False)
    monkeypatch.delenv("ARCHIPELAGO_PROXY_CA_PATH", raising=False)
    assert build_proxy_wiring() == (None, None)


def test_returns_none_when_only_url_set(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("ARCHIPELAGO_PROXY_URL", "http://host.docker.internal:8080")
    monkeypatch.delenv("ARCHIPELAGO_PROXY_CA_PATH", raising=False)
    assert build_proxy_wiring() == (None, None)


def test_returns_none_when_only_ca_path_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARCHIPELAGO_PROXY_URL", raising=False)
    monkeypatch.setenv("ARCHIPELAGO_PROXY_CA_PATH", "/abs/ca.crt")
    assert build_proxy_wiring() == (None, None)


def test_returns_wiring_when_both_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARCHIPELAGO_PROXY_URL", "http://host.docker.internal:8080")
    monkeypatch.setenv("ARCHIPELAGO_PROXY_CA_PATH", "/abs/ca.crt")

    env, vols = build_proxy_wiring()

    assert env == {
        "HTTPS_PROXY": "http://host.docker.internal:8080",
        "NODE_EXTRA_CA_CERTS": "/etc/archipelago/mitmproxy-ca.crt",
    }
    assert vols == {"/abs/ca.crt": {"bind": "/etc/archipelago/mitmproxy-ca.crt", "mode": "ro"}}
