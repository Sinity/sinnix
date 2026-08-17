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

from . import pages
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

    def _write_html(self, status: int, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    @property
    def reducer(self) -> Reducer:
        return self.server.reducer  # type: ignore[attr-defined]

    def _serve_page(self, path: str) -> None:
        """One hub page, rendered from the live snapshot at request time.

        The snapshot is this process's own, not a file re-read: a page shows
        what the reducer currently believes, which is the whole reason the
        pages moved here from a timer.
        """
        snapshot = self.reducer.snapshot()
        error = None
        if not snapshot:
            snapshot = None
            error = "the reducer has not published a snapshot yet"
        manifest = pages.load_manifest(self.server.hub_manifest)  # type: ignore[attr-defined]
        inventory, _ = pages.load_json(self.server.inventory_path)  # type: ignore[attr-defined]
        self._write_html(
            HTTPStatus.OK, pages.render(path, manifest, snapshot, inventory, error)
        )

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
        if pages.is_page_route(self.path):
            self._serve_page(self.path)
        elif self.path == "/v1/health":
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
        elif self.path.startswith("/v1/"):
            self._write(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        else:
            # Everything that is not the JSON API is a browser asking for a
            # page that does not exist; answer in the language it asked in.
            self._write_html(
                HTTPStatus.NOT_FOUND,
                "<!doctype html><title>not found</title>"
                "<p>No such page. <a href=\"/\">Back to the estate.</a></p>\n",
            )

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
    hub_manifest: Path | None = None,
    inventory_path: Path = Path("/etc/sinnix/runtime-inventory.json"),
) -> None:
    def stamp(server: ThreadingHTTPServer, is_unix: bool) -> None:
        server.reducer = reducer  # type: ignore[attr-defined]
        server.token = token  # type: ignore[attr-defined]
        server.is_unix = is_unix  # type: ignore[attr-defined]
        server.hub_manifest = hub_manifest  # type: ignore[attr-defined]
        server.inventory_path = inventory_path  # type: ignore[attr-defined]

    reducer.refresh()
    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    reducer.actions = actions  # type: ignore[attr-defined]
    stamp(http, False)
    servers: list[ThreadingHTTPServer] = []
    if fds:
        for fd in fds:
            is_unix = len(servers) == 0
            sock = socket.fromfd(
                fd, socket.AF_UNIX if is_unix else socket.AF_INET, socket.SOCK_STREAM
            )
            if is_unix:
                unix = UnixServer("sinnix", Handler, bind_and_activate=False)
                unix.socket = sock
                unix.server_address = sock.getsockname()
                stamp(unix, True)
                servers.append(unix)
            else:
                inet = ThreadingHTTPServer(
                    ("127.0.0.1", 0), Handler, bind_and_activate=False
                )
                inet.socket = sock
                inet.server_address = sock.getsockname()
                stamp(inet, False)
                servers.append(inet)
        http.server_close()
    else:
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
