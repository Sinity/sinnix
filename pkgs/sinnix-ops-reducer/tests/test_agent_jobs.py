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


def response(value: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["agentctl"], 0, stdout=json.dumps(value))


def test_list_keeps_the_newest_bounded_page_in_queue_order() -> None:
    calls: list[list[str]] = []
    jobs = [{"job_id": number, "label": "p:op"} for number in range(MAX_SNAPSHOT_JOBS + 5)]

    def runner(command, **_kwargs):
        calls.append(command)
        return response(jobs)

    listed = AgentCtlClient("fixture-agentctl", runner=runner).list()
    assert calls == [["fixture-agentctl", "job", "list"]]
    assert listed["truncated"] is True
    assert len(listed["jobs"]) == MAX_SNAPSHOT_JOBS
    assert listed["jobs"][0]["job_id"] == 5
    assert listed["jobs"][-1]["job_id"] == MAX_SNAPSHOT_JOBS + 4


@pytest.mark.parametrize("value", [{"jobs": []}, ["not-a-job"], "x"])
def test_list_rejects_anything_but_a_job_array(value: object) -> None:
    client = AgentCtlClient(
        "fixture-agentctl", runner=lambda *_args, **_kwargs: response(value)
    )
    with pytest.raises(AgentCtlError):
        client.list()


def test_get_and_cancel_require_a_job_object_with_an_id() -> None:
    calls: list[list[str]] = []

    def runner(command, **_kwargs):
        calls.append(command)
        return response({"job_id": int(command[-1]), "phase": "running"})

    client = AgentCtlClient("fixture-agentctl", runner=runner)
    assert client.get(3)["job_id"] == 3
    assert client.cancel("3")["job_id"] == 3
    assert calls == [
        ["fixture-agentctl", "job", "get", "3"],
        ["fixture-agentctl", "job", "cancel", "3"],
    ]
    bare = AgentCtlClient(runner=lambda *_a, **_k: response({"phase": "running"}))
    with pytest.raises(AgentCtlError, match="no job ID"):
        bare.get(3)


def test_rejects_unbounded_and_unsuccessful_cli_output() -> None:
    oversized = subprocess.CompletedProcess(
        ["agentctl"], 0, stdout="x" * (MAX_AGENTCTL_RESPONSE_BYTES + 1)
    )
    with pytest.raises(AgentCtlError, match="exceeds"):
        AgentCtlClient(runner=lambda *_args, **_kwargs: oversized).list()

    rejected = subprocess.CompletedProcess(["agentctl"], 1, stdout="[]")
    with pytest.raises(AgentCtlError, match="rejected"):
        AgentCtlClient(runner=lambda *_args, **_kwargs: rejected).list()
