from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sinnix_agent_gateway.artifacts import ArtifactError, ArtifactService
from sinnix_agent_gateway.capabilities import PolicyError, Principal
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.desktop import DesktopDiagnosticError, DesktopService
from sinnix_mcp.execution import OwnerExecution


def desktop_service(tmp_path: Path, principal_name: str) -> tuple[DesktopService, Path]:
    captured = tmp_path / "desktop-commands.jsonl"
    runner = tmp_path / "desktop-control"
    runner.write_text(
        f"#!{sys.executable}\n"
        "import json, pathlib, sys\n"
        f"with pathlib.Path({str(captured)!r}).open('a') as output:\n"
        "    output.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1] == 'capture-output':\n"
        "    output_dir = pathlib.Path(sys.argv[sys.argv.index('--out-dir') + 1])\n"
        "    raw = output_dir / 'gateway-raw.png'\n"
        "    corrected = output_dir / 'gateway-corrected.png'\n"
        "    raw.write_bytes(b'raw fixture')\n"
        "    corrected.write_bytes(b'corrected fixture')\n"
        "    print(json.dumps({'raw_files': [str(raw)], 'corrected_files': [str(corrected)], 'color_management': {'hdr': True}}))\n"
        "else:\n"
        "    print(json.dumps({'address': '0xfixture'}))\n"
    )
    runner.chmod(0o700)
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        hypr_control_command=str(runner),
        screenshot_control_command=str(runner),
    )
    principal = Principal.for_name(principal_name)
    execution = OwnerExecution(
        {
            "HOME": str(tmp_path),
            "LANG": "C.UTF-8",
            "PATH": "/run/current-system/sw/bin",
            "XDG_RUNTIME_DIR": str(tmp_path / "runtime"),
            "WAYLAND_DISPLAY": "wayland-1",
            "HYPRLAND_INSTANCE_SIGNATURE": "fixture",
        }
    )
    return DesktopService(
        config, principal, ArtifactService(config, principal), execution
    ), captured


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
        {"dispatcher": "workspace", "args": ["name:agentbrowser"]},
    )

    assert commands(captured) == [["dispatch", "workspace", "name:agentbrowser"]]


def test_observer_cannot_mutate_desktop(tmp_path: Path) -> None:
    desktop, _ = desktop_service(tmp_path, "observer")

    with pytest.raises(PolicyError, match="desktop.action"):
        desktop.action("focus_window", {"window": "address:0xfixture"})


def test_desktop_requires_wayland_environment_before_launch(tmp_path: Path) -> None:
    desktop, _ = desktop_service(tmp_path, "observer")
    desktop.execution = OwnerExecution({})

    with pytest.raises(DesktopDiagnosticError) as caught:
        desktop.read("clients")

    response = caught.value.response
    assert response["failure_class"] == "environment_unavailable:XDG_RUNTIME_DIR"
    assert response["route"] == "desktop-hypr"
    artifact = desktop.artifacts.read(str(response["diagnostic_artifact_id"]))
    assert artifact["kind"] == "owner-diagnostic"


def test_artifact_rejects_unreceipted_capture_source(tmp_path: Path) -> None:
    desktop, _ = desktop_service(tmp_path, "observer")
    source = desktop.config.state_dir / "captures" / "unreceipted.png"
    source.write_bytes(b"fixture")

    with pytest.raises(ArtifactError, match="outside attested gateway state"):
        desktop.artifacts.register(
            source,
            kind="desktop-screenshot",
            owner_id="desktop-capture",
        )


def test_desktop_capture_registers_raw_and_corrected_artifacts(tmp_path: Path) -> None:
    desktop, captured = desktop_service(tmp_path, "observer")

    result = desktop.capture_output()
    artifacts = [
        desktop.artifacts.read(artifact_id) for artifact_id in result["artifact_ids"]
    ]
    bounded = desktop.artifacts.read(result["artifact_ids"][0], max_bytes=3)

    assert result["capture"]["fix_hdr"] is True
    assert result["receipt"]["source"] == "desktop-output"
    assert result["receipt"]["target"] == {"kind": "current-output"}
    assert [artifact["base64"] for artifact in artifacts] == [
        "cmF3IGZpeHR1cmU=",
        "Y29ycmVjdGVkIGZpeHR1cmU=",
    ]
    assert bounded["base64"] == "cmF3"
    assert bounded["next_offset"] == 3
    assert "source" not in bounded
    assert commands(captured)[0][0] == "capture-output"
    assert "--fix-hdr" in commands(captured)[0]
    assert "activate" not in commands(captured)[0]
