"""The page routes as the hub actually reaches them: over the HTTP server.

These go through `Handler.do_GET`, not the renderer directly, because the
contract Caddy depends on is "GET /work/ over this socket answers with HTML" --
routing, content type, and the JSON API still owning /v1/*.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def hub_server(hub_server_factory, tmp_path: Path) -> str:
    inventory = tmp_path / "inventory.json"
    inventory.write_text(
        json.dumps({"schema": "sinnix-runtime-inventory-v1", "surfaces": {}})
    )
    return hub_server_factory(
        sources=lambda: {"systemd_units": []}, inventory_path=inventory
    )


@pytest.mark.parametrize(
    "route",
    ["/", "/work/", "/pressure/", "/services/", "/ai/", "/shaders/", "/capabilities/"],
)
def test_every_page_route_answers_with_a_document(
    hub_server: str, http_get, route: str
) -> None:
    status, content_type, body = http_get(hub_server + route)
    assert status == 200
    assert content_type.startswith("text/html")
    assert "<title>" in body and "</html>" in body


def test_slashless_alias_renders_the_same_page(hub_server: str, http_get) -> None:
    assert http_get(hub_server + "/work")[0] == 200


def test_the_json_api_is_untouched_by_the_page_routes(hub_server: str, http_get) -> None:
    status, content_type, body = http_get(hub_server + "/v1/health")
    assert status == 200
    assert content_type == "application/json"
    assert json.loads(body)["schema"] == "sinnix-ops-v1"


def test_revision_route_is_a_bounded_projection_of_snapshot(
    hub_server: str, http_get
) -> None:
    snapshot = json.loads(http_get(hub_server + "/v1/snapshot")[2])
    status, content_type, body = http_get(hub_server + "/v1/revision")

    assert status == 200
    assert content_type == "application/json"
    assert json.loads(body) == {
        key: snapshot.get(key)
        for key in ("schema", "sequence", "observed_at", "degradation", "sources")
    }
    assert "state" not in body


def test_an_unknown_path_answers_a_browser_in_html(hub_server: str, http_get) -> None:
    status, content_type, _ = http_get(hub_server + "/nope")
    assert status == 404
    assert content_type.startswith("text/html")
    assert http_get(hub_server + "/v1/nope")[1] == "application/json"
