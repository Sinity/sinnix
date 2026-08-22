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


def test_owner_execution_preserves_combined_output_order_and_bound() -> None:
    command = [
        sys.executable,
        "-u",
        "-c",
        (
            "import sys, time; "
            "sys.stdout.write('first\\n'); sys.stdout.flush(); "
            "time.sleep(0.05); "
            "sys.stderr.write('second\\n'); sys.stderr.flush()"
        ),
    ]

    ordered = OwnerExecution().run(
        command,
        ExecutionProfile(route=OwnerRoute("fixture"), max_combined_output_bytes=13),
    )
    bounded = OwnerExecution().run(
        command,
        ExecutionProfile(route=OwnerRoute("fixture"), max_combined_output_bytes=8),
    )

    assert ordered.available is True
    assert ordered.combined_output == b"first\nsecond\n"
    assert bounded.failure_class == "command_output_bound"
    assert bounded.combined_output == b"first\nse"


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


def test_owner_execution_decodes_json_or_preserves_text_output() -> None:
    execution = OwnerExecution()
    json_result = execution.run(
        [sys.executable, "-c", "print('{\"route\": \"fixture\"}')"],
        ExecutionProfile(route=OwnerRoute("fixture")),
    )
    text_result = execution.run(
        [sys.executable, "-c", "print('plain fixture output')"],
        ExecutionProfile(route=OwnerRoute("fixture")),
    )

    assert json_result.decode_json() == {"route": "fixture"}
    assert json_result.decode_json_or_text() == {"route": "fixture"}
    assert text_result.decode_json_or_text() == "plain fixture output\n"


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


def test_owner_execution_user_bus_profile_requires_complete_session_environment() -> None:
    source = {
        "HOME": "/home/fixture",
        "LANG": "C.UTF-8",
        "PATH": "/fixture/bin",
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
        "XDG_RUNTIME_DIR": "/run/user/1000",
    }
    route = OwnerRoute("mcp-fixture", EnvironmentProfile.USER_BUS)

    environment, missing = OwnerExecution(source).environment_for(
        route, {"FIXTURE": "1"}
    )
    unavailable, missing_unavailable = OwnerExecution(
        {key: value for key, value in source.items() if key != "DBUS_SESSION_BUS_ADDRESS"}
    ).environment_for(route)

    assert missing is None
    assert environment == {**source, "FIXTURE": "1"}
    assert unavailable == {}
    assert missing_unavailable == "DBUS_SESSION_BUS_ADDRESS"


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
