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


def test_agent_start_is_a_batch_of_one_seed(
    adapter: LocalJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Red if the gateway compiles its own prompt or worktree instead of
    handing the bead to agentctl's batch route."""
    seen: dict[str, Any] = {}

    def fake_start(config, project, seeds, *, backend, model, effort, **_kwargs):
        seen.update(project=project.project_id, seeds=list(seeds), backend=backend)
        return {
            "run_id": "fixture-run",
            "workers": [
                {
                    "id": seeds[0],
                    "beads": list(seeds),
                    "branch": f"batch/fixture-run/{seeds[0]}",
                    "worktree": f"/realm/worktrees/fixture-batch-fixture-run-{seeds[0]}",
                    "backend": backend or "codex",
                    "model": model or "policy",
                    "effort": effort or "medium",
                    "task_id": JOB_ROW["job_id"],
                }
            ],
        }

    monkeypatch.setattr(batch, "start", fake_start)
    monkeypatch.setattr(
        launch,
        "get_job",
        lambda task_id: {
            **JOB_ROW,
            "label": "fixture:worker:fixture-run:fixture-1",
            "group": "agent",
        },
    )
    response = adapter.dispatch(
        _request(
            "job.agent.start",
            {"project_id": "fixture", "bead_id": "fixture-1", "backend": "claude"},
        )
    )
    assert response.error is None, response.error
    payload = response.payload.inline
    assert seen == {"project": "fixture", "seeds": ["fixture-1"], "backend": "claude"}
    assert payload["group"] == "agent"
    assert payload["run_id"] == "fixture-run"
    assert payload["lane"]["branch"] == "batch/fixture-run/fixture-1"
    assert payload["lane"]["model"] == "policy"

    def refuse(config, project, seeds, **_kwargs):
        raise batch.BatchRefusal("members", "fixture-1: claimed by agent-x")

    monkeypatch.setattr(batch, "start", refuse)
    refused = adapter.dispatch(
        _request("job.agent.start", {"project_id": "fixture", "bead_id": "fixture-1"})
    )
    assert refused.error is not None
    assert refused.error.code is ErrorCode.OPERATION_FAILED
    assert "claimed by agent-x" in refused.error.message
