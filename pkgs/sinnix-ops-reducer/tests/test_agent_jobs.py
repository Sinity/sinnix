from __future__ import annotations

import json
import subprocess

import pytest
from sinnix_ops_reducer.agent_jobs import (
    MAX_AGENTCTL_RESPONSE_BYTES,
    MAX_SNAPSHOT_JOBS,
    AgentCtlClient,
    AgentCtlError,
)


def response(value: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        ["agentctl"],
        0,
        stdout=json.dumps({"ok": True, "payload": {"kind": "inline", "value": value}}),
    )


def test_list_preserves_daemon_order_and_paging_for_an_exactly_bounded_page() -> None:
    calls: list[list[str]] = []
    jobs = [
        {
            "job_id": f"job-{number}",
            "created_at": f"2026-08-23T{10 + number // 60:02d}:{number % 60:02d}:00Z",
        }
        for number in range(MAX_SNAPSHOT_JOBS)
    ]

    def runner(command, **_kwargs):
        calls.append(command)
        return response(
            {"jobs": jobs, "truncated": True, "next_cursor": "cursor-page-2"}
        )

    listed = AgentCtlClient("fixture-agentctl", runner=runner).list()
    assert calls == [["fixture-agentctl", "job", "list"]]
    assert listed["truncated"] is True
    assert listed["next_cursor"] == "cursor-page-2"
    assert len(listed["jobs"]) == MAX_SNAPSHOT_JOBS
    assert listed["jobs"][0]["job_id"] == "job-0"


@pytest.mark.parametrize(
    "value",
    [
        {"jobs": [], "truncated": True, "next_cursor": None},
        {"jobs": [], "truncated": False, "next_cursor": "unexpected"},
        {"jobs": ["not-a-job"], "truncated": False, "next_cursor": None},
        {
            "jobs": [{}] * (MAX_SNAPSHOT_JOBS + 1),
            "truncated": False,
            "next_cursor": None,
        },
    ],
)
def test_list_rejects_contradictory_or_unbounded_pages(value: dict) -> None:
    client = AgentCtlClient("fixture-agentctl", runner=lambda *_args, **_kwargs: response(value))

    with pytest.raises(AgentCtlError):
        client.list()


def test_get_and_cancel_require_a_typed_inline_job_response() -> None:
    calls: list[list[str]] = []

    def runner(command, **_kwargs):
        calls.append(command)
        return response({"job_id": command[-1], "state": {"terminal": False}})

    client = AgentCtlClient("fixture-agentctl", runner=runner)
    assert client.get("job-1")["job_id"] == "job-1"
    assert client.cancel("job-1")["job_id"] == "job-1"
    assert calls == [
        ["fixture-agentctl", "job", "get", "job-1"],
        ["fixture-agentctl", "job", "cancel", "job-1"],
    ]


def test_rejects_unbounded_and_unsuccessful_cli_output() -> None:
    oversized = subprocess.CompletedProcess(
        ["agentctl"], 0, stdout="x" * (MAX_AGENTCTL_RESPONSE_BYTES + 1)
    )
    with pytest.raises(AgentCtlError, match="exceeds"):
        AgentCtlClient(runner=lambda *_args, **_kwargs: oversized).list()

    rejected = subprocess.CompletedProcess(["agentctl"], 1, stdout="{}")
    with pytest.raises(AgentCtlError, match="rejected"):
        AgentCtlClient(runner=lambda *_args, **_kwargs: rejected).list()
