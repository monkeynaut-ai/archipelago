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
