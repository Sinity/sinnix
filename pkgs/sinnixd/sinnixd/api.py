from __future__ import annotations

import json
import socket
import struct
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any

from sinnix_mcp import RequestEnvelope

from .service import SinnixdService

MAX_FRAME_BYTES = 1_048_576
CONNECTION_TIMEOUT_SECONDS = 5.0
ACCEPT_POLL_SECONDS = 0.1


class ProtocolError(ValueError):
    """Raised when a Unix-socket RPC frame is malformed or exceeds its bound."""


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


@dataclass
class UnixSocketServer:
    socket_path: Path
    service: SinnixdService
    connection_timeout_seconds: float = CONNECTION_TIMEOUT_SECONDS

    def serve_once(self) -> None:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            self._bind(listener)
            try:
                self._serve_connection(listener)
            finally:
                self.socket_path.unlink(missing_ok=True)

    def serve_forever(self, stop_event: Event | None = None) -> None:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            self._bind(listener)
            listener.settimeout(ACCEPT_POLL_SECONDS)
            try:
                while stop_event is None or not stop_event.is_set():
                    try:
                        self._serve_connection(listener)
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

    def _serve_connection(self, listener: socket.socket) -> None:
        connection, _address = listener.accept()
        with connection:
            connection.settimeout(self.connection_timeout_seconds)
            request_id: Any = None
            try:
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
                response = self.service.dispatch(request)
                send_frame(
                    connection,
                    {"jsonrpc": "2.0", "id": request_id, "result": response.to_dict()},
                )
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


def call(socket_path: Path, request: RequestEnvelope) -> dict[str, Any]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
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
        response = receive_frame(connection)
    if response.get("jsonrpc") != "2.0" or response.get("id") != request.request_id:
        raise ProtocolError("response does not match the request")
    result = response.get("result")
    if not isinstance(result, dict):
        raise ProtocolError("response requires an object result")
    return result
