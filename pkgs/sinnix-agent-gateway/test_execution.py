from __future__ import annotations

import sys

from sinnix_agent_gateway.execution import ExecutionProfile, OwnerExecution


def test_owner_execution_bounds_stdout_and_terminates_command() -> None:
    result = OwnerExecution().run(
        [sys.executable, "-u", "-c", "import sys; sys.stdout.write('x' * 4096)"],
        ExecutionProfile(name="fixture", max_stdout_bytes=64),
    )

    assert result.failure_class == "command_output_bound"
    assert result.output_exceeded is True
    assert result.stdout == b"x" * 64


def test_owner_execution_terminates_timed_out_command() -> None:
    result = OwnerExecution().run(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        ExecutionProfile(name="fixture", timeout_seconds=0.05),
    )

    assert result.failure_class == "command_timeout"
    assert result.timed_out is True
    assert result.exit_status is not None


def test_owner_execution_reports_unavailable_command() -> None:
    result = OwnerExecution().run(
        ["/definitely/missing/gateway-command"], ExecutionProfile(name="fixture")
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
        ExecutionProfile(name="fixture", stdin_bytes=b"gateway patch input"),
    )

    assert result.available is True
    assert result.stdout == b"tupni hctap yawetag"
