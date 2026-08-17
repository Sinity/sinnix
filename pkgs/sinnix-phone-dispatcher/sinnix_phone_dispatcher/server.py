"""The live plane: the Unix-socket HTTP API, the `serve` command that starts
it alongside the phone-stream receiver, and the sd_notify/watchdog wiring
systemd's Type=simple + NotifyAccess=main + WatchdogSec expects (same
mechanism as sinnix-ops-reducer's server.py -- no libsystemd, a datagram to
$NOTIFY_SOCKET)."""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import socketserver
import sys
import threading
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from .execute import execute
from .glance import build_glance, build_jobs, build_steering
from .receiver import start_phone_stream_server
from .state import MAX_BODY, MAX_UPLOAD, ensure_dirs, now_iso
from .uploads import store_upload


class Handler(BaseHTTPRequestHandler):
    server_version = "sinnix-phone-dispatcher/1"

    def log_message(self, fmt: str, *fmt_args: Any) -> None:
        # journald already stamps and routes; a second timestamp per request
        # would double the volume of the least interesting log on the host.
        sys.stderr.write("phone-dispatcher: " + (fmt % fmt_args) + "\n")

    def _send(self, status: HTTPStatus, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _route(self) -> str:
        """The path with the API version stripped.

        The hub mounts this behind `handle_path /phone/*`, which removes the
        mount prefix and leaves `/v1/ping`. Stripping the version here rather
        than mounting differently keeps the client's URL honest -- the phone
        asks for /phone/v1/ping, which is what it is -- and matches how the ops
        reducer sits behind the same kind of route.
        """
        route = self.path.split("?", 1)[0].rstrip("/") or "/"
        for prefix in ("/phone/v1", "/v1"):
            if route == prefix:
                return "/"
            if route.startswith(prefix + "/"):
                return route[len(prefix) :]
        return route

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's contract
        route = self._route()
        if route in ("/ping", "/"):
            self._send(HTTPStatus.OK, {"ok": True, "at": now_iso()})
        elif route == "/glance":
            self._send(HTTPStatus.OK, build_glance())
        elif route == "/steering":
            self._send(HTTPStatus.OK, build_steering())
        elif route == "/jobs":
            self._send(HTTPStatus.OK, build_jobs())
        else:
            self._send(HTTPStatus.NOT_FOUND, {"ok": False, "detail": "no such route"})

    def _query(self) -> dict[str, str]:
        _, _, raw = self.path.partition("?")
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw).items() if v}

    def do_POST(self) -> None:  # noqa: N802
        route = self._route()
        length = int(self.headers.get("Content-Length") or 0)

        # Uploads are raw bytes, so they branch before the JSON parse below --
        # and before MAX_BODY, which sizes an intent, not an archive file.
        if route == "/chunk":
            if length > MAX_UPLOAD:
                self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"ok": False, "bytes": length})
                return
            query = self._query()
            status, payload = store_upload(
                query.get("lane", "ambient"),
                query.get("name", ""),
                self.rfile.read(length),
                self.headers.get("X-Sinnix-Sha256"),
            )
            self._send(status, payload)
            return

        if length > MAX_BODY:
            self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"ok": False})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8", "replace"))
        except (ValueError, json.JSONDecodeError):
            self._send(HTTPStatus.BAD_REQUEST, {"ok": False, "detail": "not JSON"})
            return
        if not isinstance(payload, dict):
            self._send(HTTPStatus.BAD_REQUEST, {"ok": False, "detail": "expected an object"})
            return

        if route == "/intent":
            self._send(HTTPStatus.OK, execute(payload))
        elif route == "/job-answer":
            payload.setdefault("kind", "job_answer")
            self._send(HTTPStatus.OK, execute(payload))
        else:
            self._send(HTTPStatus.NOT_FOUND, {"ok": False, "detail": "no such route"})


class UnixHTTPServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True

    def get_request(self) -> tuple[Any, tuple[str, int]]:
        request, _ = super().get_request()
        # BaseHTTPRequestHandler wants a (host, port) client address and a Unix
        # socket has neither. Anything hashable does; this is the honest label.
        return request, ("unix", 0)


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


def cmd_serve(args: argparse.Namespace) -> int:
    ensure_dirs()
    sock_path = Path(args.socket)
    sock_path.parent.mkdir(parents=True, exist_ok=True)
    if sock_path.exists():
        sock_path.unlink()
    server = UnixHTTPServer(str(sock_path), Handler)
    # 0600: the hub's Caddy runs in the same user manager, and nothing else on
    # this machine has business executing the phone's intents.
    os.chmod(sock_path, 0o600)

    # The always-on telemetry receiver, absorbed from the retired
    # sinnix-phone-receiver unit. Optional at the CLI level (a host/dev run
    # without a resolved tailscale0 address can still serve the live JSON
    # API), but the systemd unit always passes all three.
    phone_stream_server = None
    if args.phone_stream_host and args.phone_stream_port and args.capture_root:
        phone_stream_server = start_phone_stream_server(
            args.phone_stream_host, args.phone_stream_port, Path(args.capture_root)
        )
    else:
        print(
            "phone-dispatcher: phone-stream: no --phone-stream-host/--phone-stream-port/"
            "--capture-root given, the always-on telemetry receiver is disabled",
            file=sys.stderr,
        )

    # serve_forever() runs on its own thread so the main thread is free to be
    # the sd_notify/watchdog loop below -- calling server.shutdown() from the
    # thread that is itself inside serve_forever() would deadlock, which is
    # why the retired script-era version spawned a one-shot thread per signal
    # instead; one long-lived server thread plus a main-thread loop is the
    # same shape sinnix-ops-reducer's serve() uses.
    shutdown_event = threading.Event()

    def request_shutdown(_signum: int, _frame: Any) -> None:
        shutdown_event.set()

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)

    server_thread = threading.Thread(target=server.serve_forever, daemon=True, name="phone-http")
    server_thread.start()
    print(f"serving on {sock_path}", file=sys.stderr)

    notify_systemd("READY=1")
    watchdog = watchdog_period()
    try:
        while not shutdown_event.is_set():
            # Pinged from this loop, not a timer thread: the point of the
            # watchdog is that a wedged process is noticed, and a keepalive
            # ticking on its own thread regardless of what else is happening
            # would defeat that.
            shutdown_event.wait(timeout=watchdog if watchdog else 5.0)
            if watchdog and not shutdown_event.is_set():
                notify_systemd("WATCHDOG=1")
    finally:
        server.shutdown()
        server_thread.join()
        server.server_close()
        sock_path.unlink(missing_ok=True)
        if phone_stream_server is not None:
            phone_stream_server.shutdown()
            phone_stream_server.server_close()
    return 0
