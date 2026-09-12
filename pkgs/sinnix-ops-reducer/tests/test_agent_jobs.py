from __future__ import annotations

import json
import subprocess

import pytest
from sinnix_ops_reducer.agent_jobs import (
    MAX_RESPONSE_BYTES,
    MAX_SNAPSHOT_JOBS,
    AgentCtlClient,
    AgentCtlError,
)


def response(value: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["agentctl"], 0, stdout=json.dumps(value))


def test_snapshot_reads_one_bounded_owner_projection() -> None:
    jobs = [{"job_id": number, "label": "p:op"} for number in range(2)]
    owner_snapshot = {
        "schema": "sinnix.agentctl.job-snapshot.v1",
        "limit": MAX_SNAPSHOT_JOBS,
        "groups": {
            "agent": {
                "status": "Paused",
                "parallel": 4,
                "running": 1,
                "queued": 1,
                "paused": 1,
                "stashed": 0,
                "terminal": 99,
                "total": 102,
            }
        },
        "jobs": jobs,
        "omitted": {"total": 100, "active": 0, "terminal": 100},
        "coverage": {
            "active": {"total": 2, "returned": 2},
            "terminal": {"total": 100, "returned": 0},
        },
        "truncated": True,
    }
    calls: list[list[str]] = []

    def runner(command, **_kwargs):
        calls.append(command)
        return response(owner_snapshot)

    snapshot = AgentCtlClient("fixture-agentctl", runner=runner).snapshot()
    assert calls == [
        ["fixture-agentctl", "--json", "job", "snapshot", "--limit", "100"],
    ]
    assert snapshot["groups"]["agent"]["terminal"] == 99
    assert snapshot["truncated"] is True
    assert snapshot["omitted"]["terminal"] == 100


@pytest.mark.parametrize("value", [{"jobs": []}, ["not-a-job"], "x"])
def test_list_rejects_anything_but_a_job_array(value: object) -> None:
    client = AgentCtlClient(
        "fixture-agentctl", runner=lambda *_args, **_kwargs: response(value)
    )
    with pytest.raises(AgentCtlError, match="job array"):
        client.list()


def test_snapshot_requires_owner_metadata_and_bounded_rows() -> None:
    client = AgentCtlClient(runner=lambda *_a, **_k: response({"jobs": []}))
    with pytest.raises(AgentCtlError, match="bounded job document"):
        client.snapshot()


def test_get_and_cancel_require_a_job_object_with_an_id() -> None:
    calls: list[list[str]] = []

    def runner(command, **_kwargs):
        calls.append(command)
        return response({"job_id": int(command[-1]), "phase": "running"})

    client = AgentCtlClient("fixture-agentctl", runner=runner)
    assert client.get(3)["job_id"] == 3
    assert client.cancel("3")["job_id"] == 3
    assert calls == [
        ["fixture-agentctl", "--json", "job", "get", "3"],
        ["fixture-agentctl", "--json", "job", "cancel", "3"],
    ]
    bare = AgentCtlClient(runner=lambda *_a, **_k: response({"phase": "running"}))
    with pytest.raises(AgentCtlError, match="no job ID"):
        bare.get(3)


def test_projects_and_view_read_the_operator_screen_per_project() -> None:
    calls: list[tuple[list[str], float]] = []

    def runner(command, **kwargs):
        calls.append((command, kwargs["timeout"]))
        if command[-2:] == ["project", "list"]:
            return response({"projects": [{"id": "sinnix"}, {"id": "polylogue"}, {}]})
        return response(
            {"schema": "sinnix.agentctl.view.v2", "lanes": [], "errors": []}
        )

    client = AgentCtlClient("fixture-agentctl", runner=runner)
    assert client.projects() == ["sinnix", "polylogue"]
    assert client.view("sinnix")["lanes"] == []
    # The view calls wt, gh and bd; it gets the long budget, the rest the short one.
    assert calls[0][1] < calls[1][1]
    assert calls[1][0] == ["fixture-agentctl", "--json", "view", "sinnix"]
    flat = AgentCtlClient(runner=lambda *_a, **_k: response({"schema": "x"}))
    with pytest.raises(AgentCtlError, match="lane document"):
        flat.view("sinnix")


def test_oversized_rejected_or_malformed_responses_are_typed_failures() -> None:
    oversized = subprocess.CompletedProcess(
        ["agentctl"], 0, stdout="x" * (MAX_RESPONSE_BYTES + 1)
    )
    with pytest.raises(AgentCtlError, match="protocol bound"):
        AgentCtlClient(runner=lambda *_a, **_k: oversized).list()
    rejected = subprocess.CompletedProcess(["agentctl"], 1, stdout="[]")
    with pytest.raises(AgentCtlError, match="rejected"):
        AgentCtlClient(runner=lambda *_a, **_k: rejected).list()
    malformed = subprocess.CompletedProcess(["agentctl"], 0, stdout="{")
    with pytest.raises(AgentCtlError, match="malformed"):
        AgentCtlClient(runner=lambda *_a, **_k: malformed).list()

    def missing(*_a, **_k):
        raise FileNotFoundError("agentctl")

    with pytest.raises(AgentCtlError, match="unavailable"):
        AgentCtlClient(runner=missing).list()
