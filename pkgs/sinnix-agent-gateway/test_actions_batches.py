"""Typed batch actions over a recorded LocalJobs stand-in.

Every worker and landing id these actions return is the pueue task id
``jobs.*`` takes, and every bead comes from the run manifest.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import anyio
import pytest
from conftest import DirectJobs, call, ok
from sinnix_agent_gateway import server as server_module
from sinnix_agent_gateway.actions import batches, jobs
from sinnix_agent_gateway.app import Runtime, create_server
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.locators import RunLocator
from sinnix_mcp import ErrorCode

OWNED = (*batches.ACTIONS, *jobs.ACTIONS)
RUN_ID = "fixture-20260906-012123-a2c81926"
RUN_REF = f"sinnix://projects/fixture/runs/{RUN_ID}"

RUN = {
    "run_id": RUN_ID,
    "project_id": "fixture",
    "base_commit": "b" * 40,
    "created_at": "2026-09-06T01:21:23+00:00",
    "harness": "queued",
    "stage": "working",
    "prepared": True,
    "accepted": False,
    "acceptance": None,
    "abandoned": None,
    "workers": [
        {
            "worker_id": "fixture-7",
            "beads": ["fixture-7", "fixture-8"],
            "branch": f"batch/{RUN_ID}/fixture-7",
            "worktree": f"/realm/worktrees/fixture-batch-{RUN_ID}-fixture-7",
            "stage": "running",
            "job_id": "41",
            "job_launch_reference": "fixture-worker-abcd1234",
            "job_ids": ["41"],
            "backend": "claude",
            "model": "claude-opus-5",
            "effort": "high",
            "result_filed": False,
            "state": {"phase": "running", "terminal": False, "exit_code": None},
        }
    ],
    "landing": {
        "job_id": "42",
        "job_launch_reference": "fixture-integrate-9f10",
        "integration_branch": f"batch/{RUN_ID}/integration",
        "candidate_sha": None,
        "pr_number": None,
        "failure": None,
        "state": {"phase": "queued", "terminal": False, "exit_code": None},
    },
}


FakeJobs = DirectJobs


def make_server(
    tmp_path: Path, principal: str, monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, FakeJobs]:
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={
            "fixture": ProjectConfig(
                project_id="fixture", path=project, observer_read=True
            )
        },
    )
    runtime = Runtime.create(config, principal)
    fake = FakeJobs(default=RUN)
    runtime.jobs = fake  # type: ignore[assignment]
    monkeypatch.setattr(Runtime, "create", classmethod(lambda _c, _g, _p: runtime))
    monkeypatch.setattr(
        server_module,
        "visible_actions",
        lambda name: tuple(a for a in OWNED if name in a.principals),
    )
    return create_server(config, principal), fake


def test_run_locator_accepts_a_ref_a_full_id_or_a_suffix() -> None:
    assert RunLocator(ref=RUN_REF).resolve() == {
        "project_id": "fixture",
        "run_id": RUN_ID,
    }
    assert RunLocator(run_id="a2c81926").resolve() == {"run_id": "a2c81926"}
    with pytest.raises(ValueError, match="exactly one"):
        RunLocator()


def test_status_names_every_worker_bead_and_the_pueue_ids_jobs_actions_take(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if a supervisor has to parse a task label to learn a run's beads."""
    server, fake = make_server(tmp_path, "observer", monkeypatch)

    data = ok(server, "batches.status", {"target": {"run_id": "a2c81926"}})

    assert data["ref"] == RUN_REF and data["run_id"] == RUN_ID
    assert data["project_ref"] == "sinnix://projects/fixture"
    assert data["stage"] == "working" and data["accepted"] is False
    worker = data["workers"][0]
    assert worker["beads"] == ["fixture-7", "fixture-8"]
    assert worker["bead_refs"] == [
        "sinnix://projects/fixture/beads/fixture-7",
        "sinnix://projects/fixture/beads/fixture-8",
    ]
    assert worker["job_id"] == 41 and worker["job_ref"] == "sinnix://jobs/41"
    # The stable identity a jobs.* call takes so a reorder cannot redirect it.
    assert worker["job_launch_reference"] == "fixture-worker-abcd1234"
    assert worker["job_ids"] == [41]
    assert worker["state"]["phase"] == "running"
    assert data["landing"]["job_id"] == 42
    assert data["landing"]["job_ref"] == "sinnix://jobs/42"
    assert data["landing"]["job_launch_reference"] == "fixture-integrate-9f10"
    assert data["affordances"] == ["batches.status", "jobs.wait", "jobs.logs"]
    assert fake.calls[-1].arguments == {"run_id": "a2c81926"}

    by_ref = ok(server, "batches.status", {"target": {"ref": RUN_REF}})
    assert by_ref["ref"] == RUN_REF
    assert fake.calls[-1].arguments == {"project_id": "fixture", "run_id": RUN_ID}


def test_list_pages_runs_and_forwards_the_project_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, fake = make_server(tmp_path, "observer", monkeypatch)
    fake.responses["batch.list"] = {"runs": [RUN], "total": 3, "truncated": True}

    page = ok(server, "batches.list", {"project": {"project": "fixture"}, "limit": 1})

    assert [run["run_id"] for run in page["runs"]] == [RUN_ID]
    assert page["total"] == 3 and page["truncated"] is True
    assert fake.calls[-1].arguments == {"limit": 1, "project_id": "fixture"}

    unknown = call(server, "batches.list", {"project": {"project": "nope"}})
    assert unknown["error"]["code"] == "not_found"


def test_start_sends_the_beads_and_the_worker_grouping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, fake = make_server(tmp_path, "operator", monkeypatch)
    fake.responses["batch.start"] = {**RUN, "existing": False, "resumed": True}

    started = ok(
        server,
        "batches.start",
        {
            "project": {"project": "fixture"},
            "beads": ["fixture-7", "fixture-8"],
            "workers": [["fixture-7", "fixture-8"]],
            "backend": "claude",
            "model": "claude-opus-5",
            "effort": "high",
            "idempotency_key": "batch-1",
        },
    )

    assert started["run_id"] == RUN_ID and started["resumed"] is True
    assert started["existing"] is False
    assert fake.calls[-1].arguments == {
        "project_id": "fixture",
        "beads": ["fixture-7", "fixture-8"],
        "workers": [["fixture-7", "fixture-8"]],
        "backend": "claude",
        "model": "claude-opus-5",
        "effort": "high",
    }

    fake.errors["batch.start"] = (
        ErrorCode.OPERATION_FAILED,
        "members: fixture-7 is claimed by agent-x",
        {"refusal": "members"},
    )
    refused = call(
        server,
        "batches.start",
        {
            "project": {"project": "fixture"},
            "beads": ["fixture-7"],
            "idempotency_key": "batch-2",
        },
    )
    assert refused["error"]["code"] == "conflict"
    assert refused["error"]["details"]["next_action"] == "beads.query"
    assert "claimed by agent-x" in refused["error"]["message"]


def test_land_and_resume_return_the_queued_task_rather_than_running_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if a caller has to hold an MCP request open for a whole landing."""
    server, fake = make_server(tmp_path, "operator", monkeypatch)
    fake.responses["batch.land"] = {**RUN, "landing_job_id": "77"}
    fake.responses["batch.resume"] = {**RUN, "resumed_job_id": "78"}

    landed = ok(
        server,
        "batches.land",
        {"target": {"run_id": "a2c81926"}, "idempotency_key": "land-1"},
    )
    assert landed["landing_job_id"] == 77
    assert landed["landing_job_ref"] == "sinnix://jobs/77"

    resumed = ok(
        server,
        "batches.resume",
        {
            "target": {"run_id": "a2c81926"},
            "worker": "fixture-7",
            "effort": "high",
            "idempotency_key": "resume-1",
        },
    )
    assert resumed["resumed_job_id"] == 78
    assert fake.calls[-1].arguments == {
        "run_id": "a2c81926",
        "worker_id": "fixture-7",
        "backend": None,
        "model": None,
        "effort": "high",
    }


def test_a_landed_run_offers_no_further_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, fake = make_server(tmp_path, "observer", monkeypatch)
    fake.responses["batch.status"] = {
        **RUN,
        "stage": "landed",
        "accepted": True,
        "acceptance": {"candidate_sha": "c" * 40, "beads": {}, "residual": []},
    }

    data = ok(server, "batches.status", {"target": {"run_id": "a2c81926"}})

    assert data["accepted"] is True and data["affordances"] == ["batches.list"]


def test_observers_may_read_a_run_but_not_change_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, _ = make_server(tmp_path, "observer", monkeypatch)

    async def names() -> set[str]:
        return {tool.name for tool in await server.list_tools()}

    visible = anyio.run(names)
    assert {"batches.list", "batches.status"} <= visible
    assert visible.isdisjoint({"batches.start", "batches.land", "batches.resume"})
