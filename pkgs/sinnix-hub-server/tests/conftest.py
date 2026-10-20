"""A hub listener on a loopback port, stamped the way `server.serve` stamps it.

Every path defaults to an absent name under `tmp_path`, so a route that reads
a declarative source sees "not there" -- which is every hermetic build -- and
no test can reach a real host file. `emitter_factory` is deliberately unset:
its production default probes live systemd, and a suite that needs the health
route supplies its own.
"""

from __future__ import annotations

import threading
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from sinnix_hub_server.feedback import FeedbackSpool
from sinnix_hub_server.server import Handler
from sinnix_runtime.snapshot import SnapshotBuilder


@pytest.fixture
def hub_server_factory(tmp_path: Path) -> Iterator[Callable[..., str]]:
    servers: list[ThreadingHTTPServer] = []

    def start(
        *,
        sources: Callable[[], dict[str, Any]] = dict,
        inventory_path: Path | None = None,
        hub_manifest: Path | None = None,
        feedback: FeedbackSpool | None = None,
        actions: Any = None,
    ) -> str:
        builder = SnapshotBuilder(tmp_path / "status.json", tmp_path / "token", sources)
        builder.refresh()
        builder.actions = actions
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.builder = builder
        server.token = "fixture-token"
        # The unix-socket path: Caddy proxies the pages over the hub server's
        # 0600 socket, which the hub server treats as authorized.
        server.is_unix = True
        server.hub_manifest = hub_manifest
        server.inventory_path = inventory_path or tmp_path / "missing-inventory.json"
        server.feedback = feedback
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{server.server_address[1]}"

    try:
        yield start
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()


def get(url: str) -> tuple[int, str, str]:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return (
                response.status,
                response.headers["Content-Type"],
                response.read().decode(),
            )
    except urllib.error.HTTPError as error:
        return error.code, error.headers["Content-Type"], error.read().decode()


@pytest.fixture
def http_get() -> Callable[[str], tuple[int, str, str]]:
    return get
