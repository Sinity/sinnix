"""Typed batch actions over a recorded LocalJobs stand-in.

Every worker and landing id these actions return is the pueue task id
``jobs.*`` takes, and every bead comes from the run manifest.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from conftest import DirectJobs, call, ok
from mcp.server.mcpserver.exceptions import ToolError
from sinnix_agent_gateway import server as server_module
from sinnix_agent_gateway.actions import batches, jobs
from sinnix_agent_gateway.app import Runtime, create_server
from sinnix_agent_gateway.config import GatewayConfig, ProjectConfig
from sinnix_agent_gateway.locators import RunLocator

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
            "worktree": f"/realm/worktree/fixture-batch-{RUN_ID}-fixture-7",
            "stage": "running",
            "task_id": "41",
            "job_id": "fixture-worker-abcd1234",
            "task_ids": ["41"],
            "backend": "claude",
            "model": "claude-opus-5",
            "effort": "high",
            "result_filed": False,
            "state": {"phase": "running", "terminal": False, "exit_code": None},
        }
    ],
    "landing": {
        "task_id": "42",
        "job_id": "fixture-integrate-9f10",
        "integration_branch": f"batch/{RUN_ID}/integration",
        "candidate_sha": None,
        "pr_number": None,
        "failure": None,
        "state": {"phase": "queued", "terminal": False, "exit_code": None},
    },
}


FakeJobs = DirectJobs


def make_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, FakeJobs]:
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    config = GatewayConfig(
        state_dir=tmp_path / "state",
        projects={"fixture": ProjectConfig(project_id="fixture", path=project)},
    )
    runtime = Runtime.create(config)
    fake = FakeJobs(default=RUN)
    runtime.jobs = fake  # type: ignore[assignment]
    monkeypatch.setattr(Runtime, "create", classmethod(lambda _c, _g: runtime))
    monkeypatch.setattr(
        server_module,
        "ALL_ACTIONS",
        OWNED,
    )
    return create_server(config), fake


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
    server, fake = make_server(tmp_path, monkeypatch)

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
    assert worker["task_id"] == 41 and worker["job_ref"] == "sinnix://jobs/41"
    # The stable identity a jobs.* call takes so a reorder cannot redirect it.
    assert worker["job_id"] == "fixture-worker-abcd1234"
    assert worker["task_ids"] == [41]
    assert worker["state"]["phase"] == "running"
    assert data["landing"]["task_id"] == 42
    assert data["landing"]["job_ref"] == "sinnix://jobs/42"
    assert data["landing"]["job_id"] == "fixture-integrate-9f10"
    assert data["next_actions"] == ["batches.status", "jobs.wait", "jobs.logs"]
    assert fake.calls[-1].arguments == {"run_id": "a2c81926"}

    by_ref = ok(server, "batches.status", {"target": {"ref": RUN_REF}})
    assert by_ref["ref"] == RUN_REF
    assert fake.calls[-1].arguments == {"project_id": "fixture", "run_id": RUN_ID}


def test_list_pages_runs_and_forwards_the_project_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, fake = make_server(tmp_path, monkeypatch)
    fake.responses["batch.list"] = {"runs": [RUN], "total": 3, "truncated": True}

    page = ok(server, "batches.list", {"project": {"project": "fixture"}, "limit": 1})

    assert [run["run_id"] for run in page["runs"]] == [RUN_ID]
    assert page["total"] == 3 and page["truncated"] is True
    assert fake.calls[-1].arguments == {"limit": 1, "project_id": "fixture"}

    unknown = call(server, "batches.list", {"project": {"project": "nope"}})
    assert unknown["error"]["code"] == "not_found"


def test_a_landed_run_offers_no_further_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, fake = make_server(tmp_path, monkeypatch)
    fake.responses["batch.status"] = {
        **RUN,
        "stage": "landed",
        "accepted": True,
        "acceptance": {"candidate_sha": "c" * 40, "beads": {}, "residual": []},
    }

    data = ok(server, "batches.status", {"target": {"run_id": "a2c81926"}})

    assert data["accepted"] is True and data["next_actions"] == ["batches.list"]


@pytest.mark.parametrize("action", ["batches.start", "batches.land", "batches.resume"])
def test_retired_mutations_have_no_tool_or_owner_effect(tmp_path, monkeypatch, action):
    server, owner = make_server(tmp_path, monkeypatch)
    with pytest.raises(ToolError, match="Unknown tool"):
        call(server, action, {})
    assert owner.calls == []
