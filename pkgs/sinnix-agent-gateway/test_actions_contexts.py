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
    assert "batches.start" in data["affordances"]
    snapshot_id = data["snapshot_ref"].rsplit("/", 1)[1]
    assert runtime.context_snapshots is not None
    assert runtime.context_snapshots.get(snapshot_id)["intent"] == "project.orientation"


def test_project_orientation_reuses_revision_checked_project_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, runtime, _ = make_server(tmp_path, "observer", monkeypatch, with_git=True)
    original = runtime.projects.summary
    calls = 0

    def counted(project_id: str):
        nonlocal calls
        calls += 1
        return original(project_id)

    monkeypatch.setattr(runtime.projects, "summary", counted)
    monkeypatch.setattr(runtime.projects, "summary_revision", lambda _project: "rev-a")

    for _ in range(2):
        response = call(
            server,
            "context.compose",
            {"intent": "project.orientation", "project": {"project": "fixture"}},
        )
        assert response["result"]["outcome"] == "ok", response

    # The authority view shares the project payload with the orientation
    # component, while the revision hook skips the payload probe on the second
    # composition.
    assert calls == 2


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


@pytest.mark.parametrize("target", [{"job_id": 41}, {"ref": "sinnix://jobs/41"}])
def test_job_review_follows_launch_identity_across_reorders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: dict
) -> None:
    """Dropping the locator reference returns the replacement queue occupant."""
    server, runtime, fake = make_server(tmp_path, "operator", monkeypatch)
    reference = "fixture-worker-original"

    def observe(arguments: dict, job_id: str) -> dict:
        if arguments.get("launch_reference") != reference:
            return {**DONE, "launch_reference": "fixture-worker-replacement"}
        return {**DONE, "job_id": job_id, "launch_reference": reference}

    fake.responses["job.get"] = lambda args: observe(args, "42")
    fake.responses["job.result"] = lambda args: {
        **observe(args, "43"),
        "kind": "exit",
        "value": "original output",
    }
    response = call(
        server,
        "context.compose",
        {"intent": "job.review", "job": {**target, "launch_reference": reference}},
    )
    assert response["result"]["outcome"] == "ok", response
    data = response["data"]
    components = {row["name"]: row for row in data["components"]}
    assert components["job"]["data"]["launch_reference"] == reference
    assert components["result"]["data"]["launch_reference"] == reference
    assert (
        components["job"]["source_ref"]
        == data["target_ref"]
        == data["ref"]
        == "sinnix://jobs/42"
    )
    assert components["result"]["source_ref"] == "sinnix://jobs/43"
    assert components["result"]["data"]["value"] == "original output"
    assert (
        runtime.context_snapshots.get(data["snapshot_ref"].rsplit("/", 1)[1])[
            "target_ref"
        ]
        == data["target_ref"]
    )


def test_job_review_does_not_expose_a_result_for_another_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, _, fake = make_server(tmp_path, "operator", monkeypatch)
    reference = "fixture-worker-original"
    fake.responses["job.get"] = {**DONE, "launch_reference": reference}
    fake.responses["job.result"] = {
        **DONE,
        "launch_reference": "fixture-worker-replacement",
        "value": "wrong output",
    }
    response = call(
        server,
        "context.compose",
        {"intent": "job.review", "job": {"job_id": 41, "launch_reference": reference}},
    )
    assert response["result"]["outcome"] == "ok", response
    result = next(
        row for row in response["data"]["components"] if row["name"] == "result"
    )
    assert result["status"] == "unavailable"
    assert result.get("data") is None
