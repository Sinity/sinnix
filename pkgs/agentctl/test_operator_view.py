"""The operator screen: pueue, worktrunk, gh and bd facts, in local time, nothing decided."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from conftest import FakeBd, FakePueue, bead
from agentctl import operator_view
from agentctl.config import Config
from agentctl.lanes import LaneRow
from agentctl.projects import load_project_adapter
from agentctl.pueue import Task
from agentctl.worktrunk import Worktree

NOW = datetime(2026, 9, 3, 9, 0, tzinfo=UTC)


def task(
    task_id: int,
    label: str,
    *,
    status: str = "Running",
    result: str | None = None,
    exit_code: int | None = None,
    group: str = "normal",
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
        started_at="2026-09-03T08:30:00+00:00",
        ended_at="2026-09-03T08:40:00+00:00" if status == "Done" else None,
    )


def lane(
    branch: str,
    bead_id: str,
    *,
    pr: dict[str, Any] | None = None,
    state: str = "ahead",
    dirty: bool = False,
) -> LaneRow:
    return LaneRow(
        worktree=Worktree(
            branch=branch,
            path=Path("/w") / branch.replace("/", "-"),
            head="h",
            main=False,
            dirty=dirty,
            state=state,
        ),
        bead=bead_id,
        pr=pr,
    )


def pull(
    number: int,
    *,
    mergeable: str = "MERGEABLE",
    checks: str = "SUCCESS",
    auto: bool = False,
    state: str = "OPEN",
    review: str = "",
    head: str = "h",
    body: str = "",
) -> dict[str, Any]:
    return {
        "number": number,
        "state": state,
        "body": body,
        "mergeable": mergeable,
        "headRefOid": head,
        "reviewDecision": review,
        "reviews": [
            {
                "author": {"login": "chatgpt-codex-connector"},
                "state": "APPROVED",
                "commit": {"oid": "h"},
            }
        ],
        "comments": [],
        "reactionGroups": [],
        "autoMergeRequest": {"enabledAt": "x"} if auto else None,
        "statusCheckRollup": [
            {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": checks}
        ],
    }


def merged_pull(
    number: int, branch: str, bead_id: str, *, head: str = "h"
) -> dict[str, Any]:
    """A merged PR whose publication marker binds this bead, branch and head."""
    marker = json.dumps(
        {"bead": bead_id, "branch": branch, "head": head},
        separators=(",", ":"),
        sort_keys=True,
    )
    return pull(
        number,
        state="MERGED",
        head=head,
        body=f"Landed.\n\n<!-- agentctl:lane-publication {marker} -->\n",
    )


def snapshot(**overrides: Any) -> operator_view.Snapshot:
    values: dict[str, Any] = {
        "project_id": "fixture",
        "now": NOW,
        "tasks": (
            task(1, "fixture:verify_all", group="pytest"),
            task(2, "fixture:lane:fx-1", group="agent"),
            task(3, "fixture:check", status="Done", result="Failed", exit_code=2),
            task(
                4,
                "fixture:lane:fx-2",
                status="Done",
                result="Success",
                exit_code=0,
                group="agent",
            ),
            task(
                5,
                "fixture:lane:fx-4",
                status="Done",
                result="Failed",
                exit_code=1,
                group="agent",
            ),
        ),
        "groups": {"agent": "Running", "normal": "Paused", "pytest": "Running"},
        "lanes": (
            lane(
                "feature/packet/fx-1",
                "fx-1",
                pr=pull(41, mergeable="CONFLICTING", auto=True),
            ),
            lane("feature/packet/fx-2", "fx-2", pr=pull(42, checks="FAILURE")),
            lane("feature/packet/fx-3", "fx-3", dirty=True),
            lane("feature/packet/fx-4", "fx-4"),
            lane("feature/packet/fx-5", "fx-5", pr=pull(45, auto=True)),
            lane("feature/packet/fx-6", "fx-6", state="integrated"),
            lane(
                "feature/packet/fx-7",
                "fx-7",
                pr=merged_pull(47, "feature/packet/fx-7", "fx-7"),
                state="integrated",
            ),
        ),
        "ready": (bead("fx-9", "Ready work"),),
        "beads": {"fx-7": bead("fx-7", "Landed work")},
    }
    values.update(overrides)
    return operator_view.Snapshot(**values)


def stages_of(snap: operator_view.Snapshot) -> dict[str, tuple[str, str]]:
    agents = operator_view.agents_by_bead(snap.tasks)
    return {
        row.bead: operator_view.lane_stage(
            row, agents.get(row.bead or ""), snap.beads.get(row.bead or "")
        )
        for row in snap.lanes
    }


def test_stage_and_next_follow_from_the_queue_then_pr_then_agent_facts() -> None:
    """Breaks if a conflicting PR, a red check, or a failed agent stops naming its next step."""
    stages = stages_of(snapshot())
    assert stages["fx-1"] == ("lane running", "wait")
    assert stages["fx-2"] == ("checks failing", "fix in lane, push")
    assert stages["fx-3"] == ("idle", "lane rebase or publish")
    assert stages["fx-4"] == ("lane failed", "job logs, then lane rebase")
    assert stages["fx-5"] == ("auto-merge armed", "wait for merge")
    assert stages["fx-7"] == ("merged", "lane sync")
    conflicting = operator_view.lane_stage(
        lane("feature/packet/fx-1", "fx-1", pr=pull(41, mergeable="CONFLICTING")), None
    )
    assert conflicting == ("conflicting", "lane rebase")
    done = operator_view.lane_stage(
        lane("b", "fx-2"),
        task(4, "fixture:lane:fx-2", status="Done", result="Success", group="agent"),
    )
    assert done == ("unpublished", "lane publish")


def test_a_lane_is_merged_only_through_a_merged_pr_that_binds_it() -> None:
    """Breaks if wt's integrated verdict or an unbound merged PR reads as completion."""
    fresh = lane("feature/packet/fx-6", "fx-6", state="integrated")
    assert operator_view.lane_stage(fresh, None) == ("idle", "lane rebase or publish")
    bound = lane(
        "feature/packet/fx-7",
        "fx-7",
        pr=merged_pull(47, "feature/packet/fx-7", "fx-7"),
        state="integrated",
    )
    assert operator_view.lane_stage(bound, None, bead("fx-7", "Landed work")) == (
        "merged",
        "lane sync",
    )
    # The lane's branch was moved onto the squash commit after its PR merged:
    # nothing of its own is left, and lane sync names the failed binding.
    past_head = lane(
        "feature/packet/fx-7",
        "fx-7",
        pr=merged_pull(47, "feature/packet/fx-7", "fx-7", head="earlier"),
        state="integrated",
    )
    assert operator_view.lane_stage(past_head, None, bead("fx-7", "Landed work")) == (
        "merged PR is not this head",
        "lane sync",
    )
    # The same PR with work pushed after the merge: this head is unpublished.
    ahead = lane(
        "feature/packet/fx-7",
        "fx-7",
        pr=merged_pull(47, "feature/packet/fx-7", "fx-7", head="earlier"),
    )
    assert operator_view.lane_stage(ahead, None, bead("fx-7", "Landed work")) == (
        "merged PR is not this head",
        "lane publish",
    )
    other_bead = lane(
        "feature/packet/fx-7",
        "fx-7",
        pr=merged_pull(47, "feature/packet/fx-7", "fx-8"),
        state="integrated",
    )
    assert operator_view.lane_stage(other_bead, None, bead("fx-7", "Landed work")) == (
        "merged PR is not this head",
        "lane sync",
    )


def test_a_lane_with_an_unfinished_job_reports_that_job() -> None:
    """Breaks if branch or PR state is read before the queue, sending work at a live lane."""
    fresh = lane("feature/packet/fx-1", "fx-1", state="integrated")
    running = task(2, "fixture:lane:fx-1", group="agent")
    assert operator_view.lane_stage(fresh, running) == ("lane running", "wait")
    conflicting = lane(
        "feature/packet/fx-1", "fx-1", pr=pull(41, mergeable="CONFLICTING")
    )
    queued = task(9, "fixture:rebase:fx-1", status="Queued", group="agent")
    assert operator_view.lane_stage(conflicting, queued) == ("rebase queued", "wait")
    landed = lane(
        "feature/packet/fx-7",
        "fx-7",
        pr=merged_pull(47, "feature/packet/fx-7", "fx-7"),
        state="integrated",
    )
    assert operator_view.lane_stage(landed, running, bead("fx-7", "Landed work")) == (
        "lane running",
        "wait",
    )


def test_no_lane_next_action_merges_by_hand() -> None:
    """Breaks if an open PR's next action is a gh merge instead of the armed gate."""
    green = lane("feature/packet/fx-5", "fx-5", pr=pull(45))
    assert operator_view.lane_stage(green, None) == ("pr open", "lane publish")
    assert not [
        following
        for _stage, following in stages_of(snapshot()).values()
        if following.startswith("gh ")
    ]


def test_render_shows_groups_attention_jobs_lanes_with_timing_and_ready() -> None:
    text = operator_view.render(snapshot())

    assert "== fixture at" in text
    assert "normal idle PAUSED" in text
    assert "agent 1 running" in text
    assert "! job 3 fixture:check failed exit 2 at" in text and "(20m ago)" in text
    assert "! feature-packet-fx-2 checks failing PR #42" in text
    assert "! feature-packet-fx-4 lane failed" in text
    assert "== jobs: 2 active" in text
    assert "== lanes: 7" in text
    lane_lines = {
        line.split()[0]: line
        for line in text.splitlines()
        if line.strip().startswith("feature-packet-")
    }
    assert "lane running" in lane_lines["feature-packet-fx-1"]
    assert "#2" in lane_lines["feature-packet-fx-1"]
    assert "30m" in lane_lines["feature-packet-fx-1"]
    assert "#41 open checks:pass auto" in lane_lines["feature-packet-fx-1"]
    assert lane_lines["feature-packet-fx-1"].rstrip().endswith("wait")
    assert "idle dirty" in lane_lines["feature-packet-fx-3"]
    assert lane_lines["feature-packet-fx-6"].rstrip().endswith("lane rebase or publish")
    assert lane_lines["feature-packet-fx-7"].rstrip().endswith("lane sync")
    assert "== ready: 1 beads" in text and "fx-9" in text


def test_render_says_nothing_needs_attention_when_nothing_does() -> None:
    text = operator_view.render(snapshot(tasks=(), lanes=(), ready=()))
    assert "== nothing needs attention" in text
    assert "== lanes: 0" in text


def test_checks_summary_orders_fail_over_pending_over_pass() -> None:
    assert operator_view._checks({"statusCheckRollup": []}) == "none"
    assert (
        operator_view._checks(
            {
                "statusCheckRollup": [
                    {"status": "IN_PROGRESS"},
                    {"conclusion": "SUCCESS", "status": "COMPLETED"},
                ]
            }
        )
        == "pending"
    )
    assert (
        operator_view._checks(
            {
                "statusCheckRollup": [
                    {"status": "IN_PROGRESS"},
                    {"conclusion": "FAILURE", "status": "COMPLETED"},
                ]
            }
        )
        == "fail"
    )
    assert (
        operator_view._checks({"statusCheckRollup": [{"state": "SUCCESS"}]}) == "pass"
    )


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
        "lane_rows",
        lambda project, full=False: [lane("feature/packet/fx-1", "fx-1")],
    )
    monkeypatch.setattr(
        operator_view,
        "SubprocessBdReader",
        lambda root: FakeBd(beads={"fx-1": bead("fx-1", "One")}),
    )

    collected = operator_view.collect(config, project, now=NOW)
    assert [item.label for item in collected.tasks] == ["fixture:check"]
    assert [row.bead for row in collected.lanes] == ["fx-1"]
    assert [item["id"] for item in collected.ready] == ["fx-1"]
    assert collected.errors == ()

    fake_pueue.fail_tasks = True
    degraded = operator_view.collect(config, project, now=NOW)
    assert degraded.tasks == ()
    assert degraded.errors and degraded.errors[0].startswith("pueue:")
    assert "! pueue:" in operator_view.render(degraded)


def test_to_dict_carries_stage_next_timing_and_group_counts() -> None:
    payload = snapshot().to_dict()
    assert payload["schema"] == "sinnix.agentctl.view.v2"
    assert payload["groups"]["normal"] == {
        "status": "Paused",
        "running": 0,
        "queued": 0,
        "paused": 0,
    }
    assert payload["groups"]["agent"]["running"] == 1
    lanes = {row["bead"]: row for row in payload["lanes"]}
    assert lanes["fx-1"]["stage"] == "lane running" and lanes["fx-1"]["next"] == "wait"
    assert lanes["fx-7"]["stage"] == "merged" and lanes["fx-7"]["next"] == "lane sync"
    assert (
        lanes["fx-1"]["elapsed"] == "30m"
        and lanes["fx-1"]["since"] == "2026-09-03T08:30:00+00:00"
    )
    assert lanes["fx-1"]["agent"]["job_id"] == 2
    assert lanes["fx-2"]["pr"]["checks"] == "fail"
    assert lanes["fx-3"]["pr"] is None and lanes["fx-3"]["agent"] is None
