from __future__ import annotations

import hashlib
import json

import pytest

from sinnix_agent_gateway.app import Runtime
from sinnix_agent_gateway.audit import AuditService
from sinnix_agent_gateway.capabilities import Principal
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.registry import REGISTRY
from sinnix_agent_gateway.results import ResultError, ResultService


def config(tmp_path, *, max_result_bytes: int = 262_144):
    return GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        max_result_bytes=max_result_bytes,
    )


def test_result_snapshot_preserves_owner_page_and_receipt(tmp_path) -> None:
    cfg = config(tmp_path)
    audit = AuditService(cfg, Principal.for_name("observer"))
    receipt = audit.append("gateway.catalog", "ok", {"count": 2})
    results = ResultService(cfg, Principal.for_name("observer"))

    snapshot = results.record(
        action="gateway.catalog",
        owner="registry",
        route="registry.search",
        outcome="ok",
        payload={"cursor": 3, "next_cursor": 5, "total": 9, "rows": ["one", "two"]},
        receipt=receipt,
    )

    assert snapshot["result"]["ref"] == (
        f"sinnix://results/{snapshot['result']['result_id']}"
    )
    assert snapshot["receipt"] == {
        "receipt_id": receipt["event_id"],
        "ref": f"sinnix://receipts/{receipt['event_id']}",
        "sequence": receipt["sequence"],
        "entry_hash": receipt["entry_hash"],
    }
    assert snapshot["page"] == {
        "kind": "cursor",
        "cursor": 3,
        "next_cursor": 5,
        "total": 9,
    }
    assert results.read(snapshot["result"]["result_id"]) == snapshot


def test_result_snapshot_rejects_cross_principal_reads(tmp_path) -> None:
    cfg = config(tmp_path)
    audit = AuditService(cfg, Principal.for_name("observer"))
    snapshot = ResultService(cfg, Principal.for_name("observer")).record(
        action="gateway.status",
        owner="gateway",
        route="observe.gateway_status",
        outcome="ok",
        payload={"status": "ready"},
        receipt=audit.append("gateway.status", "ok"),
    )

    with pytest.raises(ResultError, match="unavailable"):
        ResultService(cfg, Principal.for_name("operator")).read(
            snapshot["result"]["result_id"]
        )


def test_runtime_v2_envelopes_success_and_public_error(tmp_path) -> None:
    runtime = Runtime.create(config(tmp_path), "observer")
    action = REGISTRY.action("gateway.catalog")

    success = runtime.execute_v2(
        action,
        lambda: {"cursor": 0, "next_cursor": None, "total": 1, "rows": ["bead"]},
        {"text": "bead"},
    )
    failure = runtime.execute_v2(
        action,
        lambda: (_ for _ in ()).throw(ValueError("invalid filter")),
        {"verb": "invalid"},
    )

    assert success["result"]["outcome"] == "ok"
    assert success["page"] == {
        "kind": "cursor",
        "cursor": 0,
        "next_cursor": None,
        "total": 1,
    }
    assert runtime.results.read(success["result"]["result_id"]) == success
    request_sha256 = hashlib.sha256(
        json.dumps({"text": "bead"}, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    success_receipt = runtime.audit.receipt(success["receipt"]["receipt_id"])
    assert success["result"]["request_sha256"] == request_sha256
    assert success_receipt["outcome"] == "ok"
    assert success_receipt["payload"]["request_sha256"] == request_sha256
    assert failure["result"]["outcome"] == "error"
    assert failure["error"] == {"code": "invalid_request", "message": "invalid filter"}
    assert runtime.audit.receipt(failure["receipt"]["receipt_id"])["outcome"] == "error"
    assert failure["result"]["request_sha256"] == hashlib.sha256(
        json.dumps({"verb": "invalid"}, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def test_runtime_v2_replaces_an_oversized_owner_payload_with_typed_error(tmp_path) -> None:
    runtime = Runtime.create(config(tmp_path, max_result_bytes=1_024), "observer")
    action = REGISTRY.action("gateway.catalog")

    response = runtime.execute_v2(
        action, lambda: {"rows": ["x" * 2_000]}, {"text": "large"}
    )

    assert response["result"]["outcome"] == "error"
    assert response["error"]["code"] == "response_bound"
    assert response["receipt"]["ref"].startswith("sinnix://receipts/")
