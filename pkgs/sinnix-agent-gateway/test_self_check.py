from __future__ import annotations

from pathlib import Path

from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.self_check import GatewaySelfCheck


def make_executable(path: Path) -> None:
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o755)


def test_self_check_reports_configured_routes_and_missing_command(tmp_path: Path) -> None:
    command = tmp_path / "owner"
    make_executable(command)
    result = GatewaySelfCheck(
        GatewayConfig(
            state_dir=tmp_path / "state",
            projects={},
            observe_command=str(command),
            capture_command=str(command),
            hypr_control_command=str(command),
            screenshot_control_command=str(command),
            kitty_control_command=str(command),
            chrome_control_command=str(command),
            beads_command=str(tmp_path / "missing-bd"),
        )
    ).run()

    assert result["status"] == "degraded"
    routes = {row["route"]: row for row in result["routes"]}
    assert routes["machine.observe"] == {
        "route": "machine.observe",
        "status": "pass",
        "command": str(command),
        "absolute_configured_path": True,
    }
    assert routes["beads"] == {
        "route": "beads",
        "status": "unavailable",
        "failure_class": "command_unavailable",
        "command": str(tmp_path / "missing-bd"),
    }


def test_self_check_reports_missing_broker_environment(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    result = GatewaySelfCheck(
        GatewayConfig(
            state_dir=tmp_path / "state",
            projects={},
            mcp_broker_servers={"fixture": {"brokered": True}},
        )
    ).run()

    bus = next(row for row in result["routes"] if row["route"] == "mcp.user_bus")
    assert bus == {
        "route": "mcp.user_bus",
        "status": "degraded",
        "failure_class": "user_bus_environment_missing",
        "dbus_session_bus_address": False,
        "xdg_runtime_dir": False,
    }
