from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from agentctl import batch, launch
from agentctl.config import Config
from sinnix_agent_gateway.execution import LocalJobs
from sinnix_mcp import ErrorCode, RequestEnvelope

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


def _request(operation: str, arguments: dict[str, Any]) -> RequestEnvelope:
    return RequestEnvelope(
        request_id=str(uuid4()),
        correlation_id=str(uuid4()),
        operation=operation,
        owner="systemd-jobs",
        principal="operator",
        arguments=arguments,
    )


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
    response = adapter.dispatch(
        _request("job.start", {"project_id": "fixture", "operation": "verify"})
    )
    assert response.error is None
    assert seen == {"project_id": "fixture", "operation": "verify", "workspace": None}
    payload = response.payload.inline
    assert payload["job_id"] == "41"
    assert payload["kind"] == "declared-operation"
    assert payload["state"] == {
        "phase": "queued",
        "terminal": False,
        "exit_code": None,
    }
    assert set(payload).isdisjoint({"contract", "principal", "artifacts"})


def test_unknown_operation_is_an_error_envelope(adapter: LocalJobs) -> None:
    """Red if an unrouted operation raises or answers with a payload."""
    response = adapter.dispatch(_request("job.teleport", {}))
    assert response.payload is None
    assert response.error is not None
    assert response.error.code is ErrorCode.INVALID_ARGUMENT


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
    response = adapter.dispatch(
        _request(
            "job.shell.start",
            {
                "project_id": "fixture",
                "checkout_id": "default",
                "argv": ["printf", "fixture"],
                "cwd": "sub",
                "timeout_seconds": 60,
            },
        )
    )
    assert response.error is None, response.error
    assert response.payload.inline["group"] == "interactive"
    assert seen["label"] == "fixture:shell"
    assert seen["working_directory"] == (root / "sub").resolve()
    assert seen["argv"] == ("/bin/sh", "-c", "printf", "fixture")
    assert seen["timeout_seconds"] == 60
    assert seen["result_kind"] == "exit"

    escaped = adapter.dispatch(
        _request(
            "job.shell.start",
            {
                "project_id": "fixture",
                "checkout_id": "default",
                "argv": ["true"],
                "cwd": "../..",
                "timeout_seconds": 60,
            },
        )
    )
    assert escaped.error is not None
    assert escaped.error.code is ErrorCode.POLICY_DENIED
    assert len(seen) == 9


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
            "task_ids": [41],
            "result": None,
            "stage": "running",
            "task": {"phase": "running", "terminal": False, "exit_code": None},
        }
    ],
    "landing": {
        "task_id": 42,
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
    response = adapter.dispatch(
        _request(
            "batch.start",
            {
                "project_id": "fixture",
                "beads": ["fixture-1", "fixture-2"],
                "workers": [["fixture-1", "fixture-2"]],
                "backend": "claude",
            },
        )
    )
    assert response.error is None, response.error
    payload = response.payload.inline
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
    assert worker["state"] == {"phase": "running", "terminal": False, "exit_code": None}
    assert worker["result_filed"] is False
    assert payload["landing"]["job_id"] == "42"
    assert payload["landing"]["state"]["phase"] == "queued"

    def refuse(config, project, seeds, **_kwargs):
        raise batch.BatchRefusal("members", "fixture-1: claimed by agent-x")

    monkeypatch.setattr(batch, "start", refuse)
    refused = adapter.dispatch(
        _request("batch.start", {"project_id": "fixture", "beads": ["fixture-1"]})
    )
    assert refused.error is not None
    assert refused.error.code is ErrorCode.OPERATION_FAILED
    assert refused.error.details.inline == {"refusal": "members"}
    assert "claimed by agent-x" in refused.error.message


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

    response = adapter.dispatch(_request("batch.land", {"run_id": "a2c81926"}))
    assert response.error is None, response.error
    assert response.payload.inline["landing_job_id"] == "77"

    def refuse(*_args):
        raise batch.BatchRefusal("landing_in_progress", "landing task 42 is queued")

    monkeypatch.setattr(batch, "queue", refuse)
    refused = adapter.dispatch(_request("batch.land", {"run_id": "a2c81926"}))
    assert refused.error is not None
    assert refused.error.code is ErrorCode.OPERATION_FAILED
    assert refused.error.details.inline == {"refusal": "landing_in_progress"}


def test_batch_verbs_refuse_a_run_that_belongs_to_another_project(
    adapter: LocalJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        batch, "resolve_run_id", lambda _c, token: RUN_DOCUMENT["run_id"]
    )
    monkeypatch.setattr(
        batch, "load", lambda *_a: type("R", (), {"project": "other"})()
    )
    refused = adapter.dispatch(
        _request("batch.status", {"run_id": "a2c81926", "project_id": "fixture"})
    )
    assert refused.error is not None
    assert refused.error.code is ErrorCode.INVALID_ARGUMENT
    assert "belongs to other" in refused.error.message
