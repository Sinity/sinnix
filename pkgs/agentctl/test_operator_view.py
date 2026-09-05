"""The operator screen: pueue and manifest facts, in local time, nothing decided."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from agentctl import manifest, operator_view
from agentctl.config import Config
from agentctl.manifest import Run
from agentctl.projects import load_project_adapter
from agentctl.pueue import Task
from conftest import FakeBd, FakePueue, bead

NOW = datetime(2026, 9, 3, 9, 0, tzinfo=UTC)
SHA = "c" * 40


def task(
    task_id: int,
    label: str,
    *,
    status: str = "Running",
    result: str | None = None,
    exit_code: int | None = None,
    group: str = "normal",
    ended_at: str = "2026-09-03T08:40:00+00:00",
) -> Task:
    return Task(
        task_id=task_id,
        label=label,
        group=group,
        status=status,
        result=result,
        exit_code=exit_code,
        path="/x",
        dependencies=(),
        command="agentctl-run /s/inputs/ref.json",
        enqueued_at="2026-09-03T08:00:00+00:00",
        started_at=None
        if status in {"Queued", "Stashed"}
        else "2026-09-03T08:30:00+00:00",
        ended_at=ended_at if status == "Done" else None,
    )


def worker(
    worker_id: str, *, task_id: int | None, result: bool = False
) -> dict[str, Any]:
    return {
        "id": worker_id,
        "beads": [worker_id],
        "branch": f"batch/run-1/{worker_id}",
        "worktree": f"/w/{worker_id}",
        "task_id": task_id,
        "task_ids": [task_id] if task_id is not None else [],
        "claimed": True,
        "result_path": None,
        "result": {
            "candidate_sha": SHA,
            "beads": [],
            "unresolved": [],
            "verification": [],
        }
        if result
        else None,
    }


def run(
    run_id: str,
    workers: list[dict[str, Any]],
    *,
    landing_task: int | None = None,
    accepted: bool = False,
    failure: dict[str, Any] | None = None,
    harness: str = "queued",
) -> Run:
    return Run.from_dict(
        {
            "run_id": run_id,
            "project": "fixture",
            "base_commit": "b" * 40,
            "created_at": "2026-09-03T08:00:00+00:00",
            "harness": harness,
            "runtime_revision": "/nix/store/x",
            "verify_profile": "check",
            "review_profile": "review",
            "workers": workers,
            "landing": {
                "task_id": landing_task,
                "integration_branch": f"batch/{run_id}/integration",
                "integration_worktree": None,
                "pr_number": None,
                "candidate_sha": SHA if accepted else None,
                "verify_run": None,
                "review_verdict": None,
                "refreshes": 0,
                "failure": failure,
            },
            "acceptance": {"candidate_sha": SHA, "beads": {}} if accepted else None,
            "prepared": True,
        }
    )


def snapshot(**overrides: Any) -> operator_view.Snapshot:
    values: dict[str, Any] = {
        "project_id": "fixture",
        "now": NOW,
        "tasks": (
            task(1, "fixture:verify_all", group="pytest"),
            task(2, "fixture:worker:run-1:fx-1", group="agent"),
            task(3, "fixture:check", status="Done", result="Failed", exit_code=2),
            task(
                4,
                "fixture:worker:run-1:fx-2",
                status="Done",
                result="Success",
                exit_code=0,
                group="agent",
            ),
            task(
                5,
                "fixture:worker:run-2:fx-4",
                status="Done",
                result="Failed",
                exit_code=1,
                group="agent",
            ),
            task(6, "fixture:land:run-1", status="Queued", group="fixture-land"),
            task(
                7,
                "fixture:land:run-2",
                status="Done",
                result="DependencyFailed",
                group="fixture-land",
            ),
            task(8, "fixture:land:run-3", status="Running", group="fixture-land"),
            task(9, "fixture:land:run-5", status="Stashed", group="fixture-land"),
        ),
        "groups": {"agent": "Running", "normal": "Paused", "pytest": "Running"},
        "runs": (
            run(
                "run-1",
                [worker("fx-1", task_id=2), worker("fx-2", task_id=4, result=True)],
                landing_task=6,
            ),
            run("run-2", [worker("fx-4", task_id=5)], landing_task=7),
            run("run-3", [worker("fx-5", task_id=None, result=True)], landing_task=8),
            run("run-4", [worker("fx-6", task_id=None, result=True)], accepted=True),
            run(
                "run-5",
                [worker("fx-7", task_id=None)],
                landing_task=9,
                harness="external",
            ),
        ),
        "ready": (bead("fx-9", "Ready work"),),
    }
    values.update(overrides)
    return operator_view.Snapshot(**values)


def stages_of(snap: operator_view.Snapshot) -> dict[str, dict[str, Any]]:
    return {
        row["run"]: row
        for row in (operator_view.run_dict(r, snap.tasks, NOW) for r in snap.runs)
    }


def test_stage_and_next_follow_from_the_queue_then_the_manifest() -> None:
    """Breaks if a failed worker, a stashed landing or a landed run stops naming its next step."""
    stages = stages_of(snapshot())
    assert (stages["run-1"]["stage"], stages["run-1"]["next"]) == ("working", "wait")
    assert [w["stage"] for w in stages["run-1"]["workers"]] == ["running", "done"]
    assert (stages["run-2"]["stage"], stages["run-2"]["next"]) == (
        "landing dependency-failed",
        "job logs 7, then batch land or batch resume",
    )
    assert stages["run-2"]["workers"][0]["stage"] == "failed"
    assert (stages["run-3"]["stage"], stages["run-3"]["next"]) == ("landing", "wait")
    assert (stages["run-4"]["stage"], stages["run-4"]["next"]) == ("landed", "-")
    assert stages["run-5"]["stage"] == "stashed"
    assert stages["run-5"]["next"].startswith("batch result")
    assert stages["run-5"]["workers"][0]["stage"] == "awaiting result"


def test_an_active_worker_or_landing_task_is_never_landed() -> None:
    """jcub: a run whose worker or landing task is queued or running is that task."""
    accepted = run(
        "run-x", [worker("fx", task_id=2, result=True)], landing_task=6, accepted=True
    )
    row = operator_view.run_dict(accepted, snapshot().tasks, NOW)
    assert row["stage"] == "working"
    accepted_landing = run(
        "run-y", [worker("fx", task_id=4, result=True)], landing_task=8, accepted=True
    )
    row = operator_view.run_dict(accepted_landing, snapshot().tasks, NOW)
    assert row["stage"] == "landing"
    queued_landing = run(
        "run-z", [worker("fx", task_id=4, result=True)], landing_task=6, accepted=True
    )
    assert (
        operator_view.run_dict(queued_landing, snapshot().tasks, NOW)["stage"]
        == "landing"
    )
    # Only once nothing is live does the acceptance record decide.
    quiet = run("run-q", [worker("fx", task_id=4, result=True)], accepted=True)
    assert operator_view.run_dict(quiet, snapshot().tasks, NOW)["stage"] == "landed"


def test_a_recorded_failure_names_itself_and_a_failed_worker_asks_for_resume() -> None:
    failed = run(
        "run-f",
        [worker("fx", task_id=4, result=True)],
        failure={"code": "review_rejected", "detail": "x"},
    )
    row = operator_view.run_dict(failed, snapshot().tasks, NOW)
    assert row["stage"] == "failed: review_rejected"
    assert row["next"] == "batch land"
    awaiting = run("run-w", [worker("fx", task_id=5)])
    row = operator_view.run_dict(awaiting, snapshot().tasks, NOW)
    assert (row["stage"], row["next"]) == ("awaiting workers", "batch resume --worker")


def test_render_shows_groups_attention_jobs_runs_with_timing_and_ready() -> None:
    text = operator_view.render(snapshot())

    assert "== fixture at" in text
    assert "normal idle PAUSED" in text
    assert "agent 1 running" in text
    assert "! job 3 fixture:check failed exit 2 at" in text and "(20m ago)" in text
    assert "! run run-2 landing dependency-failed: job logs 7" in text
    assert "== jobs: 5 active" in text
    assert "== runs: 4 open, 1 landed, 0 abandoned" in text
    rows = [
        line.split() for line in text.splitlines() if line.strip().startswith("run-")
    ]
    by_key = {(row[0], row[1]): row for row in rows}
    assert by_key[("run-1", "fx-1")][2] == "running"
    assert "#2" in by_key[("run-1", "fx-1")] and "30m" in by_key[("run-1", "fx-1")]
    assert by_key[("run-1", "landing")][-1] == "wait"
    assert by_key[("run-2", "fx-4")][2] == "failed"
    assert ("run-4", "landing") not in by_key
    assert "== ready: 1 beads" in text and "fx-9" in text


def test_attention_is_limited_to_the_last_six_hours() -> None:
    """Breaks if a failure from days ago keeps the screen shouting."""
    old = "2026-09-02T08:40:00+00:00"
    snap = snapshot(
        tasks=(
            task(
                3,
                "fixture:check",
                status="Done",
                result="Failed",
                exit_code=2,
                ended_at=old,
            ),
            task(
                5,
                "fixture:worker:run-2:fx-4",
                status="Done",
                result="Failed",
                exit_code=1,
                group="agent",
                ended_at=old,
            ),
            task(
                7,
                "fixture:land:run-2",
                status="Done",
                result="DependencyFailed",
                group="fixture-land",
                ended_at=old,
            ),
        ),
        runs=(run("run-2", [worker("fx-4", task_id=5)], landing_task=7),),
    )
    text = operator_view.render(snap)
    assert "== nothing needs attention" in text
    assert "run-2" in text
    fresh = operator_view.render(snapshot())
    assert "! job 3 fixture:check failed" in fresh and "! run run-2" in fresh


def test_render_says_nothing_needs_attention_when_nothing_does() -> None:
    text = operator_view.render(snapshot(tasks=(), runs=(), ready=()))
    assert "== nothing needs attention" in text
    assert "== runs: 0 open, 0 landed, 0 abandoned" in text


def test_age_and_local_clock_read_iso_stamps() -> None:
    assert operator_view.age("2026-09-03T08:59:30+00:00", NOW) == "30s"
    assert operator_view.age("2026-09-03T08:30:00+00:00", NOW) == "30m"
    assert operator_view.age("2026-09-03T06:00:00+00:00", NOW) == "3h00"
    assert operator_view.age("2026-08-30T06:00:00+00:00", NOW) == "4d"
    assert operator_view.age(None, NOW) == "?"
    assert operator_view.local_clock("2026-09-03T08:30:00Z").count(":") == 1
    assert (
        operator_view.local_clock("2026-09-03T08:30:00Z", seconds=True).count(":") == 2
    )


def test_collect_reads_each_source_and_keeps_going_when_one_is_down(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = load_project_adapter(project_root)
    fake_pueue.add(
        group="normal",
        label="fixture:check",
        command=("true",),
        working_directory=project_root,
    )
    fake_pueue.add(
        group="normal",
        label="other:check",
        command=("true",),
        working_directory=project_root,
    )
    run_manifest = run("run-1", [worker("fx-1", task_id=1)])
    manifest.create(config, run_manifest)
    manifest.create(
        config,
        Run.from_dict(
            {
                **run("run-2", [worker("fx-2", task_id=None)]).to_dict(),
                "project": "other",
            }
        ),
    )
    monkeypatch.setattr(
        operator_view,
        "SubprocessBdReader",
        lambda root: FakeBd(
            beads={
                "fx-1": bead("fx-1", "One"),
                "fx-epic": bead("fx-epic", "Epic", issue_type="epic"),
                "fx-decision": bead("fx-decision", "Decide", issue_type="decision"),
            }
        ),
    )

    collected = operator_view.collect(config, project, now=NOW)
    assert [item.label for item in collected.tasks] == ["fixture:check"]
    assert [item.run_id for item in collected.runs] == ["run-1"]
    assert [item["id"] for item in collected.ready] == ["fx-1"]
    assert collected.errors == ()

    fake_pueue.fail_tasks = True
    degraded = operator_view.collect(config, project, now=NOW)
    assert degraded.tasks == ()
    assert degraded.errors and degraded.errors[0].startswith("pueue:")
    assert "! pueue:" in operator_view.render(degraded)


def test_to_dict_carries_stage_next_timing_and_group_counts() -> None:
    payload = snapshot().to_dict()
    assert payload["schema"] == "sinnix.agentctl.view.v3"
    assert payload["groups"]["normal"] == {
        "status": "Paused",
        "running": 0,
        "queued": 0,
        "paused": 0,
    }
    assert payload["groups"]["agent"]["running"] == 1
    runs = {row["run"]: row for row in payload["runs"]}
    assert runs["run-1"]["stage"] == "working" and runs["run-1"]["next"] == "wait"
    assert runs["run-4"]["stage"] == "landed" and runs["run-4"]["accepted"]
    first = runs["run-1"]["workers"][0]
    assert first["elapsed"] == "30m" and first["since"] == "2026-09-03T08:30:00+00:00"
    assert first["job"] == 2
    assert (
        runs["run-1"]["landing"]["job"] == 6
        and runs["run-1"]["landing"]["phase"] == "queued"
    )
    json.dumps(payload)
