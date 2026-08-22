from __future__ import annotations

from pathlib import Path

from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.route_preflight import GatewayRoutePreflight


def test_route_preflight_reports_configured_routes_and_missing_command(tmp_path: Path) -> None:
    command = tmp_path / "command"
    command.write_text("#!/bin/sh\n")
    command.chmod(0o755)
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        observe_command=str(command),
        capture_command="missing-command",
        hypr_control_command=str(command),
        screenshot_control_command=str(command),
        kitty_control_command=str(command),
        chrome_control_command=str(command),
        beads_command=str(command),
    )

    result = GatewayRoutePreflight(config).run()

    assert result["status"] == "degraded"
    routes = {route["route"]: route for route in result["routes"]}
    assert routes["machine.observe"]["status"] == "pass"
    assert routes["capture.query"] == {
        "route": "capture.query",
        "status": "unavailable",
        "failure_class": "command_unavailable",
        "command": "missing-command",
    }


def test_route_preflight_reports_missing_broker_environment(tmp_path: Path, monkeypatch) -> None:
    command = tmp_path / "command"
    command.write_text("#!/bin/sh\n")
    command.chmod(0o755)
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        observe_command=str(command),
        capture_command=str(command),
        hypr_control_command=str(command),
        screenshot_control_command=str(command),
        kitty_control_command=str(command),
        chrome_control_command=str(command),
        beads_command=str(command),
        mcp_broker_servers={"fixture": {"brokered": True}},
    )

    result = GatewayRoutePreflight(config).run()

    assert result["status"] == "degraded"
    assert result["routes"][-1] == {
        "route": "mcp.user_bus",
        "status": "degraded",
        "failure_class": "user_bus_environment_missing",
        "dbus_session_bus_address": False,
        "xdg_runtime_dir": False,
    }
