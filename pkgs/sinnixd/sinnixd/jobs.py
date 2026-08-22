from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID, uuid4

from .projects import ProjectAdapter, ProjectOperation

DEFAULT_TIMEOUT_SECONDS = 3_600
JOB_UNIT_PREFIX = "sinnixd-job-"


class SystemdJobError(RuntimeError):
    """Raised when systemd cannot create or inspect a declared job service."""


class SystemdJobs(Protocol):
    """The systemd boundary for declared project-operation services."""

    def start(
        self,
        *,
        unit: str,
        command: Sequence[str],
        working_directory: str,
        environment: Mapping[str, str],
        timeout_seconds: int,
    ) -> None: ...

    def show(self, unit: str) -> Mapping[str, str]: ...

    def stop(self, unit: str) -> None: ...


@dataclass(frozen=True)
class UserSystemdJobs:
    """Launch and inspect transient user services through the user manager."""

    def start(
        self,
        *,
        unit: str,
        command: Sequence[str],
        working_directory: str,
        environment: Mapping[str, str],
        timeout_seconds: int,
    ) -> None:
        args = [
            "systemd-run",
            "--user",
            "--service",
            "--quiet",
            f"--unit={unit}",
            "--slice=agent.slice",
            f"--property=WorkingDirectory={working_directory}",
            f"--property=RuntimeMaxSec={timeout_seconds}s",
            "--property=ClearEnvironment=yes",
        ]
        args.extend(f"--setenv={key}={value}" for key, value in sorted(environment.items()))
        args.extend(["--", *command])
        self._run(args)

    def show(self, unit: str) -> Mapping[str, str]:
        output = self._run(
            [
                "systemctl",
                "--user",
                "show",
                unit,
                "--property=ActiveState",
                "--property=SubState",
                "--property=MainPID",
                "--property=Result",
                "--property=ExecMainCode",
                "--property=ExecMainStatus",
                "--property=ControlGroup",
                "--property=InvocationID",
            ]
        )
        return dict(line.split("=", 1) for line in output.splitlines() if "=" in line)

    def stop(self, unit: str) -> None:
        self._run(["systemctl", "--user", "stop", unit])

    @staticmethod
    def _run(args: Sequence[str]) -> str:
        try:
            result = subprocess.run(
                args,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as error:
            raise SystemdJobError(f"systemd command is unavailable: {args[0]}") from error
        except subprocess.CalledProcessError as error:
            detail = error.stderr.strip() or error.stdout.strip() or str(error)
            raise SystemdJobError(detail) from error
        return result.stdout


def job_unit_name(job_id: str) -> str:
    try:
        parsed = UUID(job_id)
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError("job_id must be a UUID") from error
    return f"{JOB_UNIT_PREFIX}{parsed}.service"


@dataclass(frozen=True)
class DeclaredProjectJobs:
    """Start only catalogued project operations as transient user services."""

    systemd: SystemdJobs
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    def start(
        self,
        *,
        project: ProjectAdapter,
        operation: ProjectOperation,
        correlation_id: str,
    ) -> dict[str, Any]:
        job_id = str(uuid4())
        unit = job_unit_name(job_id)
        command = (*project.environment.command, *operation.command)
        environment = self._environment(
            project=project,
            operation=operation,
            job_id=job_id,
            correlation_id=correlation_id,
        )
        self.systemd.start(
            unit=unit,
            command=command,
            working_directory=str(project.root),
            environment=environment,
            timeout_seconds=self.timeout_seconds,
        )
        return {
            "job_id": job_id,
            "unit": unit,
            "project_id": project.project_id,
            "operation": operation.name,
            "command": list(command),
            "timeout_seconds": self.timeout_seconds,
        }

    def status(self, job_id: str) -> dict[str, Any]:
        unit = job_unit_name(job_id)
        return {
            "job_id": job_id,
            "unit": unit,
            "systemd": dict(self.systemd.show(unit)),
        }

    def cancel(self, job_id: str) -> dict[str, Any]:
        unit = job_unit_name(job_id)
        self.systemd.stop(unit)
        return {"job_id": job_id, "unit": unit, "cancel_requested": True}

    @staticmethod
    def _environment(
        *,
        project: ProjectAdapter,
        operation: ProjectOperation,
        job_id: str,
        correlation_id: str,
    ) -> dict[str, str]:
        environment = {
            key: os.environ[key]
            for key in project.environment.inherit
            if key in os.environ and key not in project.environment.unset
        }
        environment["PATH"] = os.environ.get("PATH", "/run/current-system/sw/bin")
        environment.update(
            {
                "SINNIXD_JOB_ID": job_id,
                "SINNIXD_CORRELATION_ID": correlation_id,
                "SINNIXD_PROJECT_ID": project.project_id,
                "SINNIXD_OPERATION": operation.name,
            }
        )
        return environment
