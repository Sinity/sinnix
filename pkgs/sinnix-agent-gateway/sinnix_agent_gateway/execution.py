"""The gateway's job owner: agentctl's launch and batch routes, called in process.

A job is a pueue task and a batch is a run manifest. Direct adapter calls
return owner mappings and raise typed owner errors.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from agentctl import batch, launch
from agentctl.config import Config, ConfigError, load_config, resolve_project
from agentctl.projects import ProjectConfigError
from agentctl.prompts import PromptError
from agentctl.pueue import PueueError
from agentctl.worktrunk import WorktrunkError
from sinnix_mcp import ErrorCode

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


class JobOwnerError(Exception):
    """A bounded, typed refusal from the in-process agentctl adapter."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})


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


def _launch_reference(arguments: Mapping[str, Any]) -> str | None:
    """The job's own name, when the caller kept the one its start returned.

    It becomes a filename under the state directory, so it is one path
    component here and not a path.
    """
    reference = _optional_str(arguments, "launch_reference")
    if reference is not None and not launch.REFERENCE.match(reference):
        raise _Refusal(
            ErrorCode.INVALID_ARGUMENT, "launch_reference must be a launch reference"
        )
    return reference


def _sort_key(job: Mapping[str, Any]) -> tuple[str, str]:
    return (str(job.get("enqueued_at") or ""), str(job.get("job_id")))


def _encode_cursor(key: tuple[str, str], project_id: str | None = None) -> str:
    return base64.urlsafe_b64encode(
        json.dumps(
            {"key": list(key), "project_id": project_id}, separators=(",", ":")
        ).encode()
    ).decode()


def _decode_cursor(cursor: str) -> tuple[tuple[str, str], str | None]:
    try:
        value = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    except (ValueError, json.JSONDecodeError) as error:
        raise _Refusal(
            ErrorCode.STALE_CURSOR, "job list cursor is unreadable"
        ) from error
    if not isinstance(value, dict):
        raise _Refusal(ErrorCode.STALE_CURSOR, "job list cursor is unreadable")
    key = value.get("key")
    project_id = value.get("project_id")
    if (
        not isinstance(key, list)
        or len(key) != 2
        or any(not isinstance(item, str) for item in key)
        or (project_id is not None and not isinstance(project_id, str))
    ):
        raise _Refusal(ErrorCode.STALE_CURSOR, "job list cursor is unreadable")
    return (key[0], key[1]), project_id


def job_payload(job: Mapping[str, Any]) -> dict[str, Any]:
    """The job as the gateway reads it: a string id and a nested state.

    ``binding`` is what the task was queued for — its beads, run and worker —
    read back from the launch input, so bead membership never depends on
    parsing a pueue label.
    """
    return {
        "job_id": str(job.get("job_id")),
        "launch_reference": job.get("reference"),
        "binding": job.get("binding"),
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
            "dependencies": job.get("dependencies"),
        },
        "enqueued_at": job.get("enqueued_at"),
        "started_at": job.get("started_at"),
        "ended_at": job.get("ended_at"),
        **{
            key: job[key]
            for key in (
                "attempt",
                "artifacts",
                "attempts",
                "attempt_count",
                "next_attempt_offset",
                "queue_present",
                "outcome",
                "reused",
            )
            if key in job
        },
    }


# A refusal the caller fixes by sending different arguments; every other
# refusal is a state agentctl observed, not a malformed request. The code
# itself travels in the error details, where the batch actions map it to a
# typed failure and the action that follows.
ARGUMENT_REFUSALS = frozenset(
    {"ambiguous_run", "harness", "project", "unknown_run", "worker_missing"}
)


def worker_payload(worker: Mapping[str, Any]) -> dict[str, Any]:
    """One worker of a run: its beads, its worktree and its current task."""
    task = worker.get("task") if isinstance(worker.get("task"), Mapping) else {}
    task_id = worker.get("task_id")
    return {
        "worker_id": worker.get("id"),
        "beads": [str(bead) for bead in worker.get("beads") or []],
        "branch": worker.get("branch"),
        "worktree": worker.get("worktree"),
        "stage": worker.get("stage"),
        "job_id": str(task_id) if isinstance(task_id, int) else None,
        "job_launch_reference": worker.get("task_reference"),
        "job_ids": [str(item) for item in worker.get("task_ids") or []],
        "backend": worker.get("backend"),
        "model": worker.get("model"),
        "effort": worker.get("effort"),
        "provenance": worker.get("provenance"),
        "attempts": worker.get("attempts"),
        "result_filed": bool(worker.get("result")),
        "state": {
            "phase": task.get("phase"),
            "terminal": task.get("terminal"),
            "exit_code": task.get("exit_code"),
            "dependencies": task.get("dependencies"),
        }
        if task
        else None,
    }


def run_payload(document: Mapping[str, Any]) -> dict[str, Any]:
    """The run manifest as the gateway reads it, with pueue's view of each task."""
    raw = document.get("landing")
    landing = raw if isinstance(raw, Mapping) else {}
    task = landing.get("task") if isinstance(landing.get("task"), Mapping) else {}
    task_id = landing.get("task_id")
    return {
        "run_id": document.get("run_id"),
        "project_id": document.get("project"),
        "base_commit": document.get("base_commit"),
        "created_at": document.get("created_at"),
        "harness": document.get("harness"),
        "stage": document.get("stage"),
        "prepared": bool(document.get("prepared")),
        "accepted": document.get("acceptance") is not None,
        "acceptance": document.get("acceptance"),
        "abandoned": document.get("abandoned"),
        "workers": [
            worker_payload(worker)
            for worker in document.get("workers") or []
            if isinstance(worker, Mapping)
        ],
        "landing": {
            "job_id": str(task_id) if isinstance(task_id, int) else None,
            "job_launch_reference": landing.get("task_reference"),
            "integration_branch": landing.get("integration_branch"),
            "candidate_sha": landing.get("candidate_sha"),
            "pr_number": landing.get("pr_number"),
            "failure": landing.get("failure"),
            "state": {
                "phase": task.get("phase"),
                "terminal": task.get("terminal"),
                "exit_code": task.get("exit_code"),
            }
            if task
            else None,
        },
    }


class LocalJobs:
    """Calls agentctl's job and batch routes directly in this process.

    The adapter exposes one method per owner operation.  Runtime translates
    the gateway operation name to one of these methods, so no protocol
    envelope or second serialization boundary is involved.
    """

    def __init__(self, config: Config | None = None) -> None:
        self._config = config

    @property
    def config(self) -> Config:
        if self._config is None:
            self._config = load_config()
        return self._config

    def _call(
        self,
        handler: Callable[[Mapping[str, Any]], dict[str, Any]],
        arguments: Mapping[str, Any],
    ) -> dict[str, Any]:
        try:
            payload = handler(arguments)
        except _Refusal as refusal:
            raise JobOwnerError(refusal.code, str(refusal)) from refusal
        except batch.BatchRefusal as refusal:
            raise JobOwnerError(
                ErrorCode.INVALID_ARGUMENT
                if refusal.code in ARGUMENT_REFUSALS
                else ErrorCode.OPERATION_FAILED,
                str(refusal),
                {"refusal": refusal.code},
            ) from refusal
        except PueueError as error:
            raise JobOwnerError(ErrorCode.OWNER_UNAVAILABLE, str(error)) from error
        except (
            launch.JobError,
            batch.BatchError,
            WorktrunkError,
            ConfigError,
            PromptError,
            ProjectConfigError,
            KeyError,
            OSError,
        ) as error:
            raise JobOwnerError(ErrorCode.OPERATION_FAILED, str(error)) from error
        except ValueError as error:
            raise JobOwnerError(ErrorCode.INVALID_ARGUMENT, str(error)) from error
        try:
            json.dumps(payload, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as error:
            raise JobOwnerError(
                ErrorCode.RESULT_INVALID, "job owner response is not JSON serializable"
            ) from error
        return payload

    # These methods deliberately accept keyword arguments so Runtime can pass
    # a typed operation's fields without constructing an envelope.
    def start(self, **arguments: Any) -> dict[str, Any]:
        return self._call(self._start, arguments)

    def reconcile_start(self, owner_request_key: str) -> dict[str, Any] | None:
        job = launch.lookup_operation_request(self.config, owner_request_key)
        return job_payload(job) if job is not None else None

    def get(self, **arguments: Any) -> dict[str, Any]:
        return self._call(self._get, arguments)

    def wait(self, **arguments: Any) -> dict[str, Any]:
        return self._call(self._wait, arguments)

    def logs(self, **arguments: Any) -> dict[str, Any]:
        return self._call(self._logs, arguments)

    def result(self, **arguments: Any) -> dict[str, Any]:
        return self._call(self._result, arguments)

    def cancel(self, **arguments: Any) -> dict[str, Any]:
        return self._call(self._cancel, arguments)

    def list(self, **arguments: Any) -> dict[str, Any]:
        return self._call(self._list, arguments)

    def retry(self, **arguments: Any) -> dict[str, Any]:
        return self._call(self._retry, arguments)

    def clean(self, **arguments: Any) -> dict[str, Any]:
        return self._call(self._clean, arguments)

    def shell_start(self, **arguments: Any) -> dict[str, Any]:
        arguments.pop("principal", None)
        arguments.pop("result", None)
        return self._call(self._shell_start, arguments)

    def batch_list(self, **arguments: Any) -> dict[str, Any]:
        return self._call(self._batch_list, arguments)

    def batch_start(self, **arguments: Any) -> dict[str, Any]:
        return self._call(self._batch_start, arguments)

    def batch_status(self, **arguments: Any) -> dict[str, Any]:
        return self._call(self._batch_status, arguments)

    def batch_land(self, **arguments: Any) -> dict[str, Any]:
        return self._call(self._batch_land, arguments)

    def batch_resume(self, **arguments: Any) -> dict[str, Any]:
        return self._call(self._batch_resume, arguments)

    def _project(self, project_id: str) -> Any:
        try:
            return resolve_project(self.config, project_id)
        except (KeyError, PromptError) as error:
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
        parameters = arguments.get("parameters") or {}
        if not isinstance(parameters, Mapping):
            raise _Refusal(ErrorCode.INVALID_ARGUMENT, "parameters must be an object")
        extra_argv = parameters.get("argv", [])
        if not isinstance(extra_argv, list) or not all(
            isinstance(item, str) and item for item in extra_argv
        ):
            raise _Refusal(
                ErrorCode.INVALID_ARGUMENT,
                "parameters.argv must be a list of non-empty strings",
            )
        job = launch.start_operation(
            self.config,
            project,
            operation,
            workspace=workspace,
            extra_argv=extra_argv,
            **(
                {"owner_request_key": arguments["owner_request_key"]}
                if arguments.get("owner_request_key") is not None
                else {}
            ),
        )
        return job_payload(job)

    def _get(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        return job_payload(
            launch.get_job(
                _require_int(arguments, "job_id"),
                self.config,
                _launch_reference(arguments),
                **{
                    key: arguments[key]
                    for key in ("attempt", "attempt_offset", "attempt_limit")
                    if arguments.get(key) is not None
                },
            )
        )

    def _wait(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        job_id = _require_int(arguments, "job_id")
        timeout_seconds = _require_int(arguments, "timeout_seconds")
        job = launch.wait(
            job_id,
            timeout_seconds=float(timeout_seconds),
            reference=_launch_reference(arguments),
        )
        return {**job_payload(job), "timed_out": bool(job.get("wait_timed_out"))}

    def _logs(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        job_id = _require_int(arguments, "job_id")
        reference = _launch_reference(arguments)
        offset = int(arguments.get("offset") or 0)
        max_bytes = int(arguments.get("max_bytes") or MAX_LOG_BYTES)
        page = launch.read_job_artifact(
            self.config,
            job_id,
            reference,
            attempt=arguments.get("attempt"),
            offset=offset,
            limit=max_bytes,
        )
        view = launch.get_job(job_id, self.config, reference, attempt=page["attempt"])
        return {
            **job_payload(view),
            **page,
            "content": page["text"],
            "max_bytes": max_bytes,
            "truncated": page["next_offset"] is not None,
        }

    def _result(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        job_id = _require_int(arguments, "job_id")
        observed = launch.result(
            self.config,
            job_id,
            _launch_reference(arguments),
            attempt=arguments.get("attempt"),
            offset=int(arguments.get("offset") or 0),
            limit=int(arguments.get("max_bytes") or MAX_LOG_BYTES),
        )
        return {
            **job_payload(observed),
            "kind": observed.get("kind"),
            "value": observed.get("value"),
            "page": observed.get("page"),
        }

    def _cancel(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        job_id = _require_int(arguments, "job_id")
        job = launch.cancel(self.config, job_id, reference=_launch_reference(arguments))
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
            after, cursor_project_id = _decode_cursor(cursor)
            if cursor_project_id != project_id:
                raise _Refusal(
                    ErrorCode.STALE_CURSOR,
                    "job list cursor does not match the project filter",
                )
            rows = [row for row in rows if _sort_key(row) < after]
        page = launch.attach_bindings(self.config, rows[:limit])
        truncated = len(rows) > len(page)
        return {
            "jobs": [job_payload(row) for row in page],
            "total": len(rows),
            "truncated": truncated,
            "next_cursor": _encode_cursor(_sort_key(page[-1]), project_id)
            if truncated and page
            else None,
            "snapshot": {"ordering": JOB_LIST_ORDERING, "ceiling": ceiling},
        }

    def _retry(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        return job_payload(
            launch.retry(
                _require_int(arguments, "job_id"), _launch_reference(arguments)
            )
        )

    def _clean(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        job_id = _require_int(arguments, "job_id")
        cleaned = launch.clean(self.config, job_id, _launch_reference(arguments))
        return {
            **job_payload(cleaned),
            "cleaned": bool(cleaned.get("cleaned")),
            "removed": [str(path) for path in cleaned.get("removed") or []],
        }

    # ----------------------------------------------------------- batches

    def _run_id(self, arguments: Mapping[str, Any]) -> str:
        """A run id or the suffix every agentctl verb also accepts."""
        return batch.resolve_run_id(self.config, _require_str(arguments, "run_id"))

    def _run_project(self, run_id: str, arguments: Mapping[str, Any]) -> Any:
        """The run's own project; an explicit project_id must agree with it."""
        declared = _optional_str(arguments, "project_id")
        owner = batch.load(self.config, run_id).project
        if declared is not None and declared != owner:
            raise batch.BatchRefusal(
                "project", f"run {run_id} belongs to {owner}, not {declared}"
            )
        return self._project(owner)

    def _status(self, run_id: str, project: Any) -> dict[str, Any]:
        return run_payload(batch.status(self.config, run_id, project=project))

    def _batch_list(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        project_id = _optional_str(arguments, "project_id")
        if project_id is not None:
            self._project(project_id)
        runs = batch.list_runs(self.config, project_id)
        limit = int(arguments.get("limit") or 50)
        page = sorted(runs, key=lambda run: run.created_at, reverse=True)[:limit]
        # No project: `batch status` reads the landing PR from GitHub when it
        # has one, and a list must not make one network call per run.
        return {
            "runs": [self._status(run.run_id, None) for run in page],
            "total": len(runs),
            "truncated": len(runs) > len(page),
        }

    def _batch_start(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        """agentctl validates the members, claims them, creates the worktrees, queues the workers and the landing."""
        project = self._project(_require_str(arguments, "project_id"))
        beads = arguments.get("beads")
        if (
            not isinstance(beads, list)
            or not beads
            or any(not isinstance(item, str) or not item for item in beads)
        ):
            raise _Refusal(
                ErrorCode.INVALID_ARGUMENT, "beads must be a non-empty list of bead ids"
            )
        workers = arguments.get("workers")
        if workers is not None and (
            not isinstance(workers, list)
            or not all(
                isinstance(group, list)
                and group
                and all(isinstance(item, str) and item for item in group)
                for group in workers
            )
        ):
            raise _Refusal(
                ErrorCode.INVALID_ARGUMENT,
                "workers must be a list of non-empty bead id lists",
            )
        run = batch.start(
            self.config,
            project,
            beads,
            workers=workers,
            backend=_optional_str(arguments, "backend"),
            model=_optional_str(arguments, "model"),
            effort=_optional_str(arguments, "effort"),
        )
        return {
            **self._status(str(run["run_id"]), project),
            "existing": bool(run.get("existing")),
            "resumed": bool(run.get("resumed")),
        }

    def _batch_status(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        run_id = self._run_id(arguments)
        return self._status(run_id, self._run_project(run_id, arguments))

    def _batch_land(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        """Queue a landing task; pueue runs the landing, which can take hours."""
        run_id = self._run_id(arguments)
        project = self._run_project(run_id, arguments)
        queued = batch.queue(self.config, project, run_id)
        return {
            **self._status(run_id, project),
            "landing_job_id": str(queued["landing_task_id"]),
        }

    def _batch_resume(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        run_id = self._run_id(arguments)
        project = self._run_project(run_id, arguments)
        resumed = batch.resume(
            self.config,
            project,
            run_id,
            _require_str(arguments, "worker_id"),
            backend=_optional_str(arguments, "backend"),
            model=_optional_str(arguments, "model"),
            effort=_optional_str(arguments, "effort"),
        )
        return {
            **self._status(run_id, project),
            "resumed_job_id": str(resumed["job"]["job_id"]),
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
