from __future__ import annotations

import os
import select
import signal
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from .capabilities import Capability, Principal
from .config import GatewayConfig


class ShellError(ValueError):
    pass


class ShellService:
    def __init__(self, config: GatewayConfig, principal: Principal):
        self.config = config
        self.principal = principal

    def _stop(self, unit: str) -> None:
        subprocess.run(
            [self.config.systemctl_command, "--user", "stop", unit],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    def query(
        self,
        argv: list[str],
        cwd: str = "/",
        timeout_seconds: int = 30,
        max_bytes: int = 64_000,
    ) -> dict[str, Any]:
        self.principal.require(Capability.SHELL_QUERY)
        if not argv or len(argv) > 128 or any(not isinstance(arg, str) for arg in argv):
            raise ShellError("argv must contain 1-128 string arguments")
        if sum(len(arg) for arg in argv) > 32_768:
            raise ShellError("argv exceeds the configured bound")
        if timeout_seconds < 1 or timeout_seconds > 300:
            raise ShellError("timeout_seconds must be 1-300")
        max_bytes = max(1, min(max_bytes, self.config.max_result_bytes))
        workdir = Path(cwd).expanduser().resolve(strict=True)
        if not workdir.is_dir():
            raise ShellError("cwd is not a directory")
        unit = f"sinnix-gateway-query-{uuid.uuid4().hex}.service"
        env_command = shutil.which("env")
        if env_command is None:
            raise ShellError("env command is unavailable")
        environment = {
            "HOME": os.environ.get("HOME", "/home/sinity"),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "PATH": os.environ.get("PATH", "/run/current-system/sw/bin"),
        }
        for name in ("DBUS_SESSION_BUS_ADDRESS", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR"):
            value = os.environ.get(name)
            if value:
                environment[name] = value
        command = [
            self.config.systemd_run_command,
            "--user",
            "--wait",
            "--pipe",
            "--quiet",
            "--collect",
            f"--unit={unit}",
            "--property=ReadOnlyPaths=/",
            "--property=PrivateTmp=true",
            "--property=NoNewPrivileges=true",
            "--property=ProtectSystem=strict",
            "--property=ProtectHome=read-only",
            f"--property=RuntimeMaxSec={timeout_seconds}",
            f"--property=WorkingDirectory={workdir}",
            "--",
            env_command,
            "-i",
            *(f"{name}={value}" for name, value in environment.items()),
            *argv,
        ]
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        assert process.stdout is not None
        deadline = time.monotonic() + timeout_seconds + 10
        output = bytearray()
        truncated = False
        timed_out = False
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    raise subprocess.TimeoutExpired(command, timeout_seconds)
                ready, _, _ = select.select([process.stdout], [], [], remaining)
                if not ready:
                    timed_out = True
                    raise subprocess.TimeoutExpired(command, timeout_seconds)
                chunk = os.read(
                    process.stdout.fileno(), min(65_536, max_bytes + 1 - len(output))
                )
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) > max_bytes:
                    truncated = True
                    self._stop(unit)
                    break
            try:
                exit_status = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._stop(unit)
                os.killpg(process.pid, signal.SIGKILL)
                exit_status = process.wait()
        except subprocess.TimeoutExpired:
            self._stop(unit)
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            exit_status = None
        return {
            "argv": argv,
            "cwd": str(workdir),
            "unit": unit,
            "exit_status": exit_status,
            "timed_out": timed_out,
            "truncated": truncated,
            "output": output[:max_bytes].decode("utf-8", errors="replace"),
        }
