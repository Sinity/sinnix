from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pytest

from sinnix_agent_gateway.artifacts import ArtifactService
from sinnix_agent_gateway.capabilities import PolicyError, Principal
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.execution import OwnerExecution
from sinnix_agent_gateway.terminals import (
    TerminalDiagnosticError,
    TerminalError,
    TerminalService,
)


def terminal_service(tmp_path: Path, principal_name: str) -> tuple[TerminalService, Path]:
    captured = tmp_path / "terminal-commands.jsonl"
    runner = tmp_path / "kitty-control"
    runner.write_text(
        f"#!{sys.executable}\n"
        "import json, pathlib, sys\n"
        f"with pathlib.Path({str(captured)!r}).open('a') as output:\n"
        "    output.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "print(json.dumps([{'id': 7, 'tabs': []}]))\n"
    )
    runner.chmod(0o700)
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        kitty_control_command=str(runner),
    )
    execution = OwnerExecution(
        {
            "HOME": str(tmp_path),
            "LANG": "C.UTF-8",
            "PATH": "/run/current-system/sw/bin",
            "XDG_RUNTIME_DIR": str(tmp_path / "runtime"),
        }
    )
    principal = Principal.for_name(principal_name)
    return TerminalService(config, principal, ArtifactService(config, principal), execution), captured


def commands(path: Path) -> list[list[str]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_observer_can_list_terminal_inventory(tmp_path: Path) -> None:
    terminals, captured = terminal_service(tmp_path, "observer")

    result = terminals.read("list")

    assert result == {"operation": "list", "result": [{"id": 7, "tabs": []}]}
    assert commands(captured) == [["list", "--json"]]


def test_operator_sends_exact_terminal_text_vector(tmp_path: Path) -> None:
    terminals, captured = terminal_service(tmp_path, "operator")

    terminals.action(
        "send",
        {"match": "id:7", "text": "printf fixture", "enter": True},
    )

    assert commands(captured) == [
        ["send", "--match", "id:7", "--text", "printf fixture", "--enter"]
    ]


def test_observer_cannot_mutate_terminal(tmp_path: Path) -> None:
    terminals, _ = terminal_service(tmp_path, "observer")

    with pytest.raises(PolicyError, match="terminal.action"):
        terminals.action("focus", {"match": "id:7"})


def test_terminal_requires_runtime_directory_before_launch(tmp_path: Path) -> None:
    terminals, _ = terminal_service(tmp_path, "observer")
    terminals.execution = OwnerExecution({})

    with pytest.raises(TerminalError, match="environment_unavailable:XDG_RUNTIME_DIR"):
        terminals.read("list")


def test_terminal_failure_writes_redacted_diagnostic_artifact(tmp_path: Path) -> None:
    terminals, _ = terminal_service(tmp_path, "observer")
    runner = Path(terminals.config.kitty_control_command)
    runner.write_text("#!/bin/sh\nprintf 'token=fixture-secret\\n' >&2\nexit 23\n")
    runner.chmod(0o700)

    with pytest.raises(TerminalDiagnosticError) as caught:
        terminals.read("list")

    response = caught.value.response
    assert response["failure_class"] == "command_failed"
    assert response["exit_status"] == 23
    artifact = terminals.artifacts.read(str(response["diagnostic_artifact_id"]))
    diagnostic = json.loads(base64.b64decode(artifact["base64"]))
    assert artifact["kind"] == "owner-diagnostic"
    assert diagnostic["route"] == "terminal-kitty"
    assert diagnostic["stderr_excerpt"] == "token=[REDACTED]"
    assert "command" not in diagnostic
