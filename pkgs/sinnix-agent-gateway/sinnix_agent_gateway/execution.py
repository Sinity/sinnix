from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping, Sequence


class EnvironmentProfile(StrEnum):
    """Minimal parent-environment subsets for direct owner adapters."""

    PLAIN = "plain"
    AGENT_JOB = "agent-job"
    TERMINAL = "terminal"
    USER_BUS = "user-bus"
    USER_BUS_OPTIONAL = "user-bus-optional"
    SESSION_OPTIONAL = "session-optional"
    WAYLAND = "wayland"


@dataclass(frozen=True)
class OwnerRoute:
    """Declared process-execution context.

    Direct owner routes use the bounded one-shot facade. Durable jobs reuse the
    declared environment and detached process mechanics while retaining their
    own manifests, artifacts, and lifecycle authority.
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
    max_combined_output_bytes: int | None = None
    cwd: Path | None = None
    environment: Mapping[str, str] = field(default_factory=dict)
    stdin_bytes: bytes | None = None

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("execution timeout must be positive")
        if self.max_stdout_bytes < 1 or self.max_stderr_bytes < 1:
            raise ValueError("execution output bounds must be positive")
        if self.max_combined_output_bytes is not None and self.max_combined_output_bytes < 1:
            raise ValueError("combined execution output bound must be positive")


@dataclass(frozen=True)
class ExecutionResult:
    command: tuple[str, ...]
    exit_status: int | None
    stdout: bytes
    stderr: bytes
    combined_output: bytes = b""
    timed_out: bool = False
    output_exceeded: bool = False
    failure_class: str | None = None

    @property
    def available(self) -> bool:
        return self.failure_class is None and self.exit_status == 0

    def stderr_excerpt(self) -> str:
        return self.stderr.decode("utf-8", errors="replace").strip()[:2_000]

    def decode_json(self) -> Any:
        """Decode successful owner output when its contract requires JSON."""
        return json.loads(self.stdout)

    def decode_json_or_text(self) -> Any:
        """Decode JSON owner output while preserving plain-text owner responses."""
        try:
            return self.decode_json()
        except json.JSONDecodeError:
            return self.stdout.decode("utf-8", errors="replace")


class OwnerDiagnosticError(ValueError):
    """A direct owner failure with a safe response and private artifact."""

    def __init__(self, response: dict[str, object]):
        self.response = response
        super().__init__(str(response.get("failure_class", "owner_route_failed")))


class OwnerExecutionStartError(RuntimeError):
    """A failed kernel-managed process launch with a typed classification."""

    def __init__(self, failure_class: str):
        self.failure_class = failure_class
        super().__init__(failure_class)


class OwnerExecution:
    """Own declared process startup and direct-owner bounded execution."""

    _REQUIRED_ENVIRONMENT: dict[EnvironmentProfile, tuple[str, ...]] = {
        EnvironmentProfile.PLAIN: (),
        EnvironmentProfile.AGENT_JOB: (),
        EnvironmentProfile.TERMINAL: ("XDG_RUNTIME_DIR",),
        EnvironmentProfile.USER_BUS: (
            "DBUS_SESSION_BUS_ADDRESS",
            "XDG_RUNTIME_DIR",
        ),
        EnvironmentProfile.USER_BUS_OPTIONAL: (),
        EnvironmentProfile.SESSION_OPTIONAL: (),
        EnvironmentProfile.WAYLAND: (
            "XDG_RUNTIME_DIR",
            "WAYLAND_DISPLAY",
            "HYPRLAND_INSTANCE_SIGNATURE",
        ),
    }
    _OPTIONAL_ENVIRONMENT: dict[EnvironmentProfile, tuple[str, ...]] = {
        EnvironmentProfile.AGENT_JOB: (
            "DBUS_SESSION_BUS_ADDRESS",
            "DISPLAY",
            "LC_ALL",
            "SHELL",
            "SSH_AUTH_SOCK",
            "TERM",
            "USER",
            "WAYLAND_DISPLAY",
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "XDG_RUNTIME_DIR",
            "XDG_STATE_HOME",
        ),
        EnvironmentProfile.USER_BUS_OPTIONAL: (
            "DBUS_SESSION_BUS_ADDRESS",
            "XDG_RUNTIME_DIR",
        ),
        EnvironmentProfile.SESSION_OPTIONAL: (
            "DBUS_SESSION_BUS_ADDRESS",
            "WAYLAND_DISPLAY",
            "XDG_RUNTIME_DIR",
        ),
    }

    def __init__(self, base_environment: Mapping[str, str] | None = None):
        source = os.environ if base_environment is None else base_environment
        self.base_environment = dict(source)

    def environment_for(
        self, route: OwnerRoute, overrides: Mapping[str, str] | None = None
    ) -> tuple[dict[str, str], str | None]:
        """Build the declared minimal environment without launching a command."""
        source = self.base_environment
        environment = {
            "HOME": source.get("HOME", str(Path.home())),
            "LANG": source.get("LANG", "C.UTF-8"),
            "PATH": source.get("PATH", "/run/current-system/sw/bin"),
        }
        for name in self._REQUIRED_ENVIRONMENT[route.environment_profile]:
            value = source.get(name)
            if not value:
                return {}, name
            environment[name] = value
        for name in self._OPTIONAL_ENVIRONMENT.get(route.environment_profile, ()):
            value = source.get(name)
            if value:
                environment[name] = value
        if overrides is not None:
            environment.update(overrides)
        return environment, None

    def start(
        self,
        command: Sequence[str],
        profile: ExecutionProfile,
        *,
        stdin: Any = subprocess.DEVNULL,
        stdout: Any = subprocess.PIPE,
        stderr: Any = subprocess.PIPE,
    ) -> subprocess.Popen[bytes]:
        """Start a detached child with the route's declared environment."""
        if not command:
            raise OwnerExecutionStartError("command_empty")
        normalized = tuple(str(part) for part in command)
        environment, missing_environment = self.environment_for(
            profile.route, profile.environment
        )
        if missing_environment is not None:
            raise OwnerExecutionStartError(
                f"environment_unavailable:{missing_environment}"
            )
        try:
            return subprocess.Popen(
                normalized,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                cwd=profile.cwd,
                env=environment,
                start_new_session=True,
            )
        except OSError as exc:
            raise OwnerExecutionStartError(
                f"command_unavailable:{type(exc).__name__}"
            ) from exc

    @staticmethod
    def terminate(process: subprocess.Popen[bytes]) -> None:
        """Terminate one detached process group, escalating after one second."""
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
        try:
            process = self.start(
                normalized,
                profile,
                stdin=(
                    subprocess.PIPE
                    if profile.stdin_bytes is not None
                    else subprocess.DEVNULL
                ),
            )
        except OwnerExecutionStartError as exc:
            return ExecutionResult(
                command=normalized,
                exit_status=None,
                stdout=b"",
                stderr=b"",
                failure_class=exc.failure_class,
            )

        stdout = bytearray()
        stderr = bytearray()
        combined_output = bytearray()
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
                    self.terminate(process)
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
                    if profile.max_combined_output_bytes is not None:
                        combined_limit = profile.max_combined_output_bytes
                        combined_room = combined_limit + 1 - len(combined_output)
                        if combined_room > 0:
                            combined_output.extend(chunk[:combined_room])
                        if len(combined_output) > combined_limit:
                            exceeded = True
                    else:
                        combined_output.extend(chunk)
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
                    if exceeded:
                        self.terminate(process)
                        break
                if exceeded:
                    break
        finally:
            selector.close()
            if process.stdin is not None:
                process.stdin.close()
            if process.poll() is None:
                self.terminate(process)
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
            combined_output=bytes(
                combined_output[: profile.max_combined_output_bytes]
                if profile.max_combined_output_bytes is not None
                else combined_output
            ),
            timed_out=timed_out,
            output_exceeded=exceeded,
            failure_class=failure,
        )
