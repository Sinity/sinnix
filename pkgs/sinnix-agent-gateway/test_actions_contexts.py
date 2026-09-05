"""context.compose over real owners with a recorded job owner."""

from __future__ import annotations

from pathlib import Path

import pytest
from sinnix_agent_gateway.actions.contexts import ComposeInput
from test_actions_jobs import DONE, call, make_server


def test_compose_input_binds_target_to_intent() -> None:
    with pytest.raises(ValueError, match="job.review takes job"):
        ComposeInput.model_validate(
            {"intent": "job.review", "project": {"project": "x"}}
        )
    with pytest.raises(ValueError, match="takes project"):
        ComposeInput.model_validate({"intent": "incident", "job": {"job_id": 1}})


def test_project_orientation_composes_and_persists_a_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, runtime, _ = make_server(tmp_path, "observer", monkeypatch, with_git=True)
    composed = call(
        server,
        "context.compose",
        {"intent": "project.orientation", "project": {"project": "fixture"}},
    )
    assert composed["result"]["outcome"] == "ok", composed
    data = composed["data"]
    assert data["ref"] == "sinnix://projects/fixture" == data["target_ref"]
    assert data["snapshot_ref"].startswith("sinnix://contexts/")
    names = [row["name"] for row in data["components"]]
    assert names == ["project", "checkout", "tasks", "authority"]
    by_name = {row["name"]: row for row in data["components"]}
    assert by_name["project"]["status"] == "available", by_name["project"]
    assert by_name["project"]["data"]["project_id"] == "fixture"
    assert all(
        row["snapshot_ref"] == data["snapshot_ref"] for row in data["components"]
    )
    assert "agent.for_bead" in data["affordances"]
    snapshot_id = data["snapshot_ref"].rsplit("/", 1)[1]
    assert runtime.context_snapshots is not None
    assert runtime.context_snapshots.get(snapshot_id)["intent"] == "project.orientation"


def test_job_review_reads_the_job_owner_and_incident_reads_the_machine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, _, fake = make_server(tmp_path, "operator", monkeypatch, with_git=True)
    fake.responses["job.get"] = DONE
    fake.responses["job.result"] = {**DONE, "kind": "exit", "value": None}
    fake.responses["job.list"] = {
        "jobs": [DONE],
        "total": 1,
        "truncated": False,
        "next_cursor": None,
        "snapshot": {"ordering": "created_at_desc_job_id_desc", "ceiling": ["x", "41"]},
    }
    review = call(
        server, "context.compose", {"intent": "job.review", "job": {"job_id": 41}}
    )
    assert review["result"]["outcome"] == "ok", review
    data = review["data"]
    assert data["ref"] == "sinnix://jobs/41"
    by_name = {row["name"]: row for row in data["components"]}
    assert (
        by_name["job"]["status"] == "available"
        and by_name["job"]["data"]["job_id"] == "41"
    )
    assert by_name["result"]["data"]["kind"] == "exit"
    assert by_name["project"]["status"] == "available"
    assert data["job"]["job_id"] == "41"
    assert "jobs.logs" in data["affordances"]

    incident = call(
        server,
        "context.compose",
        {"intent": "incident", "project": {"project": "fixture"}},
    )
    assert incident["result"]["outcome"] == "ok", incident
    names = [row["name"] for row in incident["data"]["components"]]
    assert names == ["runtime", "transitions", "receipts", "jobs"]
    jobs = {row["name"]: row for row in incident["data"]["components"]}["jobs"]
    assert (
        jobs["status"] == "available"
        and jobs["data"]["jobs"][0]["ref"] == "sinnix://jobs/41"
    )
