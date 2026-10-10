from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from sinnix_lib.process import run_bounded


class EnvironmentProfile(StrEnum):
    """Minimal parent-environment subsets for declared owner adapters."""

    PLAIN = "plain"
    AGENT_JOB = "agent-job"
    TERMINAL = "terminal"
    USER_BUS = "user-bus"
    USER_BUS_OPTIONAL = "user-bus-optional"
    SESSION_OPTIONAL = "session-optional"
    WAYLAND = "wayland"


@dataclass(frozen=True)
class OwnerRoute:
    """Declared process-execution context."""

    name: str
    environment_profile: EnvironmentProfile = EnvironmentProfile.PLAIN


@dataclass(frozen=True)
class ExecutionProfile:
    """Declared policy for a bounded direct owner command."""

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
        if (
            self.max_combined_output_bytes is not None
            and self.max_combined_output_bytes < 1
        ):
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
    stopped_early: bool = False
    failure_class: str | None = None
    # A process outside the killed group still held a pipe when the drain
    # ended; output it wrote afterwards is missing and it may still run.
    output_incomplete: bool = False

    @property
    def available(self) -> bool:
        return self.failure_class is None and (
            self.exit_status == 0 or self.stopped_early
        )

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
    """Run declared owner processes with bounded output and tree cleanup."""

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
        # The kitty owner places agent windows through the compositor; without
        # its instance it cannot keep them off the operator's workspaces.
        EnvironmentProfile.TERMINAL: (
            "HYPRLAND_INSTANCE_SIGNATURE",
            "WAYLAND_DISPLAY",
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

    def run(
        self,
        command: Sequence[str],
        profile: ExecutionProfile,
        *,
        stdout_chunk_callback: Callable[[bytes], bool | None] | None = None,
    ) -> ExecutionResult:
        if not command:
            raise ValueError("owner command cannot be empty")
        normalized = tuple(str(part) for part in command)
        environment, missing_environment = self.environment_for(
            profile.route, profile.environment
        )
        if missing_environment is not None:
            return ExecutionResult(
                command=normalized,
                exit_status=None,
                stdout=b"",
                stderr=b"",
                failure_class=f"environment_unavailable:{missing_environment}",
            )
        try:
            result = run_bounded(
                normalized,
                timeout=profile.timeout_seconds,
                cwd=profile.cwd,
                env=environment,
                stdin=profile.stdin_bytes,
                stdout_limit=profile.max_stdout_bytes,
                stderr_limit=profile.max_stderr_bytes,
                combined_limit=profile.max_combined_output_bytes,
                on_stdout_chunk=stdout_chunk_callback,
                capture_stdout=stdout_chunk_callback is None,
                capture_combined=(
                    stdout_chunk_callback is None
                    or profile.max_combined_output_bytes is not None
                ),
            )
        except OSError as exc:
            return ExecutionResult(
                command=normalized,
                exit_status=None,
                stdout=b"",
                stderr=b"",
                failure_class=f"command_unavailable:{type(exc).__name__}",
            )
        if result.error_type is not None:
            return ExecutionResult(
                command=normalized,
                exit_status=None,
                stdout=result.stdout,
                stderr=result.stderr,
                failure_class=f"command_unavailable:{result.error_type}",
            )
        failure = (
            "command_stream_decode"
            if result.error and "stdout callback failed:" in result.error
            else "command_timeout"
            if result.timed_out
            else "command_output_bound"
            if result.limited
            else "command_failed"
            if not result.stopped_early and result.returncode != 0
            else None
        )
        return ExecutionResult(
            command=normalized,
            exit_status=result.exit_status,
            stdout=result.stdout,
            stderr=result.stderr,
            combined_output=result.combined_output,
            timed_out=result.timed_out,
            output_exceeded=result.limited,
            stopped_early=result.stopped_early,
            failure_class=failure,
            output_incomplete=result.output_incomplete,
        )

    def run_jsonl(
        self,
        command: Sequence[str],
        profile: ExecutionProfile,
        on_row: Callable[[Any], bool | None],
        *,
        max_row_bytes: int | None = None,
    ) -> ExecutionResult:
        """Stream JSONL rows; zero disables the row bound for trusted producers."""
        if max_row_bytes is not None and max_row_bytes < 0:
            raise ValueError("JSONL row bound cannot be negative")
        pending = bytearray()
        scan_from = 0
        row_bound = profile.max_stdout_bytes if max_row_bytes is None else max_row_bytes

        def consume(chunk: bytes) -> bool | None:
            nonlocal scan_from
            pending.extend(chunk)
            if row_bound and len(pending) > row_bound and b"\n" not in pending:
                raise ValueError("JSONL row exceeded stream bound")
            while (newline := pending.find(b"\n", scan_from)) >= 0:
                line = bytes(pending[:newline])
                del pending[: newline + 1]
                scan_from = 0
                if row_bound and len(line) > row_bound:
                    raise ValueError("JSONL row exceeded stream bound")
                if not line:
                    continue
                if on_row(json.loads(line)) is False:
                    return False
            scan_from = len(pending)
            return None

        result = self.run(command, profile, stdout_chunk_callback=consume)
        if result.failure_class is not None:
            return result
        if pending:
            return replace(result, failure_class="command_stream_decode")
        return result
