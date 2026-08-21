from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from sinnix_agent_gateway.capabilities import PolicyError, Principal
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.desktop import DesktopService


def desktop_service(tmp_path: Path, principal_name: str) -> tuple[DesktopService, Path]:
    captured = tmp_path / "desktop-commands.jsonl"
    runner = tmp_path / "desktop-control"
    runner.write_text(
        f"#!{sys.executable}\n"
        "import json, pathlib, sys\n"
        f"with pathlib.Path({str(captured)!r}).open('a') as output:\n"
        "    output.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "print(json.dumps({'address': '0xfixture'}))\n"
    )
    runner.chmod(0o700)
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        hypr_control_command=str(runner),
        screenshot_control_command=str(runner),
    )
    return DesktopService(config, Principal.for_name(principal_name)), captured


def commands(path: Path) -> list[list[str]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_observer_can_read_desktop_state(tmp_path: Path) -> None:
    desktop, captured = desktop_service(tmp_path, "observer")

    result = desktop.read("clients")

    assert result == {
        "operation": "clients",
        "owner": "hypr",
        "result": {"address": "0xfixture"},
    }
    assert commands(captured) == [["clients", "--json"]]


def test_operator_focus_uses_wrapper_and_verifies_active_window(tmp_path: Path) -> None:
    desktop, captured = desktop_service(tmp_path, "operator")

    result = desktop.action("focus_window", {"window": "address:0xfixture"})

    assert result["target"] == {"window": "address:0xfixture"}
    assert result["postcondition"] == {"address": "0xfixture"}
    assert commands(captured) == [
        ["focus-window", "address:0xfixture"],
        ["active-window"],
    ]


def test_operator_dispatch_uses_exact_argument_vector(tmp_path: Path) -> None:
    desktop, captured = desktop_service(tmp_path, "operator")

    desktop.action(
        "dispatch",
        {"dispatcher": "workspace", "args": ["special:agentbrowser"]},
    )

    assert commands(captured) == [["dispatch", "workspace", "special:agentbrowser"]]


def test_observer_cannot_take_desktop_action(tmp_path: Path) -> None:
    desktop, _ = desktop_service(tmp_path, "observer")

    with pytest.raises(PolicyError, match="desktop.action"):
        desktop.action("focus_window", {"window": "address:0xfixture"})
