from __future__ import annotations

import json
import os
import secrets
import socket
import sys
import threading
import time
from http import HTTPStatus
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from . import health, pages
from .actions import ActionError, ActionService
from .feedback import MAX_BODY as FEEDBACK_MAX_BODY
from .feedback import SCHEMA as FEEDBACK_SCHEMA
from .feedback import FeedbackSpool
from .reducer import Reducer

FEEDBACK_PATH = "/feedback"
FAILURE_PATH = "/v1/health/failure"


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

    def _cors(self) -> None:
        """Only the feedback route carries these.

        A generated report is often opened straight off disk as file://, whose
        Origin is null, and the handback must work from there. The action API
        deliberately gets the opposite treatment -- the hub's Caddy site
        refuses a cross-origin POST to /ops/* outright -- so these headers stay
        on the write-only sink and nowhere near a route that can change state.
        """
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _write_feedback(self, status: int, value: dict[str, Any]) -> None:
        body = json.dumps(value, sort_keys=True).encode() + b"\n"
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _spool_feedback(self) -> None:
        spool: FeedbackSpool | None = self.server.feedback  # type: ignore[attr-defined]
        if spool is None:
            self._write_feedback(
                HTTPStatus.NOT_FOUND, {"error": "no feedback spool configured"}
            )
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        if length < 0:
            self._write_feedback(
                HTTPStatus.LENGTH_REQUIRED, {"error": "Content-Length required"}
            )
            return
        if length > FEEDBACK_MAX_BODY:
            self._write_feedback(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"error": f"payload exceeds {FEEDBACK_MAX_BODY} bytes"},
            )
            return
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            self._write_feedback(HTTPStatus.BAD_REQUEST, {"error": f"invalid JSON: {error}"})
            return
        result = spool.append(
            payload,
            self.headers.get("Referer") or self.headers.get("X-Hub-Page"),
            self.headers.get("User-Agent"),
        )
        self._write_feedback(HTTPStatus.CREATED, {"schema": FEEDBACK_SCHEMA, **result})

    def _record_failure(self) -> None:
        """systemd's OnFailure hook, routed into the process that owns the
        dedup state so the fast path and the sweep cannot drift apart."""
        try:
            length = int(self.headers.get("Content-Length", "-1"))
            if length < 0 or length > 4096:
                raise ValueError("request body is missing or too large")
            request = json.loads(self.rfile.read(length))
            unit = str(request["unit"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            self._write(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        inventory, _ = pages.load_json(self.server.inventory_path)  # type: ignore[attr-defined]
        # A fresh emitter per event: emitted_keys is the prune's universe and
        # the fast path must never contribute to it.
        health.emit_failure(
            unit,
            str(request.get("result") or "unknown"),
            inventory or {},
            self.server.emitter_factory(),  # type: ignore[attr-defined]
        )
        self._write(HTTPStatus.CREATED, {"status": "recorded", "unit": unit})

    def do_OPTIONS(self) -> None:
        # application/json is not a CORS-simple content type, so every elicit
        # judgment is preflighted before it is posted.
        if self.path != FEEDBACK_PATH:
            self._write(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

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
        elif self.path == FEEDBACK_PATH:
            # Health only. There is deliberately no way to read the spool back.
            self._write_feedback(
                HTTPStatus.OK,
                {
                    "schema": FEEDBACK_SCHEMA,
                    "status": "ready",
                    "accepts": "POST application/json",
                },
            )
        elif self.path == "/v1/health":
            self._write(HTTPStatus.OK, self.reducer.health())
        elif self.path == "/v1/health/lanes":
            # The sweep's believed status per key, as the state file holds it:
            # what the sentinel's state file answered, from the process that
            # now owns it.
            self._write(
                HTTPStatus.OK,
                {
                    "schema": health.SCHEMA,
                    "ledger": str(health.ledger_path()),
                    "keys": health.current_state(
                        self.server.emitter_factory().state  # type: ignore[attr-defined]
                    ),
                },
            )
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
        if self.path == FEEDBACK_PATH:
            self._spool_feedback()
            return
        if self.path == FAILURE_PATH:
            self._record_failure()
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


def notify_systemd(message: str) -> None:
    """sd_notify without libsystemd: it is a datagram to $NOTIFY_SOCKET."""
    address = os.environ.get("NOTIFY_SOCKET")
    if not address:
        return
    if address.startswith("@"):  # abstract namespace
        address = "\0" + address[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.connect(address)
            sock.sendall(message.encode())
    except OSError:
        return


def watchdog_period() -> float:
    """Half of WatchdogSec, systemd's own recommended keepalive interval."""
    try:
        usec = int(os.environ.get("WATCHDOG_USEC", "0"))
    except ValueError:
        return 0.0
    return usec / 2_000_000 if usec > 0 else 0.0


def run_sweep(
    inventory_path: Path, emitter_factory: Callable[[], health.Emitter]
) -> None:
    """One health sweep, isolated: a broken probe or an unreadable inventory
    must not take the reducer's snapshot loop down with it."""
    try:
        inventory, _ = pages.load_json(inventory_path)
        if inventory:
            health.sweep(inventory, emitter_factory())
    except Exception as error:  # a sweep is advisory; the reducer is not
        print(f"sinnix-ops-reducer: health sweep failed: {error}", file=sys.stderr)


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
    feedback: FeedbackSpool | None = None,
    emitter_factory: Callable[[], health.Emitter] = health.Emitter,
    sweep_interval: float = health.SWEEP_INTERVAL_SECONDS,
) -> None:
    def stamp(server: ThreadingHTTPServer, is_unix: bool) -> None:
        server.reducer = reducer  # type: ignore[attr-defined]
        server.token = token  # type: ignore[attr-defined]
        server.is_unix = is_unix  # type: ignore[attr-defined]
        server.hub_manifest = hub_manifest  # type: ignore[attr-defined]
        server.inventory_path = inventory_path  # type: ignore[attr-defined]
        server.feedback = feedback  # type: ignore[attr-defined]
        server.emitter_factory = emitter_factory  # type: ignore[attr-defined]

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
    notify_systemd("READY=1")
    watchdog = watchdog_period()
    last_sweep = 0.0
    last_ping = 0.0
    try:
        while True:
            time.sleep(interval)
            reducer.refresh()
            # The health sweep is deliberately slower than the snapshot: it
            # shells out to df, systemctl and every lane's liveness probe, and
            # its confirm-2 debounce is defined in sweeps, so its cadence is
            # what "two agreeing samples" means in wall-clock terms.
            if time.monotonic() - last_sweep >= sweep_interval:
                last_sweep = time.monotonic()
                run_sweep(inventory_path, emitter_factory)
            # Pinged from the loop, not a timer thread: the point of the
            # watchdog is that a wedged refresh is noticed, and a keepalive on
            # its own thread would keep ticking through exactly that.
            if watchdog and time.monotonic() - last_ping >= watchdog:
                last_ping = time.monotonic()
                notify_systemd("WATCHDOG=1")
    finally:
        for server in servers:
            server.shutdown()
