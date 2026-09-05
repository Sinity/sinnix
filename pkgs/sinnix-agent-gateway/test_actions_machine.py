"""Typed machine actions: observe sections, systemd units, reducer operations."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import anyio
from mcp.types import CallToolResult
from sinnix_agent_gateway.action import Action
from sinnix_agent_gateway.actions import machine
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.locators import UnitLocator
from sinnix_agent_gateway.runtime import Runtime
from sinnix_agent_gateway.tooling import build_tool

BY_NAME = {action.name: action for action in machine.ACTIONS}


def call(
    runtime: Runtime, name: str, arguments: dict, actions: dict[str, Action] = BY_NAME
) -> dict:
    tool = build_tool(actions[name], runtime)

    async def invoke():
        return await tool.fn(**arguments)

    result = anyio.run(invoke)
    if isinstance(result, CallToolResult):
        assert result.structured_content is not None
        return result.structured_content
    return result


def script(path: Path, body: str) -> Path:
    path.write_text(f"#!{sys.executable}\nimport json, sys\n{body}")
    path.chmod(0o700)
    return path


UNITS = [
    {
        "unit": "alpha.service",
        "load": "loaded",
        "active": "active",
        "sub": "running",
        "description": "Alpha",
    },
    {
        "unit": "beta.service",
        "load": "loaded",
        "active": "failed",
        "sub": "failed",
        "description": "Beta",
    },
    {
        "unit": "gamma.timer",
        "load": "loaded",
        "active": "active",
        "sub": "waiting",
        "description": "Gamma",
    },
]


def fake_systemctl(tmp_path: Path) -> Path:
    return script(
        tmp_path / "systemctl",
        """
argv = sys.argv[1:]
if "list-units" in argv:
    print(json.dumps(%s)); sys.exit(0)
if "show" in argv:
    unit = [a for a in argv if not a.startswith("-") and a not in ("show", "--user", "--system") and a != "-p"][0]
    props = argv[argv.index("-p") + 1 :: 2]
    if unit == "missing.service":
        print("LoadState=not-found\\nActiveState=inactive\\nSubState=dead\\nMainPID=0\\nControlGroup=")
        sys.exit(0)
    values = {"LoadState": "loaded", "ActiveState": "active", "SubState": "running", "MainPID": str(%d), "ControlGroup": "/user.slice/user-1000.slice/user@1000.service/app.slice/" + unit, "Id": unit, "NRestarts": "2"}
    for p in props:
        print(f"{p}={values.get(p, '')}")
    sys.exit(0)
sys.exit(2)
"""
        % (json.dumps(UNITS), __import__("os").getpid()),
    )


def fake_journalctl(tmp_path: Path) -> Path:
    return script(
        tmp_path / "journalctl",
        """
Path = __import__("pathlib").Path
Path(sys.argv[0] + ".args").write_text(json.dumps(sys.argv[1:]))
rows = [
    {"MESSAGE": "started", "PRIORITY": "6", "__REALTIME_TIMESTAMP": "1700000000000000", "_PID": "42", "SYSLOG_IDENTIFIER": "alpha", "__CURSOR": "c1"},
    {"MESSAGE": [104, 105], "PRIORITY": "3", "__REALTIME_TIMESTAMP": "1700000001000000", "_PID": "42", "_COMM": "alpha", "__CURSOR": "c2"},
]
for row in rows:
    print(json.dumps(row))
""",
    )


def fake_observe(tmp_path: Path) -> Path:
    report = {
        "schema": "sinnix.observe.v1",
        "generated_at": "2026-08-21T00:00:00Z",
        "window": {},
        "live_pressure": {"cpu": {"some": {"avg10": 0.5}}},
        "storage": {"mounts": [{"path": "/realm"}]},
        "systemd_units": UNITS,
        "resource_slices": [{"slice": "agent.slice"}],
        "blocked_tasks": [],
    }
    return script(
        tmp_path / "observe",
        """
report = %s
section = sys.argv[sys.argv.index("--section") + 1]
key = {"units": "systemd_units", "slices": "resource_slices", "blocked_tasks": "blocked_tasks"}.get(section)
if key:
    cursor = int(sys.argv[sys.argv.index("--cursor") + 1]); limit = int(sys.argv[sys.argv.index("--page-limit") + 1])
    rows = report[key]; page = rows[cursor:cursor + limit]
    report[key] = {"total": len(rows), "cursor": cursor, "next_cursor": cursor + len(page) if cursor + len(page) < len(rows) else None, "rows": page}
print(json.dumps(report))
"""
        % json.dumps(report),
    )


class FakeResponse:
    def __init__(self, status: int, payload: object):
        self.status = status
        self.payload = json.dumps(payload).encode()

    def read(self, _amount: int) -> bytes:
        return self.payload


class FakeConnection:
    def __init__(self, responses: dict[str, FakeResponse]):
        self.responses = responses
        self.requests: list[tuple] = []

    def request(self, method, path, body=None, headers=None) -> None:
        self.requests.append((method, path, json.loads(body) if body else None))
        self.current = self.responses[path]

    def getresponse(self) -> FakeResponse:
        return self.current

    def close(self) -> None:
        pass


def make_runtime(tmp_path: Path, principal: str = "operator") -> Runtime:
    transitions = tmp_path / "transitions.jsonl"
    transitions.write_text(
        '{"unit":"beta.service","to":"failed"}\n{"unit":"alpha.service","to":"active"}\n'
    )
    cfg = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        systemctl_command=str(fake_systemctl(tmp_path)),
        journalctl_command=str(fake_journalctl(tmp_path)),
        observe_command=str(fake_observe(tmp_path)),
        runtime_transitions=transitions,
        ops_socket_path=tmp_path / "ops.sock",
    )
    runtime = Runtime.create(cfg, principal)
    receipt = {
        "schema": "sinnix-ops-action-v1",
        "receipt_id": "owner-receipt",
        "idempotency_key": "restart-alpha",
        "action": "restart",
        "target": {"unit": "alpha.service"},
        "operator_reason": "test",
        "expected_revision": 17,
        "status": "accepted",
    }
    connection = FakeConnection(
        {
            "/v1/revision": FakeResponse(
                200,
                {
                    "schema": "sinnix-ops-v1",
                    "sequence": 17,
                    "observed_at": "2026-08-25T00:00:00Z",
                    "degradation": None,
                    "sources": {},
                },
            ),
            "/v1/actions": FakeResponse(201, receipt),
        }
    )
    runtime.machine_actions.connection_factory = lambda _path: connection
    runtime._fake_connection = connection  # type: ignore[attr-defined]
    return runtime


def test_unit_locator_forms() -> None:
    assert UnitLocator(name="alpha").resolve() == (
        "alpha.service",
        "user",
        "sinnix://machine/units/user/alpha.service",
    )
    assert (
        UnitLocator(name="gamma.timer", scope="system").resolve()[2]
        == "sinnix://machine/units/system/gamma.timer"
    )
    assert UnitLocator(ref="sinnix://machine/units/system/x.service").resolve() == (
        "x.service",
        "system",
        "sinnix://machine/units/system/x.service",
    )


def test_units_list_get_logs(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    listing = call(
        runtime, "machine.units.list", {"scope": "user", "pattern": "*.service"}
    )["data"]
    assert [row["unit"] for row in listing["units"]] == [
        "alpha.service",
        "beta.service",
    ]
    assert listing["units"][0]["ref"] == "sinnix://machine/units/user/alpha.service"

    detail = call(runtime, "machine.units.get", {"target": {"name": "alpha"}})["data"]
    assert detail["active"] == "running" or detail["active"] == "active"
    assert detail["main_pid"] == __import__("os").getpid()
    assert detail["process_ref"].startswith("sinnix://processes/")
    assert detail["properties"]["NRestarts"] == "2"

    missing = call(runtime, "machine.units.get", {"target": {"name": "missing"}})
    assert missing["error"]["code"] == "not_found"

    logs = call(
        runtime,
        "machine.units.logs",
        {"target": {"name": "alpha"}, "lines": 5, "since": "-1h", "priority": "err"},
    )["data"]
    assert [entry["message"] for entry in logs["entries"]] == ["started", "hi"]
    assert logs["entries"][0]["at"].startswith("2023-11-14T22:13:20")
    assert logs["entries"][1]["identifier"] == "alpha"
    args = json.loads((tmp_path / "journalctl.args").read_text())
    assert args[:6] == ["--user", "-o", "json", "--no-pager", "-u", "alpha.service"]
    assert "--since" in args and "-p" in args


def test_query_sections_and_actions_revision(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    units = call(
        runtime, "machine.query", {"operation": "units", "cursor": 1, "limit": 1}
    )["data"]
    assert units["available"] and units["total"] == 3 and units["next_cursor"] == 2
    assert units["rows"][0]["unit"] == "beta.service"
    revision = call(runtime, "machine.query", {"operation": "actions"})["data"]
    assert revision["revision"] == 17 and revision["schema_name"] == "sinnix-ops-v1"
    bad = call(runtime, "machine.query", {"operation": "actions", "cursor": 3})
    assert bad["error"]["code"] == "invalid_request"


def test_snapshot_composes_sections_with_availability(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path, "observer")
    data = call(runtime, "machine.snapshot", {})["data"]
    assert data["load"]["available"] and "1m" in data["load"]["data"]
    assert data["memory"]["data"]["bytes"]["MemTotal"] > 0
    assert data["pressure"]["data"] == {"cpu": {"some": {"avg10": 0.5}}}
    assert data["disks"]["data"] == {"mounts": [{"path": "/realm"}]}
    assert [row["unit"] for row in data["units"]["data"]["notable"]] == ["beta.service"]
    assert data["gpu"]["available"] is False and data["network"]["available"] is False
    assert data["incidents"]["data"][-1] == {"unit": "alpha.service", "to": "active"}
    assert data["ops_revision"]["data"]["revision"] == 17


def test_operate_and_units_operate_go_through_reducer(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    result = call(
        runtime,
        "machine.operate",
        {
            "target": "sinnix://machine/units/user/alpha.service",
            "request": {"action": "restart"},
            "reason": "test",
            "expected_revision": 17,
            "idempotency_key": "restart-alpha",
        },
    )
    assert result["result"]["outcome"] == "ok", result
    assert result["data"]["owner_receipt"]["receipt_id"] == "owner-receipt"
    method, path, body = runtime._fake_connection.requests[-1]  # type: ignore[attr-defined]
    assert (method, path) == ("POST", "/v1/actions")
    assert body == {
        "action": "restart",
        "target": {"unit": "alpha.service"},
        "expected_revision": 17,
        "idempotency_key": "restart-alpha",
        "operator_reason": "test",
        "parameters": {},
    }

    units = call(
        runtime,
        "machine.units.operate",
        {
            "target": {"name": "alpha"},
            "action": "restart",
            "reason": "test",
            "preconditions": {"expected_revision": 17},
            "idempotency_key": "restart-alpha",
        },
    )
    assert units["result"]["outcome"] == "ok", units
    assert units["data"]["ref"] == "sinnix://machine/units/user/alpha.service"

    no_reason = call(
        runtime,
        "machine.operate",
        {
            "target": "sinnix://machine/units/user/alpha.service",
            "request": {"action": "restart"},
            "expected_revision": 17,
            "idempotency_key": "k2",
        },
    )
    assert no_reason["error"]["code"] == "invalid_request"
    no_revision = call(
        runtime,
        "machine.operate",
        {
            "target": "sinnix://machine/units/user/alpha.service",
            "request": {"action": "restart"},
            "reason": "r",
            "idempotency_key": "k3",
        },
    )
    assert no_revision["error"]["code"] == "precondition_failed"


def test_observer_cannot_operate(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path, "observer")
    denied = call(
        runtime,
        "machine.units.operate",
        {
            "target": {"name": "alpha"},
            "action": "stop",
            "reason": "r",
            "expected_revision": 17,
            "idempotency_key": "k",
        },
    )
    assert denied["error"]["code"] == "policy_denied"
