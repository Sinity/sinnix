from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Mapping, Sequence


class EnvironmentProfile(StrEnum):
    """Minimal parent-environment subsets for direct owner adapters."""

    PLAIN = "plain"
    TERMINAL = "terminal"
    WAYLAND = "wayland"


@dataclass(frozen=True)
class OwnerRoute:
    """Declared direct-owner execution context.

    Durable jobs, operator shell execution, and brokered MCP sessions have
    different lifecycles and do not use this one-shot route contract.
    """

    name: str
    environment_profile: EnvironmentProfile = EnvironmentProfile.PLAIN


@dataclass(frozen=True)
class ExecutionProfile:
    """Declared policy for an ordinary direct owner command."""

    route: OwnerRoute
    timeout_seconds: float = 20.0
    max_stdout_bytes: int = 262_144
    max_stderr_bytes: int = 8_192
    cwd: Path | None = None
    environment: Mapping[str, str] = field(default_factory=dict)
    stdin_bytes: bytes | None = None

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("execution timeout must be positive")
        if self.max_stdout_bytes < 1 or self.max_stderr_bytes < 1:
            raise ValueError("execution output bounds must be positive")


@dataclass(frozen=True)
class ExecutionResult:
    command: tuple[str, ...]
    exit_status: int | None
    stdout: bytes
    stderr: bytes
    timed_out: bool = False
    output_exceeded: bool = False
    failure_class: str | None = None

    @property
    def available(self) -> bool:
        return self.failure_class is None and self.exit_status == 0

    def stderr_excerpt(self) -> str:
        return self.stderr.decode("utf-8", errors="replace").strip()[:2_000]


class OwnerDiagnosticError(ValueError):
    """A direct owner failure with a safe response and private artifact."""

    def __init__(self, response: dict[str, object]):
        self.response = response
        super().__init__(str(response.get("failure_class", "owner_route_failed")))


class OwnerExecution:
    """Run one direct owner command with one bounded cancellation mechanism."""

    _REQUIRED_ENVIRONMENT: dict[EnvironmentProfile, tuple[str, ...]] = {
        EnvironmentProfile.PLAIN: (),
        EnvironmentProfile.TERMINAL: ("XDG_RUNTIME_DIR",),
        EnvironmentProfile.WAYLAND: (
            "XDG_RUNTIME_DIR",
            "WAYLAND_DISPLAY",
            "HYPRLAND_INSTANCE_SIGNATURE",
        ),
    }

    def __init__(self, base_environment: Mapping[str, str] | None = None):
        source = os.environ if base_environment is None else base_environment
        self.base_environment = dict(source)

    def _environment(
        self, profile: ExecutionProfile
    ) -> tuple[dict[str, str], str | None]:
        source = self.base_environment
        environment = {
            "HOME": source.get("HOME", str(Path.home())),
            "LANG": source.get("LANG", "C.UTF-8"),
            "PATH": source.get("PATH", "/run/current-system/sw/bin"),
        }
        for name in self._REQUIRED_ENVIRONMENT[profile.route.environment_profile]:
            value = source.get(name)
            if not value:
                return {}, name
            environment[name] = value
        environment.update(profile.environment)
        return environment, None

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                return
            process.wait()

    def run(self, command: Sequence[str], profile: ExecutionProfile) -> ExecutionResult:
        if not command:
            raise ValueError("owner command cannot be empty")
        normalized = tuple(str(part) for part in command)
        environment, missing_environment = self._environment(profile)
        if missing_environment is not None:
            return ExecutionResult(
                command=normalized,
                exit_status=None,
                stdout=b"",
                stderr=b"",
                failure_class=f"environment_unavailable:{missing_environment}",
            )
        try:
            process = subprocess.Popen(
                normalized,
                stdin=(
                    subprocess.PIPE
                    if profile.stdin_bytes is not None
                    else subprocess.DEVNULL
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=profile.cwd,
                env=environment,
                start_new_session=True,
            )
        except OSError as exc:
            return ExecutionResult(
                command=normalized,
                exit_status=None,
                stdout=b"",
                stderr=b"",
                failure_class=f"command_unavailable:{type(exc).__name__}",
            )

        stdout = bytearray()
        stderr = bytearray()
        pending_stdin = memoryview(profile.stdin_bytes or b"")
        exceeded = False
        selector = selectors.DefaultSelector()
        assert process.stdout is not None
        assert process.stderr is not None
        selector.register(process.stdout, selectors.EVENT_READ, ("stdout", stdout))
        selector.register(process.stderr, selectors.EVENT_READ, ("stderr", stderr))
        if process.stdin is not None:
            selector.register(process.stdin, selectors.EVENT_WRITE, ("stdin", None))
        deadline = time.monotonic() + profile.timeout_seconds
        timed_out = False
        try:
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    self._terminate(process)
                    break
                for key, _ in selector.select(min(remaining, 0.1)):
                    stream, destination = key.data
                    if stream == "stdin":
                        try:
                            written = os.write(key.fd, pending_stdin[:65_536])
                        except BrokenPipeError:
                            written = 0
                        pending_stdin = pending_stdin[written:]
                        if not pending_stdin:
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                        continue
                    chunk = os.read(key.fd, 65_536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    assert destination is not None
                    limit = (
                        profile.max_stdout_bytes
                        if stream == "stdout"
                        else profile.max_stderr_bytes
                    )
                    room = limit + 1 - len(destination)
                    if room > 0:
                        destination.extend(chunk[:room])
                    if len(destination) > limit:
                        exceeded = True
                        self._terminate(process)
                        break
                if exceeded:
                    break
        finally:
            selector.close()
            if process.stdin is not None:
                process.stdin.close()
            if process.poll() is None:
                self._terminate(process)
        exit_status = process.wait()
        if timed_out:
            failure = "command_timeout"
        elif exceeded:
            failure = "command_output_bound"
        elif exit_status != 0:
            failure = "command_failed"
        else:
            failure = None
        return ExecutionResult(
            command=normalized,
            exit_status=exit_status,
            stdout=bytes(stdout[: profile.max_stdout_bytes]),
            stderr=bytes(stderr[: profile.max_stderr_bytes]),
            timed_out=timed_out,
            output_exceeded=exceeded,
            failure_class=failure,
        )
