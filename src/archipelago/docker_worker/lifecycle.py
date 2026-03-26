"""Docker container lifecycle — manages container execution independently of task logic."""

import contextlib
import queue
import shutil
import socket
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Literal, Protocol

import docker
import structlog
from pydantic import BaseModel, Field
from websockets.sync.server import ServerConnection, serve

from archipelago.docker_worker.container import create_archipelago_container_manager
from archipelago.docker_worker.models import WorkerConstraints
from archipelago.docker_worker.progress import parse_progress, transform_progress_events
from archipelago.docker_worker.protocol import (
    AgentEventMessage,
    ControlMessage,
    InputMessage,
    OutputMessage,
    ProtocolError,
    StatusMessage,
    parse_protocol_message,
)
from archipelago.docker_worker.recovery import persist_workspace_state

logger = structlog.get_logger(__name__)


class LifecycleResult(BaseModel):
    """Result returned by the docker lifecycle after container execution."""

    output_lines: list[str] = Field(default_factory=list)
    exit_code: int | None = None
    commit_hash: str = "unknown"
    patches: list[Any] = Field(default_factory=list)
    evidence: list[Any] = Field(default_factory=list)
    collected_files: dict[str, str] = Field(default_factory=dict)


class HitlCallback(Protocol):
    """Callback for human-in-the-loop interaction during container execution."""

    def __call__(self, prompt_type: str, payload: dict[str, Any]) -> str: ...


class DockerLifecycleProtocol(Protocol):
    """Protocol for docker lifecycle implementations."""

    def execute(
        self,
        *,
        prompt: str,
        workspace_volume: str,
        extra_env: dict[str, str] | None = None,
        constraints: WorkerConstraints | None = None,
        hitl_callback: Any | None = None,
        timeout_seconds: int = 3600,
        connection_timeout_seconds: int = 120,
        auto_approve_low_risk: bool = False,
        collect_files: list[str] | None = None,
    ) -> LifecycleResult: ...


# ── Internal helpers ──


def _get_free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class _HandlerWSServer:
    """Ephemeral WebSocket server for a single adapter connection."""

    def __init__(self) -> None:
        self.message_queue: queue.Queue[str | None] = queue.Queue()
        self.connected = threading.Event()
        self._ws: ServerConnection | None = None
        self._server = None
        self._server_thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self, port: int) -> None:
        def _handler(ws: ServerConnection) -> None:
            with self._lock:
                self._ws = ws
            self.connected.set()
            try:
                while True:
                    try:
                        raw = ws.recv(timeout=0.5)
                        self.message_queue.put(raw if isinstance(raw, str) else raw.decode())
                    except TimeoutError:
                        continue
            except Exception:
                logger.debug("WebSocket handler loop ended", exc_info=True)
            finally:
                self.message_queue.put(None)

        self._server = serve(_handler, "0.0.0.0", port)
        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()

    def send(self, message: str) -> bool:
        with self._lock:
            ws = self._ws
        if not ws:
            return False
        try:
            ws.send(message)
            return True
        except Exception:
            logger.debug("WebSocket send failed", exc_info=True)
            return False

    def shutdown(self) -> None:
        if self._server:
            with contextlib.suppress(Exception):
                self._server.shutdown()


def _send_input(ws_server: _HandlerWSServer, session_id: str, text: str) -> bool:
    msg = InputMessage(type="input", session_id=session_id, text=text)
    return ws_server.send(msg.model_dump_json())


def _send_control(
    ws_server: _HandlerWSServer,
    session_id: str,
    command: Literal["resize", "terminate", "kill"],
    args: dict[str, Any] | None = None,
) -> None:
    msg = ControlMessage(
        type="control",
        session_id=session_id,
        command=command,
        args=args or {},
    )
    ws_server.send(msg.model_dump_json())


def _process_messages(
    ws_server: _HandlerWSServer,
    session_id: str,
    deadline: float,
    auto_approve_low_risk: bool,
    hitl_callback: HitlCallback | None = None,
) -> LifecycleResult:
    """Process protocol messages until completion or timeout. Returns a LifecycleResult."""
    output_lines: list[str] = []
    exit_code: int | None = None

    while time.time() < deadline:
        try:
            raw = ws_server.message_queue.get(timeout=0.1)
        except queue.Empty:
            continue

        if raw is None:
            logger.info("adapter_connection_dropped")
            return LifecycleResult(output_lines=output_lines, exit_code=1)

        try:
            msg = parse_protocol_message(raw)
        except ProtocolError:
            logger.warning("malformed_protocol_message", raw=raw[:200])
            continue

        if isinstance(msg, OutputMessage):
            output_lines.append(msg.text)
            logger.info("cc_output", text=msg.text)

        elif isinstance(msg, AgentEventMessage):
            logger.info(
                "agent_event",
                event_type=msg.event_type,
                payload=msg.payload,
            )
            if msg.event_type == "clarification_requested":
                payload = msg.payload
                blocking = payload.get("blocking", True)
                if blocking:
                    if hitl_callback is not None:
                        response = hitl_callback("clarification", payload)
                        _send_input(ws_server, session_id, response)
                        continue
                    logger.info("clarification_unhandled", payload=payload)
                    return LifecycleResult(output_lines=output_lines, exit_code=1)
            elif msg.event_type == "permission_requested":
                payload = msg.payload
                risk_level = payload.get("risk_level", "medium")
                if risk_level == "low" and auto_approve_low_risk:
                    if not _send_input(ws_server, session_id, "yes\n"):
                        return LifecycleResult(output_lines=output_lines, exit_code=1)
                else:
                    if hitl_callback is not None:
                        response = hitl_callback("permission", payload)
                        _send_input(ws_server, session_id, response)
                        continue
                    logger.info("permission_unhandled", payload=payload)
                    return LifecycleResult(output_lines=output_lines, exit_code=1)

        elif isinstance(msg, StatusMessage):
            logger.info(
                "status_message",
                status=msg.status,
                exit_code=msg.exit_code,
            )
            if msg.status == "exited":
                exit_code = msg.exit_code
                break
            elif msg.status == "completed":
                exit_code = 0
                break

    return LifecycleResult(output_lines=output_lines, exit_code=exit_code)


# ── DockerLifecycle ──


class DockerLifecycle:
    """Manages the full Docker container lifecycle for running Claude Code."""

    def execute(
        self,
        *,
        prompt: str,
        workspace_volume: str,
        extra_env: dict[str, str] | None = None,
        constraints: WorkerConstraints | None = None,
        hitl_callback: HitlCallback | None = None,
        timeout_seconds: int = 3600,
        connection_timeout_seconds: int = 120,
        auto_approve_low_risk: bool = False,
        collect_files: list[str] | None = None,
    ) -> LifecycleResult:
        constraints = constraints or WorkerConstraints()

        try:
            client = docker.from_env()
        except Exception as e:
            logger.error("Docker unavailable: %s", e)
            return LifecycleResult(exit_code=1)

        container_mgr = create_archipelago_container_manager(client)

        ws_server = _HandlerWSServer()
        port = _get_free_port()
        session_id = str(uuid.uuid4())
        ws_server.start(port)

        container_handle = None
        temp_dirs: list[Path] = []
        try:
            ws_url = f"ws://host.docker.internal:{port}/{session_id}"
            env: dict[str, str] = {
                "ARCHIPELAGO_WS_URL": ws_url,
                "ARCHIPELAGO_TURN_TIMEOUT": str(constraints.turn_timeout_seconds),
                "ARCHIPELAGO_SKIP_PERMISSIONS": ("1" if constraints.skip_permissions else "0"),
            }
            if extra_env:
                env.update(extra_env)

            container_handle = container_mgr.create_container(
                workspace_volume=workspace_volume,
                constraints=constraints,
                extra_env=env,
            )
            container_mgr.start(container_handle)

            if not ws_server.connected.wait(timeout=connection_timeout_seconds):
                raise TimeoutError(
                    f"Adapter did not connect within {connection_timeout_seconds} seconds"
                )

            if not _send_input(ws_server, session_id, prompt):
                return LifecycleResult(exit_code=1)

            deadline = time.time() + timeout_seconds
            result = _process_messages(
                ws_server=ws_server,
                session_id=session_id,
                deadline=deadline,
                auto_approve_low_risk=auto_approve_low_risk,
                hitl_callback=hitl_callback,
            )

            if result.exit_code is None and time.time() >= deadline:
                _send_control(ws_server, session_id, "terminate")

            # Capture commit hash from container git state
            commit_hash = "unknown"
            if container_handle:
                exit_code, output = container_handle._container.exec_run(
                    f"git -C {container_handle.workspace_path} rev-parse HEAD"
                )
                if exit_code == 0:
                    commit_hash = output.decode().strip()

            # Collect progress.jsonl from container
            patches: list[Any] = []
            evidence: list[Any] = []
            if container_handle:
                try:
                    progress_dir = Path(tempfile.mkdtemp(prefix="archipelago-progress-"))
                    temp_dirs.append(progress_dir)
                    container_mgr.copy_from_container(
                        container_handle,
                        f"{container_handle.workspace_path}/progress.jsonl",
                        progress_dir / "progress.jsonl",
                    )
                    events = parse_progress(progress_dir)
                    patches, evidence = transform_progress_events(events)
                except Exception:
                    logger.debug("Could not collect progress.jsonl", exc_info=True)

            # Collect requested files from container
            collected_files: dict[str, str] = {}
            if container_handle and collect_files:
                for container_path in collect_files:
                    try:
                        content = container_mgr.read_file_from_container(
                            container_handle, container_path
                        )
                        if content is not None:
                            collected_files[container_path] = content
                    except Exception:
                        logger.debug("Could not collect %s", container_path, exc_info=True)

            return LifecycleResult(
                output_lines=result.output_lines,
                exit_code=result.exit_code,
                commit_hash=commit_hash,
                patches=[p.model_dump() for p in patches],
                evidence=[e.model_dump() for e in evidence],
                collected_files=collected_files,
            )

        except Exception as e:
            logger.error("Docker lifecycle error: %s", e)
            # Crash recovery: persist workspace state
            if container_handle:
                try:
                    recovery_dir = Path(tempfile.mkdtemp(prefix="archipelago-recovery-"))
                    temp_dirs.append(recovery_dir)
                    persist_workspace_state(
                        workspace_path=None,
                        output_path=recovery_dir,
                        container_mgr=container_mgr,
                        container_handle=container_handle,
                    )
                except Exception:
                    logger.debug("Could not persist workspace state", exc_info=True)

            return LifecycleResult(exit_code=1)

        finally:
            ws_server.shutdown()
            if container_handle:
                with contextlib.suppress(Exception):
                    container_mgr.destroy(container_handle)
            for d in temp_dirs:
                with contextlib.suppress(Exception):
                    shutil.rmtree(d)
