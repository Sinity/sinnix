from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

from .capabilities import Capability, Principal
from .config import GatewayConfig
from sinnix_mcp.execution import EnvironmentProfile, ExecutionProfile, OwnerExecution, OwnerRoute


class ShellError(ValueError):
    pass


class ShellService:
    def __init__(
        self,
        config: GatewayConfig,
        principal: Principal,
        execution: OwnerExecution | None = None,
    ):
        self.config = config
        self.principal = principal
        self.execution = execution

    def _execution(self) -> OwnerExecution:
        return self.execution or OwnerExecution()

    def _stop(self, unit: str) -> None:
        self._execution().run(
            [self.config.systemctl_command, "--user", "stop", unit],
            ExecutionProfile(
                route=OwnerRoute("shell-cancel", EnvironmentProfile.SESSION_OPTIONAL),
                timeout_seconds=5,
                max_stdout_bytes=16_384,
                max_stderr_bytes=8_192,
            ),
        )

    def _environment(self, overlay: dict[str, str] | None = None) -> dict[str, str]:
        if overlay is not None:
            if len(overlay) > 64:
                raise ShellError("environment overlay has more than 64 variables")
            for name, value in overlay.items():
                if not name or not name.replace("_", "a").isalnum() or not name[0].isalpha():
                    raise ShellError(f"invalid environment variable name: {name!r}")
                if not isinstance(value, str) or len(value) > 8_192:
                    raise ShellError(f"invalid environment value for {name}")
        environment, _ = self._execution().environment_for(
            OwnerRoute("shell-environment", EnvironmentProfile.SESSION_OPTIONAL), overlay
        )
        return environment

    @staticmethod
    def _validate(
        argv: list[str], cwd: str, timeout_seconds: int, max_bytes: int
    ) -> tuple[Path, int]:
        if not argv or len(argv) > 128 or any(not isinstance(arg, str) for arg in argv):
            raise ShellError("argv must contain 1-128 string arguments")
        if sum(len(arg) for arg in argv) > 32_768:
            raise ShellError("argv exceeds the configured bound")
        if timeout_seconds < 1 or timeout_seconds > 3_600:
            raise ShellError("timeout_seconds must be 1-3600")
        workdir = Path(cwd).expanduser().resolve(strict=True)
        if not workdir.is_dir():
            raise ShellError("cwd is not a directory")
        return workdir, max(1, max_bytes)

    def _execute(
        self,
        *,
        unit_prefix: str,
        argv: list[str],
        cwd: str,
        timeout_seconds: int,
        max_bytes: int,
        environment: dict[str, str] | None,
        as_root: bool,
    ) -> dict[str, Any]:
        workdir, max_bytes = self._validate(argv, cwd, timeout_seconds, max_bytes)
        max_bytes = min(max_bytes, self.config.max_result_bytes)
        env_command = shutil.which("env")
        if env_command is None:
            raise ShellError("env command is unavailable")
        command_argv = list(argv)
        identity = "user"
        if as_root:
            sudo = shutil.which("sudo")
            if sudo is None:
                raise ShellError("sudo command is unavailable")
            command_argv = [sudo, "-n", "--", *command_argv]
            identity = "root"
        unit = f"{unit_prefix}-{uuid.uuid4().hex}.service"
        command = [
            self.config.systemd_run_command,
            "--user",
            "--wait",
            "--pipe",
            "--quiet",
            "--collect",
            f"--unit={unit}",
            f"--property=RuntimeMaxSec={timeout_seconds}",
            f"--property=WorkingDirectory={workdir}",
        ]
        command.extend(
            [
                "--",
                env_command,
                "-i",
                *(f"{name}={value}" for name, value in self._environment(environment).items()),
                *command_argv,
            ]
        )
        result = self._execution().run(
            command,
            ExecutionProfile(
                route=OwnerRoute("shell-run", EnvironmentProfile.SESSION_OPTIONAL),
                timeout_seconds=timeout_seconds + 10,
                max_stdout_bytes=max_bytes,
                max_stderr_bytes=max_bytes,
                max_combined_output_bytes=max_bytes,
            ),
        )
        if result.timed_out or result.output_exceeded:
            self._stop(unit)
        output = result.combined_output
        return {
            "argv": argv,
            "cwd": str(workdir),
            "identity": identity,
            "unit": unit,
            "exit_status": None if result.timed_out else result.exit_status,
            "timed_out": result.timed_out,
            "truncated": result.output_exceeded,
            "output": output.decode("utf-8", errors="replace"),
        }

    def run(
        self,
        argv: list[str],
        cwd: str = "/",
        timeout_seconds: int = 300,
        max_bytes: int = 64_000,
        environment: dict[str, str] | None = None,
        as_root: bool = False,
    ) -> dict[str, Any]:
        self.principal.require(Capability.SHELL_RUN)
        return self._execute(
            unit_prefix="sinnix-gateway-run",
            argv=argv,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            max_bytes=max_bytes,
            environment=environment,
            as_root=as_root,
        )
