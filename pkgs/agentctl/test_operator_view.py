"""The operator screen: queue groups, recent failures, active jobs, ready beads."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from agentctl import operator_view
from agentctl.config import Config
from agentctl.projects import load_project_adapter
from agentctl.pueue import Task
from conftest import FakePueue


def bead(bead_id: str, title: str, *, issue_type: str = "task") -> dict[str, Any]:
    return {"id": bead_id, "title": title, "issue_type": issue_type, "status": "open"}


NOW = datetime(2026, 9, 3, 9, 0, tzinfo=UTC)


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


def snapshot(**overrides: Any) -> operator_view.Snapshot:
    values: dict[str, Any] = {
        "project_id": "fixture",
        "now": NOW,
        "tasks": (
            task(1, "fixture:verify_all", group="pytest"),
            task(2, "fixture:shell", group="agent"),
            task(3, "fixture:check", status="Done", result="Failed", exit_code=2),
            task(4, "fixture:fmt", status="Done", result="Success", exit_code=0),
            task(6, "fixture:verify", status="Queued"),
            task(9, "fixture:later", status="Stashed"),
        ),
        "groups": {"agent": "Running", "normal": "Paused", "pytest": "Running"},
        "ready": (bead("fx-9", "Ready work"),),
    }
    values.update(overrides)
    return operator_view.Snapshot(**values)


def test_render_shows_groups_attention_jobs_with_timing_and_ready() -> None:
    text = operator_view.render(snapshot())

    assert "== fixture at" in text
    assert "normal global unknown; fixture 1 queued 1 stashed PAUSED" in text
    assert "agent global unknown; fixture 1 running" in text
    assert "! job 3 fixture:check failed exit 2 at" in text and "(20m ago)" in text
    assert "job 4" not in text
    assert "== jobs: 4 active" in text
    rows = {
        line.split()[0]: line.split()
        for line in text.splitlines()
        if line.strip()[:1].isdigit()
    }
    assert rows["2"][1:3] == ["fixture:shell", "running"] and "30m" in rows["2"]
    assert rows["9"][2] == "stashed"
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
        ),
    )
    assert "== nothing needs attention" in operator_view.render(snap)
    assert "! job 3 fixture:check failed" in operator_view.render(snapshot())


def test_render_says_nothing_needs_attention_when_nothing_does() -> None:
    text = operator_view.render(snapshot(tasks=(), ready=()))
    assert "== nothing needs attention" in text
    assert "== jobs: 0 active" in text
    assert "== ready: 0 beads" in text


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
    monkeypatch.setattr(
        operator_view,
        "ready_beads",
        lambda root: [
            bead("fx-1", "One"),
            bead("fx-epic", "Epic", issue_type="epic"),
            bead("fx-decision", "Decide", issue_type="decision"),
        ],
    )

    collected = operator_view.collect(config, project, now=NOW)
    assert [item.label for item in collected.tasks] == ["fixture:check"]
    assert [item["id"] for item in collected.ready] == ["fx-1"]
    assert collected.errors == ()

    fake_pueue.fail_tasks = True
    degraded = operator_view.collect(config, project, now=NOW)
    assert degraded.tasks == ()
    assert degraded.errors and degraded.errors[0].startswith("pueue:")
    assert "! pueue:" in operator_view.render(degraded)
    assert "pueue unavailable" in operator_view.render(degraded)
    assert degraded.to_dict()["groups"] == {}
    assert degraded.to_dict()["queue_read"] is False


@pytest.mark.parametrize("group_paused", [False, True])
def test_collect_distinguishes_global_occupancy_from_project_work(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    group_paused: bool,
) -> None:
    project = load_project_adapter(project_root)
    first = fake_pueue.add(
        group="bulk",
        label="other:scan",
        command=("true",),
        working_directory=project_root,
    )
    fake_pueue.add(
        group="bulk",
        label="third:check",
        command=("true",),
        working_directory=project_root,
    )
    queued = fake_pueue.add(
        group="bulk",
        label="fixture:check",
        command=("true",),
        working_directory=project_root,
        after=(first,),
    )
    stashed = fake_pueue.add(
        group="bulk",
        label="fixture:later",
        command=("true",),
        working_directory=project_root,
        stashed=True,
    )
    paused = fake_pueue.add(
        group="bulk",
        label="other:paused",
        command=("true",),
        working_directory=project_root,
    )
    fake_pueue._set(paused, status="Paused")
    if group_paused:
        fake_pueue.pause("bulk")
    reads = 0

    def status() -> operator_view.pueue.Status:
        nonlocal reads
        reads += 1
        return fake_pueue.status()

    def unexpected_read() -> None:
        raise AssertionError("collect must use one coherent pueue status response")

    monkeypatch.setattr(operator_view.pueue, "status", status)
    monkeypatch.setattr(operator_view.pueue, "tasks", unexpected_read)
    monkeypatch.setattr(operator_view.pueue, "groups_status", unexpected_read)
    monkeypatch.setattr(operator_view, "ready_beads", lambda root: [])
    collected = operator_view.collect(config, project, now=NOW)
    payload = collected.to_dict()
    text = operator_view.render(collected)

    assert reads == 1 and payload["queue_read"] is True
    assert [row["task_id"] for row in payload["jobs"]] == [queued, stashed]
    assert payload["groups"]["bulk"] == {
        "status": "Paused" if group_paused else "Running",
        "scope": "project",
        "running": 0,
        "queued": 1,
        "paused": 0,
        "stashed": 1,
        "global": {"running": 2, "queued": 1, "paused": 1, "stashed": 1, "parallel": 1},
    }
    assert (
        "bulk global 2 running 1 queued 1 paused 1 stashed, parallel 1; fixture 1 queued 1 stashed"
        in text
    )
    assert ("fixture 1 queued 1 stashed PAUSED" in text) is group_paused
    assert "bulk global idle" not in text

    fake_pueue.fail_tasks = True
    unavailable = operator_view.collect(config, project, now=NOW)
    assert reads == 2
    assert unavailable.to_dict()["queue_read"] is False
    assert unavailable.to_dict()["groups"] == {}
    assert "pueue unavailable" in operator_view.render(unavailable)
    assert "global idle" not in operator_view.render(unavailable)


def test_to_dict_carries_jobs_ready_and_group_counts() -> None:
    payload = snapshot().to_dict()
    assert payload["schema"] == "sinnix.agentctl.view.v4"
    assert payload["groups"]["normal"] == {
        "status": "Paused",
        "scope": "project",
        "running": 0,
        "queued": 1,
        "paused": 0,
        "stashed": 1,
        "global": None,
    }
    assert payload["groups"]["agent"]["running"] == 1
    assert [job["task_id"] for job in payload["jobs"]] == [1, 2, 3, 4, 6, 9]
    assert payload["ready"] == [{"id": "fx-9", "title": "Ready work", "type": "task"}]
    json.dumps(payload)


def test_ready_beads_reads_bd_ready_in_the_project(tmp_path: Path) -> None:
    executable = tmp_path / "bd"
    executable.write_text(
        "#!/bin/sh\n"
        'test "$*" = "ready --limit 0 --json" || exit 9\n'
        "pwd > cwd\n"
        """echo '[{"id": "fx-1", "title": "One"}]'\n"""
    )
    executable.chmod(0o755)
    assert operator_view.ready_beads(tmp_path, str(executable)) == [
        {"id": "fx-1", "title": "One"}
    ]
    assert (tmp_path / "cwd").read_text().strip() == str(tmp_path)
    executable.write_text("#!/bin/sh\necho '{\"error\": \"no db\"}'\n")
    with pytest.raises(operator_view.TaskReadError):
        operator_view.ready_beads(tmp_path, str(executable))
    executable.write_text("#!/bin/sh\nexit 1\n")
    with pytest.raises(operator_view.TaskReadError):
        operator_view.ready_beads(tmp_path, str(executable))
