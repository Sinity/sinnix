from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from sinnix_agent_gateway.execution import LocalJobs
from sinnix_mcp import ErrorCode, RequestEnvelope
from sinnixd import lanes, launch
from sinnixd.config import Config

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


def test_agent_start_is_a_lane(
    adapter: LocalJobs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Red if the gateway compiles its own prompt or worktree instead of
    handing the bead to agentctl's lane route."""
    seen: dict[str, Any] = {}

    def fake_lane_start(config, project, bead_id, *, backend, model, effort):
        seen.update(project=project.project_id, bead=bead_id, backend=backend)
        return {
            "bead": bead_id,
            "beads": [bead_id],
            "branch": f"feature/packet/{bead_id}",
            "worktree": f"/realm/worktrees/fixture-feature-packet-{bead_id}",
            "backend": backend or "codex",
            "model": model or "policy",
            "effort": effort or "medium",
            "job": {**JOB_ROW, "label": f"fixture:lane:{bead_id}", "group": "agent"},
        }

    monkeypatch.setattr(lanes, "lane_start", fake_lane_start)
    response = adapter.dispatch(
        _request(
            "job.agent.start",
            {"project_id": "fixture", "bead_id": "fixture-1", "backend": "claude"},
        )
    )
    assert response.error is None, response.error
    payload = response.payload.inline
    assert seen == {"project": "fixture", "bead": "fixture-1", "backend": "claude"}
    assert payload["group"] == "agent"
    assert payload["lane"]["branch"] == "feature/packet/fixture-1"
    assert payload["lane"]["model"] == "policy"

    def refuse(config, project, bead_id, **_kwargs):
        raise lanes.LaneError("feature/packet/fixture-1 already has a worktree")

    monkeypatch.setattr(lanes, "lane_start", refuse)
    refused = adapter.dispatch(
        _request("job.agent.start", {"project_id": "fixture", "bead_id": "fixture-1"})
    )
    assert refused.error is not None
    assert refused.error.code is ErrorCode.OPERATION_FAILED
    assert "already has a worktree" in refused.error.message
