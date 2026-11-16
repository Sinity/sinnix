from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from agentctl import artifacts, job_queries, launch, pueue
from agentctl.config import Config
from agentctl.limits import MAX_AGENT_TIMEOUT_SECONDS
from sinnix_agent_gateway.execution import JobOwnerError, LocalJobs

DESCRIPTOR = """
schema = 1

[project]
id = "fixture"
display_name = "Fixture"
root_markers = [".agentctl/project.toml"]

[environment]
kind = "none"
command = ["/bin/sh", "-c"]

[operations.verify]
description = "fixture verification"
exec = ["true"]
"""

JOB_ROW = {
    "task_id": 41,
    "label": "fixture:verify",
    "kind": "declared-operation",
    "project": "fixture",
    "operation": "verify",
    "group": "normal",
    "phase": "queued",
    "terminal": False,
    "exit_code": None,
}


def _call(
    adapter: LocalJobs, operation: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    methods = {
        "job.start": adapter.start,
        "job.get": adapter.get,
        "job.wait": adapter.wait,
        "job.logs": adapter.logs,
        "job.result": adapter.result,
        "job.cancel": adapter.cancel,
        "job.list": adapter.list,
        "job.retry": adapter.retry,
        "job.clean": adapter.clean,
        "job.shell.start": adapter.shell_start,
        "job.queues": adapter.queues,
    }
    return methods[operation](**arguments)


EMPTY_QUEUE = pueue.Status({}, {"normal": {"status": "Running", "parallel_tasks": 3}})


@pytest.fixture(autouse=True)
def _no_live_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unfinished job's queue read must never reach the operator's pueued."""
    monkeypatch.setattr(pueue, "live", lambda: EMPTY_QUEUE)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    root = tmp_path / "fixture"
    (root / ".agentctl").mkdir(parents=True)
    (root / ".agentctl" / "project.toml").write_text(DESCRIPTOR)
    (root / "sub").mkdir()
    return root


@pytest.fixture
def adapter(tmp_path: Path, root: Path) -> LocalJobs:
    config = Config(
        project_roots=(root,),
        event_spool=tmp_path / "events.jsonl",
        state_dir=tmp_path / "state",
        agentctl_executable="/bin/true",
    )
    return LocalJobs(config)


def test_job_start_launches_the_declared_operation(
    adapter: LocalJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Red if job.start stops reaching the launch route or drops its job identity."""
    seen: dict[str, Any] = {}

    def fake_start(
        config, project, operation, *, workspace=None, extra_argv=(), binding=None
    ):
        seen["binding"] = binding
        seen["project_id"] = project.project_id
        seen["operation"] = operation.name
        seen["workspace"] = workspace
        return {**JOB_ROW, "path": str(project.root)}

    monkeypatch.setattr(launch, "start_operation", fake_start)
    payload = _call(
        adapter, "job.start", {"project_id": "fixture", "operation": "verify"}
    )
    assert seen == {
        "project_id": "fixture",
        "operation": "verify",
        "workspace": None,
        "binding": {"actor": "sinnix-gateway:operator"},
    }
    assert payload["task_id"] == "41"
    assert payload["kind"] == "declared-operation"
    assert payload["state"] == {
        "phase": "queued",
        "terminal": False,
        "exit_code": None,
        "dependencies": None,
    }
    assert set(payload).isdisjoint({"contract", "principal", "artifacts"})


def test_job_start_forwards_declared_operation_arguments(
    adapter: LocalJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}

    def fake_start(
        config, project, operation, *, workspace=None, extra_argv=(), binding=None
    ):
        seen["extra_argv"] = extra_argv
        return JOB_ROW

    monkeypatch.setattr(launch, "start_operation", fake_start)
    _call(
        adapter,
        "job.start",
        {
            "project_id": "fixture",
            "operation": "verify",
            "parameters": {"argv": ["--changed-only", "src/main.py"]},
        },
    )
    assert seen["extra_argv"] == ["--changed-only", "src/main.py"]


def test_unknown_operation_is_an_error(adapter: LocalJobs) -> None:
    """Red if an unrouted operation is silently accepted."""
    with pytest.raises(KeyError):
        _call(adapter, "job.teleport", {})


def test_shell_start_queues_the_argv_inside_the_checkout(
    adapter: LocalJobs, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Red if a shell command escapes the checkout, skips the project
    environment, or lands outside the lane it was routed to."""
    seen: dict[str, Any] = {}

    def fake_enqueue(config, **kwargs):
        seen.update(kwargs)
        return {**JOB_ROW, "label": kwargs["label"], "group": kwargs["group"]}

    monkeypatch.setattr(launch, "enqueue", fake_enqueue)
    payload = _call(
        adapter,
        "job.shell.start",
        {
            "project_id": "fixture",
            "checkout_id": "default",
            "argv": ["printf", "fixture"],
            "cwd": "sub",
            "group": "shell-quick",
            "timeout_seconds": 60,
        },
    )
    assert payload["group"] == "shell-quick"
    assert seen["label"] == "fixture:shell"
    assert seen["working_directory"] == (root / "sub").resolve()
    assert seen["argv"] == ("/bin/sh", "-c", "printf", "fixture")
    assert seen["timeout_seconds"] == 60
    assert seen["result_kind"] == "exit"

    with pytest.raises(JobOwnerError) as escaped:
        _call(
            adapter,
            "job.shell.start",
            {
                "project_id": "fixture",
                "checkout_id": "default",
                "argv": ["true"],
                "cwd": "../..",
                "group": "shell-quick",
                "timeout_seconds": 60,
            },
        )
    assert escaped.value.code == "policy_denied"
    assert len(seen) == 10

    long = _call(
        adapter,
        "job.shell.start",
        {
            "project_id": "fixture",
            "checkout_id": "default",
            "argv": ["claude", "-p", "work"],
            "group": "shell-long",
        },
    )
    assert long["group"] == "shell-long"
    # No ceiling asked for: the unit gets the agent watchdog, not an hour.
    assert seen["timeout_seconds"] == MAX_AGENT_TIMEOUT_SECONDS

    with pytest.raises(JobOwnerError) as foreign:
        _call(
            adapter,
            "job.shell.start",
            {
                "project_id": "fixture",
                "checkout_id": "default",
                "argv": ["true"],
                "group": "bulk",
            },
        )
    assert foreign.value.code == "invalid_request"


def test_job_list_cursor_is_bound_to_the_project_filter(
    adapter: LocalJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [
        {
            **JOB_ROW,
            "task_id": 30,
            "project": "b",
            "enqueued_at": "2026-09-07T02:00:00Z",
        },
        {
            **JOB_ROW,
            "task_id": 20,
            "project": "a",
            "enqueued_at": "2026-09-07T01:00:00Z",
        },
    ]
    monkeypatch.setattr(job_queries, "list_jobs", lambda _project=None: rows)
    monkeypatch.setattr(job_queries, "attach_bindings", lambda _config, page: page)

    first = adapter.list(limit=1)
    assert [row["task_id"] for row in first["jobs"]] == ["30"]
    second = adapter.list(limit=1, cursor=first["next_cursor"])
    assert [row["task_id"] for row in second["jobs"]] == ["20"]

    with pytest.raises(JobOwnerError) as stale:
        adapter.list(limit=1, project_id="b", cursor=first["next_cursor"])
    assert stale.value.code == "stale_cursor"


def test_job_operations_pass_the_job_id_through_to_agentctl(
    adapter: LocalJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The optional job ID reaches each read and control as a filter."""
    job_id = "fixture-verify-3f9a21c8"
    selected = {**JOB_ROW, "task_id": 41, "job_id": job_id}
    seen: dict[str, Any] = {}

    def record(name: str, value: Any = selected) -> Any:
        def call(*args: Any, **kwargs: Any) -> Any:
            seen[name] = (args, kwargs)
            return value

        return call

    monkeypatch.setattr(job_queries, "wait", record("wait"))
    monkeypatch.setattr(job_queries, "get_job", record("get"))
    monkeypatch.setattr(launch, "cancel", record("cancel"))
    monkeypatch.setattr(launch, "retry", record("retry"))
    monkeypatch.setattr(
        launch, "clean", record("clean", {**selected, "cleaned": True, "removed": []})
    )
    monkeypatch.setattr(
        job_queries,
        "result",
        record("result", {**selected, "kind": "exit", "value": None}),
    )

    for operation, arguments in (
        ("job.wait", {"timeout_seconds": 5}),
        ("job.get", {}),
        ("job.cancel", {}),
        ("job.retry", {}),
        ("job.clean", {}),
        ("job.result", {}),
    ):
        answer = _call(
            adapter,
            operation,
            {"task_id": 41, "job_id": job_id, **arguments},
        )
        assert answer["job_id"] == job_id
        assert answer["task_id"] == "41"

    for name in ("wait", "get", "cancel", "retry", "clean", "result"):
        args, kwargs = seen[name]
        assert job_id in (*args, *kwargs.values()), name
    assert seen["retry"][0][0] is adapter.config


@pytest.mark.parametrize("already_terminal", [False, True])
def test_cancel_keeps_requester_and_does_not_infer_prior_terminal_state(
    adapter: LocalJobs,
    monkeypatch: pytest.MonkeyPatch,
    already_terminal: bool,
) -> None:
    seen = {}
    request = {"actor": "gateway:operator", "reason": "stop requested", "attempt": 1}

    def cancel(*args: Any, **kwargs: Any) -> dict[str, Any]:
        seen.update(kwargs)
        return {
            **JOB_ROW,
            "phase": "cancelled",
            "terminal": True,
            "already_terminal": already_terminal,
            "cancellation": request,
            "state": "stopped",
            "unit": "fixture.service",
        }

    monkeypatch.setattr(launch, "cancel", cancel)
    answer = adapter.cancel(
        task_id=41, actor="gateway:operator", reason="stop requested"
    )
    assert seen["actor"] == "gateway:operator" and seen["reason"] == "stop requested"
    assert answer["already_terminal"] is already_terminal
    assert answer["cancellation"] == request
    assert (
        answer["unit"] == "fixture.service"
        and answer["cancellation_state"] == "stopped"
    )


def test_a_job_id_that_is_a_path_is_refused(adapter: LocalJobs) -> None:
    """It names one file under the state directory; a path would leave it."""
    with pytest.raises(JobOwnerError) as refused:
        _call(
            adapter,
            "job.get",
            {"task_id": 41, "job_id": "../../etc/passwd"},
        )
    assert refused.value.code == "invalid_request"


def test_job_logs_reads_only_the_selected_task(
    adapter: LocalJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = "fixture-verify-3f9a21c8"
    jobs_dir = adapter.config.jobs_dir
    jobs_dir.mkdir(parents=True, exist_ok=True)
    log_path = jobs_dir / f"{job_id}.log"
    artifacts.begin({"log_path": str(log_path)}, "fixture-input")
    log_path.write_text(f"log of {job_id}")
    task = pueue.Task(
        task_id=41,
        label="fixture:verify",
        group="normal",
        status="Done",
        result="Success",
        exit_code=0,
        path=str(jobs_dir),
        dependencies=(),
        command=f"agentctl-run {jobs_dir / f'{job_id}.json'}",
    )
    monkeypatch.setattr(pueue, "task", lambda task_id: task if task_id == 41 else None)
    monkeypatch.setattr(pueue, "log", lambda _task_id: "")

    answer = adapter.logs(task_id=41, job_id=job_id)
    assert answer["job_id"] == job_id
    assert answer["task_id"] == "41"
    assert answer["content"] == f"log of {job_id}"

    with pytest.raises(JobOwnerError):
        adapter.logs(task_id=41, job_id="fixture-other-0badc0de")


def test_job_logs_keeps_the_job_and_page_on_one_attempt(adapter, root, monkeypatch):
    job_id = "fixture-verify-output-race"
    adapter.config.inputs_dir.mkdir(parents=True)
    path = adapter.config.inputs_dir / f"{job_id}.json"
    document = {
        "job_id": job_id,
        "queue_task_id": 41,
        "working_directory": str(root),
        "log_path": str(adapter.config.jobs_dir / f"{job_id}.log"),
        "pool": "normal",
    }
    path.write_text(json.dumps(document))
    selected = pueue.Task(
        task_id=41,
        label="fixture:verify",
        group="normal",
        status="Running",
        result=None,
        exit_code=None,
        path=str(root),
        dependencies=(),
        command=f"agentctl-run {path}",
    )
    monkeypatch.setattr(pueue, "task", lambda task_id: selected)
    original_view = job_queries.artifact_view

    def start_after_view(config, task, attempt=None):
        view = original_view(config, task, attempt)
        if not view["attempts"]:
            started = artifacts.begin(document, str(path))
            Path(started["log_path"]).write_text("new attempt output")
        return view

    monkeypatch.setattr(job_queries, "artifact_view", start_after_view)
    first = adapter.logs(task_id=41, job_id=job_id)
    assert first["attempt"] == 0 and first["attempt_count"] == 0
    assert first["available"] is False and first["content"] == ""
    assert first["checkout"]["path"] == str(root)
    second = adapter.logs(task_id=41, job_id=job_id)
    assert second["attempt"] == 1 and second["content"] == "new attempt output"
    assert second["checkout"]["path"] == str(root)


def _task(
    task_id: int, status: str, *, group: str, started: str | None = None
) -> pueue.Task:
    return pueue.Task(
        task_id=task_id,
        label="fixture:shell",
        group=group,
        status=status,
        result=None,
        exit_code=None,
        path="/fixture",
        dependencies=(),
        enqueued_at="2026-09-29T10:00:00+00:00",
        started_at=started,
    )


def test_an_unfinished_job_answers_with_its_place_in_the_queue(
    adapter: LocalJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Red if a queued job's answer omits who holds its group's slots."""
    busy = pueue.Status(
        {
            40: _task(
                40, "Running", group="shell-long", started="2026-09-29T09:00:00+00:00"
            ),
            41: _task(41, "Queued", group="shell-long"),
        },
        {"shell-long": {"status": "Running", "parallel_tasks": 1}},
    )
    monkeypatch.setattr(pueue, "live", lambda: busy)
    queued = {**JOB_ROW, "group": "shell-long", "task_id": 41}
    monkeypatch.setattr(job_queries, "get_job", lambda *args, **kwargs: queued)

    answer = _call(adapter, "job.get", {"task_id": 41})

    queue = answer["queue"]
    assert queue["group"] == "shell-long" and queue["parallel"] == 1
    assert queue["position"] == 1 and queue["queued_count"] == 1
    assert [entry["task_id"] for entry in queue["occupied_by"]] == [40]
    assert queue["occupied_by"][0]["seconds"] > 0

    rows = _call(adapter, "job.queues", {"groups": ["shell-long"]})["queues"]
    assert [row["group"] for row in rows] == ["shell-long"]
    assert rows[0]["running_count"] == 1 and rows[0]["queued_count"] == 1

    def unavailable() -> pueue.Status:
        raise pueue.PueueError("daemon unreachable")

    monkeypatch.setattr(pueue, "live", unavailable)
    degraded = _call(adapter, "job.get", {"task_id": 41})
    # The job's own answer stands; the missing queue is named, not fatal.
    assert "queue" not in degraded
    assert degraded["queue_unavailable"] == "daemon unreachable"
    assert degraded["task_id"] == "41"


@pytest.mark.parametrize("shell", [False, True])
def test_remote_run_binding_reaches_job_owner(adapter, monkeypatch, shell):
    from sinnix_agent_gateway.calllog import RUN_ID

    seen = {}

    def capture(*args, **kwargs):
        seen.update(kwargs)
        return JOB_ROW

    monkeypatch.setattr(launch, "enqueue", capture)
    monkeypatch.setattr(launch, "start_operation", capture)
    token = RUN_ID.set("wfr_fixture")
    try:
        if shell:
            adapter.shell_start(
                project_id="fixture", argv=["true"], group="shell-quick"
            )
        else:
            adapter.start(project_id="fixture", operation="verify")
    finally:
        RUN_ID.reset(token)
    assert seen["binding"] == {
        "actor": "sinnix-gateway:operator:wfr_fixture",
        "remote_run_id": "wfr_fixture",
    }
