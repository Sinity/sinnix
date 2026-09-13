from __future__ import annotations

import json
import subprocess
import sys

import anyio
import pytest
from sinnix_agent_gateway.audit import AuditService
from sinnix_agent_gateway.capabilities import Principal
from sinnix_agent_gateway.cli import build_manifest, verify_approval
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.results import RequestContext, ResultError, ResultService


@pytest.mark.parametrize("size", [200, 20000])
def test_full_observations_survive_restart_and_share_only_payload_bytes(tmp_path, size):
    config = GatewayConfig(
        projects={}, state_dir=tmp_path / "state", max_result_bytes=8192
    )
    principal = Principal.for_name("observer")
    audit = AuditService(config, principal)
    service = ResultService(config, principal)
    payload = {"text": "x" * size}
    responses = []
    for index in range(2):
        responses.append(
            service.record(
                action="sessions.orchestration",
                owner="polylogue",
                route="owner",
                outcome="ok",
                payload=payload,
                receipt=audit.append("observe", "ok"),
                request=RequestContext.create("a" * 64, request_id=f"request-{index}"),
                meta={"coverage": {"observation": index}},
            )
        )
    restarted = ResultService(config, principal)
    observations = [restarted.read(row["result"]["result_id"]) for row in responses]
    assert [row["data"] for row in observations] == [payload, payload]
    assert [row["meta"]["coverage"] for row in observations] == [
        {"observation": 0},
        {"observation": 1},
    ]
    assert (
        observations[0]["result"]["request_id"]
        != observations[1]["result"]["request_id"]
    )
    blobs = list((config.state_dir / "payloads").iterdir())
    assert len(blobs) == 1
    if size > 8192:
        assert all(row["data"]["truncated"] for row in responses)
    with pytest.raises(ResultError):
        ResultService(config, Principal.for_name("agent-control")).read(
            responses[0]["result"]["result_id"]
        )


@pytest.mark.parametrize("after_effect", [False, True])
def test_crashed_pending_call_is_indeterminate_without_reexecution(
    tmp_path, after_effect
):
    state = tmp_path / "state"
    effect = tmp_path / "effect"
    code = """
import os, sys
from pathlib import Path
from sinnix_agent_gateway.audit import AuditService
from sinnix_agent_gateway.capabilities import Principal
from sinnix_agent_gateway.config import GatewayConfig
service = AuditService(GatewayConfig(projects={}, state_dir=Path(sys.argv[1])), Principal.for_name('operator'))
assert service.claim_idempotency('fixture.change', 'key', 'a'*64)[0] == 'new'
if sys.argv[3] == 'True':
    Path(sys.argv[2]).write_text('accepted once')
os._exit(37)
"""
    crashed = subprocess.run(
        [sys.executable, "-c", code, str(state), str(effect), str(after_effect)]
    )
    assert crashed.returncode == 37
    service = AuditService(
        GatewayConfig(projects={}, state_dir=state), Principal.for_name("operator")
    )
    assert service.claim_idempotency("fixture.change", "key", "a" * 64) == (
        "indeterminate",
        None,
    )
    assert service.claim_idempotency("fixture.change", "key", "a" * 64) == (
        "indeterminate",
        None,
    )
    assert effect.exists() == after_effect
    with service._connect() as connection:
        assert (
            connection.execute("select state from idempotency").fetchone()[0]
            == "indeterminate"
        )


def test_pending_contention_and_confirmed_response_replay(tmp_path):
    config = GatewayConfig(projects={}, state_dir=tmp_path)
    first = AuditService(config, Principal.for_name("operator"))
    second = AuditService(config, Principal.for_name("operator"))
    assert first.claim_idempotency("fixture.change", "key", "a" * 64)[0] == "new"
    assert second.claim_idempotency("fixture.change", "key", "a" * 64)[0] == "pending"
    response = {"receipt": {"receipt_id": "receipt"}, "data": {"accepted": True}}
    first.complete_idempotency("fixture.change", "key", "a" * 64, response)
    assert second.claim_idempotency("fixture.change", "key", "a" * 64) == (
        "replay",
        response,
    )
    assert second.claim_idempotency("fixture.change", "key", "b" * 64)[0] == "conflict"
    competing_observation = {
        "receipt": {"receipt_id": "later"},
        "data": {"accepted": True},
    }
    assert (
        second.complete_idempotency(
            "fixture.change", "key", "a" * 64, competing_observation
        )
        == response
    )


def test_package_manifest_checks_code_and_principal_separately_from_connector(tmp_path):
    path = tmp_path / "manifest.json"
    config = GatewayConfig(
        projects={}, state_dir=tmp_path / "state", package_manifest_path=path
    )
    manifest = anyio.run(build_manifest, config, "observer")
    path.write_text(json.dumps({"principal": "observer", "manifest": manifest}))
    assert (
        verify_approval(config, "observer")["tool_manifest_hash"] == manifest["sha256"]
    )
    path.write_text(json.dumps({"principal": "operator", "manifest": manifest}))
    with pytest.raises(ValueError, match="principal"):
        verify_approval(config, "observer")
    path.write_text(
        json.dumps({"principal": "observer", "manifest": {"sha256": "a" * 64}})
    )
    with pytest.raises(ValueError, match="drift"):
        verify_approval(config, "observer")


@pytest.mark.parametrize("size", [200, 20000])
def test_owner_product_availability_is_independent_of_presentation_budget(
    tmp_path, size
):
    from types import SimpleNamespace

    from sinnix_agent_gateway.actions.products import owner_product
    from sinnix_agent_gateway.artifacts import ArtifactService
    from sinnix_agent_gateway.mcp_broker import McpBrokerService

    config = GatewayConfig(projects={}, state_dir=tmp_path, max_result_bytes=8192)
    principal = Principal.for_name("observer")
    data = {"evidence": "x" * size, "coverage": {"complete": False}}

    class Broker(McpBrokerService):
        async def owner_result(self, *args, **kwargs):
            return {"structuredContent": data, "isError": False}

    broker = Broker(config, principal, ArtifactService(config, principal))

    async def invoke():
        presentation = await broker.call("polylogue", "get", {}, write=False)
        product = await owner_product(
            SimpleNamespace(mcp_broker=broker), "polylogue", "get", {}
        )
        return presentation, product

    presentation, product = anyio.run(invoke)
    assert presentation["truncated"] == (size > 8192)
    assert product.availability == "available"
    assert product.data == data


def test_interrupted_launch_reconciles_owner_identity_without_running_again(tmp_path):
    from types import SimpleNamespace

    from sinnix_agent_gateway.actions import BY_NAME
    from sinnix_agent_gateway.runtime import Runtime

    config = GatewayConfig(projects={}, state_dir=tmp_path)
    runtime = Runtime.create(config, "operator")
    request = {"idempotency_key": "launch-key"}
    context = runtime._request_context(request)
    runtime.audit.claim_idempotency(
        "operations.run", "launch-key", context.request_sha256
    )
    runtime.audit.abandon_idempotency("operations.run", "launch-key")
    seen = []

    def reconcile(key):
        seen.append(key)
        return {
            "job_id": "7",
            "launch_reference": "retained-launch",
            "state": {"phase": "queued"},
        }

    runtime.jobs = SimpleNamespace(reconcile_start=reconcile)

    async def forbidden():
        pytest.fail("ambiguous launch must not execute again")

    async def invoke():
        return await runtime.execute_v2_async(
            BY_NAME["operations.run"], forbidden, request
        )

    response = anyio.run(invoke)
    assert response["result"]["outcome"] == "ok", response
    assert response["data"]["launch_reference"] == "retained-launch"
    assert seen == [runtime.owner_request_key("operations.run", "launch-key")]
    assert anyio.run(invoke) == response
    assert len(seen) == 1


def test_unreconciled_interruption_returns_indeterminate_and_no_effect(tmp_path):
    from sinnix_agent_gateway.actions import BY_NAME
    from sinnix_agent_gateway.runtime import Runtime

    runtime = Runtime.create(GatewayConfig(projects={}, state_dir=tmp_path), "operator")
    request = {"idempotency_key": "change-key"}
    context = runtime._request_context(request)
    runtime.audit.claim_idempotency(
        "files.change", "change-key", context.request_sha256
    )
    runtime.audit.abandon_idempotency("files.change", "change-key")

    async def forbidden():
        pytest.fail("ambiguous mutation must not execute again")

    async def invoke():
        return await runtime.execute_v2_async(
            BY_NAME["files.change"], forbidden, request
        )

    response = anyio.run(invoke)
    assert response["error"]["code"] == "indeterminate", response


@pytest.mark.parametrize("action_name", ["machine.operate", "machine.units.operate"])
@pytest.mark.parametrize("tampered", [None, "parameters", "manager"])
def test_machine_recovery_requires_exact_confirmed_owner_request(
    tmp_path, action_name, tampered
):
    import hashlib
    from types import SimpleNamespace

    from sinnix_agent_gateway.actions import BY_NAME
    from sinnix_agent_gateway.runtime import Runtime

    runtime = Runtime.create(GatewayConfig(projects={}, state_dir=tmp_path), "operator")
    expected = {
        "kind": "unit",
        "unit": "fixture.service",
        "manager": "user",
        "properties": {"InvocationID": "one"},
    }
    request = {
        "idempotency_key": "machine-key",
        "reason": "fixture operation",
        "expected_target": expected,
        **(
            {
                "target": "sinnix://machine/units/user/fixture.service",
                "request": {"action": "restart"},
            }
            if action_name == "machine.operate"
            else {
                "target": {"name": "fixture.service", "scope": "user"},
                "action": "restart",
            }
        ),
    }
    context = runtime._request_context(request)
    runtime.audit.claim_idempotency(action_name, "machine-key", context.request_sha256)
    runtime.audit.abandon_idempotency(action_name, "machine-key")
    target = {"unit": "fixture.service", "manager": "user"}
    owner_request = {
        "action": "restart",
        "target": target,
        "expected_target": expected,
        "idempotency_key": "machine-key",
        "operator_reason": "fixture operation",
        "parameters": {},
    }
    if tampered == "parameters":
        owner_request["parameters"] = {"unexpected": "effect"}
    if tampered == "manager":
        owner_request["target"] = {"unit": "fixture.service", "manager": "system"}
    receipt = {
        **owner_request,
        "schema": "sinnix-ops-action-v1",
        "receipt_id": "receipt",
        "status": "confirmed",
        "request_hash": hashlib.sha256(
            json.dumps(owner_request, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    runtime.machine_actions = SimpleNamespace(lookup=lambda key: receipt)

    async def forbidden():
        pytest.fail("owner lookup must not repeat the mutation")

    async def invoke():
        return await runtime.execute_v2_async(BY_NAME[action_name], forbidden, request)

    response = anyio.run(invoke)
    if tampered:
        assert response["error"]["code"] == "indeterminate", response
    else:
        assert response["result"]["outcome"] == "ok", response
        assert response["data"]["owner_receipt"]["target"] == target
        assert anyio.run(invoke) == response


def test_error_after_mutation_exposes_uncertainty_and_never_repeats(tmp_path):
    from sinnix_agent_gateway.actions import BY_NAME
    from sinnix_agent_gateway.runtime import Runtime

    runtime = Runtime.create(GatewayConfig(projects={}, state_dir=tmp_path), "operator")
    effects = []

    async def interrupted():
        effects.append("accepted")
        raise RuntimeError("connection lost after mutation")

    async def invoke():
        return await runtime.execute_v2_async(
            BY_NAME["files.change"], interrupted, {"idempotency_key": "uncertain"}
        )

    first = anyio.run(invoke)
    assert first["error"]["details"] == {
        "mutation_outcome": "indeterminate",
        "retry_safe": False,
    }
    second = anyio.run(invoke)
    assert second["error"]["code"] == "indeterminate"
    assert effects == ["accepted"]


def test_stopped_process_reconciles_without_resolving_a_live_process(tmp_path):
    import hashlib
    from types import SimpleNamespace

    from sinnix_agent_gateway.actions import BY_NAME
    from sinnix_agent_gateway.runtime import Runtime

    runtime = Runtime.create(GatewayConfig(projects={}, state_dir=tmp_path), "operator")
    expected = {"kind": "process", "pid": 424242, "start_ticks": 7}
    request = {
        "target": {"pid": 424242},
        "request": {"operation": "stop", "expected_target": expected},
        "reason": "stop fixture",
        "idempotency_key": "stop-key",
    }
    context = runtime._request_context(request)
    runtime.audit.claim_idempotency(
        "processes.signal", "stop-key", context.request_sha256
    )
    runtime.audit.abandon_idempotency("processes.signal", "stop-key")
    owner_request = {
        "action": "stop",
        "target": {"process": {"pid": 424242, "start_ticks": 7}},
        "expected_target": expected,
        "operator_reason": "stop fixture",
        "idempotency_key": "stop-key",
        "parameters": {},
    }
    receipt = {
        **owner_request,
        "schema": "sinnix-ops-action-v1",
        "status": "confirmed",
        "receipt_id": "stopped",
        "request_hash": hashlib.sha256(
            json.dumps(owner_request, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    runtime.machine_actions = SimpleNamespace(lookup=lambda key: receipt)

    async def forbidden():
        pytest.fail("stopped process must never be resolved or signaled again")

    async def invoke():
        return await runtime.execute_v2_async(
            BY_NAME["processes.signal"], forbidden, request
        )

    response = anyio.run(invoke)
    assert response["result"]["outcome"] == "ok", response
    assert response["data"]["ref"] == "sinnix://processes/424242/7"
    assert response["data"]["delivered"] is True
    assert anyio.run(invoke) == response
