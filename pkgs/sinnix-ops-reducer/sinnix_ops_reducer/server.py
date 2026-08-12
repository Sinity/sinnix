from __future__ import annotations

import json
import secrets
import socket
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .actions import ActionError, ActionService
from .reducer import Reducer


def ensure_token(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError:
        token = ""
    if not token:
        token = secrets.token_urlsafe(32)
        path.write_text(token + "\n", encoding="utf-8")
    path.chmod(0o600)
    return token


class Handler(BaseHTTPRequestHandler):
    server_version = "sinnix-ops/1"

    def _write(
        self, status: int, value: dict[str, Any], content_type: str = "application/json"
    ) -> None:
        body = json.dumps(value, sort_keys=True).encode() + b"\n"
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @property
    def reducer(self) -> Reducer:
        return self.server.reducer  # type: ignore[attr-defined]

    def _authorized(self) -> bool:
        if self.server.is_unix:  # type: ignore[attr-defined]
            return True
        if self.headers.get("Origin"):
            return False
        host = self.headers.get("Host", "")
        if not (host.startswith("127.0.0.1:") or host.startswith("localhost:")):
            return False
        return secrets.compare_digest(
            self.headers.get("Authorization", ""),
            f"Bearer {self.server.token}",  # type: ignore[attr-defined]
        )

    def do_GET(self) -> None:
        if not self._authorized():
            self._write(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        if self.path == "/v1/health":
            self._write(HTTPStatus.OK, self.reducer.health())
        elif self.path == "/v1/snapshot":
            try:
                value = json.loads(
                    self.reducer.snapshot_path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                value = self.reducer.health()
            self._write(HTTPStatus.OK, value)
        elif self.path == "/v1/events":
            last = self.headers.get("Last-Event-ID")
            try:
                sequence = int(last) if last is not None else None
            except ValueError:
                sequence = None
            events = self.reducer.events_since(sequence)
            body = b"".join(
                f"id: {event['sequence']}\ndata: {json.dumps(event, sort_keys=True)}\n\n".encode()
                for event in events
            )
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/v1/receipts":
            receipts = list(self.reducer.actions.receipts.values())[-20:]
            self._write(
                HTTPStatus.OK,
                {"schema": "sinnix-ops-receipts-v1", "receipts": receipts},
            )
        elif self.path.startswith("/v1/actions/"):
            key = self.path.removeprefix("/v1/actions/")
            receipt = self.reducer.actions.lookup(key)
            if receipt is None:
                self._write(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            else:
                self._write(HTTPStatus.OK, receipt)
        else:
            self._write(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:
        if not self._authorized():
            self._write(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        if self.path != "/v1/actions":
            self._write(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
            if length < 0 or length > 65536:
                raise ActionError("request body is missing or too large")
            value = json.loads(self.rfile.read(length))
            self._write(HTTPStatus.CREATED, self.reducer.actions.execute(value))
        except (json.JSONDecodeError, ActionError) as error:
            status = error.status if isinstance(error, ActionError) else 400
            self._write(status, {"error": str(error)})

    def log_message(self, *_args: object) -> None:
        return


class UnixServer(ThreadingHTTPServer):
    address_family = socket.AF_UNIX

    def server_bind(self) -> None:
        return


def serve(
    reducer: Reducer,
    token: str,
    fds: list[int],
    interval: float,
    actions: ActionService,
) -> None:
    reducer.refresh()
    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    http.reducer = reducer  # type: ignore[attr-defined]
    reducer.actions = actions  # type: ignore[attr-defined]
    http.token = token  # type: ignore[attr-defined]
    servers: list[ThreadingHTTPServer] = []
    if fds:
        for fd in fds:
            is_unix = len(servers) == 0
            sock = socket.fromfd(
                fd, socket.AF_UNIX if is_unix else socket.AF_INET, socket.SOCK_STREAM
            )
            if len(servers) == 0:
                unix = UnixServer("sinnix", Handler, bind_and_activate=False)
                unix.socket = sock
                unix.server_address = sock.getsockname()
                unix.reducer = reducer  # type: ignore[attr-defined]
                unix.token = token  # type: ignore[attr-defined]
                unix.is_unix = True  # type: ignore[attr-defined]
                servers.append(unix)
            else:
                inet = ThreadingHTTPServer(
                    ("127.0.0.1", 0), Handler, bind_and_activate=False
                )
                inet.socket = sock
                inet.server_address = sock.getsockname()
                inet.reducer = reducer  # type: ignore[attr-defined]
                inet.token = token  # type: ignore[attr-defined]
                inet.is_unix = False  # type: ignore[attr-defined]
                servers.append(inet)
        http.server_close()
    else:
        http.is_unix = False  # type: ignore[attr-defined]
        servers = [http]
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        while True:
            time.sleep(interval)
            reducer.refresh()
    finally:
        for server in servers:
            server.shutdown()
