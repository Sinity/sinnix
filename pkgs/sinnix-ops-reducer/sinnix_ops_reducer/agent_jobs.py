from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from typing import Any


MAX_AGENTCTL_RESPONSE_BYTES = 1_048_576
MAX_SNAPSHOT_JOBS = 100
DEFAULT_TIMEOUT_SECONDS = 5.0


class AgentCtlError(RuntimeError):
    """AgentCTL did not provide a bounded typed job response."""


class AgentCtlClient:
    """Small reducer-side reader for Sinnixd's typed job lifecycle."""

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
        raw_jobs = value.get("jobs")
        if not isinstance(raw_jobs, list):
            raise AgentCtlError("AgentCTL job.list payload has no jobs array")
        truncated = value.get("truncated")
        next_cursor = value.get("next_cursor")
        if not isinstance(truncated, bool) or (
            next_cursor is not None and not isinstance(next_cursor, str)
        ):
            raise AgentCtlError("AgentCTL job.list payload has invalid paging metadata")
        jobs = [job for job in raw_jobs if isinstance(job, dict)]
        jobs.sort(key=lambda job: str(job.get("created_at") or ""), reverse=True)
        return {
            "jobs": jobs[:MAX_SNAPSHOT_JOBS],
            "truncated": truncated,
            "next_cursor": next_cursor,
        }

    def get(self, job_id: str) -> dict[str, Any]:
        return self._job_response(("job", "get", job_id))

    def cancel(self, job_id: str) -> dict[str, Any]:
        return self._job_response(("job", "cancel", job_id))

    def _job_response(self, arguments: Sequence[str]) -> dict[str, Any]:
        value = self._call(arguments)
        if not isinstance(value.get("job_id"), str):
            raise AgentCtlError("AgentCTL job response has no job ID")
        return value

    def _call(self, arguments: Sequence[str]) -> dict[str, Any]:
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
            raise AgentCtlError(f"AgentCTL is unavailable: {type(error).__name__}") from error
        if result.returncode != 0:
            raise AgentCtlError("AgentCTL rejected the job request")
        output = result.stdout
        if len(output.encode()) > MAX_AGENTCTL_RESPONSE_BYTES:
            raise AgentCtlError("AgentCTL response exceeds the protocol bound")
        try:
            response = json.loads(output)
        except json.JSONDecodeError as error:
            raise AgentCtlError("AgentCTL returned malformed JSON") from error
        if not isinstance(response, dict) or response.get("ok") is not True:
            raise AgentCtlError("AgentCTL returned an unsuccessful response")
        payload = response.get("payload")
        if not isinstance(payload, dict) or payload.get("kind") != "inline":
            raise AgentCtlError("AgentCTL returned a non-inline job response")
        value = payload.get("value")
        if not isinstance(value, dict):
            raise AgentCtlError("AgentCTL payload is not an object")
        return value
