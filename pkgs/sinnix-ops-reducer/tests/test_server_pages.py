"""The page routes as the hub actually reaches them: over the HTTP server.

These go through `Handler.do_GET`, not the renderer directly, because the
contract Caddy depends on is "GET /work/ over this socket answers with HTML" --
routing, content type, and the JSON API still owning /v1/*.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from sinnix_ops_reducer.reducer import Reducer
from sinnix_ops_reducer.server import Handler


@pytest.fixture
def hub_server(tmp_path: Path):
    reducer = Reducer(
        tmp_path / "status.json", tmp_path / "token", lambda: {"systemd_units": []}
    )
    reducer.refresh()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.reducer = reducer
    server.token = "fixture-token"
    # The unix-socket path: Caddy proxies the pages over the reducer's 0600
    # socket, which the reducer treats as authorized.
    server.is_unix = True
    server.hub_manifest = None
    server.inventory_path = tmp_path / "inventory.json"
    (tmp_path / "inventory.json").write_text(
        json.dumps({"schema": "sinnix-runtime-inventory-v1", "surfaces": {}})
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def get(url: str) -> tuple[int, str, str]:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status, response.headers["Content-Type"], response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.headers["Content-Type"], error.read().decode()


@pytest.mark.parametrize("route", ["/", "/work/", "/services/", "/ai/", "/shaders/"])
def test_every_page_route_answers_with_a_document(hub_server: str, route: str) -> None:
    status, content_type, body = get(hub_server + route)
    assert status == 200
    assert content_type.startswith("text/html")
    assert "<title>" in body and "</html>" in body


def test_slashless_alias_renders_the_same_page(hub_server: str) -> None:
    assert get(hub_server + "/work")[0] == 200


def test_the_json_api_is_untouched_by_the_page_routes(hub_server: str) -> None:
    status, content_type, body = get(hub_server + "/v1/health")
    assert status == 200
    assert content_type == "application/json"
    assert json.loads(body)["schema"] == "sinnix-ops-v1"


def test_an_unknown_path_answers_a_browser_in_html(hub_server: str) -> None:
    status, content_type, _ = get(hub_server + "/nope")
    assert status == 404
    assert content_type.startswith("text/html")
    assert get(hub_server + "/v1/nope")[1] == "application/json"
