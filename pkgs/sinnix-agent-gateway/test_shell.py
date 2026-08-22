from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import sinnix_agent_gateway.shell as shell_module
from sinnix_agent_gateway.capabilities import PolicyError, Principal
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.shell import ShellService


def shell_service(tmp_path: Path, principal_name: str) -> tuple[ShellService, Path]:
    captured = tmp_path / "systemd-run.json"
    runner = tmp_path / "systemd-run"
    runner.write_text(
        f"#!{sys.executable}\n"
        "import json, pathlib, sys\n"
        f"pathlib.Path({str(captured)!r}).write_text(json.dumps(sys.argv[1:]))\n"
        "print('query output')\n"
    )
    runner.chmod(0o700)
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        systemd_run_command=str(runner),
    )
    return ShellService(config, Principal.for_name(principal_name)), captured


def test_operator_shell_run_has_no_observer_sandbox_and_scrubs_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, captured = shell_service(tmp_path, "operator")
    monkeypatch.setenv("UNRELATED_SECRET", "must-not-reach-command")

    result = service.run(
        ["printf", "hello"],
        cwd=str(tmp_path),
        max_bytes=128,
        environment={"GATEWAY_FIXTURE": "present"},
    )
    command = json.loads(captured.read_text())

    assert result["output"] == "query output\n"
    assert result["identity"] == "user"
    assert "--property=ReadOnlyPaths=/" not in command
    assert "--property=PrivateTmp=true" not in command
    assert "--property=NoNewPrivileges=true" not in command
    assert "--property=ProtectSystem=strict" not in command
    marker = command.index("--")
    environment = command[marker + 3 : command.index("printf")]
    assert "GATEWAY_FIXTURE=present" in environment
    assert not any("UNRELATED_SECRET" in value for value in environment)


def test_operator_root_shell_run_uses_explicit_noninteractive_sudo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, captured = shell_service(tmp_path, "operator")
    monkeypatch.setattr(
        shell_module.shutil,
        "which",
        lambda program: f"/fixture/{program}",
    )

    result = service.run(["id", "-u"], cwd=str(tmp_path), as_root=True)
    command = json.loads(captured.read_text())

    assert result["identity"] == "root"
    assert command[-5:] == ["/fixture/sudo", "-n", "--", "id", "-u"]


def test_observer_cannot_run_operator_shell(tmp_path: Path) -> None:
    service, _ = shell_service(tmp_path, "observer")

    with pytest.raises(PolicyError, match="shell.run"):
        service.run(["true"], cwd=str(tmp_path))
