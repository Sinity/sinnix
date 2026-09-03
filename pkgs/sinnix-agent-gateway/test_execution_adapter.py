from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from sinnix_agent_gateway.execution import LocalJobs
from sinnix_mcp import ErrorCode, RequestEnvelope
from sinnixd import launch
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
def adapter(tmp_path: Path) -> LocalJobs:
    root = tmp_path / "fixture"
    (root / ".agentctl").mkdir(parents=True)
    (root / ".agentctl" / "project.toml").write_text(DESCRIPTOR)
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
        return {
            "job_id": 41,
            "label": "fixture:verify",
            "project": "fixture",
            "operation": "verify",
            "phase": "queued",
            "terminal": False,
            "exit_code": None,
            "path": str(project.root),
        }

    monkeypatch.setattr(launch, "start_operation", fake_start)
    response = adapter.dispatch(
        _request("job.start", {"project_id": "fixture", "operation": "verify"})
    )
    assert response.error is None
    assert seen == {"project_id": "fixture", "operation": "verify", "workspace": None}
    payload = response.payload.inline
    assert payload["job_id"] == "41"
    assert payload["state"] == {
        "phase": "queued",
        "terminal": False,
        "exit_code": None,
    }


def test_unknown_operation_is_an_error_envelope(adapter: LocalJobs) -> None:
    """Red if an unrouted operation raises or answers with a payload."""
    response = adapter.dispatch(_request("job.teleport", {}))
    assert response.payload is None
    assert response.error is not None
    assert response.error.code is ErrorCode.INVALID_ARGUMENT


def test_shell_start_is_refused(adapter: LocalJobs) -> None:
    """Red if arbitrary shell launches become reachable through the job owner."""
    response = adapter.dispatch(_request("job.shell.start", {"argv": ["true"]}))
    assert response.error is not None
    assert response.error.code is ErrorCode.POLICY_DENIED
