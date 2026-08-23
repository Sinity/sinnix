from __future__ import annotations

import json
import socket
import struct
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import BoundedSemaphore, Event
from typing import Any, Callable

from sinnix_mcp import RequestEnvelope, ResponseEnvelope, response_envelope_from_dict

from .jobs import DEFAULT_WAIT_SECONDS, MAX_WAIT_SECONDS
from .service import SinnixdService

MAX_FRAME_BYTES = 1_048_576
CONNECTION_TIMEOUT_SECONDS = 5.0
WAIT_TRANSPORT_MARGIN_SECONDS = 5.0
ACCEPT_POLL_SECONDS = 0.1
RESERVED_CONTROL_WORKERS = 2


class ProtocolError(ValueError):
    """Raised when a Unix-socket RPC frame is malformed or exceeds its bound."""


class SinnixdClientError(ValueError):
    """The canonical client could not obtain a valid daemon response."""


def _read_exact(connection: socket.socket, length: int) -> bytes:
    chunks: list[bytes] = []
    remaining = length
    while remaining:
        chunk = connection.recv(remaining)
        if not chunk:
            raise ConnectionError("socket closed before a complete frame arrived")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def receive_frame(connection: socket.socket) -> dict[str, Any]:
    length = struct.unpack("!I", _read_exact(connection, 4))[0]
    if not length or length > MAX_FRAME_BYTES:
        raise ProtocolError(f"invalid frame length: {length}")
    try:
        value = json.loads(_read_exact(connection, length))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ProtocolError(f"invalid JSON frame: {error}") from error
    if not isinstance(value, dict):
        raise ProtocolError("request frame must be an object")
    return value


def send_frame(connection: socket.socket, value: dict[str, Any]) -> None:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    if len(payload) > MAX_FRAME_BYTES:
        raise ProtocolError("response frame exceeds its bound")
    connection.sendall(struct.pack("!I", len(payload)) + payload)


def _response_timeout_seconds(request: RequestEnvelope) -> float:
    if request.operation != "job.wait":
        return CONNECTION_TIMEOUT_SECONDS
    timeout_seconds = request.arguments.get("timeout_seconds", DEFAULT_WAIT_SECONDS)
    if (
        not isinstance(timeout_seconds, int)
        or isinstance(timeout_seconds, bool)
        or not 1 <= timeout_seconds <= MAX_WAIT_SECONDS
    ):
        return CONNECTION_TIMEOUT_SECONDS
    return timeout_seconds + WAIT_TRANSPORT_MARGIN_SECONDS


@dataclass
class UnixSocketServer:
    socket_path: Path
    service: SinnixdService
    connection_timeout_seconds: float = CONNECTION_TIMEOUT_SECONDS
    max_workers: int = 8
    ready_event: Event | None = None

    @property
    def wait_worker_count(self) -> int:
        if self.max_workers <= RESERVED_CONTROL_WORKERS:
            raise ValueError(f"max_workers must exceed {RESERVED_CONTROL_WORKERS}")
        return self.max_workers - RESERVED_CONTROL_WORKERS

    def serve_once(self) -> None:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            self._bind(listener)
            try:
                with ThreadPoolExecutor(max_workers=1, thread_name_prefix="sinnixd-rpc") as executor:
                    self._accept_connection(listener, executor, BoundedSemaphore(1))
            finally:
                self.socket_path.unlink(missing_ok=True)

    def serve_forever(self, stop_event: Event | None = None) -> None:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            self._bind(listener)
            listener.settimeout(ACCEPT_POLL_SECONDS)
            try:
                with (
                    ThreadPoolExecutor(
                        max_workers=RESERVED_CONTROL_WORKERS,
                        thread_name_prefix="sinnixd-control",
                    ) as control_executor,
                    ThreadPoolExecutor(
                        max_workers=self.wait_worker_count,
                        thread_name_prefix="sinnixd-wait",
                    ) as wait_executor,
                ):
                    control_permits = BoundedSemaphore(RESERVED_CONTROL_WORKERS)
                    wait_permits = BoundedSemaphore(self.wait_worker_count)
                    while stop_event is None or not stop_event.is_set():
                        try:
                            self._accept_connection(
                                listener,
                                control_executor,
                                control_permits,
                                wait_executor,
                                wait_permits,
                            )
                        except socket.timeout:
                            continue
            finally:
                self.socket_path.unlink(missing_ok=True)

    def _bind(self, listener: socket.socket) -> None:
        self.socket_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.socket_path.unlink(missing_ok=True)
        listener.bind(str(self.socket_path))
        self.socket_path.chmod(0o600)
        listener.listen()
        if self.ready_event is not None:
            self.ready_event.set()

    def _accept_connection(
        self,
        listener: socket.socket,
        executor: ThreadPoolExecutor,
        permits: BoundedSemaphore,
        wait_executor: ThreadPoolExecutor | None = None,
        wait_permits: BoundedSemaphore | None = None,
    ) -> None:
        if not permits.acquire(timeout=ACCEPT_POLL_SECONDS):
            return
        try:
            connection, _address = listener.accept()
        except OSError:
            permits.release()
            raise
        executor.submit(self._serve_connection, connection, permits, wait_executor, wait_permits)

    def _serve_connection(
        self,
        connection: socket.socket,
        permits: BoundedSemaphore,
        wait_executor: ThreadPoolExecutor | None = None,
        wait_permits: BoundedSemaphore | None = None,
    ) -> None:
        handed_off = False
        request_id: Any = None
        try:
            connection.settimeout(self.connection_timeout_seconds)
            raw = receive_frame(connection)
            request_id = raw.get("id")
            if raw.get("jsonrpc") != "2.0" or raw.get("method") != "dispatch":
                raise ProtocolError("request must be a JSON-RPC 2.0 dispatch call")
            params = raw.get("params")
            if not isinstance(request_id, str) or not isinstance(params, dict):
                raise ProtocolError("request requires string id and object params")
            request = RequestEnvelope(**params)
            if request.request_id != request_id:
                raise ProtocolError("JSON-RPC id must equal envelope request_id")
            if request.operation == "job.wait" and wait_executor is not None and wait_permits is not None:
                if not wait_permits.acquire(blocking=False):
                    raise ProtocolError("job.wait capacity is exhausted")
                connection.settimeout(_response_timeout_seconds(request))
                wait_executor.submit(self._serve_wait_connection, connection, request_id, request, wait_permits)
                handed_off = True
            else:
                self._send_response(connection, request_id, request)
        except (ConnectionError, OSError, ProtocolError, TypeError, ValueError) as error:
            try:
                send_frame(
                    connection,
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32600, "message": str(error)},
                    },
                )
            except OSError:
                pass
        finally:
            permits.release()
            if not handed_off:
                connection.close()

    def _serve_wait_connection(
        self,
        connection: socket.socket,
        request_id: str,
        request: RequestEnvelope,
        permits: BoundedSemaphore,
    ) -> None:
        try:
            self._send_response(connection, request_id, request)
        except OSError:
            pass
        finally:
            connection.close()
            permits.release()

    def _send_response(self, connection: socket.socket, request_id: str, request: RequestEnvelope) -> None:
        response = self.service.dispatch(request)
        send_frame(
            connection,
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": response.to_dict(),
            },
        )


def call(socket_path: Path, request: RequestEnvelope) -> dict[str, Any]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(CONNECTION_TIMEOUT_SECONDS)
        connection.connect(str(socket_path))
        send_frame(
            connection,
            {
                "jsonrpc": "2.0",
                "id": request.request_id,
                "method": "dispatch",
                "params": request.to_dict(),
            },
        )
        connection.settimeout(_response_timeout_seconds(request))
        response = receive_frame(connection)
    if response.get("jsonrpc") != "2.0" or response.get("id") != request.request_id:
        raise ProtocolError("response does not match the request")
    result = response.get("result")
    if not isinstance(result, dict):
        raise ProtocolError("response requires an object result")
    return result


@dataclass(frozen=True)
class SinnixdClient:
    """Typed client for the daemon's bounded local request/response contract."""

    socket_path: Path
    transport: Callable[[Path, RequestEnvelope], dict[str, Any]] = call

    def dispatch(self, request: RequestEnvelope) -> ResponseEnvelope:
        try:
            raw = self.transport(self.socket_path, request)
        except (OSError, ProtocolError) as error:
            raise SinnixdClientError("sinnixd is unavailable") from error
        try:
            response = response_envelope_from_dict(raw)
        except ValueError as error:
            raise SinnixdClientError("sinnixd returned an invalid response") from error
        if (
            response.request_id != request.request_id
            or response.correlation_id != request.correlation_id
        ):
            raise SinnixdClientError("sinnixd response does not match the request")
        return response
