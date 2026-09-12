from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import threading
import time
from pathlib import Path

import anyio
import pytest
from sinnix_agent_gateway.action import Action, MutationControls, RequestControls
from sinnix_agent_gateway.actions import BY_NAME as ACTIONS
from sinnix_agent_gateway.app import Runtime
from sinnix_agent_gateway.audit import AuditService
from sinnix_agent_gateway.capabilities import Principal
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.contracts import VerbFamily
from sinnix_agent_gateway.results import (
    EXPECTED_ERROR_CODES,
    ProtocolError,
    ResultError,
    ResultService,
)
from sinnix_agent_gateway.schemas import GatewayModel, V2ToolEnvelope


def _execute(runtime, action, callback, request):
    async def invoke():
        async def async_callback():
            return callback()

        return await runtime.execute_v2_async(action, async_callback, request)

    return anyio.run(invoke)


class _Out(GatewayModel):
    model_config = {"extra": "allow"}


class _ReadIn(RequestControls):
    pass


class _ChangeIn(MutationControls):
    pass


def _fixture_action(name: str, family: VerbFamily, principals: set[str]) -> Action:
    return Action(
        name=name,
        family=family,
        owner="fixture",
        summary="fixture",
        Input=_ChangeIn if family is VerbFamily.CHANGE else _ReadIn,
        Output=_Out,
        handler=lambda runtime, inp: {},
        principals=frozenset(principals),
    )


def config(tmp_path, *, max_result_bytes: int = 262_144):
    return GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        max_result_bytes=max_result_bytes,
    )


def test_large_metadata_has_retrievable_continuation(tmp_path) -> None:
    cfg = config(tmp_path)
    principal = Principal.for_name("operator")
    results = ResultService(cfg, principal)
    receipt = AuditService(cfg, principal).append("fixture.query", "ok", {})
    meta = {"coverage": {"items": ["source" * 100] * 1000}}
    result = results.record(
        action="fixture.query",
        owner="fixture",
        route="fixture",
        outcome="ok",
        payload={"answer": 42},
        receipt=receipt,
        meta=meta,
    )
    assert result["data"] == {"answer": 42}
    assert len(json.dumps(result).encode()) < cfg.max_result_bytes
    artifact_id = result["meta"]["artifact_refs"][0].rsplit("/", 1)[1]
    info = results.artifacts._metadata(artifact_id)
    retained = json.loads(info["_source"].read_text())
    assert retained["coverage"] == meta["coverage"]


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
    action = ACTIONS["gateway.catalog"]

    success = _execute(
        runtime,
        action,
        lambda: {"cursor": 0, "next_cursor": None, "total": 1, "rows": ["bead"]},
        {"text": "bead"},
    )
    failure = _execute(
        runtime,
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
    assert (
        failure["result"]["request_sha256"]
        == hashlib.sha256(
            json.dumps(
                {"verb": "invalid"}, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
    )


def test_runtime_v2_replaces_an_oversized_owner_payload_with_an_artifact(
    tmp_path,
) -> None:
    runtime = Runtime.create(config(tmp_path, max_result_bytes=1_024), "observer")
    action = ACTIONS["gateway.catalog"]

    response = _execute(
        runtime, action, lambda: {"rows": ["x" * 2_000]}, {"text": "large"}
    )

    assert response["result"]["outcome"] == "ok"
    assert response["data"]["truncated"] is True
    assert response["data"]["artifact"]["ref"].startswith("sinnix://artifacts/")
    assert response["meta"]["artifact_refs"] == [response["data"]["artifact"]["ref"]]
    assert response["receipt"]["ref"].startswith("sinnix://receipts/")


def test_large_snapshot_row_survives_paging_and_artifact_transport(tmp_path) -> None:
    runtime = Runtime.create(config(tmp_path), "observer")
    results = runtime.results
    query_sha = hashlib.sha256(b"large-snapshot-row").hexdigest()
    row = {"id": "large", "body": "x" * 300_000}
    writer = results.start_snapshot(
        query_sha256=query_sha, source_revision="revision-one", page_size=1
    )
    writer.append(row)
    writer.append({"id": "next"})
    metadata = writer.finish()
    cursor = results._cursor(
        {
            "snapshot_id": metadata["snapshot_id"],
            "principal": "observer",
            "query_sha256": query_sha,
            "source_revision": "revision-one",
            "offset": 0,
            "page_size": 1,
            "expires_at": metadata["expires_at"],
        }
    )
    page = results.continue_snapshot(cursor, query_sha256=query_sha)
    assert page["rows"] == [row]
    assert page["next_cursor"] is not None
    response = _execute(
        runtime, ACTIONS["gateway.catalog"], lambda: page, {"text": "large-row"}
    )
    assert response["result"]["outcome"] == "ok"
    artifact = response["data"]["artifact"]
    chunks = []
    offset = 0
    while offset is not None:
        chunk = results.artifacts.read(artifact["artifact_id"], offset=offset)
        chunks.append(base64.b64decode(chunk["base64"]))
        offset = chunk["next_offset"]
    assert json.loads(b"".join(chunks)) == page
    continuation = results.continue_snapshot(
        page["next_cursor"], query_sha256=query_sha
    )
    assert continuation["rows"] == [{"id": "next"}]
    assert continuation["next_cursor"] is None


def test_accepted_failure_classes_are_exactly_the_rendered_envelope_enum() -> None:
    # The enum below is what a caller reads off the published envelope schema;
    # `EXPECTED_ERROR_CODES` is what `ProtocolError` may raise. They are one
    # definition, so a code the gateway can raise is always a code it can send.
    rendered = set(
        V2ToolEnvelope.model_json_schema()["$defs"]["V2Error"]["properties"]["code"][
            "enum"
        ]
    )

    assert rendered == set(EXPECTED_ERROR_CODES)
    for code in sorted(rendered):
        assert ProtocolError(code, "safe failure").code == code
    with pytest.raises(ValueError, match="unknown protocol error code"):
        ProtocolError("retired_code", "safe failure")


def test_runtime_v2_keeps_each_expected_failure_in_a_typed_envelope(tmp_path) -> None:
    runtime = Runtime.create(config(tmp_path), "observer")
    action = _fixture_action("fixture.typed-failure", VerbFamily.QUERY, {"observer"})

    for code in EXPECTED_ERROR_CODES:
        response = _execute(
            runtime,
            action,
            lambda code=code: (_ for _ in ()).throw(
                ProtocolError(code, f"safe {code} failure")
            ),
            {"code": code},
        )

        assert response["result"]["outcome"] == "error"
        assert response["error"]["code"] == code
        assert response["error"]["message"] == f"safe {code} failure"
        assert (
            runtime.audit.receipt(response["receipt"]["receipt_id"])["outcome"]
            == "error"
        )


def test_mutation_idempotency_replays_receipt_without_second_owner_write(
    tmp_path,
) -> None:
    runtime = Runtime.create(config(tmp_path), "operator")
    action = _fixture_action("fixture.change", VerbFamily.CHANGE, {"operator"})
    writes = []

    def write() -> dict[str, object]:
        writes.append("owner write")
        return {"created": True, "ref": "sinnix://fixtures/one"}

    request = {"idempotency_key": "fixture-key", "value": 1}
    first = _execute(runtime, action, write, request)
    replay = _execute(runtime, action, write, request)
    conflict = _execute(
        runtime, action, write, {"idempotency_key": "fixture-key", "value": 2}
    )

    assert writes == ["owner write"]
    assert replay == first
    assert conflict["error"]["code"] == "idempotency_conflict"


def test_declared_deadline_and_idempotency_failures_persist_bounded_envelopes(
    tmp_path,
) -> None:
    runtime = Runtime.create(config(tmp_path), "operator")
    action = ACTIONS["batches.start"]
    request = {
        "project": {"project": "fixture"},
        "beads": ["fixture-1"],
        "backend": "codex",
        "model": "gpt-5.6-terra",
        "effort": "high",
        "request_id": "2e46daf5-e9b1-4c6e-b99d-bcd46631730b",
        "idempotency_key": "batch-failure-fixture",
    }

    deadline = _execute(
        runtime,
        action,
        lambda: pytest.fail("expired request reached the owner"),
        {**request, "deadline_at": time.time() - 1},
    )
    first = _execute(runtime, action, lambda: {"job_id": "first"}, request)
    conflict = _execute(
        runtime,
        action,
        lambda: pytest.fail("conflicting request reached the owner"),
        {**request, "instructions": "different request"},
    )
    unexpected = _execute(
        runtime,
        action,
        lambda: (_ for _ in ()).throw(RuntimeError("owner implementation bug")),
        {**request, "idempotency_key": "unexpected-owner-fixture"},
    )

    assert first["result"]["outcome"] == "ok"
    for response, code in (
        (deadline, "deadline"),
        (conflict, "idempotency_conflict"),
        (unexpected, "owner_failed"),
    ):
        assert response["error"]["code"] == code
        assert response["result"]["outcome"] == "error"
        assert response["receipt"]["receipt_id"]
        assert runtime.results.read(response["result"]["result_id"]) == response


def test_concurrent_matching_idempotency_returns_conflict_then_replays(
    tmp_path,
) -> None:
    runtime = Runtime.create(config(tmp_path), "operator")
    action = _fixture_action(
        "fixture.concurrent-change", VerbFamily.CHANGE, {"operator"}
    )
    started, release = threading.Event(), threading.Event()
    writes: list[str] = []

    def write() -> dict[str, str]:
        writes.append("write")
        started.set()
        assert release.wait(5)
        return {"ref": "sinnix://projects/fixture", "created": True}

    first_result: dict[str, object] = {}
    thread = threading.Thread(
        target=lambda: first_result.setdefault(
            "value", _execute(runtime, action, write, {"idempotency_key": "same"})
        )
    )
    thread.start()
    assert started.wait(5)
    concurrent = _execute(runtime, action, write, {"idempotency_key": "same"})
    assert concurrent["error"]["code"] == "conflict"
    release.set()
    thread.join(5)
    replay = _execute(runtime, action, write, {"idempotency_key": "same"})
    assert replay == first_result["value"]
    assert writes == ["write"]


def test_partial_completion_is_explicitly_non_atomic(tmp_path) -> None:
    runtime = Runtime.create(config(tmp_path), "operator")
    action = _fixture_action("fixture.change", VerbFamily.CHANGE, {"operator"})

    response = _execute(
        runtime,
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

    response = _execute(
        runtime,
        ACTIONS["gateway.catalog"],
        lambda: {"rows": []},
        {"preconditions": {"unexpected": "state"}},
    )

    assert response["error"]["code"] == "invalid_request"
    assert response["error"]["message"] == "action does not support preconditions"


def _project_runtime(tmp_path: Path) -> Runtime:
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "--quiet", project], check=True)
    subprocess.run(
        ["git", "config", "user.name", "Gateway Test"], cwd=project, check=True
    )
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
    response = _execute(
        runtime,
        ACTIONS["machine.operate"],
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
    assert (
        response["data"]["owner_receipt"]["operator_reason"]
        == "exercise typed operation"
    )
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
    response = _execute(
        runtime,
        ACTIONS["machine.operate"],
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


def test_snapshot_continuation_can_resize_pages_without_changing_position(
    tmp_path,
) -> None:
    results = ResultService(config(tmp_path), Principal.for_name("observer"))
    query_sha = hashlib.sha256(b"resized-snapshot").hexdigest()
    writer = results.start_snapshot(
        query_sha256=query_sha, source_revision="revision-one", page_size=1
    )
    for value in range(10):
        writer.append(value)
    first = results.finish_snapshot(writer)
    enlarged = results.continue_snapshot(
        first["next_cursor"], query_sha256=query_sha, page_size=3
    )
    assert enlarged["rows"] == [1, 2, 3]
    continued = results.continue_snapshot(
        enlarged["next_cursor"], query_sha256=query_sha
    )
    assert continued["rows"] == [4, 5, 6]
    smaller = results.continue_snapshot(
        continued["next_cursor"], query_sha256=query_sha, page_size=1
    )
    assert smaller["rows"] == [7]
    assert smaller["snapshot_ref"] == first["snapshot_ref"]
    for invalid_size in (0, -1, True, 1.5):
        with pytest.raises(ResultError) as failure:
            results.continue_snapshot(
                first["next_cursor"], query_sha256=query_sha, page_size=invalid_size
            )
        assert failure.value.failure_class == "invalid_request"
