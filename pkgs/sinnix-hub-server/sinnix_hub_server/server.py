from __future__ import annotations

import json
import secrets
import socket
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, wait
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from sinnix_lib.atomic import atomic_publish
from sinnix_lib.http import RequestBodyError, read_json_object
from sinnix_lib.lock import flock
from sinnix_lib.systemd import sd_notify, watchdog_period

from . import health, pages
from . import inventory as runtime_inventory
from .actions import ActionError, ActionService
from .feedback import MAX_BODY as FEEDBACK_MAX_BODY
from .feedback import SCHEMA as FEEDBACK_SCHEMA
from .feedback import FeedbackSpool
from .snapshot import SnapshotBuilder

FEEDBACK_PATH = "/feedback"
FAILURE_PATH = "/v1/health/failure"
BODY_LENGTH_ERRORS = frozenset(
    {
        "missing_content_length",
        "invalid_content_length",
        "negative_content_length",
        "conflicting_content_length",
    }
)


def ensure_token(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    def existing_token() -> str:
        try:
            token = path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return ""
        if token:
            path.chmod(0o600)
        return token

    if token := existing_token():
        return token
    # Keep the lock inode: concurrent starters must agree on an empty-file repair.
    with flock(path.with_name(path.name + ".lock")):
        if token := existing_token():
            return token
        candidate = secrets.token_urlsafe(32)
        payload = (candidate + "\n").encode()
        if atomic_publish(path, payload, fsync=True, mode=0o600, exclusive=True):
            return candidate
        if token := existing_token():
            return token
        atomic_publish(path, payload, fsync=True, mode=0o600)
        return candidate


class Handler(BaseHTTPRequestHandler):
    server_version = "sinnix-hub/1"

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
        """Only /feedback carries these.

        A generated report (and a ranking session page, which is one)
        is often opened straight off disk as file://, whose Origin is null,
        and the handback must work from there. The action API deliberately
        gets the opposite treatment -- the hub's Caddy site refuses a
        cross-origin POST to /ops/* outright -- so these headers stay off
        every route that can change state.
        """
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
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
            payload = read_json_object(
                self.headers, self.rfile, max_bytes=FEEDBACK_MAX_BODY
            )
        except RequestBodyError as error:
            if error.reason in BODY_LENGTH_ERRORS:
                self._write_feedback(
                    HTTPStatus.LENGTH_REQUIRED, {"error": "Content-Length required"}
                )
                return
            if error.reason == "body_too_large":
                self._write_feedback(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    {"error": f"payload exceeds {FEEDBACK_MAX_BODY} bytes"},
                )
                return
            self._write_feedback(
                HTTPStatus.BAD_REQUEST, {"error": f"invalid JSON: {error}"}
            )
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
            request = read_json_object(self.headers, self.rfile, max_bytes=4096)
        except RequestBodyError as error:
            message = (
                "request body is missing or too large"
                if error.reason in BODY_LENGTH_ERRORS
                or error.reason == "body_too_large"
                else str(error)
            )
            self._write(HTTPStatus.BAD_REQUEST, {"error": message})
            return
        try:
            unit = str(request["unit"])
        except (KeyError, TypeError, ValueError) as error:
            self._write(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        inventory, _ = pages.load_json(self.server.inventory_path)  # type: ignore[attr-defined]
        # A fresh emitter per event: emitted_keys is the prune's universe and
        # the fast path must never contribute to it.
        try:
            manager = request.get("manager")
            if manager is not None:
                manager = health.validated_manager(manager)
        except ValueError as error:
            self._write(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        health.emit_failure(
            unit,
            str(request.get("result") or "unknown"),
            inventory or {},
            self.server.emitter_factory(),  # type: ignore[attr-defined]
            manager=manager,
        )
        self._write(HTTPStatus.CREATED, {"status": "recorded", "unit": unit})

    def do_OPTIONS(self) -> None:
        # application/json is not a CORS-simple content type, so every ranking
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
    def builder(self) -> SnapshotBuilder:
        return self.server.builder  # type: ignore[attr-defined]

    def _serve_page(self, path: str) -> None:
        """One hub page, rendered from the live snapshot at request time.

        The snapshot is this process's own, not a file re-read: a page shows
        what the hub server currently believes, which is the whole reason the
        pages moved here from a timer.
        """
        requested = {
            "/": ("storage", "drift"),
            "/work/": ("workloads", "ingestion", "slices"),
        }.get(pages.canonical(path), ())
        snapshot = self.builder.page_snapshot(requested)
        error = None
        if not snapshot:
            snapshot = None
            error = "the hub server has not published a snapshot yet"
        manifest = pages.load_manifest(self.server.hub_manifest)  # type: ignore[attr-defined]
        inventory, _ = pages.load_json(self.server.inventory_path)  # type: ignore[attr-defined]
        self._write_html(
            HTTPStatus.OK,
            pages.render(
                path,
                manifest,
                snapshot,
                inventory,
                error,
            ),
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
        parts = urlsplit(self.path)
        route = parts.path
        query = parse_qs(parts.query)
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
        elif route.startswith("/v1/observe/"):
            try:
                self._write(
                    HTTPStatus.OK,
                    self.builder.observe(route.removeprefix("/v1/observe/")),
                )
            except ValueError as error:
                self._write(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            except Exception as error:
                self._write(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(error)[:240]})
        elif self.path == "/v1/health":
            self._write(HTTPStatus.OK, self.builder.health())
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
        elif route == "/v1/snapshot":
            try:
                value = json.loads(
                    self.builder.snapshot_path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                value = self.builder.health()
            # `?state=a,b` keeps only the named state keys. The Noctalia bridge
            # decodes the body inside a 25 ms Luau callback budget; the full
            # snapshot (runtime inventory, every unit, every workload row)
            # blows that budget, and the panel reads a handful of keys.
            wanted = [
                key for raw in query.get("state", []) for key in raw.split(",") if key
            ]
            if wanted and isinstance(value.get("state"), dict):
                state = value["state"]
                value = {
                    **value,
                    "state": {key: state[key] for key in wanted if key in state},
                }
            self._write(HTTPStatus.OK, value)
        elif self.path == "/v1/revision":
            try:
                snapshot = json.loads(
                    self.builder.snapshot_path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                snapshot = self.builder.health()
            self._write(
                HTTPStatus.OK,
                {
                    key: snapshot.get(key)
                    for key in (
                        "schema",
                        "sequence",
                        "observed_at",
                        "degradation",
                        "sources",
                    )
                },
            )
        elif self.path == "/v1/events":
            last = self.headers.get("Last-Event-ID")
            try:
                sequence = int(last) if last is not None else None
            except ValueError:
                sequence = None
            events = self.builder.events_since(sequence)
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
        elif route == "/v1/receipts":
            try:
                limit = int(query.get("limit", ["20"])[0])
            except ValueError:
                limit = 20
            limit = max(1, min(limit, 20))
            receipts = list(self.builder.actions.receipts.values())[-limit:]
            self._write(
                HTTPStatus.OK,
                {"schema": "sinnix-hub-receipts-v1", "receipts": receipts},
            )
        elif route.startswith("/v1/actions/"):
            key = unquote(route.removeprefix("/v1/actions/"))
            receipt = self.builder.actions.lookup(key)
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
                '<p>No such page. <a href="/">Back to the dashboard.</a></p>\n',
            )

    def do_POST(self) -> None:
        if not self._authorized():
            self._write(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        json_route = self.path in {
            FEEDBACK_PATH,
            FAILURE_PATH,
            "/v1/actions",
            "/v1/actions/prepare",
        }
        if json_route:
            content_types = self.headers.get_all("Content-Type", [])
            if len(content_types) != 1 or (
                content_types[0].split(";", 1)[0].strip().casefold()
                != "application/json"
            ):
                # Refuse before consuming a body or invoking its owner. Closing
                # also prevents unread body bytes becoming another request.
                self.close_connection = True
                writer = (
                    self._write_feedback if self.path == FEEDBACK_PATH else self._write
                )
                writer(
                    HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                    {"error": "one application/json Content-Type is required"},
                )
                return
        if self.path == FEEDBACK_PATH:
            self._spool_feedback()
            return
        if self.path == FAILURE_PATH:
            self._record_failure()
            return
        if self.path not in {"/v1/actions", "/v1/actions/prepare"}:
            self._write(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            value = read_json_object(self.headers, self.rfile, max_bytes=65536)
            if self.path == "/v1/actions/prepare":
                self._write(HTTPStatus.OK, self.builder.actions.prepare(value))
            else:
                self._write(HTTPStatus.CREATED, self.builder.actions.execute(value))
        except RequestBodyError as error:
            if error.reason in BODY_LENGTH_ERRORS or error.reason == "body_too_large":
                error = ActionError("request body is missing or too large")
            self._write(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except ValueError as error:
            status = error.status if isinstance(error, ActionError) else 400
            self._write(status, {"error": str(error)})

    def log_message(self, *_args: object) -> None:
        return


def run_sweep(
    inventory_path: Path, emitter_factory: Callable[[], health.Emitter]
) -> None:
    """One health sweep, isolated: a broken probe or an unreadable inventory
    must not take the hub server's snapshot loop down with it."""
    try:
        runtime, _ = runtime_inventory.load(inventory_path)
        if runtime:
            health.sweep(runtime, emitter_factory())
    except Exception as error:  # a sweep is advisory; the hub server is not
        print(f"sinnix-hub-server: health sweep failed: {error}", file=sys.stderr)


class UnixServer(ThreadingHTTPServer):
    address_family = socket.AF_UNIX

    def server_bind(self) -> None:
        return


def serve(
    builder: SnapshotBuilder,
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
        server.builder = builder  # type: ignore[attr-defined]
        server.token = token  # type: ignore[attr-defined]
        server.is_unix = is_unix  # type: ignore[attr-defined]
        server.hub_manifest = hub_manifest  # type: ignore[attr-defined]
        server.inventory_path = inventory_path  # type: ignore[attr-defined]
        server.feedback = feedback  # type: ignore[attr-defined]
        server.emitter_factory = emitter_factory  # type: ignore[attr-defined]

    watchdog = watchdog_period()
    last_ping = 0.0
    worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ops-refresh")

    def await_work(work: Callable[[], Any]) -> None:
        nonlocal last_ping
        pending = worker.submit(work)
        while True:
            completed, _ = wait((pending,), timeout=watchdog or None)
            # The main loop supervises completion and reports liveness.
            # Filesystem stalls must not become watchdog-triggered crashes.
            if watchdog and time.monotonic() - last_ping >= watchdog:
                last_ping = time.monotonic()
                sd_notify("WATCHDOG=1")
            if completed:
                pending.result()  # Worker errors still fail the service.
                return

    try:
        await_work(builder.refresh)
    except BaseException:
        worker.shutdown(wait=False, cancel_futures=True)
        raise
    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    builder.actions = actions  # type: ignore[attr-defined]
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
    sd_notify("READY=1")
    last_sweep = 0.0

    def refresh_and_sweep() -> None:
        nonlocal last_sweep
        time.sleep(interval)
        builder.refresh()
        # Preserve serial refreshes and the slower health-sweep cadence.
        if time.monotonic() - last_sweep >= sweep_interval:
            last_sweep = time.monotonic()
            run_sweep(inventory_path, emitter_factory)

    try:
        while True:
            await_work(refresh_and_sweep)
    finally:
        worker.shutdown(wait=False, cancel_futures=True)
        for server in servers:
            server.shutdown()
            server.server_close()
