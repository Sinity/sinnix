from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from agentctl import batch, launch, pueue
from agentctl.config import Config
from sinnix_agent_gateway.execution import JobOwnerError, LocalJobs
from sinnix_agent_gateway.owner_errors import ErrorCode

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
    "job_id": 41,
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
        "batch.list": adapter.batch_list,
        "batch.start": adapter.batch_start,
        "batch.status": adapter.batch_status,
        "batch.land": adapter.batch_land,
        "batch.resume": adapter.batch_resume,
    }
    return methods[operation](**arguments)


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
        agent_runner=tmp_path / "runner.sh",
        event_spool=tmp_path / "events.jsonl",
        state_dir=tmp_path / "state",
        agentctl_executable="/bin/true",
        worker_contract=tmp_path / "worker-contract.md",
    )
    return LocalJobs(config)


def test_job_start_launches_the_declared_operation(
    adapter: LocalJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Red if job.start stops reaching the launch route or drops its job identity."""
    seen: dict[str, Any] = {}

    def fake_start(config, project, operation, *, workspace=None, extra_argv=()):
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
    }
    assert payload["job_id"] == "41"
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

    def fake_start(config, project, operation, *, workspace=None, extra_argv=()):
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
    environment, or lands outside the interactive pool."""
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
            "timeout_seconds": 60,
        },
    )
    assert payload["group"] == "interactive"
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
                "timeout_seconds": 60,
            },
        )
    assert escaped.value.code is ErrorCode.POLICY_DENIED
    assert len(seen) == 9


def test_job_list_cursor_is_bound_to_the_project_filter(
    adapter: LocalJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [
        {
            **JOB_ROW,
            "job_id": 30,
            "project": "b",
            "enqueued_at": "2026-09-07T02:00:00Z",
        },
        {
            **JOB_ROW,
            "job_id": 20,
            "project": "a",
            "enqueued_at": "2026-09-07T01:00:00Z",
        },
    ]
    monkeypatch.setattr(launch, "list_jobs", lambda _project=None: rows)
    monkeypatch.setattr(launch, "attach_bindings", lambda _config, page: page)

    first = adapter.list(limit=1)
    assert [row["job_id"] for row in first["jobs"]] == ["30"]
    second = adapter.list(limit=1, cursor=first["next_cursor"])
    assert [row["job_id"] for row in second["jobs"]] == ["20"]

    with pytest.raises(JobOwnerError) as stale:
        adapter.list(limit=1, project_id="b", cursor=first["next_cursor"])
    assert stale.value.code is ErrorCode.STALE_CURSOR


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
            "worktree": "/realm/worktrees/fixture-batch-fixture-run-fixture-1",
            "backend": "claude",
            "model": "policy",
            "effort": "medium",
            "task_id": 41,
            "task_reference": "fixture-worker-abcd1234",
            "task_ids": [41],
            "result": None,
            "stage": "running",
            "task": {"phase": "running", "terminal": False, "exit_code": None},
        }
    ],
    "landing": {
        "task_id": 42,
        "task_reference": "fixture-integrate-9f10",
        "integration_branch": "batch/fixture-run/integration",
        "candidate_sha": None,
        "pr_number": None,
        "failure": None,
        "task": {"phase": "queued", "terminal": False, "exit_code": None},
    },
}


def test_batch_start_hands_the_beads_to_agentctl_and_answers_from_the_manifest(
    adapter: LocalJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Red if the gateway compiles its own prompt or worktree instead of
    handing the beads to agentctl's batch route."""
    seen: dict[str, Any] = {}

    def fake_start(config, project, seeds, *, workers, backend, model, effort, **_kw):
        seen.update(
            project=project.project_id,
            seeds=list(seeds),
            workers=workers,
            backend=backend,
        )
        return {"run_id": RUN_DOCUMENT["run_id"], "existing": False, "resumed": False}

    monkeypatch.setattr(batch, "start", fake_start)
    monkeypatch.setattr(batch, "status", lambda *_a, **_k: RUN_DOCUMENT)
    payload = _call(
        adapter,
        "batch.start",
        {
            "project_id": "fixture",
            "beads": ["fixture-1", "fixture-2"],
            "workers": [["fixture-1", "fixture-2"]],
            "backend": "claude",
        },
    )
    assert seen == {
        "project": "fixture",
        "seeds": ["fixture-1", "fixture-2"],
        "workers": [["fixture-1", "fixture-2"]],
        "backend": "claude",
    }
    assert payload["run_id"] == RUN_DOCUMENT["run_id"]
    assert payload["stage"] == "working" and payload["accepted"] is False
    worker = payload["workers"][0]
    assert worker["worker_id"] == "fixture-1"
    assert worker["beads"] == ["fixture-1", "fixture-2"]
    assert worker["job_id"] == "41" and worker["job_ids"] == ["41"]
    # The manifest's stable reference for each job, which jobs.* addresses by.
    assert worker["job_launch_reference"] == "fixture-worker-abcd1234"
    assert worker["state"] == {
        "phase": "running",
        "terminal": False,
        "exit_code": None,
        "dependencies": None,
    }
    assert worker["result_filed"] is False
    assert payload["landing"]["job_id"] == "42"
    assert payload["landing"]["job_launch_reference"] == "fixture-integrate-9f10"
    assert payload["landing"]["state"]["phase"] == "queued"

    def refuse(config, project, seeds, **_kwargs):
        raise batch.BatchRefusal("members", "fixture-1: claimed by agent-x")

    monkeypatch.setattr(batch, "start", refuse)
    with pytest.raises(JobOwnerError) as refused:
        _call(adapter, "batch.start", {"project_id": "fixture", "beads": ["fixture-1"]})
    assert refused.value.code is ErrorCode.OPERATION_FAILED
    assert refused.value.details == {"refusal": "members"}
    assert "claimed by agent-x" in str(refused.value)


def test_batch_land_queues_a_landing_task_and_reports_the_refusal_class(
    adapter: LocalJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Red if landing runs inside the request instead of on the queue."""
    monkeypatch.setattr(
        batch, "resolve_run_id", lambda _c, token: RUN_DOCUMENT["run_id"]
    )
    monkeypatch.setattr(
        batch, "load", lambda *_a: type("R", (), {"project": "fixture"})()
    )
    monkeypatch.setattr(batch, "status", lambda *_a, **_k: RUN_DOCUMENT)
    monkeypatch.setattr(batch, "queue", lambda *_a: {"landing_task_id": 77})
    monkeypatch.setattr(
        batch, "land", lambda *_a, **_k: pytest.fail("landing ran in the request")
    )

    response = _call(adapter, "batch.land", {"run_id": "a2c81926"})
    assert response["landing_job_id"] == "77"

    def refuse(*_args):
        raise batch.BatchRefusal("landing_in_progress", "landing task 42 is queued")

    monkeypatch.setattr(batch, "queue", refuse)
    with pytest.raises(JobOwnerError) as refused:
        _call(adapter, "batch.land", {"run_id": "a2c81926"})
    assert refused.value.code is ErrorCode.OPERATION_FAILED
    assert refused.value.details == {"refusal": "landing_in_progress"}


def test_batch_verbs_refuse_a_run_that_belongs_to_another_project(
    adapter: LocalJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        batch, "resolve_run_id", lambda _c, token: RUN_DOCUMENT["run_id"]
    )
    monkeypatch.setattr(
        batch, "load", lambda *_a: type("R", (), {"project": "other"})()
    )
    with pytest.raises(JobOwnerError) as refused:
        _call(
            adapter,
            "batch.status",
            {"run_id": "a2c81926", "project_id": "fixture"},
        )
    assert refused.value.code is ErrorCode.INVALID_ARGUMENT
    assert "belongs to other" in str(refused.value)


def test_job_operations_pass_the_launch_reference_through_to_agentctl(
    adapter: LocalJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gateway's stable job identity is agentctl's launch reference.

    Red if an operation drops it, which leaves the call addressing a queue
    position that a reorder may have given to another job.
    """
    reference = "fixture-verify-3f9a21c8"
    moved = {**JOB_ROW, "job_id": 44, "reference": reference}
    seen: dict[str, Any] = {}

    def record(name: str, value: Any = moved) -> Any:
        def call(*args: Any, **kwargs: Any) -> Any:
            seen[name] = (args, kwargs)
            return value

        return call

    monkeypatch.setattr(launch, "wait", record("wait"))
    monkeypatch.setattr(launch, "get_job", record("get"))
    monkeypatch.setattr(launch, "cancel", record("cancel"))
    monkeypatch.setattr(launch, "retry", record("retry"))
    monkeypatch.setattr(
        launch, "clean", record("clean", {**moved, "cleaned": True, "removed": []})
    )
    monkeypatch.setattr(
        launch, "result", record("result", {**moved, "kind": "exit", "value": None})
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
            {"job_id": 41, "launch_reference": reference, **arguments},
        )
        assert answer["launch_reference"] == reference
        assert answer["job_id"] == "44"

    for name in ("wait", "get", "cancel", "retry", "clean", "result"):
        args, kwargs = seen[name]
        assert reference in (*args, *kwargs.values()), name


def test_a_launch_reference_that_is_a_path_is_refused(adapter: LocalJobs) -> None:
    """It names one file under the state directory; a path would leave it."""
    with pytest.raises(JobOwnerError) as refused:
        _call(
            adapter,
            "job.get",
            {"job_id": 41, "launch_reference": "../../etc/passwd"},
        )
    assert refused.value.code is ErrorCode.INVALID_ARGUMENT


def test_job_logs_reads_the_log_of_the_job_the_reference_addresses(
    adapter: LocalJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reference is resolved once and the log comes from that task.

    Red if the read re-addresses the answering id without the reference: a
    `pueue switch` between the two reads hands back another job's log under
    this job's launch reference.
    """
    reference = "fixture-verify-3f9a21c8"
    jobs_dir = adapter.config.jobs_dir
    jobs_dir.mkdir(parents=True, exist_ok=True)

    def task(task_id: int, name: str) -> pueue.Task:
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

    mine = task(44, reference)
    occupant = task(44, "fixture-other-0badc0de")

    monkeypatch.setattr(launch.pueue, "tasks", lambda: {44: mine, 45: occupant})
    monkeypatch.setattr(launch.pueue, "log", lambda _task_id: "")

    answer = _call(adapter, "job.logs", {"job_id": 41, "launch_reference": reference})
    assert answer["launch_reference"] == reference
    assert answer["job_id"] == "44"
    assert answer["content"] == f"log of {reference}"
