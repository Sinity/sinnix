"""Readers of the owner-published agentctl job snapshot and lane views."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from typing import Any

from sinnix_lib.process import run_bounded

MAX_RESPONSE_BYTES = 1_048_576
MAX_SNAPSHOT_JOBS = 100
DEFAULT_TIMEOUT_SECONDS = 5.0


class AgentCtlError(RuntimeError):
    """The job plane did not answer with a bounded typed document."""


class AgentCtlClient:
    def __init__(
        self,
        command: str = "agentctl",
        *,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.command = command
        self.runner = runner
        self.timeout_seconds = timeout_seconds

    def snapshot(self) -> dict[str, Any]:
        """The one bounded owner projection the hub server publishes each refresh."""
        value = self._call(
            (
                self.command,
                "--json",
                "job",
                "snapshot",
                "--limit",
                str(MAX_SNAPSHOT_JOBS),
            )
        )
        if (
            not isinstance(value, dict)
            or value.get("schema") != "sinnix.agentctl.job-snapshot.v1"
            or not isinstance(value.get("groups"), dict)
            or not isinstance(value.get("jobs"), list)
            or not isinstance(value.get("omitted"), dict)
            or not isinstance(value.get("coverage"), dict)
        ):
            raise AgentCtlError(
                "agentctl job snapshot did not print a bounded job document"
            )
        if len(value["jobs"]) > MAX_SNAPSHOT_JOBS or any(
            not isinstance(job, dict) for job in value["jobs"]
        ):
            raise AgentCtlError("agentctl job snapshot has invalid job rows")
        return value

    def list(self) -> list[dict[str, Any]]:
        value = self._call((self.command, "--json", "job", "list"))
        if not isinstance(value, list) or any(
            not isinstance(job, dict) for job in value
        ):
            raise AgentCtlError("agentctl job list did not print a job array")
        return value

    def get(self, job_id: str | int, *, reference: str | None = None) -> dict[str, Any]:
        return self._job_response(
            (
                "job",
                "get",
                str(job_id),
                *(("--reference", reference) if reference else ()),
            )
        )

    def cancel(
        self,
        job_id: str | int,
        *,
        reference: str | None = None,
        expected_attempt: int | None = None,
    ) -> dict[str, Any]:
        return self._job_response(
            (
                "job",
                "cancel",
                str(job_id),
                *(("--reference", reference) if reference else ()),
                *(
                    ("--expected-attempt", str(expected_attempt))
                    if expected_attempt is not None
                    else ()
                ),
            )
        )

    def _job_response(self, arguments: Sequence[str]) -> dict[str, Any]:
        value = self._call((self.command, "--json", *arguments))
        if not isinstance(value, dict) or not isinstance(
            value.get("job_id"), (int, str)
        ):
            raise AgentCtlError("agentctl job response has no job ID")
        return value

    def _call(self, argv: Sequence[str], *, timeout: float | None = None) -> Any:
        deadline = self.timeout_seconds if timeout is None else timeout
        if self.runner is None:
            # agentctl starts native clients of its own. End the whole probe
            # before closing pipes, so cancellation cannot orphan those clients.
            probe = run_bounded(
                argv,
                timeout=deadline,
                stdout_limit=MAX_RESPONSE_BYTES,
                stderr_limit=65_536,
            )
            if probe.limited:
                raise AgentCtlError(f"{argv[0]} response exceeds the protocol bound")
            if probe.error is not None:
                raise AgentCtlError(f"{argv[0]} is unavailable: {probe.error}")
            result = subprocess.CompletedProcess(
                argv,
                probe.returncode,
                probe.stdout.decode("utf-8", "replace"),
            )
        else:
            result = self._run_injected(argv, deadline)
        if result.returncode != 0:
            raise AgentCtlError(f"{argv[0]} rejected the request")
        output = result.stdout
        if len(output.encode()) > MAX_RESPONSE_BYTES:
            raise AgentCtlError(f"{argv[0]} response exceeds the protocol bound")
        try:
            return json.loads(output)
        except json.JSONDecodeError as error:
            raise AgentCtlError(f"{argv[0]} returned malformed JSON") from error

    def _run_injected(
        self,
        argv: Sequence[str],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        assert self.runner is not None
        try:
            result = self.runner(
                list(argv),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise AgentCtlError(
                f"{argv[0]} is unavailable: {type(error).__name__}"
            ) from error
        return result
