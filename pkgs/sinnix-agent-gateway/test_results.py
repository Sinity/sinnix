from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from sinnix_agent_gateway.app import Runtime
from sinnix_agent_gateway.audit import AuditService
from sinnix_agent_gateway.capabilities import Principal
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.contracts import ActionSpec, EffectMode, VerbFamily
from sinnix_mcp.execution import ExecutionProfile, OwnerRoute
from sinnix_agent_gateway.registry import REGISTRY
from sinnix_agent_gateway.results import (
    EXPECTED_ERROR_CODES,
    ProtocolError,
    ResultError,
    ResultService,
)


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
    assert failure["error"] == {
        "code": "invalid_request",
        "message": "invalid filter",
        "details": {},
        "diagnostic_refs": [],
    }
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


def test_runtime_v2_keeps_each_expected_failure_in_a_typed_envelope(tmp_path) -> None:
    runtime = Runtime.create(config(tmp_path), "observer")
    action = REGISTRY.action("gateway.catalog")

    for code in EXPECTED_ERROR_CODES:
        response = runtime.execute_v2(
            action,
            lambda code=code: (_ for _ in ()).throw(
                ProtocolError(code, f"safe {code} failure")
            ),
            {"code": code},
        )

        assert response["result"]["outcome"] == "error"
        assert response["error"]["code"] == code
        assert response["error"]["message"] == f"safe {code} failure"
        assert runtime.audit.receipt(response["receipt"]["receipt_id"])["outcome"] == "error"


def test_jsonl_snapshot_pages_a_million_rows_without_logical_result_buffering(tmp_path) -> None:
    runtime = Runtime.create(config(tmp_path), "observer")
    action = REGISTRY.action("gateway.catalog")
    command = [
        sys.executable,
        "-c",
        "import json\nfor row in range(1_000_000): print(json.dumps({'row': row}))",
    ]

    response = runtime.execute_v2_jsonl(
        action,
        command,
        ExecutionProfile(
            route=OwnerRoute("million-row-fixture"), max_stdout_bytes=1_024
        ),
        {"query": "million rows"},
        source_revision="fixture-revision-1",
        page_size=3,
    )

    assert response["result"]["outcome"] == "ok"
    assert response["data"] == {
        "rows": [{"row": 0}, {"row": 1}, {"row": 2}],
        "row_count": 1_000_000,
    }
    assert response["page"]["kind"] == "snapshot"
    assert response["page"]["next_cursor"] is not None
    assert len(list(runtime.results.snapshots_root.glob("*"))) == 1
    next_page = runtime.results.continue_snapshot(
        response["page"]["next_cursor"],
        query_sha256=response["result"]["request_sha256"],
        source_revision="fixture-revision-1",
    )
    assert next_page["rows"] == [{"row": 3}, {"row": 4}, {"row": 5}]
    assert next_page["next_cursor"] is not None
    with pytest.raises(ResultError, match="source changed"):
        runtime.results.continue_snapshot(
            response["page"]["next_cursor"],
            query_sha256=response["result"]["request_sha256"],
            source_revision="fixture-revision-2",
        )
    with pytest.raises(ResultError, match="does not match"):
        ResultService(config(tmp_path), Principal.for_name("operator")).continue_snapshot(
            response["page"]["next_cursor"],
            query_sha256=response["result"]["request_sha256"],
        )


def test_snapshot_cursor_expires(tmp_path) -> None:
    runtime = Runtime.create(config(tmp_path), "observer")
    runtime.results.cursor_ttl_seconds = -1
    response = runtime.execute_v2_jsonl(
        REGISTRY.action("gateway.catalog"),
        [sys.executable, "-c", "print('{\\\"row\\\": 1}'); print('{\\\"row\\\": 2}')"],
        ExecutionProfile(route=OwnerRoute("expired-cursor")),
        {"query": "expiry"},
        source_revision="fixture-revision",
        page_size=1,
    )

    with pytest.raises(ResultError, match="expired"):
        runtime.results.continue_snapshot(
            response["page"]["next_cursor"],
            query_sha256=response["result"]["request_sha256"],
        )


def test_jsonl_stream_failure_cancels_child_and_removes_temp_writer(tmp_path) -> None:
    runtime = Runtime.create(config(tmp_path), "observer")
    action = REGISTRY.action("gateway.catalog")
    response = runtime.execute_v2_jsonl(
        action,
        [
            sys.executable,
            "-c",
            "import sys, time; sys.stderr.write('token=secret-value\\n'); sys.stderr.flush(); print('x' * 4096, flush=True); time.sleep(60)",
        ],
        ExecutionProfile(route=OwnerRoute("invalid-jsonl"), max_stdout_bytes=128),
        {"query": "bad stream"},
        source_revision="fixture-revision",
    )

    assert response["error"]["code"] == "owner_failed"
    assert response["error"]["details"]["failure_class"] == "command_stream_decode"
    assert "secret-value" not in json.dumps(response)
    diagnostic_id = response["error"]["diagnostic_refs"][0].rsplit("/", 1)[-1]
    diagnostic = json.loads(
        base64.b64decode(runtime.artifacts.read(diagnostic_id)["base64"])
    )
    assert diagnostic["stderr_excerpt"] == "token=[REDACTED]"
    assert list(runtime.results.snapshots_root.glob(".*.writing")) == []


def test_mutation_idempotency_replays_receipt_without_second_owner_write(tmp_path) -> None:
    runtime = Runtime.create(config(tmp_path), "operator")
    action = ActionSpec(
        name="fixture.change",
        verb=VerbFamily.CHANGE,
        domain="fixture",
        owner="fixture",
        route="fixture.write",
        effect=EffectMode.CHANGE,
        principals=frozenset({"operator"}),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        supports_idempotency=True,
        receipt_policy="audit",
    )
    writes = []

    def write() -> dict[str, object]:
        writes.append("owner write")
        return {"created": True, "ref": "sinnix://fixtures/one"}

    request = {"idempotency_key": "fixture-key", "value": 1}
    first = runtime.execute_v2(action, write, request)
    replay = runtime.execute_v2(action, write, request)
    conflict = runtime.execute_v2(
        action, write, {"idempotency_key": "fixture-key", "value": 2}
    )

    assert writes == ["owner write"]
    assert replay == first
    assert conflict["error"]["code"] == "idempotency_conflict"


def test_concurrent_matching_idempotency_returns_conflict_then_replays(tmp_path) -> None:
    runtime = Runtime.create(config(tmp_path), "operator")
    action = ActionSpec(
        name="fixture.concurrent-change", verb=VerbFamily.CHANGE, domain="fixture",
        owner="fixture", route="fixture.write", effect=EffectMode.CHANGE,
        principals=frozenset({"operator"}), input_schema={"type": "object"}, output_schema={"type": "object"},
        supports_idempotency=True, receipt_policy="audit",
    )
    started, release = threading.Event(), threading.Event()
    writes: list[str] = []

    def write() -> dict[str, str]:
        writes.append("write"); started.set(); assert release.wait(5)
        return {"ref": "sinnix://projects/fixture", "created": True}

    first_result: dict[str, object] = {}
    thread = threading.Thread(target=lambda: first_result.setdefault("value", runtime.execute_v2(action, write, {"idempotency_key": "same"})))
    thread.start(); assert started.wait(5)
    concurrent = runtime.execute_v2(action, write, {"idempotency_key": "same"})
    assert concurrent["error"]["code"] == "conflict"
    release.set(); thread.join(5)
    replay = runtime.execute_v2(action, write, {"idempotency_key": "same"})
    assert replay == first_result["value"]
    assert writes == ["write"]


def test_partial_completion_is_explicitly_non_atomic(tmp_path) -> None:
    runtime = Runtime.create(config(tmp_path), "operator")
    action = ActionSpec(
        name="fixture.change",
        verb=VerbFamily.CHANGE,
        domain="fixture",
        owner="fixture",
        route="fixture.write",
        effect=EffectMode.CHANGE,
        principals=frozenset({"operator"}),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        supports_idempotency=True,
        receipt_policy="audit",
    )

    response = runtime.execute_v2(
        action,
        lambda: (_ for _ in ()).throw(
            ProtocolError("partial_completion", "first owner step completed")
        ),
        {"idempotency_key": "partial-key"},
    )

    receipt = runtime.audit.receipt(response["receipt"]["receipt_id"])
    assert response["error"]["code"] == "partial_completion"
    assert receipt["payload"]["partial_completion"] is True
    assert receipt["payload"]["atomicity"] == "not_atomic"


def test_v2_rejects_ignored_preconditions(tmp_path) -> None:
    runtime = Runtime.create(config(tmp_path), "observer")

    response = runtime.execute_v2(
        REGISTRY.action("gateway.catalog"),
        lambda: {"rows": []},
        {"preconditions": {"unexpected": "state"}},
    )

    assert response["error"]["code"] == "invalid_request"
    assert response["error"]["message"] == "action does not support preconditions"


def _project_runtime(tmp_path: Path) -> Runtime:
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "--quiet", project], check=True)
    subprocess.run(["git", "config", "user.name", "Gateway Test"], cwd=project, check=True)
    subprocess.run(
        ["git", "config", "user.email", "gateway-test@example.invalid"],
        cwd=project,
        check=True,
    )
    (project / "tracked.txt").write_text("before\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=project, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=project, check=True)
    return Runtime.create(
        GatewayConfig(
            state_dir=tmp_path / "state",
            projects={"fixture": ProjectConfig(project_id="fixture", path=project)},
        ),
        "operator",
    )


def _checkout_preconditions(runtime: Runtime) -> dict[str, str]:
    checkout = runtime.projects.checkout("fixture", "default")["checkout"]
    return {"head": checkout["head"], "dirty_sha256": checkout["dirty_sha256"]}


def test_v2_change_uses_canonical_checkout_preconditions_and_idempotency(tmp_path) -> None:
    runtime = _project_runtime(tmp_path)
    action = REGISTRY.action("projects.change")
    reference = "sinnix://projects/fixture/checkouts/default"
    preconditions = _checkout_preconditions(runtime)
    request = {
        "ref": reference,
        "operation": "write",
        "path": "tracked.txt",
        "content": "after\n",
        "preconditions": preconditions,
        "idempotency_key": "project-write",
    }

    first = runtime.execute_v2(
        action,
        lambda: runtime.v2_change(
            reference=reference,
            operation="write",
            path="tracked.txt",
            content="after\n",
            patch=None,
            preconditions=preconditions,
        ),
        request,
    )
    replay = runtime.execute_v2(
        action,
        lambda: (_ for _ in ()).throw(AssertionError("owner was called on replay")),
        request,
    )
    stale = runtime.execute_v2(
        action,
        lambda: runtime.v2_change(
            reference=reference,
            operation="write",
            path="tracked.txt",
            content="stale\n",
            patch=None,
            preconditions=preconditions,
        ),
        {**request, "content": "stale\n", "idempotency_key": "project-stale"},
    )

    assert first["data"]["ref"] == reference
    assert first["data"]["checkout_ref"] == reference
    assert first["data"]["owner_result"] == {
        "project_id": "fixture",
        "path": "tracked.txt",
        "bytes": len(b"after\n"),
    }
    assert replay == first
    assert stale["error"]["code"] == "precondition_failed"
    assert (tmp_path / "project" / "tracked.txt").read_text() == "after\n"


def test_v2_change_preserves_project_patch_owner_contract(tmp_path) -> None:
    runtime = _project_runtime(tmp_path)
    preconditions = _checkout_preconditions(runtime)
    patch = """diff --git a/tracked.txt b/tracked.txt
--- a/tracked.txt
+++ b/tracked.txt
@@ -1 +1 @@
-before
+patched
"""

    response = runtime.execute_v2(
        REGISTRY.action("projects.change"),
        lambda: runtime.v2_change(
            reference="sinnix://projects/fixture",
            operation="apply_patch",
            path=None,
            content=None,
            patch=patch,
            preconditions=preconditions,
        ),
        {
            "ref": "sinnix://projects/fixture",
            "operation": "apply_patch",
            "patch": patch,
            "preconditions": preconditions,
            "idempotency_key": "project-patch",
        },
    )

    assert response["data"]["owner_result"] == {"project_id": "fixture", "applied": True}
    assert (tmp_path / "project" / "tracked.txt").read_text() == "patched\n"


@pytest.mark.parametrize(
    ("reference", "target"),
    [
        ("sinnix://jobs/job-1", {"job_id": "job-1"}),
        ("sinnix://machine/units/user/fixture.service", {"unit": "fixture.service"}),
        ("sinnix://processes/42/123", {"process": {"pid": 42, "start_ticks": 123}}),
    ],
)
def test_v2_operate_maps_canonical_targets_and_validates_owner_receipts(
    tmp_path, reference, target
) -> None:
    runtime = Runtime.create(config(tmp_path), "operator")
    calls: list[dict[str, object]] = []

    def execute(
        action: str,
        received_target: dict[str, object],
        expected_revision: int,
        idempotency_key: str,
        operator_reason: str,
        parameters: dict[str, object],
    ) -> dict[str, object]:
        calls.append({"target": received_target})
        return {
            "schema": "sinnix-ops-action-v1",
            "receipt_id": "owner-receipt",
            "idempotency_key": idempotency_key,
            "action": action,
            "target": received_target,
            "operator_reason": operator_reason,
            "expected_revision": expected_revision,
            "status": "accepted",
            "adapter": {"status": "ok"},
        }

    runtime.machine_actions.execute = execute  # type: ignore[method-assign]
    request = {
        "ref": reference,
        "action": "restart",
        "parameters": {},
        "reason": "exercise typed operation",
        "idempotency_key": f"operate-{target}",
        "preconditions": {"expected_revision": 7},
    }
    response = runtime.execute_v2(
        REGISTRY.action("machine.operate"),
        lambda: runtime.v2_operate(
            reference=reference,
            action="restart",
            parameters={},
            reason="exercise typed operation",
            idempotency_key=request["idempotency_key"],
            preconditions={"expected_revision": 7},
        ),
        request,
    )

    assert calls == [{"target": target}]
    assert response["data"]["ref"] == reference
    assert response["data"]["owner_receipt"]["target"] == target
    assert response["data"]["owner_receipt"]["operator_reason"] == "exercise typed operation"
    receipt = runtime.audit.receipt(response["receipt"]["receipt_id"])
    assert receipt["payload"]["owner_receipt_id"] == "owner-receipt"


def test_v2_operate_rejects_mismatched_owner_receipt(tmp_path) -> None:
    runtime = Runtime.create(config(tmp_path), "operator")

    runtime.machine_actions.execute = lambda *_args: {
        "schema": "sinnix-ops-action-v1",
        "receipt_id": "owner-receipt",
        "idempotency_key": "wrong-key",
        "action": "restart",
        "target": {"unit": "fixture.service"},
        "operator_reason": "exercise typed operation",
        "expected_revision": 7,
    }  # type: ignore[method-assign]
    response = runtime.execute_v2(
        REGISTRY.action("machine.operate"),
        lambda: runtime.v2_operate(
            reference="sinnix://machine/units/user/fixture.service",
            action="restart",
            parameters={},
            reason="exercise typed operation",
            idempotency_key="operate-key",
            preconditions={"expected_revision": 7},
        ),
        {
            "ref": "sinnix://machine/units/user/fixture.service",
            "action": "restart",
            "parameters": {},
            "reason": "exercise typed operation",
            "idempotency_key": "operate-key",
            "preconditions": {"expected_revision": 7},
        },
    )

    assert response["error"]["code"] == "owner_failed"
