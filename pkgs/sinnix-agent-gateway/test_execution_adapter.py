from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from agentctl import artifacts, batch_history, job_queries, launch, operator_view, pueue
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
        "batch.list": adapter.batch_list,
        "batch.status": adapter.batch_status,
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


RUN_DOCUMENT = {
    "run_id": "fixture-20260906-012123-a2c81926",
    "project": "fixture",
    "base_commit": "b" * 40,
    "created_at": "2026-09-06T01:21:23+00:00",
    "harness": "queued",
    "stage": "working",
    "prepared": True,
    "acceptance": None,
    "abandoned": None,
    "workers": [
        {
            "id": "fixture-1",
            "beads": ["fixture-1", "fixture-2"],
            "branch": "batch/fixture-run/fixture-1",
            "worktree": "/realm/worktree/fixture-batch-fixture-run-fixture-1",
            "backend": "claude",
            "model": "policy",
            "effort": "medium",
            "task_id": 41,
            "job_id": "fixture-worker-abcd1234",
            "task_ids": [41],
            "result": None,
            "stage": "running",
            "task": {"phase": "running", "terminal": False, "exit_code": None},
        }
    ],
    "landing": {
        "task_id": 42,
        "job_id": "fixture-integrate-9f10",
        "integration_branch": "batch/fixture-run/integration",
        "candidate_sha": None,
        "pr_number": None,
        "failure": None,
        "task": {"phase": "queued", "terminal": False, "exit_code": None},
    },
}


def test_batch_verbs_refuse_a_run_that_belongs_to_another_project(
    adapter: LocalJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        batch_history, "resolve_run_id", lambda _c, token: RUN_DOCUMENT["run_id"]
    )
    monkeypatch.setattr(
        batch_history, "load", lambda *_a: type("R", (), {"project": "other"})()
    )
    with pytest.raises(JobOwnerError) as refused:
        _call(
            adapter,
            "batch.status",
            {"run_id": "a2c81926", "project_id": "fixture"},
        )
    assert refused.value.code == "invalid_request"
    assert "belongs to other" in str(refused.value)


def test_job_operations_pass_the_job_id_through_to_agentctl(
    adapter: LocalJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gateway's stable job identity is agentctl's launch job_id.

    Red if an operation drops it, which leaves the call addressing a queue
    position that a reorder may have given to another job.
    """
    job_id = "fixture-verify-3f9a21c8"
    moved = {**JOB_ROW, "task_id": 44, "job_id": job_id}
    seen: dict[str, Any] = {}

    def record(name: str, value: Any = moved) -> Any:
        def call(*args: Any, **kwargs: Any) -> Any:
            seen[name] = (args, kwargs)
            return value

        return call

    monkeypatch.setattr(job_queries, "wait", record("wait"))
    monkeypatch.setattr(job_queries, "get_job", record("get"))
    monkeypatch.setattr(launch, "cancel", record("cancel"))
    monkeypatch.setattr(launch, "retry", record("retry"))
    monkeypatch.setattr(
        launch, "clean", record("clean", {**moved, "cleaned": True, "removed": []})
    )
    monkeypatch.setattr(
        job_queries,
        "result",
        record("result", {**moved, "kind": "exit", "value": None}),
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
        assert answer["task_id"] == "44"

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


def test_job_logs_reads_the_log_of_the_job_the_reference_addresses(
    adapter: LocalJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The job_id is resolved once and the log comes from that task.

    Red if the read re-addresses the answering id without the job_id: a
    `pueue switch` between the two reads hands back another job's log under
    this job's launch job_id.
    """
    job_id = "fixture-verify-3f9a21c8"
    jobs_dir = adapter.config.jobs_dir
    jobs_dir.mkdir(parents=True, exist_ok=True)

    def task(task_id: int, name: str) -> pueue.Task:
        artifacts.begin({"log_path": str(jobs_dir / f"{name}.log")}, "fixture-input")
        (jobs_dir / f"{name}.log").write_text(f"log of {name}")
        return pueue.Task(
            task_id=task_id,
            label="fixture:verify",
            group="normal",
            status="Done",
            result="Success",
            exit_code=0,
            path=str(jobs_dir),
            dependencies=(),
            command=f"agentctl-run {jobs_dir / f'{name}.json'}",
        )

    mine = task(44, job_id)
    occupant = task(44, "fixture-other-0badc0de")

    # Id 41 names nothing now; the job_id finds its job by the one command
    # that names its launch input, never through the whole history.
    monkeypatch.setattr(
        launch.pueue, "task", lambda task_id: {45: occupant}.get(task_id)
    )
    monkeypatch.setattr(
        launch.pueue,
        "tasks_by_command",
        lambda fragment: {
            candidate.task_id: candidate
            for candidate in (mine, occupant)
            if fragment in candidate.command
        },
    )
    monkeypatch.setattr(launch.pueue, "log", lambda _task_id: "")

    answer = _call(adapter, "job.logs", {"task_id": 41, "job_id": job_id})
    assert answer["job_id"] == job_id
    assert answer["task_id"] == "44"
    assert answer["content"] == f"log of {job_id}"


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


def test_original_status_preserves_worker_and_job_identities(adapter, monkeypatch):
    monkeypatch.setattr(
        batch_history, "resolve_run_id", lambda config, token: RUN_DOCUMENT["run_id"]
    )
    monkeypatch.setattr(
        batch_history, "load", lambda *args: type("R", (), {"project": "fixture"})()
    )
    monkeypatch.setattr(operator_view, "status", lambda *args, **kwargs: RUN_DOCUMENT)
    payload = adapter.batch_status(run_id="a2c81926")
    assert payload["run_id"] == RUN_DOCUMENT["run_id"]
    worker = payload["workers"][0]
    assert worker["beads"] == ["fixture-1", "fixture-2"]
    assert worker["task_id"] == "41" and worker["task_ids"] == ["41"]
    assert worker["job_id"] == "fixture-worker-abcd1234"
    assert payload["landing"]["job_id"] == "fixture-integrate-9f10"


@pytest.mark.parametrize("code", ["unknown_run", "ambiguous_run"])
def test_history_identity_refusals_keep_their_typed_code(adapter, monkeypatch, code):
    def refuse(*args):
        raise batch_history.HistoryRefusal(code, "fixture history refusal")

    monkeypatch.setattr(batch_history, "resolve_run_id", refuse)
    with pytest.raises(JobOwnerError) as failure:
        adapter.batch_status(run_id="not-an-executor")
    assert failure.value.details == {"refusal": code}
    assert failure.value.code == "invalid_request"


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
