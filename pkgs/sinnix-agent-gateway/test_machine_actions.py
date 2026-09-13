from __future__ import annotations

import json
from pathlib import Path

import pytest
from sinnix_agent_gateway.capabilities import PolicyError, Principal
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.machine_actions import (
    MachineActionError,
    MachineActionService,
)


class FakeResponse:
    def __init__(self, status: int, payload: object):
        self.status = status
        self.payload = json.dumps(payload).encode()

    def read(self, _amount: int) -> bytes:
        return self.payload


class FakeConnection:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.request_args: tuple[object, ...] | None = None
        self.closed = False

    def request(self, *args: object) -> None:
        self.request_args = args

    def getresponse(self) -> FakeResponse:
        return self.response

    def close(self) -> None:
        self.closed = True


def service(
    tmp_path: Path, principal_name: str, response: FakeResponse
) -> tuple[MachineActionService, FakeConnection]:
    connection = FakeConnection(response)
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        ops_socket_path=tmp_path / "ops.sock",
    )
    return (
        MachineActionService(
            config,
            Principal.for_name(principal_name),
            connection_factory=lambda _path: connection,
        ),
        connection,
    )


def test_machine_action_forwards_exact_owner_request(tmp_path: Path) -> None:
    receipt = {
        "schema": "sinnix-ops-action-v1",
        "receipt_id": "owner-receipt",
        "status": "accepted",
    }
    actions, connection = service(tmp_path, "operator", FakeResponse(201, receipt))

    result = actions.execute(
        "restart",
        {"unit": "fixture.service"},
        {
            "kind": "unit",
            "unit": "fixture.service",
            "manager": "user",
            "properties": {"InvocationID": "fixture-invocation"},
        },
        "gateway-fixture",
        "verify fixture restart",
    )

    assert result == receipt
    assert connection.closed is True
    assert connection.request_args is not None
    method, path, raw_body, headers = connection.request_args
    assert method == "POST"
    assert path == "/v1/actions"
    assert headers == {"Content-Type": "application/json"}
    assert json.loads(raw_body) == {
        "action": "restart",
        "target": {"unit": "fixture.service"},
        "expected_target": {
            "kind": "unit",
            "unit": "fixture.service",
            "manager": "user",
            "properties": {"InvocationID": "fixture-invocation"},
        },
        "idempotency_key": "gateway-fixture",
        "operator_reason": "verify fixture restart",
        "parameters": {},
    }


def test_machine_action_snapshot_exposes_bounded_authority_revision(
    tmp_path: Path,
) -> None:
    actions, connection = service(
        tmp_path,
        "operator",
        FakeResponse(
            200,
            {
                "schema": "sinnix-ops-v1",
                "sequence": 41,
                "observed_at": "2026-08-25T00:00:00Z",
                "degradation": None,
                "sources": {"sinnix-observe": {"status": "healthy"}},
                "state": {"intentionally": "not forwarded"},
            },
        ),
    )

    assert actions.snapshot() == {
        "available": True,
        "operation": "actions",
        "owner": "ops-reducer",
        "schema": "sinnix-ops-v1",
        "observed_at": "2026-08-25T00:00:00Z",
        "revision": 41,
        "degradation": None,
        "sources": {"sinnix-observe": {"status": "healthy"}},
    }
    assert connection.request_args == ("GET", "/v1/revision", None, {})
    assert connection.closed is True


def test_machine_action_snapshot_rejects_malformed_revision(tmp_path: Path) -> None:
    actions, _ = service(
        tmp_path,
        "operator",
        FakeResponse(
            200,
            {"schema": "sinnix-ops-v1", "sequence": True, "observed_at": "now"},
        ),
    )

    with pytest.raises(MachineActionError, match="malformed snapshot"):
        actions.snapshot()


def test_machine_action_returns_owner_rejection(tmp_path: Path) -> None:
    actions, _ = service(
        tmp_path,
        "operator",
        FakeResponse(409, {"error": "expected_target is stale"}),
    )

    with pytest.raises(MachineActionError, match="expected_target is stale"):
        actions.execute(
            "restart",
            {"unit": "fixture.service"},
            {
                "kind": "unit",
                "unit": "fixture.service",
                "manager": "user",
                "properties": {"InvocationID": "fixture-invocation"},
            },
            "gateway-fixture",
            "verify fixture restart",
        )


def test_observer_cannot_submit_machine_action(tmp_path: Path) -> None:
    actions, _ = service(tmp_path, "observer", FakeResponse(201, {}))

    with pytest.raises(PolicyError, match="machine.action"):
        actions.execute(
            "restart",
            {"unit": "fixture.service"},
            {
                "kind": "unit",
                "unit": "fixture.service",
                "manager": "user",
                "properties": {"InvocationID": "fixture-invocation"},
            },
            "gateway-fixture",
            "verify fixture restart",
        )


def test_prepare_reads_target_without_mutation_authority(tmp_path: Path) -> None:
    payload = {
        "action": "restart",
        "target": {"unit": "fixture.service"},
        "parameters": {},
        "expected_target": {
            "kind": "unit",
            "unit": "fixture.service",
            "manager": "user",
            "properties": {"InvocationID": "first"},
        },
        "observed_at": "2026-09-13T00:00:00Z",
    }
    actions, connection = service(tmp_path, "observer", FakeResponse(200, payload))
    assert actions.prepare("restart", {"unit": "fixture.service"}) == payload
    assert connection.request_args[:2] == ("POST", "/v1/actions/prepare")
    assert json.loads(connection.request_args[2]) == {
        "action": "restart",
        "target": {"unit": "fixture.service"},
        "parameters": {},
    }


def test_prepare_rejects_mismatched_target(tmp_path: Path) -> None:
    actions, _ = service(
        tmp_path,
        "observer",
        FakeResponse(
            200,
            {
                "action": "restart",
                "target": {"unit": "another.service"},
                "expected_target": {"kind": "unit"},
                "observed_at": "now",
            },
        ),
    )
    with pytest.raises(MachineActionError, match="malformed action preparation"):
        actions.prepare("restart", {"unit": "fixture.service"})


def test_lookup_distinguishes_missing_from_owner_failure(tmp_path: Path) -> None:
    actions, connection = service(
        tmp_path, "operator", FakeResponse(404, {"error": "not_found"})
    )
    assert actions.lookup("request / #") is None
    assert connection.request_args[:2] == ("GET", "/v1/actions/request%20%2F%20%23")
    actions, _ = service(
        tmp_path, "operator", FakeResponse(503, {"error": "unavailable"})
    )
    with pytest.raises(MachineActionError, match="unavailable"):
        actions.lookup("request")


def test_lookup_returns_retained_receipt(tmp_path: Path) -> None:
    receipt = {"idempotency_key": "one", "status": "accepted"}
    actions, _ = service(tmp_path, "operator", FakeResponse(200, receipt))
    assert actions.lookup("one") == receipt
