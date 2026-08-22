from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.execution import OwnerExecution
from sinnix_agent_gateway.route_preflight import GatewayRoutePreflight


def make_inventory(tmp_path: Path) -> tuple[Path, Path]:
    lane_path = tmp_path / "activity" / "clipboard"
    lane_path.mkdir(parents=True)
    (lane_path / "clipboard-index.jsonl").write_text('{"ts":1,"seq":1}\n')
    inventory = tmp_path / "runtime-inventory.json"
    inventory.write_text(
        json.dumps({"captures": [{"name": "clipboard", "path": str(lane_path)}]})
    )
    return inventory, lane_path


def make_owner_command(tmp_path: Path) -> str:
    command = tmp_path / "owner-command"
    command.write_text(
        f"#!{sys.executable}\n"
        "import json\n"
        "import sys\n"
        "arguments = sys.argv[1:]\n"
        "if arguments[:1] == ['query']:\n"
        "    lane = arguments[arguments.index('--lane') + 1]\n"
        "    value = [{'lane': lane}]\n"
        "elif arguments == ['screenshot-probe']:\n"
        "    value = {'focused': {}}\n"
        "elif arguments == ['probe']:\n"
        "    value = {'tools': {}}\n"
        "elif arguments == ['list', '--json']:\n"
        "    value = []\n"
        "elif arguments == ['status']:\n"
        "    value = {'Browser': 'fixture'}\n"
        "else:\n"
        "    value = {'schema': 'fixture'}\n"
        "print(json.dumps(value))\n"
    )
    command.chmod(0o755)
    return str(command)


def preflight(tmp_path: Path, **overrides: object) -> GatewayRoutePreflight:
    inventory, _ = make_inventory(tmp_path)
    command = make_owner_command(tmp_path)
    config_values = {
        "state_dir": tmp_path / "state",
        "projects": {},
        "runtime_inventory": inventory,
        "observe_command": command,
        "capture_command": command,
        "hypr_control_command": command,
        "screenshot_control_command": command,
        "kitty_control_command": command,
        "chrome_control_command": command,
        "beads_command": command,
    }
    config_values.update(overrides)
    config = GatewayConfig(**config_values)
    execution = OwnerExecution(
        {
            "HOME": str(tmp_path),
            "LANG": "C.UTF-8",
            "PATH": os.environ["PATH"],
            "XDG_RUNTIME_DIR": str(tmp_path / "runtime"),
            "WAYLAND_DISPLAY": "wayland-fixture",
            "HYPRLAND_INSTANCE_SIGNATURE": "fixture",
        }
    )
    return GatewayRoutePreflight(config, execution)


def test_route_preflight_probes_configured_owner_routes(tmp_path: Path) -> None:
    result = preflight(tmp_path).run()

    assert result["status"] == "ready"
    routes = {route["route"]: route for route in result["routes"]}
    assert routes["machine.observe"]["status"] == "pass"
    assert routes["capture.query"] == {
        "route": "capture.query",
        "command": [
            str(tmp_path / "owner-command"),
            "query",
            "--capture-root",
            str(tmp_path / "activity"),
            "--since",
            "0",
            "--lane",
            "clipboard",
        ],
        "decoder": "json_lane_summary_list",
        "timeout_seconds": 5,
        "stdout_bytes": len('[{"lane": "clipboard"}]\n'),
        "stderr_bytes": 0,
        "exit_status": 0,
        "status": "pass",
    }
    assert routes["desktop.hypr"]["decoder"] == "json_object_with_focused"
    assert routes["desktop.screenshot"]["decoder"] == "json_object_with_tools"
    assert routes["terminal.kitty"]["decoder"] == "json_list"
    assert routes["browser.chrome"]["decoder"] == "json_object_with_browser"


def test_route_preflight_reports_missing_owner_command(tmp_path: Path) -> None:
    result = preflight(
        tmp_path,
        capture_command="missing-command",
    ).run()

    assert result["status"] == "degraded"
    routes = {route["route"]: route for route in result["routes"]}
    assert routes["capture.query"] == {
        "route": "capture.query",
        "command": [
            "missing-command",
            "query",
            "--capture-root",
            str(tmp_path / "activity"),
            "--since",
            "0",
            "--lane",
            "clipboard",
        ],
        "decoder": "json_lane_summary_list",
        "timeout_seconds": 5,
        "stdout_bytes": 0,
        "stderr_bytes": 0,
        "exit_status": None,
        "status": "unavailable",
        "failure_class": "command_unavailable:FileNotFoundError",
    }


def test_route_preflight_reports_missing_broker_environment(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)

    result = preflight(
        tmp_path,
        mcp_broker_servers={"fixture": {"brokered": True}},
    ).run()

    assert result["status"] == "degraded"
    assert result["routes"][-1] == {
        "route": "mcp.user_bus",
        "status": "degraded",
        "failure_class": "user_bus_environment_missing",
        "dbus_session_bus_address": False,
        "xdg_runtime_dir": False,
    }


def test_route_preflight_reports_missing_queryable_lane(tmp_path: Path) -> None:
    inventory = tmp_path / "runtime-inventory.json"
    inventory.write_text(json.dumps({"captures": []}))
    command = make_owner_command(tmp_path)
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        runtime_inventory=inventory,
        observe_command=command,
        capture_command=command,
        hypr_control_command=command,
        screenshot_control_command=command,
        kitty_control_command=command,
        chrome_control_command=command,
        beads_command=command,
    )

    result = GatewayRoutePreflight(config).run()

    routes = {route["route"]: route for route in result["routes"]}
    assert routes["capture.query"] == {
        "route": "capture.query",
        "status": "unavailable",
        "failure_class": "queryable_lane_unavailable",
    }
