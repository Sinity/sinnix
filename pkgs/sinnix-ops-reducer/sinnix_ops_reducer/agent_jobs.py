"""Readers of the job plane: pueue's groups, agentctl's jobs and lanes.

A job is a pueue task; `agentctl --json job list` reduces the queue to job
rows (`job_id`, `label`, `kind`, `project`, `operation`, `group`, `phase`,
`terminal`, `exit_code`, `path`, `enqueued_at`, `started_at`, `ended_at`).
`pueue status --json` carries the groups, whose status (`Running` or
`Paused`) is the whole of the admission policy. `agentctl --json view <p>`
is the per-project lane screen and is read on request only: it calls wt,
gh and bd.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from typing import Any

MAX_RESPONSE_BYTES = 1_048_576
MAX_SNAPSHOT_JOBS = 100
DEFAULT_TIMEOUT_SECONDS = 5.0
# The view calls wt, gh and bd for one project; a forge round trip is inside it.
VIEW_TIMEOUT_SECONDS = 60.0


class AgentCtlError(RuntimeError):
    """The job plane did not answer with a bounded typed document."""


class AgentCtlClient:
    def __init__(
        self,
        command: str = "agentctl",
        *,
        pueue_command: str = "pueue",
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.command = command
        self.pueue_command = pueue_command
        self.runner = runner
        self.timeout_seconds = timeout_seconds

    def snapshot(self) -> dict[str, Any]:
        """Groups and the newest jobs: what the reducer publishes every refresh."""
        jobs = self.list()
        kept = jobs[-MAX_SNAPSHOT_JOBS:]
        return {
            "groups": self.groups(),
            "jobs": kept,
            "truncated": len(jobs) > len(kept),
        }

    def groups(self) -> dict[str, dict[str, Any]]:
        document = self._call((self.pueue_command, "status", "--json"))
        groups = document.get("groups") if isinstance(document, dict) else None
        tasks = document.get("tasks") if isinstance(document, dict) else None
        if not isinstance(groups, dict) or not isinstance(tasks, dict):
            raise AgentCtlError("pueue status did not print groups and tasks")
        found: dict[str, dict[str, Any]] = {}
        for name, detail in groups.items():
            if not isinstance(detail, dict):
                continue
            found[str(name)] = {
                "status": str(detail.get("status") or ""),
                "parallel": int(detail.get("parallel_tasks") or 0),
                "running": 0,
                "queued": 0,
                "paused": 0,
            }
        for task in tasks.values():
            if not isinstance(task, dict):
                continue
            group = found.get(str(task.get("group") or ""))
            status = task.get("status")
            name = (
                next(iter(status), "")
                if isinstance(status, dict)
                else str(status or "")
            ).lower()
            if group is not None and name in {"running", "queued", "paused"}:
                group[name] += 1
        return found

    def list(self) -> list[dict[str, Any]]:
        value = self._call((self.command, "--json", "job", "list"))
        if not isinstance(value, list) or any(
            not isinstance(job, dict) for job in value
        ):
            raise AgentCtlError("agentctl job list did not print a job array")
        return value

    def get(self, job_id: str | int) -> dict[str, Any]:
        return self._job_response(("job", "get", str(job_id)))

    def cancel(self, job_id: str | int) -> dict[str, Any]:
        return self._job_response(("job", "cancel", str(job_id)))

    def projects(self) -> list[str]:
        value = self._call((self.command, "--json", "project", "list"))
        rows = value.get("projects") if isinstance(value, dict) else None
        if not isinstance(rows, list):
            raise AgentCtlError("agentctl project list did not print projects")
        return [
            str(row["id"])
            for row in rows
            if isinstance(row, dict) and isinstance(row.get("id"), str)
        ]

    def view(self, project: str) -> dict[str, Any]:
        value = self._call(
            (self.command, "--json", "view", project), timeout=VIEW_TIMEOUT_SECONDS
        )
        if not isinstance(value, dict) or not isinstance(value.get("lanes"), list):
            raise AgentCtlError("agentctl view did not print a lane document")
        return value

    def _job_response(self, arguments: Sequence[str]) -> dict[str, Any]:
        value = self._call((self.command, "--json", *arguments))
        if not isinstance(value, dict) or not isinstance(
            value.get("job_id"), (int, str)
        ):
            raise AgentCtlError("agentctl job response has no job ID")
        return value

    def _call(self, argv: Sequence[str], *, timeout: float | None = None) -> Any:
        try:
            result = self.runner(
                list(argv),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=self.timeout_seconds if timeout is None else timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise AgentCtlError(
                f"{argv[0]} is unavailable: {type(error).__name__}"
            ) from error
        if result.returncode != 0:
            raise AgentCtlError(f"{argv[0]} rejected the request")
        output = result.stdout
        if len(output.encode()) > MAX_RESPONSE_BYTES:
            raise AgentCtlError(f"{argv[0]} response exceeds the protocol bound")
        try:
            return json.loads(output)
        except json.JSONDecodeError as error:
            raise AgentCtlError(f"{argv[0]} returned malformed JSON") from error
