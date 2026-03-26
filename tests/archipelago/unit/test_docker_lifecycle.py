"""DockerLifecycle — unit tests with mocked Docker and WebSocket protocol."""

import queue
import threading
from unittest.mock import MagicMock, patch

from archipelago.docker_worker.lifecycle import DockerLifecycle, LifecycleResult, _HandlerWSServer
from archipelago.docker_worker.protocol import (
    AgentEventMessage,
    OutputMessage,
    StatusMessage,
)


def _mock_docker_env(mock_docker):
    """Create a standard mock Docker client/container."""
    client = MagicMock()
    container = MagicMock()
    container.id = "c1"
    container.exec_run.return_value = (0, b"abc123")
    client.containers.create.return_value = container
    mock_docker.from_env.return_value = client
    return client, container


def _preload_ws_server(messages: list[str], *, send_return=True):
    """Create a mock _HandlerWSServer with pre-loaded messages and pre-set connected."""
    server = MagicMock(spec=_HandlerWSServer)
    q = queue.Queue()
    for m in messages:
        q.put(m)
    server.message_queue = q
    server.connected = threading.Event()
    server.connected.set()
    server.send = MagicMock(return_value=send_return)
    server.start = MagicMock()
    server.shutdown = MagicMock()
    return server


def _output_msg(text: str, session_id: str = "test") -> str:
    return OutputMessage(
        type="output",
        session_id=session_id,
        text=text,
        stream="stdout",
        timestamp=1.0,
    ).model_dump_json()


def _status_msg(status: str, exit_code: int | None = None, session_id: str = "test") -> str:
    return StatusMessage(
        type="status",
        session_id=session_id,
        status=status,
        exit_code=exit_code,
        timestamp=1.0,
    ).model_dump_json()


def _agent_event_msg(
    event_type: str,
    payload: dict,
    session_id: str = "test",
) -> str:
    return AgentEventMessage(
        session_id=session_id,
        event_type=event_type,
        payload=payload,
        raw_line="raw",
        timestamp=1.0,
    ).model_dump_json()


class TestDockerLifecycleHappyPath:
    @patch("archipelago.docker_worker.lifecycle._HandlerWSServer")
    @patch("archipelago.docker_worker.lifecycle.docker")
    def test_given_valid_prompt_when_execute_called_then_returns_completed_result(
        self, mock_docker, mock_ws_cls
    ):
        _mock_docker_env(mock_docker)
        mock_ws_cls.return_value = _preload_ws_server(
            [
                _output_msg("done"),
                _status_msg("exited", 0),
            ]
        )

        lifecycle = DockerLifecycle()
        result = lifecycle.execute(prompt="Write tests", workspace_volume="vol-1")

        assert isinstance(result, LifecycleResult)
        assert result.exit_code == 0

    @patch("archipelago.docker_worker.lifecycle._HandlerWSServer")
    @patch("archipelago.docker_worker.lifecycle.docker")
    def test_given_container_completes_when_execute_called_then_output_lines_captured(
        self, mock_docker, mock_ws_cls
    ):
        _mock_docker_env(mock_docker)
        mock_ws_cls.return_value = _preload_ws_server(
            [
                _output_msg("line 1"),
                _output_msg("line 2"),
                _status_msg("exited", 0),
            ]
        )

        lifecycle = DockerLifecycle()
        result = lifecycle.execute(prompt="Write tests", workspace_volume="vol-1")

        assert "line 1" in result.output_lines
        assert "line 2" in result.output_lines

    @patch("archipelago.docker_worker.lifecycle._HandlerWSServer")
    @patch("archipelago.docker_worker.lifecycle.docker")
    def test_given_container_completes_when_execute_called_then_commit_hash_captured(
        self, mock_docker, mock_ws_cls
    ):
        _, mock_container = _mock_docker_env(mock_docker)
        mock_container.exec_run.return_value = (0, b"deadbeef")
        mock_ws_cls.return_value = _preload_ws_server(
            [
                _status_msg("exited", 0),
            ]
        )

        lifecycle = DockerLifecycle()
        result = lifecycle.execute(prompt="Write tests", workspace_volume="vol-1")

        assert result.commit_hash == "deadbeef"


class TestDockerLifecycleFailurePaths:
    @patch("archipelago.docker_worker.lifecycle.docker")
    def test_given_docker_unavailable_when_execute_called_then_returns_failed_result(
        self, mock_docker
    ):
        mock_docker.from_env.side_effect = Exception("Docker not running")

        lifecycle = DockerLifecycle()
        result = lifecycle.execute(prompt="Write tests", workspace_volume="vol-1")

        assert result.exit_code != 0

    @patch("archipelago.docker_worker.lifecycle._HandlerWSServer")
    @patch("archipelago.docker_worker.lifecycle.docker")
    def test_given_adapter_timeout_when_execute_called_then_returns_failed_result(
        self, mock_docker, mock_ws_cls
    ):
        _mock_docker_env(mock_docker)
        ws_server = _preload_ws_server([])
        ws_server.connected = threading.Event()  # NOT set — will timeout
        mock_ws_cls.return_value = ws_server

        lifecycle = DockerLifecycle()
        result = lifecycle.execute(
            prompt="Write tests",
            workspace_volume="vol-1",
            connection_timeout_seconds=0,
        )

        assert result.exit_code != 0

    @patch("archipelago.docker_worker.lifecycle._HandlerWSServer")
    @patch("archipelago.docker_worker.lifecycle.docker")
    def test_given_prompt_delivery_fails_when_execute_called_then_returns_failed_result(
        self, mock_docker, mock_ws_cls
    ):
        _mock_docker_env(mock_docker)
        mock_ws_cls.return_value = _preload_ws_server([], send_return=False)

        lifecycle = DockerLifecycle()
        result = lifecycle.execute(prompt="Write tests", workspace_volume="vol-1")

        assert result.exit_code != 0

    @patch("archipelago.docker_worker.lifecycle._HandlerWSServer")
    @patch("archipelago.docker_worker.lifecycle.docker")
    def test_given_nonzero_exit_code_when_execute_called_then_returns_failed_result(
        self, mock_docker, mock_ws_cls
    ):
        _mock_docker_env(mock_docker)
        mock_ws_cls.return_value = _preload_ws_server(
            [
                _status_msg("exited", 1),
            ]
        )

        lifecycle = DockerLifecycle()
        result = lifecycle.execute(prompt="Write tests", workspace_volume="vol-1")

        assert result.exit_code == 1

    @patch("archipelago.docker_worker.lifecycle._HandlerWSServer")
    @patch("archipelago.docker_worker.lifecycle.docker")
    def test_given_deadline_exceeded_when_execute_called_then_returns_timed_out_result(
        self, mock_docker, mock_ws_cls
    ):
        _mock_docker_env(mock_docker)
        # Only output, no exit status — will timeout
        mock_ws_cls.return_value = _preload_ws_server([_output_msg("working...")])

        lifecycle = DockerLifecycle()
        result = lifecycle.execute(
            prompt="Write tests",
            workspace_volume="vol-1",
            timeout_seconds=0,
        )

        assert result.exit_code is None  # never exited

    @patch("archipelago.docker_worker.lifecycle._HandlerWSServer")
    @patch("archipelago.docker_worker.lifecycle.docker")
    def test_given_connection_drops_when_execute_called_then_returns_failed_result(
        self, mock_docker, mock_ws_cls
    ):
        _mock_docker_env(mock_docker)
        # None sentinel indicates connection dropped
        ws_server = _preload_ws_server([])
        ws_server.message_queue.put(None)
        mock_ws_cls.return_value = ws_server

        lifecycle = DockerLifecycle()
        result = lifecycle.execute(prompt="Write tests", workspace_volume="vol-1")

        assert result.exit_code != 0


class TestDockerLifecycleCleanup:
    @patch("archipelago.docker_worker.lifecycle._HandlerWSServer")
    @patch("archipelago.docker_worker.lifecycle.docker")
    def test_given_successful_execution_when_complete_then_container_destroyed(
        self, mock_docker, mock_ws_cls
    ):
        _, mock_container = _mock_docker_env(mock_docker)
        mock_ws_cls.return_value = _preload_ws_server([_status_msg("exited", 0)])

        lifecycle = DockerLifecycle()
        lifecycle.execute(prompt="Write tests", workspace_volume="vol-1")

        mock_container.remove.assert_called_once()

    @patch("archipelago.docker_worker.lifecycle._HandlerWSServer")
    @patch("archipelago.docker_worker.lifecycle.docker")
    def test_given_exception_during_execution_when_complete_then_container_still_destroyed(
        self, mock_docker, mock_ws_cls
    ):
        _, mock_container = _mock_docker_env(mock_docker)
        ws_server = _preload_ws_server([])
        ws_server.connected = threading.Event()  # NOT set — timeout
        mock_ws_cls.return_value = ws_server

        lifecycle = DockerLifecycle()
        lifecycle.execute(
            prompt="Write tests",
            workspace_volume="vol-1",
            connection_timeout_seconds=0,
        )

        mock_container.remove.assert_called_once()

    @patch("archipelago.docker_worker.lifecycle._HandlerWSServer")
    @patch("archipelago.docker_worker.lifecycle.docker")
    def test_given_exception_during_execution_when_complete_then_ws_server_shut_down(
        self, mock_docker, mock_ws_cls
    ):
        _mock_docker_env(mock_docker)
        ws_server = _preload_ws_server([])
        ws_server.connected = threading.Event()  # NOT set — timeout
        mock_ws_cls.return_value = ws_server

        lifecycle = DockerLifecycle()
        lifecycle.execute(
            prompt="Write tests",
            workspace_volume="vol-1",
            connection_timeout_seconds=0,
        )

        ws_server.shutdown.assert_called_once()


class TestDockerLifecycleHitl:
    @patch("archipelago.docker_worker.lifecycle._HandlerWSServer")
    @patch("archipelago.docker_worker.lifecycle.docker")
    def test_given_clarification_requested_when_hitl_callback_provided_then_response_sent(
        self, mock_docker, mock_ws_cls
    ):
        _mock_docker_env(mock_docker)
        ws_server = _preload_ws_server(
            [
                _agent_event_msg(
                    "clarification_requested",
                    {"question": "Which DB?", "options": ["pg"], "default": "pg", "blocking": True},
                ),
                _status_msg("exited", 0),
            ]
        )
        mock_ws_cls.return_value = ws_server

        callback = MagicMock(return_value="pg")
        lifecycle = DockerLifecycle()
        lifecycle.execute(
            prompt="Write tests",
            workspace_volume="vol-1",
            hitl_callback=callback,
        )

        callback.assert_called_once_with(
            "clarification",
            {
                "question": "Which DB?",
                "options": ["pg"],
                "default": "pg",
                "blocking": True,
            },
        )

    @patch("archipelago.docker_worker.lifecycle._HandlerWSServer")
    @patch("archipelago.docker_worker.lifecycle.docker")
    def test_given_permission_requested_when_low_risk_and_auto_approve_then_approved(
        self, mock_docker, mock_ws_cls
    ):
        _mock_docker_env(mock_docker)
        ws_server = _preload_ws_server(
            [
                _agent_event_msg(
                    "permission_requested",
                    {"action": "install dep", "risk_level": "low", "why_needed": "needed"},
                ),
                _status_msg("exited", 0),
            ]
        )
        mock_ws_cls.return_value = ws_server

        lifecycle = DockerLifecycle()
        result = lifecycle.execute(
            prompt="Write tests",
            workspace_volume="vol-1",
            auto_approve_low_risk=True,
        )

        # Auto-approved — should complete without callback
        assert result.exit_code == 0
        # Verify "yes" was sent back
        send_calls = [str(c) for c in ws_server.send.call_args_list]
        assert any("yes" in c for c in send_calls)
