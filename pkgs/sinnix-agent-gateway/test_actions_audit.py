"""Typed audit, results and capability index actions."""

from __future__ import annotations

from pathlib import Path

from sinnix_agent_gateway.actions import audit
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.runtime import Runtime
from test_actions_machine import call
from test_capability_index import index_path

BY_NAME = {action.name: action for action in audit.ACTIONS}
ROWS = [
    {
        "kind": "script",
        "name": "sinnix-observe",
        "description": "Inspect machine state",
        "enabled": True,
        "invoke": "sinnix observe",
    },
    {
        "kind": "service",
        "name": "polylogued",
        "description": "Polylogue daemon",
        "enabled": False,
    },
    {
        "kind": "script",
        "name": "sinnix-screenshot-control",
        "description": "Capture the screen",
        "enabled": True,
    },
]


def runtime(tmp_path: Path, principal: str = "operator") -> Runtime:
    return Runtime.create(
        GatewayConfig(
            state_dir=tmp_path / "state",
            projects={},
            ops_socket_path=tmp_path / "ops.sock",
            capability_index=index_path(tmp_path, ROWS),
        ),
        principal,
    )


def test_verify_and_receipt(tmp_path: Path) -> None:
    rt = runtime(tmp_path)
    first = call(rt, "audit.verify", {}, BY_NAME)
    assert first["data"]["valid"] is True
    receipt_id = first["receipt"]["receipt_id"]
    receipt = call(rt, "audit.receipt", {"receipt_id": receipt_id}, BY_NAME)["data"]
    assert (
        receipt["ref"] == f"sinnix://receipts/{receipt_id}"
        and receipt["operation"] == "audit.verify"
    )
    assert receipt["schema_name"] == "sinnix.gateway-audit-receipt.v1"
    again = call(rt, "audit.verify", {}, BY_NAME)["data"]
    assert again["checked"] >= 2 and again["head_hash"]
    missing = call(
        rt,
        "audit.receipt",
        {"ref": "sinnix://receipts/00000000-0000-0000-0000-000000000000"},
        BY_NAME,
    )
    assert missing["error"]["code"] == "not_found"
    foreign = call(
        Runtime.create(rt.config, "observer"),
        "audit.receipt",
        {"receipt_id": receipt_id},
        BY_NAME,
    )
    assert foreign["error"]["code"] == "policy_denied"


def test_results_get(tmp_path: Path) -> None:
    rt = runtime(tmp_path)
    missing = call(rt, "results.get", {"result_id": "nope"}, BY_NAME)
    assert missing["error"]["code"] == "not_found"


def test_capabilities_search_and_describe(tmp_path: Path) -> None:
    rt = runtime(tmp_path, "observer")
    found = call(
        rt,
        "capabilities.query",
        {"request": {"operation": "search", "query": "machine state"}},
        BY_NAME,
    )["data"]
    assert [row["name"] for row in found["rows"]] == ["sinnix-observe"]
    assert (
        found["rows"][0]["ref"] == "sinnix://capabilities/sinnix-observe"
        and found["source"]["host"] == "test-host"
    )
    paged = call(
        rt,
        "capabilities.query",
        {"request": {"operation": "search", "kind": "script", "cursor": 1, "limit": 1}},
        BY_NAME,
    )["data"]
    assert (
        paged["total"] == 2
        and paged["rows"][0]["name"] == "sinnix-screenshot-control"
        and paged["next_cursor"] is None
    )
    stale = call(
        rt,
        "capabilities.query",
        {"request": {"operation": "search", "cursor": 50}},
        BY_NAME,
    )
    assert stale["error"]["code"] == "stale_cursor"
    described = call(
        rt,
        "capabilities.query",
        {"request": {"operation": "describe", "name": "polylogued"}},
        BY_NAME,
    )["data"]
    assert (
        described["available"]
        and described["rows"][0]["enabled"] is False
        and described["ambiguous"] is False
    )
    unknown = call(
        rt,
        "capabilities.query",
        {"request": {"operation": "describe", "name": "nope"}},
        BY_NAME,
    )["data"]
    assert unknown["available"] is False and unknown["reason"] == "capability not found"
