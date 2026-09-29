from __future__ import annotations

import json
import sys
import time

from sinnix_agent_gateway.owner_execution import (
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


def test_owner_execution_waits_for_child_after_both_output_pipes_close() -> None:
    result = OwnerExecution().run(
        [
            sys.executable,
            "-c",
            "import os, time; os.close(1); os.close(2); time.sleep(0.2)",
        ],
        ExecutionProfile(route=OwnerRoute("fixture"), timeout_seconds=1),
    )

    assert result.available is True
    assert result.timed_out is False


def test_owner_execution_timeout_does_not_wait_for_sigterm_ignoring_child() -> None:
    started = time.monotonic()
    result = OwnerExecution().run(
        [
            sys.executable,
            "-c",
            "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)",
        ],
        ExecutionProfile(route=OwnerRoute("fixture"), timeout_seconds=0.05),
    )

    assert result.failure_class == "command_timeout"
    assert time.monotonic() - started < 0.4


def test_owner_execution_deadline_covers_blocked_large_stdin_write() -> None:
    started = time.monotonic()
    result = OwnerExecution().run(
        [
            sys.executable,
            "-c",
            "import sys, time; sys.stdin.buffer.read(1); "
            "sys.stdout.buffer.write(b'y' * 131072); "
            "sys.stdout.buffer.flush(); time.sleep(60)",
        ],
        ExecutionProfile(
            route=OwnerRoute("fixture"),
            timeout_seconds=0.05,
            stdin_bytes=b"x" * (8 * 1024 * 1024),
        ),
    )

    assert result.failure_class == "command_timeout"
    assert time.monotonic() - started < 0.4


def test_owner_execution_deadline_kills_descendant_holding_pipes() -> None:
    started = time.monotonic()
    result = OwnerExecution().run(
        [
            sys.executable,
            "-c",
            "import os, time; os.fork() and os._exit(0); time.sleep(0.8)",
        ],
        ExecutionProfile(route=OwnerRoute("fixture"), timeout_seconds=0.05),
    )

    assert result.failure_class == "command_timeout"
    assert time.monotonic() - started < 0.4


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


def test_owner_execution_allows_a_stream_consumer_to_stop_a_command_early() -> None:
    seen: list[bytes] = []

    def stop_after_first(chunk: bytes) -> bool:
        seen.append(chunk)
        return False

    result = OwnerExecution().run(
        [sys.executable, "-u", "-c", "import time; print('first'); time.sleep(60)"],
        ExecutionProfile(route=OwnerRoute("fixture"), timeout_seconds=2),
        stdout_chunk_callback=stop_after_first,
    )

    assert seen == [b"first\n"]
    assert result.stdout == b""
    assert result.stopped_early is True
    assert result.available is True


def test_owner_execution_handles_child_that_closes_stdin() -> None:
    result = OwnerExecution().run(
        [sys.executable, "-c", "import os; os.close(0); print('done')"],
        ExecutionProfile(
            route=OwnerRoute("fixture"),
            stdin_bytes=b"unused input",
            timeout_seconds=1,
        ),
    )

    assert result.available is True
    assert result.stdout == b"done\n"


def test_owner_execution_decodes_json_or_preserves_text_output() -> None:
    execution = OwnerExecution()
    json_result = execution.run(
        [sys.executable, "-c", 'print(\'{"route": "fixture"}\')'],
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
    assert (
        not {
            "OPENAI_API_KEY",
            "OPENAI_TUNNEL_RUNTIME_KEY",
            "CREDENTIALS_DIRECTORY",
        }
        & environment.keys()
    )


def test_owner_execution_user_bus_profile_requires_complete_session_environment() -> (
    None
):
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
        {
            key: value
            for key, value in source.items()
            if key != "DBUS_SESSION_BUS_ADDRESS"
        }
    ).environment_for(route)

    assert missing is None
    assert environment == {**source, "FIXTURE": "1"}
    assert unavailable == {}
    assert missing_unavailable == "DBUS_SESSION_BUS_ADDRESS"


def test_owner_execution_wayland_profile_requires_complete_session_environment() -> (
    None
):
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


def test_owner_execution_timeout_drain_ends_despite_a_session_escapee() -> None:
    """Fails if a setsid descendant holding stdout extends the owner deadline."""
    script = (
        "import os, time\n"
        "if os.fork() == 0:\n"
        "    os.setsid()\n"
        "    time.sleep(1.5)\n"
        "    os._exit(0)\n"
        "time.sleep(30)\n"
    )
    started = time.monotonic()
    result = OwnerExecution().run(
        [sys.executable, "-c", script],
        ExecutionProfile(route=OwnerRoute("fixture"), timeout_seconds=0.35),
    )

    assert result.failure_class == "command_timeout"
    assert result.output_incomplete is True
    assert time.monotonic() - started < 1.0


def test_owner_execution_stream_interrupt_leaves_no_child(tmp_path) -> None:
    """Fails if the owner child outlives a callback KeyboardInterrupt."""
    marker = tmp_path / "marker"
    script = (
        "import time\n"
        "print('READY', flush=True)\n"
        "time.sleep(0.5)\n"
        f"open({str(marker)!r}, 'w').write('late')\n"
    )

    def interrupt(chunk: bytes) -> None:
        if b"READY" in chunk:
            raise KeyboardInterrupt

    try:
        OwnerExecution().run(
            [sys.executable, "-c", script],
            ExecutionProfile(route=OwnerRoute("fixture"), timeout_seconds=10),
            stdout_chunk_callback=interrupt,
        )
    except KeyboardInterrupt:
        pass
    else:
        raise AssertionError("the callback's KeyboardInterrupt must propagate")

    time.sleep(1.0)
    assert not marker.exists()


def test_terminal_profile_carries_the_compositor_instance() -> None:
    """Fails if the kitty owner runs without the Hyprland instance.

    Without HYPRLAND_INSTANCE_SIGNATURE the owner's hyprctl calls reach no
    compositor, so agent terminals opened on the operator's workspace.
    """
    execution = OwnerExecution(
        {
            "PATH": "/fixture/bin",
            "XDG_RUNTIME_DIR": "/run/user/1000",
            "HYPRLAND_INSTANCE_SIGNATURE": "fixture-instance",
            "WAYLAND_DISPLAY": "wayland-1",
        }
    )
    environment, missing = execution.environment_for(
        OwnerRoute("terminal-kitty", EnvironmentProfile.TERMINAL)
    )

    assert missing is None
    assert environment["HYPRLAND_INSTANCE_SIGNATURE"] == "fixture-instance"
    assert environment["WAYLAND_DISPLAY"] == "wayland-1"
