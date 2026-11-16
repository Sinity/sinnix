"""The operator state engine on synthetic facts."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sinnix_runtime.operator_state import SCHEMA, engine, history, text
from sinnix_runtime.operator_state.history import JobLog, estimate_range, summarize

NOW = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)


def stamp(minutes_ago: float) -> str:
    return engine.iso(NOW - timedelta(minutes=minutes_ago))


def commit(name: str, minutes_ago: float) -> dict[str, str]:
    return {"commit": name * 40, "at": stamp(minutes_ago), "subject": f"change {name}"}


def facts(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "projects": [
            {"id": "alpha", "root": "/x/alpha"},
            {"id": "host", "root": "/x/host"},
        ],
        "jobs": {"jobs": [], "groups": {}},
        "beads": {
            "alpha": {"human": [], "open": 3, "in_progress_count": 0, "in_progress": []}
        },
        "git": {
            "alpha": {
                "default_branch": "origin/main",
                "commits": [commit("b", 30), commit("a", 90)],
            },
            "host": {"default_branch": "origin/main", "commits": [commit("c", 20)]},
        },
        "pulls": {
            "alpha": {
                "merged": [
                    {
                        "number": 7,
                        "url": "u7",
                        "merge_commit": "a" * 40,
                        "check": "passed",
                    },
                    {
                        "number": 8,
                        "url": "u8",
                        "merge_commit": "b" * 40,
                        "check": "passed",
                    },
                ]
            },
            "host": {"merged": []},
        },
        "deployed": {
            "host_revision": "c" * 40,
            "projects": {
                "host": {"kind": "host", "revision": "c" * 40, "contains": {"c" * 40}},
                "alpha": {
                    "kind": "flake-input",
                    "revision": "a" * 40,
                    "contains": {"a" * 40},
                },
            },
        },
        "job_history": {},
        "closed_beads": [],
        "limits": {},
    }
    base.update(overrides)
    return base


def test_nothing_waiting_is_a_zero_count_and_human_tasks_raise_it() -> None:
    assert engine.compute(facts(), {}, NOW)["counts"]["waiting"] == 0
    waiting = facts(
        beads={
            "alpha": {
                "human": [
                    {
                        "id": "alpha-1",
                        "title": "Pick a name",
                        "priority": 1,
                        "created_at": stamp(125),
                    }
                ]
            }
        },
        plannotator={
            "installed": True,
            "items": [{"id": "p1", "title": "Plan", "since": stamp(5)}],
        },
    )
    state = engine.compute(waiting, {}, NOW)
    assert state["schema"] == SCHEMA
    assert state["counts"]["waiting"] == 2
    assert [row["id"] for row in state["waiting"]] == ["alpha-1", "p1"]
    assert state["waiting"][0]["age_seconds"] == 125 * 60
    assert "alpha alpha-1: Pick a name (waiting 2.1h)" in text.render_text(state)
    # The reserved slots exist and stay empty.
    assert state["muted"] is None and state["small_next_move"] is None


def test_a_merged_change_the_running_revision_lacks_is_merged_not_live() -> None:
    state = engine.compute(facts(), {}, NOW)
    by_commit = {
        row["short"]: row for rows in state["finished"].values() for row in rows
    }
    assert by_commit["a" * 9]["state"] == "finished"
    assert by_commit["b" * 9]["state"] == "merged_not_live"
    assert by_commit["c" * 9]["state"] == "finished"
    assert state["counts"]["merged_not_live"] == 1
    assert [row["short"] for row in state["finished"]["merged_not_live"]] == ["b" * 9]
    # Agent-written text appears only beside the commit and check it cites.
    line = text.change_line(by_commit["b" * 9])
    assert (
        line
        == 'merged, not yet live: "change b" [alpha bbbbbbbbb, pull request 8, check passed]'
    )
    product = next(row for row in state["products"] if row["project"] == "alpha")
    assert (
        product["merged_not_live"] == 1
        and product["deployment"]["kind"] == "flake-input"
    )
    assert "contains" not in product["deployment"]
    json.dumps(state)  # the document is plain JSON


def test_a_failing_or_unread_check_is_not_finished() -> None:
    inputs = facts()
    inputs["pulls"]["alpha"]["merged"][0]["check"] = "failing"  # type: ignore[index]
    del inputs["pulls"]["host"]["merged"]  # type: ignore[index]
    state = engine.compute(inputs, {}, NOW)
    assert {row["short"]: row["state"] for row in state["finished"]["unverified"]} == {
        "a" * 9: "check_failing",
        "c" * 9: "check_unknown",
    }
    assert state["counts"]["finished_new"] == 0


def test_last_looked_splits_finished_into_new_and_earlier() -> None:
    memory: dict[str, object] = {}
    first = engine.compute(facts(), memory, NOW)
    # Never looked: everything finished is new, timed by its merge.
    assert first["counts"]["finished_new"] == 2
    assert memory["finished_at"]["alpha:" + "a" * 40] == stamp(90)  # type: ignore[index]

    memory["last_looked_at"] = engine.iso(NOW)
    later = NOW + timedelta(minutes=10)
    assert engine.compute(facts(), memory, later)["counts"]["finished_new"] == 0

    # The running revision now contains b: it finishes when that is observed,
    # after the operator last looked, although it merged before.
    live = facts()
    live["deployed"]["projects"]["alpha"]["contains"] = {"a" * 40, "b" * 40}  # type: ignore[index]
    state = engine.compute(live, memory, later)
    assert [row["short"] for row in state["finished"]["new"]] == ["b" * 9]
    assert state["finished"]["new"][0]["finished_at"] == engine.iso(later)
    assert {row["short"] for row in state["finished"]["earlier"]} == {"a" * 9, "c" * 9}

    memory["last_looked_at"] = engine.iso(later)
    assert (
        engine.compute(live, memory, later + timedelta(minutes=1))["counts"][
            "finished_new"
        ]
        == 0
    )


def test_changes_wait_for_the_running_revision_to_be_read() -> None:
    memory: dict[str, object] = {}
    early = engine.compute(facts(deployed={}), memory, NOW)
    assert early["counts"]["finished_new"] == 0
    assert all(
        row["state"] == "live_unknown" for row in early["finished"]["unverified"]
    )
    # Once read, changes still take their merge time, not the moment of reading.
    state = engine.compute(facts(), memory, NOW + timedelta(minutes=5))
    assert {row["finished_at"] for row in state["finished"]["new"]} == {
        stamp(90),
        stamp(20),
    }


def test_a_range_from_few_samples_is_wide_and_says_so() -> None:
    thin = summarize([60, 600, 7200], "closed tasks of size small")
    assert thin["thin"] and thin["samples"] == 3
    assert (thin["low_seconds"], thin["high_seconds"]) == (60, 7200)
    assert "only 3" in thin["note"]
    assert engine.range_text(thin).endswith(
        "(3 closed tasks of size small) [few samples]"
    )
    assert summarize([], "runs")["samples"] == 0
    assert engine.range_text(summarize([], "runs of x")) == "no history (runs of x)"
    wide = summarize(range(1, 101), "runs")
    assert (
        not wide["thin"]
        and wide["low_seconds"] < wide["median_seconds"] < wide["high_seconds"]
    )


def closed(
    kind: str, size: str | None, hours: float, human: bool = False
) -> dict[str, object]:
    row = {
        "issue_type": kind,
        "labels": ([f"size:{size}"] if size else []) + (["human"] if human else []),
        "created_at": stamp(hours * 60 + 600),
        "started_at": stamp(hours * 60),
        "closed_at": stamp(0),
    }
    sample = history.bead_sample("alpha", row)
    assert sample is not None
    return sample


def test_estimate_falls_back_in_the_open_when_the_exact_set_is_small() -> None:
    samples = [closed("bug", "small", 1), closed("bug", "small", 2)]
    samples += [closed("bug", None, hours) for hours in range(1, 11)]
    result = estimate_range(samples, "bug", "small")
    assert result["exact_match_samples"] == 2
    assert result["claim_to_close"]["samples"] == 12
    assert result["fallback"] == (
        "only 2 closed tasks of kind bug and size small; "
        "the range uses closed tasks of kind bug, any size"
    )
    exact = estimate_range(samples, "feature", "large")
    assert (
        exact["claim_to_close"]["samples"] == 12
    )  # nothing matches: every closed task
    assert history.bead_size({"estimated_minutes": 90}) == "medium"
    assert history.bead_size({"labels": ["size:extra-large"]}) == "xlarge"
    assert history.bead_own_range(
        {"metadata": {"estimate_low_minutes": "30", "estimate_high_minutes": 120}}
    ) == {"low_seconds": 1800, "high_seconds": 7200}


def job(task_id: int, phase: str, **fields: object) -> dict[str, object]:
    return {
        "task_id": task_id,
        "job_id": f"job-{task_id}",
        "label": "alpha:test",
        "project": "alpha",
        "operation": "test",
        "group": "normal",
        "phase": phase,
        "terminal": False,
        "attempt": 1,
        **fields,
    }


def test_running_rows_say_for_whom_and_queued_rows_say_why() -> None:
    jobs = {
        "groups": {},
        "jobs": [
            job(
                1,
                "running",
                started_at=stamp(20),
                command="cargo test",
                caller={
                    "harness": "claude",
                    "session": "0123456789",
                    "bead": "alpha-9",
                },
            ),
            job(
                2,
                "queued",
                enqueued_at=stamp(5),
                wait={
                    "reason": "pool-full",
                    "group": "normal",
                    "occupied_by": [
                        {"task_id": 1, "label": "alpha:test", "started_at": stamp(20)}
                    ],
                },
            ),
            job(
                3,
                "queued",
                enqueued_at=stamp(4),
                group="bulk",
                wait={"reason": "group-paused", "group": "bulk"},
            ),
        ],
    }
    state = engine.compute(facts(jobs=jobs), {}, NOW)
    assert state["counts"]["running"] == 1 and state["counts"]["queued"] == 2
    assert text.job_line(state["running"][0]) == (
        "alpha:test #1 in pool normal, running 20m; for task alpha-9, claude session 01234567"
    )
    assert state["queued"][0]["waiting_because"] == (
        "pool normal full behind alpha:test (#1, running 20m)"
    )
    assert state["queued"][1]["waiting_because"] == "pool bulk is paused in the queue"
    assert "caller not recorded" in text.job_line(state["queued"][0])


def test_stalled_signals_overrun_silence_and_repeated_failure() -> None:
    jobs = {
        "groups": {},
        "jobs": [
            job(1, "running", started_at=stamp(120), log_idle_seconds=2400),
            job(2, "running", started_at=stamp(3)),
        ],
    }
    failure = {
        "label": "alpha:lint",
        "project": "alpha",
        "working_directory": "/x/alpha",
        "outcome": "failure",
        "exit_code": 1,
    }
    recent = [
        {**failure, "ended_at": stamp(50), "outcome": "success", "exit_code": 0},
        *({**failure, "ended_at": stamp(minutes)} for minutes in (40, 30, 20)),
        {**failure, "label": "alpha:fmt", "ended_at": stamp(10)},
    ]
    history_facts = {"run_seconds": {"alpha:test": [300] * 10}, "recent": recent}
    state = engine.compute(facts(jobs=jobs, job_history=history_facts), {}, NOW)
    assert sorted(row["signal"] for row in state["stalled"]) == [
        "overrun",
        "repeated-failure",
        "silent",
    ]
    assert state["counts"]["stalled"] == 3
    repeated = next(
        row for row in state["stalled"] if row["signal"] == "repeated-failure"
    )
    assert repeated["text"].startswith(
        "alpha:lint failed 3 times in a row in /x/alpha with exit 1"
    )


def test_job_log_reads_only_appended_bytes_and_pairs_start_with_finish(
    tmp_path: Path,
) -> None:
    path = tmp_path / "events.jsonl"

    def event(phase: str, at: str, **fields: object) -> str:
        return (
            json.dumps(
                {
                    "kind": "queue-task",
                    "job_id": "j1",
                    "attempt": 1,
                    "label": "alpha:test",
                    "pool": "normal",
                    "phase": phase,
                    "emitted_at": at,
                    **fields,
                }
            )
            + "\n"
        )

    path.write_text(
        event("started", "2026-03-01T10:00:00Z", enqueued_at="2026-03-01T09:58:00Z")
        + '{"kind":"other"}\n'
        + '{"kind":"pressure","action":"closed","group":"bulk","emitted_at":"2026-03-01T10:00:30Z"}\n'
    )
    log = JobLog(path)
    log.refresh()
    assert log.finished_count == 0 and log.wait_seconds["normal"][0] == 120
    offset = log.offset
    with path.open("a") as handle:
        handle.write(
            event("finished", "2026-03-01T10:05:00Z", outcome="success", exit_code=0)
        )
        handle.write('{"kind":"queue-task","job_id":"partial')  # no newline yet
    log.refresh()
    assert log.offset > offset
    assert list(log.run_seconds["alpha:test"]) == [300]
    assert log.recent[-1]["outcome"] == "success" and log.finished_count == 1
    log.refresh()
    assert log.finished_count == 1  # nothing is read twice


def test_summary_lines_are_bounded_for_the_panel() -> None:
    humans = [
        {"id": f"alpha-{n}", "title": "Q", "priority": 2, "created_at": stamp(n)}
        for n in range(9)
    ]
    state = engine.compute(facts(beads={"alpha": {"human": humans}}), {}, NOW)
    lines = text.summary_lines(state)
    assert len(lines["waiting"]) == text.PANEL_ROWS + 1
    assert lines["waiting"][-1] == "and 3 more on the hub page"
    assert lines["limits"][0].startswith("memory") or lines["limits"]


def test_a_source_that_keeps_failing_waits_longer_and_keeps_its_last_value() -> None:
    from sinnix_runtime.operator_state.service import Source

    answers = iter([lambda: "first", None, None, lambda: "second"])

    def collect() -> str:
        answer = next(answers)
        if answer is None:
            raise RuntimeError("unavailable")
        return answer()

    source = Source("fixture", 10, collect)
    assert source.due(0) == float("inf")
    source.refresh()
    start = source.attempted
    assert source.due(start + 10) == 1
    source.refresh()
    source.refresh()
    assert source.value == "first" and source.failures == 2
    assert "unavailable" in source.error
    assert source.due(source.attempted + 10) == 0.25
    source.refresh()
    assert source.value == "second" and source.failures == 0 and source.error is None
