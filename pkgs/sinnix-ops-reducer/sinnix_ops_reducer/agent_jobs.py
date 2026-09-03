from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from typing import Any

MAX_AGENTCTL_RESPONSE_BYTES = 1_048_576
MAX_SNAPSHOT_JOBS = 100
DEFAULT_TIMEOUT_SECONDS = 5.0


class AgentCtlError(RuntimeError):
    """agentctl did not provide a bounded typed job response."""


class AgentCtlClient:
    """Reducer-side reader of `agentctl job list|get|cancel`.

    `job list` prints a JSON array of job objects; `job get` and `job cancel`
    print one job object whose `job_id` is the pueue task id.
    """

    def __init__(
        self,
        command: str = "agentctl",
        *,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.command = command
        self.runner = runner
        self.timeout_seconds = timeout_seconds

    def list(self) -> dict[str, Any]:
        value = self._call(("job", "list"))
        if not isinstance(value, list) or any(
            not isinstance(job, dict) for job in value
        ):
            raise AgentCtlError("agentctl job list did not print a job array")
        # The reducer snapshot is bounded; the newest tasks are the ones a
        # dashboard reads.
        jobs = value[-MAX_SNAPSHOT_JOBS:]
        return {"jobs": jobs, "truncated": len(value) > len(jobs)}

    def get(self, job_id: str | int) -> dict[str, Any]:
        return self._job_response(("job", "get", str(job_id)))

    def cancel(self, job_id: str | int) -> dict[str, Any]:
        return self._job_response(("job", "cancel", str(job_id)))

    def _job_response(self, arguments: Sequence[str]) -> dict[str, Any]:
        value = self._call(arguments)
        if not isinstance(value, dict) or not isinstance(
            value.get("job_id"), (int, str)
        ):
            raise AgentCtlError("agentctl job response has no job ID")
        return value

    def _call(self, arguments: Sequence[str]) -> Any:
        try:
            result = self.runner(
                [self.command, *arguments],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise AgentCtlError(
                f"agentctl is unavailable: {type(error).__name__}"
            ) from error
        if result.returncode != 0:
            raise AgentCtlError("agentctl rejected the job request")
        output = result.stdout
        if len(output.encode()) > MAX_AGENTCTL_RESPONSE_BYTES:
            raise AgentCtlError("agentctl response exceeds the protocol bound")
        try:
            return json.loads(output)
        except json.JSONDecodeError as error:
            raise AgentCtlError("agentctl returned malformed JSON") from error
