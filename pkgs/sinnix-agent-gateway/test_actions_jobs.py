"""Typed job actions over a recorded LocalJobs stand-in."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp.types import CallToolResult
from sinnix_agent_gateway import server as server_module
from sinnix_agent_gateway.actions import contexts, jobs, waits
from sinnix_agent_gateway.app import Runtime, create_server
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.locators import JobLocator, encode_file_ref
from sinnix_mcp import (
    ErrorCode,
    ErrorEnvelope,
    OpaquePayload,
    RequestEnvelope,
    ResponseEnvelope,
)

OWNED = (*jobs.ACTIONS, *waits.ACTIONS, *contexts.ACTIONS)


@dataclass
class FakeJobs:
    """Stands in for LocalJobs: records every request, answers from a table."""

    calls: list[RequestEnvelope] = field(default_factory=list)
    responses: dict[str, Any] = field(default_factory=dict)
    errors: dict[str, tuple[ErrorCode, str]] = field(default_factory=dict)

    def dispatch(self, request: RequestEnvelope) -> ResponseEnvelope:
        self.calls.append(request)
        error = self.errors.get(request.operation)
        if error is not None:
            return ResponseEnvelope(
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                owner="systemd-jobs",
                error=ErrorEnvelope(error[0], error[1], OpaquePayload.bounded({})),
            )
        answer = self.responses.get(request.operation, {"job_id": "41"})
        if callable(answer):
            answer = answer(request.arguments)
        return ResponseEnvelope(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            owner="systemd-jobs",
            payload=OpaquePayload.bounded(answer),
        )


def git(path: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)


def make_server(
    tmp_path: Path,
    principal: str,
    monkeypatch: pytest.MonkeyPatch,
    *,
    with_git: bool = False,
) -> tuple[Any, Runtime, FakeJobs]:
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    if with_git and not (project / ".git").exists():
        git(project, "init", "-q", "-b", "master")
        git(
            project,
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@x",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "root",
        )
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={
            "fixture": ProjectConfig(
                project_id="fixture", path=project, observer_read=True
            )
        },
    )
    runtime = Runtime.create(config, principal)
    fake = FakeJobs()
    runtime.jobs = fake  # type: ignore[assignment]
    monkeypatch.setattr(Runtime, "create", classmethod(lambda _cls, _c, _p: runtime))
    monkeypatch.setattr(
        server_module,
        "visible_actions",
        lambda name: tuple(action for action in OWNED if name in action.principals),
    )
    return create_server(config, principal), runtime, fake


def call(server: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async def invoke() -> Any:
        return await server.call_tool(name, arguments)

    result = anyio.run(invoke)
    if isinstance(result, CallToolResult):
        assert result.structured_content is not None
        return result.structured_content
    return result


RUNNING = {
    "job_id": "41",
    "label": "fixture:lane:fixture-7",
    "kind": "attested-agent",
    "project_id": "fixture",
    "operation": "lane:fixture-7",
    "group": "agent",
    "checkout": {"path": "/realm/worktrees/fixture-feature-packet-fixture-7"},
    "state": {"phase": "running", "terminal": False, "exit_code": None},
    "enqueued_at": "2026-09-05T10:00:00+00:00",
}
DONE = {**RUNNING, "state": {"phase": "succeeded", "terminal": True, "exit_code": 0}}


def test_job_locator_accepts_ref_or_id() -> None:
    assert JobLocator(job_id=41).resolve() == (41, "sinnix://jobs/41")
    assert JobLocator(ref="sinnix://jobs/41").resolve() == (41, "sinnix://jobs/41")
    with pytest.raises(ValueError, match="exactly one"):
        JobLocator()


def test_list_pages_with_refs_and_forwards_the_project_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, _, fake = make_server(tmp_path, "observer", monkeypatch)
    fake.responses["job.list"] = {
        "jobs": [
            RUNNING,
            {
                **DONE,
                "job_id": "40",
                "label": "fixture:check",
                "kind": "declared-operation",
            },
        ],
        "total": 2,
        "truncated": True,
        "next_cursor": "c2",
        "snapshot": {"ordering": "created_at_desc_job_id_desc", "ceiling": ["x", "41"]},
    }
    page = call(server, "jobs.list", {"project": {"project": "fixture"}, "limit": 2})
    assert page["result"]["outcome"] == "ok", page
    data = page["data"]
    assert [job["ref"] for job in data["jobs"]] == [
        "sinnix://jobs/41",
        "sinnix://jobs/40",
    ]
    assert data["next_cursor"] == "c2" and data["truncated"] is True
    lane = data["jobs"][0]["lane"]
    assert lane["bead"] == "fixture-7"
    assert lane["bead_ref"] == "sinnix://projects/fixture/beads/fixture-7"
    assert lane["worktree_ref"] == encode_file_ref(RUNNING["checkout"]["path"])
    assert data["jobs"][1]["lane"] is None
    assert "jobs.cancel" in data["jobs"][0]["affordances"]
    assert "jobs.retry" in data["jobs"][1]["affordances"]
    assert fake.calls[0].arguments == {"limit": 2, "project_id": "fixture"}

    unknown = call(server, "jobs.list", {"project": {"project": "nope"}})
    assert unknown["error"]["code"] == "not_found"


def test_get_returns_summary_log_range_and_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, _, fake = make_server(tmp_path, "observer", monkeypatch)
    fake.responses["job.get"] = DONE
    fake.responses["job.logs"] = lambda args: {
        "job_id": "41",
        "content": "abcdef"[args["offset"] : args["offset"] + args["max_bytes"]],
        "offset": args["offset"],
        "max_bytes": args["max_bytes"],
        "truncated": args["offset"] + args["max_bytes"] < 6,
    }
    fake.responses["job.result"] = {**DONE, "kind": "artifact", "value": {"passed": 3}}

    summary = call(server, "jobs.get", {"target": {"job_id": 41}})["data"]
    assert (
        summary["ref"] == "sinnix://jobs/41"
        and summary["state"]["phase"] == "succeeded"
    )
    assert summary["log"] is None and summary["result"] is None
    assert summary["lane"]["bead"] == "fixture-7"

    logged = call(
        server,
        "jobs.get",
        {
            "target": {"ref": "sinnix://jobs/41"},
            "projection": "log",
            "offset": 2,
            "max_bytes": 2,
        },
    )["data"]
    assert logged["log"] == {
        "ref": "sinnix://jobs/41",
        "job_id": 41,
        "content": "cd",
        "offset": 2,
        "max_bytes": 2,
        "returned_bytes": 2,
        "truncated": True,
        "next_offset": 4,
        "affordances": ["jobs.get", "jobs.logs"],
    }
    tail = call(server, "jobs.logs", {"target": {"job_id": 41}, "offset": 4})["data"]
    assert tail["content"] == "ef" and tail["next_offset"] is None

    result = call(
        server, "jobs.get", {"target": {"job_id": 41}, "projection": "result"}
    )["data"]
    assert result["result"] == {"kind": "artifact", "value": {"passed": 3}}
    assert [c.operation for c in fake.calls] == [
        "job.get",
        "job.get",
        "job.logs",
        "job.logs",
        "job.get",
        "job.result",
    ]

    fake.responses["job.get"] = {**DONE, "job_id": "99"}
    mismatch = call(server, "jobs.get", {"target": {"job_id": 41}})
    assert mismatch["error"]["code"] == "owner_failed"


def test_wait_reports_terminal_or_timeout_from_the_queue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, _, fake = make_server(tmp_path, "observer", monkeypatch)
    fake.responses["job.wait"] = {
        **RUNNING,
        "timed_out": True,
        "detail": "still running",
    }
    waited = call(
        server, "jobs.wait", {"target": {"job_id": 41}, "timeout_seconds": 5}
    )["data"]
    assert waited["outcome"] == "timeout" and waited["timed_out"] is True
    assert (
        waited["detail"] == "still running" and "jobs.cancel" in waited["affordances"]
    )
    assert fake.calls[-1].arguments == {"job_id": 41, "timeout_seconds": 5}

    fake.responses["job.wait"] = DONE
    done = call(server, "jobs.wait", {"target": {"job_id": 41}})["data"]
    assert done["outcome"] == "terminal" and done["job"]["state"]["terminal"] is True


def test_cancel_checks_the_phase_and_surfaces_reap_survivors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, _, fake = make_server(tmp_path, "operator", monkeypatch)
    fake.responses["job.get"] = RUNNING
    fake.responses["job.cancel"] = {
        **RUNNING,
        "state": {"phase": "cancelled", "terminal": True, "exit_code": None},
        "cancel_requested": True,
        "already_terminal": False,
        "cancelled": "killed",
        "reaped": {
            "scope": {
                "unit": "agentctl-agent-x.scope",
                "stopped": False,
                "survivors": [4242],
            }
        },
    }
    stale = call(
        server,
        "jobs.cancel",
        {"target": {"job_id": 41}, "expected_phase": "queued", "idempotency_key": "c1"},
    )
    assert stale["error"]["code"] == "precondition_failed"
    assert stale["error"]["details"]["phase"] == "running"
    assert [c.operation for c in fake.calls] == ["job.get"]

    cancelled = call(
        server,
        "jobs.cancel",
        {
            "target": {"job_id": 41},
            "expected_phase": "running",
            "idempotency_key": "c2",
        },
    )["data"]
    assert cancelled["previous_phase"] == "running"
    assert cancelled["cancelled"] == "killed" and cancelled["scope_stopped"] is False
    assert cancelled["survivors"] == [4242] and cancelled["warnings"]
    assert cancelled["job"]["state"]["phase"] == "cancelled"

    fake.responses["job.retry"] = {
        **RUNNING,
        "state": {"phase": "queued", "terminal": False, "exit_code": None},
    }
    retried = call(
        server, "jobs.retry", {"target": {"job_id": 41}, "idempotency_key": "r1"}
    )["data"]
    assert (
        retried["state"]["phase"] == "queued"
        and fake.calls[-1].operation == "job.retry"
    )


def test_cancel_and_retry_are_not_offered_to_observers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, _, _ = make_server(tmp_path, "observer", monkeypatch)

    async def names() -> set[str]:
        return {tool.name for tool in await server.list_tools()}

    visible = anyio.run(names)
    assert {
        "jobs.list",
        "jobs.get",
        "jobs.wait",
        "wait.for",
        "events.tail",
        "context.compose",
    } <= visible
    assert visible.isdisjoint(
        {"jobs.cancel", "jobs.retry", "operations.run", "shell.run", "agent.for_bead"}
    )


def test_operations_run_targets_the_root_or_a_linked_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, runtime, fake = make_server(
        tmp_path, "operator", monkeypatch, with_git=True
    )
    fake.responses["job.start"] = {
        **DONE,
        "job_id": "50",
        "label": "fixture:check",
        "kind": "declared-operation",
        "operation": "check",
        "state": {"phase": "queued", "terminal": False, "exit_code": None},
    }
    started = call(
        server,
        "operations.run",
        {
            "checkout": {"project": "fixture"},
            "operation": "check",
            "idempotency_key": "op-1",
        },
    )
    assert started["result"]["outcome"] == "ok", started
    assert started["data"]["ref"] == "sinnix://jobs/50"
    assert fake.calls[-1].arguments == {
        "project_id": "fixture",
        "operation": "check",
        "parameters": {},
    }

    worktree = tmp_path / "wt"
    git(
        runtime.config.projects["fixture"].path,
        "worktree",
        "add",
        "-q",
        str(worktree),
        "-b",
        "lane",
    )
    on_worktree = call(
        server,
        "operations.run",
        {
            "checkout": {"path": str(worktree)},
            "operation": "check",
            "idempotency_key": "op-2",
        },
    )
    assert on_worktree["result"]["outcome"] == "ok", on_worktree
    assert fake.calls[-1].arguments["workspace_id"] == str(worktree.resolve())

    fake.errors["job.start"] = (ErrorCode.INVALID_ARGUMENT, "unknown operation: nope")
    refused = call(
        server,
        "operations.run",
        {
            "checkout": {"project": "fixture"},
            "operation": "nope",
            "idempotency_key": "op-3",
        },
    )
    assert refused["error"]["code"] == "invalid_request"
    assert refused["error"]["details"]["project"] == "fixture"


def test_shell_run_is_operator_only_and_keeps_cwd_inside_the_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, _, fake = make_server(tmp_path, "operator", monkeypatch)
    fake.responses["job.shell.start"] = {
        **DONE,
        "job_id": "51",
        "label": "fixture:shell",
        "operation": "shell",
        "group": "interactive",
    }
    started = call(
        server,
        "shell.run",
        {
            "checkout": {"project": "fixture"},
            "argv": ["git", "status"],
            "cwd": "sub",
            "timeout_seconds": 60,
            "idempotency_key": "sh-1",
        },
    )
    assert started["result"]["outcome"] == "ok", started
    assert started["data"]["group"] == "interactive"
    assert fake.calls[-1].arguments == {
        "project_id": "fixture",
        "checkout_id": "default",
        "argv": ["git", "status"],
        "cwd": "sub",
        "timeout_seconds": 60,
        "result": "exit-status",
    }
    fake.errors["job.shell.start"] = (
        ErrorCode.POLICY_DENIED,
        "cwd must stay inside the checkout",
    )
    escaped = call(
        server,
        "shell.run",
        {
            "checkout": {"project": "fixture"},
            "argv": ["ls"],
            "cwd": "../..",
            "idempotency_key": "sh-2",
        },
    )
    assert escaped["error"]["code"] == "policy_denied"


def test_agent_for_bead_starts_a_lane_and_maps_a_taken_bead_to_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, _, fake = make_server(tmp_path, "operator", monkeypatch)
    fake.responses["job.agent.start"] = {
        **RUNNING,
        "lane": {
            "bead": "fixture-7",
            "beads": ["fixture-7", "fixture-8"],
            "branch": "feature/packet/fixture-7",
            "worktree": "/realm/worktrees/fixture-feature-packet-fixture-7",
            "backend": "codex",
            "model": "gpt-5.6-terra",
            "effort": "high",
        },
    }
    started = call(
        server,
        "agent.for_bead",
        {
            "bead": {"id": "fixture-7"},
            "backend": "codex",
            "model": "gpt-5.6-terra",
            "effort": "high",
            "idempotency_key": "lane-1",
        },
    )
    assert started["result"]["outcome"] == "ok", started
    data = started["data"]
    assert data["ref"] == "sinnix://jobs/41" and data["job"]["job_id"] == 41
    assert data["bead_ref"] == "sinnix://projects/fixture/beads/fixture-7"
    assert data["beads"] == ["fixture-7", "fixture-8"]
    assert data["branch"] == "feature/packet/fixture-7"
    assert data["worktree_ref"] == encode_file_ref(data["worktree"])
    assert fake.calls[-1].arguments == {
        "project_id": "fixture",
        "bead_id": "fixture-7",
        "backend": "codex",
        "model": "gpt-5.6-terra",
        "effort": "high",
    }

    fake.errors["job.agent.start"] = (
        ErrorCode.OPERATION_FAILED,
        "feature/packet/fixture-7 already has a worktree at /realm/worktrees/x",
    )
    taken = call(
        server,
        "agent.for_bead",
        {"bead": {"id": "fixture-7"}, "idempotency_key": "lane-2"},
    )
    assert taken["error"]["code"] == "conflict"
    assert taken["error"]["details"]["bead"] == "fixture-7"
    assert taken["error"]["details"]["next_action"] == "agent.for_bead"
