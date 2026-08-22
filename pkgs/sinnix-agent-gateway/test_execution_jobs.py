from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from sinnix_agent_gateway.artifacts import ArtifactService
from sinnix_agent_gateway.capabilities import Principal
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.execution import OwnerExecution
from sinnix_agent_gateway.execution_job import main as execution_job_main
from sinnix_agent_gateway.jobs import JobError, JobService


def proc_start(pid: int) -> str:
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[-1].split()
    return fields[19]


def execution_service(tmp_path: Path) -> tuple[JobService, Path]:
    captured = tmp_path / "execution-request.json"
    scope = tmp_path / "scope-exec"
    scope.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        "if '--allow-nested-scope' not in sys.argv: raise SystemExit('nested scope flag required')\n"
        "unit = sys.argv[sys.argv.index('--unit') + 1]\n"
        "command = sys.argv[sys.argv.index('--') + 1:]\n"
        "os.environ['SINNIX_AGENT_SCOPE_UNIT'] = unit\n"
        "os.execvpe(command[0], command, os.environ)\n"
    )
    scope.chmod(0o700)
    runner = tmp_path / "execution-job"
    runner.write_text(
        f"#!{sys.executable}\n"
        "import argparse, json, os, pathlib\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--job-id', required=True)\n"
        "parser.add_argument('--launch-id', required=True)\n"
        "parser.add_argument('--state-dir', required=True)\n"
        "parser.add_argument('--request', required=True)\n"
        "parser.add_argument('--scope-unit', required=True)\n"
        "args = parser.parse_args()\n"
        "request = json.loads(pathlib.Path(args.request).read_text())\n"
        f"pathlib.Path({str(captured)!r}).write_text(json.dumps(request))\n"
        "root = pathlib.Path(args.state_dir)\n"
        "(root / f'{args.job_id}.log').write_text('fixture output')\n"
        "stat = pathlib.Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(') ', 1)[-1].split()\n"
        "manifest = {\n"
        "  'schema_version': 4, 'kind': 'shell', 'job_id': args.job_id,\n"
        "  'launch_id': args.launch_id, 'lifecycle': 'running',\n"
        "  'command': {'argv': request['argv'], 'cwd': request['cwd'], 'identity': request['identity']},\n"
        "  'artifacts': {'log': str(root / f'{args.job_id}.log')},\n"
        "  'launcher': {'pid': os.getpid(), 'proc_start': stat[19],\n"
        "               'scope_unit': args.scope_unit, 'cgroup': '/fixture'},\n"
        "}\n"
        "(root / f'{args.job_id}.json').write_text(json.dumps(manifest))\n"
    )
    runner.chmod(0o700)
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={},
        agent_scope_exec_command=str(scope),
        execution_job_command=str(runner),
    )
    principal = Principal.for_name("operator")
    return JobService(config, principal, ArtifactService(config, principal)), captured


def test_gateway_config_loads_execution_commands(tmp_path: Path) -> None:
    config_path = tmp_path / "gateway.json"
    config_path.write_text(
        json.dumps(
            {
                "stateDir": str(tmp_path / "state"),
                "projects": {},
                "agentScopeExecCommand": "/fixture/scope-exec",
                "executionJobCommand": "/fixture/execution-job",
            }
        )
    )

    config = GatewayConfig.load(config_path)

    assert config.agent_scope_exec_command == "/fixture/scope-exec"
    assert config.execution_job_command == "/fixture/execution-job"


def test_execution_helper_rejects_unreserved_launch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = "unreserved-shell"
    launch_id = "unreserved-launch"
    scope_unit = f"sinnix-gateway-exec-{job_id}.scope"
    request = tmp_path / "request.json"
    request.write_text(json.dumps({"job_id": job_id, "launch_id": launch_id}))
    monkeypatch.setenv("SINNIX_AGENT_SCOPE_UNIT", scope_unit)

    with pytest.raises(SystemExit, match="reservation"):
        execution_job_main(
            [
                "--job-id",
                job_id,
                "--launch-id",
                launch_id,
                "--state-dir",
                str(tmp_path),
                "--request",
                str(request),
                "--scope-unit",
                scope_unit,
            ]
        )


def test_execution_helper_runs_command_and_writes_attestation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = "shell-helper"
    launch_id = "launch-helper"
    scope_unit = f"sinnix-gateway-exec-{job_id}.scope"
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "job_id": job_id,
                "launch_id": launch_id,
                "argv": [
                    sys.executable,
                    "-c",
                    "import os; print(os.environ['WAYLAND_DISPLAY'])",
                ],
                "cwd": str(tmp_path),
                "identity": "user",
                "environment": {
                    "HOME": "/home/fixture",
                    "LANG": "C.UTF-8",
                    "PATH": "/fixture/bin",
                    "WAYLAND_DISPLAY": "fixture-wayland",
                },
                "timeout_seconds": 1,
            }
        )
    )
    reservation = tmp_path / ".reservations" / job_id
    reservation.mkdir(parents=True)
    (reservation / "launch-id").write_text(launch_id)
    monkeypatch.setenv("SINNIX_AGENT_SCOPE_UNIT", scope_unit)

    result = execution_job_main(
        [
            "--job-id",
            job_id,
            "--launch-id",
            launch_id,
            "--state-dir",
            str(tmp_path),
            "--request",
            str(request),
            "--scope-unit",
            scope_unit,
        ]
    )

    manifest = json.loads((tmp_path / f"{job_id}.json").read_text())
    assert result == 0
    assert manifest["lifecycle"] == "succeeded"
    assert manifest["launcher"]["scope_unit"] == scope_unit
    assert manifest["launcher"]["cwd"] == str(Path.cwd().resolve())
    assert (tmp_path / f"{job_id}.log").read_text() == "fixture-wayland\n"
    assert not request.exists()


def test_execution_helper_records_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = "shell-timeout"
    launch_id = "launch-timeout"
    scope_unit = f"sinnix-gateway-exec-{job_id}.scope"
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "job_id": job_id,
                "launch_id": launch_id,
                "argv": [sys.executable, "-c", "import time; time.sleep(30)"],
                "cwd": str(tmp_path),
                "identity": "user",
                "environment": dict(os.environ),
                "timeout_seconds": 1,
            }
        )
    )
    reservation = tmp_path / ".reservations" / job_id
    reservation.mkdir(parents=True)
    (reservation / "launch-id").write_text(launch_id)
    monkeypatch.setenv("SINNIX_AGENT_SCOPE_UNIT", scope_unit)

    result = execution_job_main(
        [
            "--job-id",
            job_id,
            "--launch-id",
            launch_id,
            "--state-dir",
            str(tmp_path),
            "--request",
            str(request),
            "--scope-unit",
            scope_unit,
        ]
    )

    manifest = json.loads((tmp_path / f"{job_id}.json").read_text())
    assert result == 124
    assert manifest["lifecycle"] == "timed_out"
    assert manifest["exit_status"] == 124


def test_start_shell_creates_attested_execution_job(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    jobs, captured = execution_service(tmp_path)
    calls = []
    original_start = OwnerExecution.start

    def record_start(self: OwnerExecution, *args: object, **kwargs: object) -> object:
        calls.append(args[1])
        return original_start(self, *args, **kwargs)

    monkeypatch.setattr(OwnerExecution, "start", record_start)
    monkeypatch.setenv("SINNIX_GATEWAY_PROBE_SECRET", "must-not-propagate")

    result = jobs.start_shell(["printf", "fixture"], cwd=str(tmp_path))

    request = json.loads(captured.read_text())
    manifest = jobs._load(result["job_id"])
    assert result["accepted"] is True
    assert result["kind"] == "shell"
    assert result["unit"] == f"sinnix-gateway-exec-{result['job_id']}.scope"
    assert request["argv"] == ["printf", "fixture"]
    assert request["identity"] == "user"
    assert "SINNIX_GATEWAY_PROBE_SECRET" not in request["environment"]
    assert any(getattr(profile.route, "name", None) == "execution-job-launch" for profile in calls)
    assert manifest["schema_version"] == 4
    assert manifest["kind"] == "shell"


def test_start_shell_uses_explicit_sudo_for_root_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs, captured = execution_service(tmp_path)
    sudo = tmp_path / "sudo"
    sudo.write_text("#!/bin/sh\nexit 0\n")
    sudo.chmod(0o700)
    original_which = shutil.which

    def which(command: str, *args: object, **kwargs: object) -> str | None:
        return str(sudo) if command == "sudo" else original_which(command, *args, **kwargs)

    monkeypatch.setattr("sinnix_agent_gateway.jobs.shutil.which", which)

    result = jobs.start_shell(["id", "-u"], cwd=str(tmp_path), as_root=True)

    request = json.loads(captured.read_text())
    assert result["identity"] == "root"
    assert request["identity"] == "root"
    assert request["argv"] == [str(sudo), "-n", "--", "id", "-u"]


def test_shell_status_hides_raw_argv_and_keeps_output_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    jobs, _ = execution_service(tmp_path)
    job_id = "shell-status"
    log = jobs.root / f"{job_id}.log"
    log.write_text("fixture output")
    (jobs.root / f"{job_id}.json").write_text(
        json.dumps(
            {
                "schema_version": 4,
                "kind": "shell",
                "job_id": job_id,
                "lifecycle": "running",
                "command": {
                    "argv": ["secret-command", "credential"],
                    "argv_sha256": "fixture-digest",
                    "cwd": str(tmp_path),
                    "identity": "user",
                },
                "artifacts": {"log": str(log)},
                "launcher": {"scope_unit": f"sinnix-gateway-exec-{job_id}.scope"},
            }
        )
    )
    monkeypatch.setattr(
        jobs,
        "_shell_live",
        lambda _unit: {"available": True, "ActiveState": "active"},
    )

    status = jobs.status(job_id)
    output = jobs.read_output(job_id)

    assert status["command"]["argv"] == {
        "count": 2,
        "executable": "secret-command",
        "sha256": "fixture-digest",
    }
    assert "credential" not in json.dumps(status)
    assert output["base64"] == "Zml4dHVyZSBvdXRwdXQ="


def test_shell_cancel_rejects_cgroup_mismatch_before_systemd_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs, _ = execution_service(tmp_path)
    job_id = "shell-cancel"
    manifest = {
        "schema_version": 4,
        "kind": "shell",
        "job_id": job_id,
        "lifecycle": "running",
        "command": {"cwd": str(tmp_path)},
        "launcher": {
            "pid": os.getpid(),
            "proc_start": proc_start(os.getpid()),
            "scope_unit": f"sinnix-gateway-exec-{job_id}.scope",
            "cgroup": "/wrong-cgroup",
        },
    }
    (jobs.root / f"{job_id}.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(jobs, "_cgroup_for_pid", lambda _pid: "/actual-cgroup")

    with pytest.raises(JobError, match="process identity"):
        jobs.cancel(job_id)


def test_shell_cancel_rejects_launcher_cwd_mismatch_before_systemd_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs, _ = execution_service(tmp_path)
    job_id = "shell-cancel-cwd"
    actual_cgroup = jobs._cgroup_for_pid(os.getpid())
    manifest = {
        "schema_version": 4,
        "kind": "shell",
        "job_id": job_id,
        "lifecycle": "running",
        "command": {"cwd": str(tmp_path)},
        "launcher": {
            "pid": os.getpid(),
            "proc_start": proc_start(os.getpid()),
            "cwd": str(tmp_path),
            "scope_unit": f"sinnix-gateway-exec-{job_id}.scope",
            "cgroup": actual_cgroup,
        },
    }
    (jobs.root / f"{job_id}.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(
        jobs,
        "_shell_live",
        lambda unit: {"available": True, "ControlGroup": actual_cgroup, "unit": unit},
    )

    with pytest.raises(JobError, match="launcher directory"):
        jobs.cancel(job_id)
