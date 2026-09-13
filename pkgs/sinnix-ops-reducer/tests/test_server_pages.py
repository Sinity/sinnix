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


def test_the_json_api_is_untouched_by_the_page_routes(
    hub_server: str, http_get
) -> None:
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


def test_snapshot_state_query_projects_the_named_keys(
    hub_server: str, http_get
) -> None:
    full = json.loads(http_get(hub_server + "/v1/snapshot")[2])
    assert "systemd_units" in full["state"]

    status, _, body = http_get(hub_server + "/v1/snapshot?state=systemd_units,absent")
    projected = json.loads(body)

    assert status == 200
    assert projected["state"] == {"systemd_units": full["state"]["systemd_units"]}
    assert {k: v for k, v in projected.items() if k != "state"} == {
        k: v for k, v in full.items() if k != "state"
    }


def test_snapshot_without_query_is_unprojected(hub_server: str, http_get) -> None:
    body = http_get(hub_server + "/v1/snapshot")[2]
    assert "systemd_units" in json.loads(body)["state"]


def test_prepare_and_execute_share_the_http_target_contract(
    hub_server_factory, tmp_path
):
    import urllib.error
    import urllib.request
    from urllib.parse import quote

    from sinnix_ops_reducer.actions import ActionService

    inventory = tmp_path / "inventory.json"
    inventory.write_text(
        json.dumps(
            {
                "schema": "sinnix-runtime-inventory-v1",
                "surfaces": {
                    "fixture": {
                        "unit": "fixture.service",
                        "manager": "user",
                        "observe": {"restartable": True},
                    }
                },
            }
        )
    )
    live = {
        "LoadState": "loaded",
        "ActiveState": "active",
        "SubState": "running",
        "InvocationID": "first",
    }
    calls = []
    actions = ActionService(
        lambda: {"sequence": 999},
        inventory,
        tmp_path / "receipts.json",
        adapter=lambda *_: calls.append("restart") or {},
        unit_state_prober=lambda *_: live,
    )
    url = hub_server_factory(inventory_path=inventory, actions=actions)

    def post(route, payload):
        request = urllib.request.Request(
            url + route,
            json.dumps(payload).encode(),
            {"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    status, prepared = post(
        "/v1/actions/prepare",
        {"action": "restart", "target": {"unit": "fixture"}, "parameters": {}},
    )
    assert status == 200
    assert prepared["expected_target"]["properties"]["InvocationID"] == "first"
    prepared.pop("observed_at")
    request = prepared | {
        "idempotency_key": "http / # %2F",
        "operator_reason": "fixture",
    }
    assert post("/v1/actions", request)[0] == 201
    with urllib.request.urlopen(
        url + "/v1/actions/" + quote(request["idempotency_key"], safe="")
    ) as response:
        assert json.load(response)["idempotency_key"] == request["idempotency_key"]
    live["InvocationID"] = "second"
    assert post("/v1/actions", request)[0] == 201
    request["idempotency_key"] = "http-stale"
    assert post("/v1/actions", request)[0] == 409
    assert post("/v1/actions", request)[0] == 409
    assert calls == ["restart"]
