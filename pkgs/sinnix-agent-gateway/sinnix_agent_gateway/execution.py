"""The gateway's job owner: agentctl's launch and batch routes, called in process.

A job is a pueue task. Every operation answers with a ResponseEnvelope; a
refusal is an ErrorEnvelope whose code the gateway's own error classes cover,
never an exception.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from agentctl import batch, launch
from agentctl.config import Config, ConfigError, load_config, resolve_project
from agentctl.packets import PacketError
from agentctl.projects import ProjectConfigError
from agentctl.pueue import PueueError
from agentctl.worktrunk import WorktrunkError
from sinnix_mcp import (
    ErrorCode,
    ErrorEnvelope,
    OpaquePayload,
    RequestEnvelope,
    ResponseEnvelope,
)

OWNER = "systemd-jobs"
JOB_LIST_ORDERING = "created_at_desc_job_id_desc"
DEFAULT_CHECKOUT = "default"
SHELL_OPERATION = "shell"
SHELL_GROUP = "interactive"
MAX_LOG_BYTES = 262_144


class _Refusal(Exception):
    """An operation the owner declines, carrying the code the response reports."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


def _require_int(arguments: Mapping[str, Any], name: str) -> int:
    value = arguments.get(name)
    if isinstance(value, bool):
        raise _Refusal(ErrorCode.INVALID_ARGUMENT, f"{name} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as error:
            raise _Refusal(
                ErrorCode.INVALID_ARGUMENT, f"{name} must be an integer"
            ) from error
    raise _Refusal(ErrorCode.INVALID_ARGUMENT, f"{name} must be an integer")


def _require_str(arguments: Mapping[str, Any], name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value:
        raise _Refusal(ErrorCode.INVALID_ARGUMENT, f"{name} must be a non-empty string")
    return value


def _optional_str(arguments: Mapping[str, Any], name: str) -> str | None:
    value = arguments.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise _Refusal(ErrorCode.INVALID_ARGUMENT, f"{name} must be a non-empty string")
    return value


def _sort_key(job: Mapping[str, Any]) -> tuple[str, str]:
    return (str(job.get("enqueued_at") or ""), str(job.get("job_id")))


def _encode_cursor(key: tuple[str, str]) -> str:
    return base64.urlsafe_b64encode(json.dumps(list(key)).encode()).decode()


def _decode_cursor(cursor: str) -> tuple[str, str]:
    try:
        value = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    except (ValueError, json.JSONDecodeError) as error:
        raise _Refusal(
            ErrorCode.STALE_CURSOR, "job list cursor is unreadable"
        ) from error
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(not isinstance(item, str) for item in value)
    ):
        raise _Refusal(ErrorCode.STALE_CURSOR, "job list cursor is unreadable")
    return (value[0], value[1])


def job_payload(job: Mapping[str, Any]) -> dict[str, Any]:
    """The job as the gateway reads it: a string id and a nested state."""
    return {
        "job_id": str(job.get("job_id")),
        "label": job.get("label"),
        "kind": job.get("kind"),
        "project_id": job.get("project"),
        "operation": job.get("operation"),
        "group": job.get("group"),
        "checkout": {"path": job.get("path")},
        "state": {
            "phase": job.get("phase"),
            "terminal": job.get("terminal"),
            "exit_code": job.get("exit_code"),
        },
        "enqueued_at": job.get("enqueued_at"),
        "started_at": job.get("started_at"),
        "ended_at": job.get("ended_at"),
    }


class LocalJobs:
    """Dispatches the gateway's job operations onto agentctl in this process."""

    def __init__(self, config: Config | None = None) -> None:
        self._config = config

    @property
    def config(self) -> Config:
        if self._config is None:
            self._config = load_config()
        return self._config

    def dispatch(self, request: RequestEnvelope) -> ResponseEnvelope:
        handler = self._handlers().get(request.operation)
        if handler is None:
            return self._error(
                request,
                ErrorCode.INVALID_ARGUMENT,
                f"unknown job operation: {request.operation}",
            )
        try:
            payload = handler(request.arguments)
        except _Refusal as refusal:
            return self._error(request, refusal.code, str(refusal))
        except PueueError as error:
            return self._error(request, ErrorCode.OWNER_UNAVAILABLE, str(error))
        except (
            launch.JobError,
            batch.BatchRefusal,
            batch.BatchError,
            WorktrunkError,
            ConfigError,
            PacketError,
            ProjectConfigError,
            KeyError,
            OSError,
        ) as error:
            return self._error(request, ErrorCode.OPERATION_FAILED, str(error))
        return ResponseEnvelope(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            owner=OWNER,
            payload=OpaquePayload.bounded(payload),
        )

    def _handlers(self) -> dict[str, Callable[[Mapping[str, Any]], dict[str, Any]]]:
        return {
            "job.start": self._start,
            "job.get": self._get,
            "job.wait": self._wait,
            "job.logs": self._logs,
            "job.result": self._result,
            "job.cancel": self._cancel,
            "job.list": self._list,
            "job.agent.start": self._agent_start,
            "job.shell.start": self._shell_start,
        }

    @staticmethod
    def _error(
        request: RequestEnvelope, code: ErrorCode, message: str
    ) -> ResponseEnvelope:
        return ResponseEnvelope(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            owner=OWNER,
            error=ErrorEnvelope(code, message, OpaquePayload.bounded({})),
        )

    def _project(self, project_id: str) -> Any:
        try:
            return resolve_project(self.config, project_id)
        except (KeyError, PacketError) as error:
            raise _Refusal(
                ErrorCode.INVALID_ARGUMENT, f"unknown project: {project_id}"
            ) from error

    def _worktree(self, project: Any, checkout_id: Any) -> Path:
        if checkout_id is None or checkout_id == DEFAULT_CHECKOUT:
            return Path(project.root)
        if isinstance(checkout_id, str) and checkout_id.startswith("/"):
            return Path(checkout_id)
        raise _Refusal(
            ErrorCode.INVALID_ARGUMENT,
            "checkout must be 'default' or an absolute worktree path",
        )

    def _start(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        project = self._project(_require_str(arguments, "project_id"))
        name = _require_str(arguments, "operation")
        try:
            operation = project.operation(name)
        except KeyError as error:
            raise _Refusal(ErrorCode.INVALID_ARGUMENT, str(error)) from error
        workspace_id = arguments.get("workspace_id")
        workspace = (
            None if workspace_id is None else self._worktree(project, workspace_id)
        )
        job = launch.start_operation(
            self.config, project, operation, workspace=workspace
        )
        return job_payload(job)

    def _get(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        return job_payload(launch.get_job(_require_int(arguments, "job_id")))

    def _wait(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        job_id = _require_int(arguments, "job_id")
        timeout_seconds = _require_int(arguments, "timeout_seconds")
        job = launch.wait(job_id, timeout_seconds=float(timeout_seconds))
        return {**job_payload(job), "timed_out": bool(job.get("wait_timed_out"))}

    def _logs(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        job_id = _require_int(arguments, "job_id")
        offset = int(arguments.get("offset") or 0)
        max_bytes = int(arguments.get("max_bytes") or MAX_LOG_BYTES)
        raw = launch.logs(self.config, job_id).encode()
        window = raw[offset : offset + max_bytes]
        return {
            "job_id": str(job_id),
            "content": window.decode("utf-8", "replace"),
            "offset": offset,
            "max_bytes": max_bytes,
            "truncated": offset + len(window) < len(raw),
        }

    def _result(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        job_id = _require_int(arguments, "job_id")
        observed = launch.result(self.config, job_id)
        return {
            **job_payload(observed),
            "kind": observed.get("kind"),
            "value": observed.get("value"),
        }

    def _cancel(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        job_id = _require_int(arguments, "job_id")
        job = launch.cancel(self.config, job_id)
        return {
            **job_payload(job),
            "cancel_requested": True,
            "already_terminal": bool(job.get("terminal")),
        }

    def _list(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        limit = int(arguments.get("limit") or 50)
        project_id = arguments.get("project_id")
        rows = sorted(
            launch.list_jobs(project_id if isinstance(project_id, str) else None),
            key=_sort_key,
            reverse=True,
        )
        ceiling = list(_sort_key(rows[0])) if rows else ["", ""]
        cursor = arguments.get("cursor")
        if isinstance(cursor, str) and cursor:
            after = _decode_cursor(cursor)
            rows = [row for row in rows if _sort_key(row) < after]
        page = rows[:limit]
        truncated = len(rows) > len(page)
        return {
            "jobs": [job_payload(row) for row in page],
            "total": len(rows),
            "truncated": truncated,
            "next_cursor": _encode_cursor(_sort_key(page[-1]))
            if truncated and page
            else None,
            "snapshot": {"ordering": JOB_LIST_ORDERING, "ceiling": ceiling},
        }

    def _agent_start(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        """A batch of one seed: agentctl validates, claims, creates the worktree, queues the worker."""
        project = self._project(_require_str(arguments, "project_id"))
        run = batch.start(
            self.config,
            project,
            [_require_str(arguments, "bead_id")],
            backend=_optional_str(arguments, "backend"),
            model=_optional_str(arguments, "model"),
            effort=_optional_str(arguments, "effort"),
        )
        worker = run["workers"][0]
        task = (
            launch.get_job(worker["task_id"])
            if worker.get("task_id") is not None
            else None
        )
        return {
            **(job_payload(task) if task else {}),
            "run_id": run["run_id"],
            "lane": {
                "bead": worker["leader"],
                "beads": list(worker["beads"]),
                "branch": worker["branch"],
                "worktree": worker.get("worktree"),
                "backend": worker.get("backend"),
                "model": worker.get("model"),
                "effort": worker.get("effort"),
            },
        }

    def _shell_start(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        """One argv queued in the interactive pool, inside the project's environment."""
        project = self._project(_require_str(arguments, "project_id"))
        worktree = self._worktree(project, arguments.get("checkout_id"))
        argv = arguments.get("argv")
        if (
            not isinstance(argv, list)
            or not argv
            or any(not isinstance(item, str) or not item for item in argv)
        ):
            raise _Refusal(ErrorCode.INVALID_ARGUMENT, "argv must be a non-empty list")
        cwd = (worktree / str(arguments.get("cwd") or ".")).resolve()
        if worktree.resolve() not in (cwd, *cwd.parents):
            raise _Refusal(ErrorCode.POLICY_DENIED, "cwd must stay inside the checkout")
        if not cwd.is_dir():
            raise _Refusal(ErrorCode.INVALID_ARGUMENT, f"cwd does not exist: {cwd}")
        job = launch.enqueue(
            self.config,
            project=project,
            operation=SHELL_OPERATION,
            label=launch.label_for(project.project_id, SHELL_OPERATION),
            group=SHELL_GROUP,
            argv=project.environment.command_for(argv),
            working_directory=cwd,
            timeout_seconds=_require_int(arguments, "timeout_seconds"),
            result_kind="exit",
            environment=project.environment.values(),
        )
        return job_payload(job)
