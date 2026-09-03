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


PUEUE_STATUS = {
    "groups": {
        "agent": {"status": "Paused", "parallel_tasks": 4},
        "pytest": {"status": "Running", "parallel_tasks": 1},
    },
    "tasks": {
        "1": {"id": 1, "group": "agent", "status": {"Running": {}}},
        "2": {"id": 2, "group": "agent", "status": {"Paused": {}}},
        "3": {"id": 3, "group": "agent", "status": "Queued"},
        "4": {"id": 4, "group": "pytest", "status": {"Done": {"result": "Success"}}},
    },
}


def test_snapshot_reads_groups_from_pueue_and_jobs_from_agentctl_as_json() -> None:
    """Red if `--json` is dropped (agentctl prints a table) or if the group
    counts stop coming from pueue's own task states."""
    jobs = [{"job_id": number, "label": "p:op"} for number in range(MAX_SNAPSHOT_JOBS + 5)]
    calls: list[list[str]] = []

    def runner(command, **_kwargs):
        calls.append(command)
        if command[0] == "fixture-pueue":
            return response(PUEUE_STATUS)
        return response(jobs)

    snapshot = AgentCtlClient(
        "fixture-agentctl", pueue_command="fixture-pueue", runner=runner
    ).snapshot()
    assert calls == [
        ["fixture-agentctl", "--json", "job", "list"],
        ["fixture-pueue", "status", "--json"],
    ]
    assert snapshot["groups"] == {
        "agent": {"status": "Paused", "parallel": 4, "running": 1, "queued": 1, "paused": 1},
        "pytest": {"status": "Running", "parallel": 1, "running": 0, "queued": 0, "paused": 0},
    }
    assert snapshot["truncated"] is True
    assert len(snapshot["jobs"]) == MAX_SNAPSHOT_JOBS
    assert snapshot["jobs"][0]["job_id"] == 5


@pytest.mark.parametrize("value", [{"jobs": []}, ["not-a-job"], "x"])
def test_list_rejects_anything_but_a_job_array(value: object) -> None:
    client = AgentCtlClient(
        "fixture-agentctl", runner=lambda *_args, **_kwargs: response(value)
    )
    with pytest.raises(AgentCtlError, match="job array"):
        client.list()


def test_groups_require_pueue_to_print_groups_and_tasks() -> None:
    client = AgentCtlClient(runner=lambda *_a, **_k: response({"tasks": {}}))
    with pytest.raises(AgentCtlError, match="groups and tasks"):
        client.groups()


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
        return response({"schema": "sinnix.agentctl.view.v2", "lanes": [], "errors": []})

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
