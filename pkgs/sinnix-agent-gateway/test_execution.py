from __future__ import annotations

import json
import sys

from sinnix_agent_gateway.execution import (
    EnvironmentProfile,
    ExecutionProfile,
    OwnerExecution,
    OwnerRoute,
)


def test_owner_execution_bounds_stdout_and_terminates_command() -> None:
    result = OwnerExecution().run(
        [sys.executable, "-u", "-c", "import sys; sys.stdout.write('x' * 4096)"],
        ExecutionProfile(route=OwnerRoute("fixture"), max_stdout_bytes=64),
    )

    assert result.failure_class == "command_output_bound"
    assert result.output_exceeded is True
    assert result.stdout == b"x" * 64


def test_owner_execution_terminates_timed_out_command() -> None:
    result = OwnerExecution().run(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        ExecutionProfile(route=OwnerRoute("fixture"), timeout_seconds=0.05),
    )

    assert result.failure_class == "command_timeout"
    assert result.timed_out is True
    assert result.exit_status is not None


def test_owner_execution_reports_unavailable_command() -> None:
    result = OwnerExecution().run(
        ["/definitely/missing/gateway-command"],
        ExecutionProfile(route=OwnerRoute("fixture")),
    )

    assert result.available is False
    assert result.failure_class == "command_unavailable:FileNotFoundError"


def test_owner_execution_streams_stdin_while_collecting_stdout() -> None:
    result = OwnerExecution().run(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read()[::-1])",
        ],
        ExecutionProfile(
            route=OwnerRoute("fixture"), stdin_bytes=b"gateway patch input"
        ),
    )

    assert result.available is True
    assert result.stdout == b"tupni hctap yawetag"


def test_owner_execution_profile_omits_ambient_credentials() -> None:
    source = {
        "HOME": "/home/fixture",
        "LANG": "C.UTF-8",
        "PATH": "/fixture/bin",
        "OPENAI_API_KEY": "secret",
        "OPENAI_TUNNEL_RUNTIME_KEY": "secret",
        "CREDENTIALS_DIRECTORY": "/run/credentials/gateway",
    }
    result = OwnerExecution(source).run(
        [
            sys.executable,
            "-c",
            "import json, os; print(json.dumps(dict(os.environ)))",
        ],
        ExecutionProfile(route=OwnerRoute("fixture")),
    )

    assert result.available is True
    environment = json.loads(result.stdout)
    assert environment["HOME"] == "/home/fixture"
    assert environment["LANG"] == "C.UTF-8"
    assert environment["PATH"] == "/fixture/bin"
    assert not {
        "OPENAI_API_KEY",
        "OPENAI_TUNNEL_RUNTIME_KEY",
        "CREDENTIALS_DIRECTORY",
    } & environment.keys()


def test_owner_execution_wayland_profile_requires_complete_session_environment() -> None:
    route = OwnerRoute("desktop-fixture", EnvironmentProfile.WAYLAND)
    source = {
        "HOME": "/home/fixture",
        "LANG": "C.UTF-8",
        "PATH": "/fixture/bin",
        "XDG_RUNTIME_DIR": "/run/user/1000",
        "WAYLAND_DISPLAY": "wayland-1",
        "HYPRLAND_INSTANCE_SIGNATURE": "fixture",
    }
    successful = OwnerExecution(source).run(
        [sys.executable, "-c", "import os; print(os.environ['WAYLAND_DISPLAY'])"],
        ExecutionProfile(route=route),
    )
    unavailable = OwnerExecution({}).run(
        [sys.executable, "-c", "raise SystemExit(1)"],
        ExecutionProfile(route=route),
    )

    assert successful.available is True
    assert successful.stdout == b"wayland-1\n"
    assert unavailable.failure_class == "environment_unavailable:XDG_RUNTIME_DIR"
