"""Path claims, session parking and the quota check, on synthetic fixtures."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sinnix_runtime.operator_state import claims, engine, quota, sessions, text

NOW = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
ALPHA = {"harness": "claude", "session": "alpha-session"}
BETA = {"harness": "codex", "session": "beta-session"}


# ---------------------------------------------------------------- claims


def test_overlapping_claim_is_reported_to_the_new_claimant(tmp_path: Path) -> None:
    """Breaks if a second session claiming inside a claimed path is not told
    who holds it, or if the claim is refused."""
    store = tmp_path / "claims.json"
    first, others = claims.claim(
        tmp_path / "repo" / "modules",
        "memory settings",
        who=ALPHA,
        duration_seconds=3600,
        store=store,
        now=NOW,
    )
    assert others == []

    second, others = claims.claim(
        tmp_path / "repo" / "modules" / "memory.nix",
        "slice limits",
        who=BETA,
        duration_seconds=3600,
        store=store,
        now=NOW,
    )

    assert [other["id"] for other in others] == [first["id"]]
    active = claims.active(store, NOW)
    assert [row["id"] for row in active] == [first["id"], second["id"]]
    pairs = claims.overlaps(active)
    assert len(pairs) == 1
    assert "alpha-se" in claims.overlap_line(pairs[0])
    document = json.loads(store.read_text())
    assert document["schema"] == claims.SCHEMA
    assert set(document["claims"][0]) == {
        "id",
        "path",
        "purpose",
        "harness",
        "session",
        "claimed_at",
        "expires_at",
    }


def test_a_claim_expires_by_itself_and_release_drops_only_the_callers(
    tmp_path: Path,
) -> None:
    store = tmp_path / "claims.json"
    claims.claim("/x/a", "one", who=ALPHA, duration_seconds=60, store=store, now=NOW)
    claims.claim("/x/b", "two", who=ALPHA, duration_seconds=7200, store=store, now=NOW)
    claims.claim("/x/b", "three", who=BETA, duration_seconds=7200, store=store, now=NOW)
    later = NOW + timedelta(minutes=5)

    assert sorted(row["purpose"] for row in claims.active(store, later)) == [
        "three",
        "two",
    ]
    released = claims.release(who=ALPHA, store=store, now=later)

    assert [row["purpose"] for row in released] == ["two"]
    assert [row["purpose"] for row in claims.active(store, later)] == ["three"]


def test_sibling_paths_and_one_sessions_own_claims_do_not_overlap() -> None:
    assert not claims.overlapping("/x/modules", "/x/modules-old")
    rows = [
        {"session": "a", "path": "/x/m", "purpose": "p"},
        {"session": "a", "path": "/x/m/file", "purpose": "q"},
    ]
    assert claims.overlaps(rows) == []


@pytest.mark.parametrize(
    "text_, seconds", [("90m", 5400), ("4h", 14400), ("1h30m", 5400), ("2d", 172800)]
)
def test_durations(text_: str, seconds: float) -> None:
    assert claims.parse_duration(text_) == seconds


def test_a_malformed_duration_is_refused() -> None:
    with pytest.raises(ValueError):
        claims.parse_duration("soon")


def test_claim_command_prints_the_overlap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store = str(tmp_path / "claims.json")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "alpha-session")
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    assert claims.main(["--store", store, "claim", "/x/m", "--for", "first"]) == 0
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "gamma-session")
    assert claims.main(["--store", store, "claim", "/x/m/f", "--for", "second"]) == 0
    out = capsys.readouterr().out
    assert 'overlaps /x/m: claude session alpha-se, for "first"' in out
    assert claims.main(["--store", store, "release"]) == 0
    assert claims.main(["--store", store, "claims"]) == 0
    listed = capsys.readouterr().out
    assert "released /x/m/f" in listed and "/x/m: claude session alpha-se" in listed


# ---------------------------------------------------------------- quota


def limits(claude: float | None, codex: float | None = None) -> dict[str, object]:
    value: dict[str, object] = {}
    if claude is not None:
        value["claude"] = {
            "seven_day_percent": claude,
            "seven_day_resets_at": "2026-03-05T06:00:00+00:00",
            "five_hour_percent": 99.0,
        }
    else:
        value["claude"] = {"error": "RuntimeError: token expired"}
    if codex is not None:
        value["codex"] = {
            "windows": [
                {"window_minutes": 300, "used_percent": 99.0, "resets_at": "x"},
                {
                    "window_minutes": 10080,
                    "used_percent": codex,
                    "resets_at": "2026-03-04T06:00:00+00:00",
                },
            ]
        }
    return value


def test_discretionary_work_waits_at_the_weekly_threshold_only() -> None:
    """Breaks if the five-hour window, or another provider's usage, makes
    work wait when the weekly window of the gating provider is below."""
    below = quota.verdict(limits(84.0, 99.0))
    at = quota.verdict(limits(85.0, 10.0))

    assert below["ok"] is True and "below the 85% threshold" in below["reason"]
    assert at["ok"] is False
    assert at["resets_at"] == "2026-03-05T06:00:00+00:00"
    assert "Claude weekly usage 85%" in at["reason"]


def test_any_provider_waits_for_the_last_reset_and_unknown_is_not_a_wait() -> None:
    both = quota.verdict(limits(90.0, 95.0), provider="any")
    unknown = quota.verdict(limits(None))

    assert both["ok"] is False and both["resets_at"] == "2026-03-05T06:00:00+00:00"
    assert unknown["ok"] is None and "token expired" in unknown["reason"]
    assert quota.verdict(limits(None, 20.0), provider="any")["ok"] is True


def test_quota_command_exit_status(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(quota, "read_limits", lambda: limits(91.0))
    assert quota.main(["ok", "--for", "discretionary"]) == quota.EXIT_WAIT
    assert capsys.readouterr().out.startswith("wait: Claude weekly usage 91%")
    assert quota.main(["ok", "--for", "discretionary", "--threshold", "95"]) == 0
    monkeypatch.setattr(quota, "read_limits", lambda: limits(None))
    assert quota.main(["ok", "--for", "discretionary"]) == quota.EXIT_UNKNOWN


# ---------------------------------------------------------------- sessions

STAMP = NOW.timestamp()


def process(
    proc: Path,
    pid: int,
    argv: list[str],
    *,
    parent: int = 1,
    start: str = "500",
    tty: int = (136 << 8) | 7,
    environ: dict[str, str] | None = None,
    children: list[int] | None = None,
) -> None:
    root = proc / str(pid)
    (root / "task" / str(pid)).mkdir(parents=True)
    fields = ["S", str(parent), "1", "1", str(tty), *["0"] * 14, start, "0"]
    (root / "stat").write_text(f"{pid} ({Path(argv[0]).name} x) " + " ".join(fields))
    (root / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    (root / "environ").write_bytes(
        b"\0".join(f"{k}={v}".encode() for k, v in (environ or {}).items())
    )
    (root / "status").write_text("VmRSS:\t  200000 kB\nVmSwap:\t  100000 kB\n")
    (root / "cgroup").write_text("0::/user.slice/session.scope\n")
    (root / "task" / str(pid) / "children").write_text(
        " ".join(str(child) for child in children or [])
    )


def record(kind: str, content: object, **extra: object) -> str:
    return json.dumps({"type": kind, "message": {"content": content}, **extra})


def session(
    config: Path,
    proc: Path,
    pid: int,
    name: str,
    lines: list[str],
    *,
    idle_minutes: float,
    status: str = "idle",
    **process_arguments: object,
) -> str:
    sid = f"{name}-0000-0000-0000-000000000000"
    process(proc, pid, ["/x/bin/claude"], **process_arguments)  # type: ignore[arg-type]
    (config / "sessions").mkdir(parents=True, exist_ok=True)
    changed = STAMP - idle_minutes * 60
    (config / "sessions" / f"{pid}.json").write_text(
        json.dumps(
            {
                "pid": pid,
                "sessionId": sid,
                "cwd": "/x/project",
                "procStart": "500",
                "kind": "interactive",
                "name": name,
                "status": status,
                "statusUpdatedAt": changed * 1000,
            }
        )
    )
    transcript = config / "projects" / "-x-project" / f"{sid}.jsonl"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    transcript.write_text("\n".join(lines) + "\n")
    os.utime(transcript, (changed, changed))
    return sid


PROMPT = record("user", "do the thing")
DONE = record("assistant", [{"type": "text", "text": "done"}])


def tool(name: str, call: str, **tool_input: object) -> str:
    return record(
        "assistant",
        [{"type": "tool_use", "id": call, "name": name, "input": tool_input}],
    )


def result(call: str) -> str:
    return record("user", [{"type": "tool_result", "tool_use_id": call}])


@pytest.fixture
def machine(tmp_path: Path) -> dict[str, object]:
    """Sessions in every state parking must tell apart."""
    config, proc = tmp_path / "claude", tmp_path / "proc"
    ids = {
        "finished": session(
            config,
            proc,
            10,
            "finished",
            [PROMPT, tool("Bash", "t1", command="ls"), result("t1"), DONE],
            idle_minutes=300,
        ),
        "toolcall": session(
            config,
            proc,
            11,
            "toolcall",
            [PROMPT, tool("Bash", "t1", command="make")],
            idle_minutes=300,
        ),
        "jobwait": session(
            config,
            proc,
            12,
            "jobwait",
            [
                PROMPT,
                tool("Bash", "t1", command="agentctl job wait 7 --job-id x"),
                result("t1"),
                DONE,
            ],
            idle_minutes=300,
        ),
        "checkwait": session(
            config,
            proc,
            13,
            "checkwait",
            [
                PROMPT,
                tool("Bash", "t1", command="gh pr checks 5 --required --watch"),
                result("t1"),
                DONE,
            ],
            idle_minutes=300,
        ),
        "agentwait": session(
            config,
            proc,
            14,
            "agentwait",
            [PROMPT, tool("Agent", "t1", prompt="x"), result("t1"), DONE],
            idle_minutes=300,
        ),
        "child": session(
            config,
            proc,
            15,
            "child",
            [PROMPT, DONE],
            idle_minutes=300,
            environ={"CLAUDE_CODE_SESSION_ID": "coordinator-session"},
        ),
        "queued": session(config, proc, 16, "queued", [PROMPT, DONE], idle_minutes=300),
        "recent": session(config, proc, 17, "recent", [PROMPT, DONE], idle_minutes=20),
        "touched": session(
            config,
            proc,
            18,
            "touched",
            [PROMPT, DONE],
            idle_minutes=300,
            tty=(136 << 8) | 9,
        ),
        "busy": session(
            config, proc, 19, "busy", [PROMPT, DONE], idle_minutes=300, status="busy"
        ),
        "nested": session(
            config, proc, 20, "nested", [PROMPT, DONE], idle_minutes=300, parent=30
        ),
        "background": session(
            config,
            proc,
            21,
            "background",
            [PROMPT, DONE],
            idle_minutes=300,
            children=[31],
        ),
        "headless": session(
            config, proc, 22, "headless", [PROMPT, DONE], idle_minutes=300, tty=0
        ),
    }
    process(proc, 30, ["/x/bin/claude"], start="400")
    process(
        proc,
        31,
        ["zsh", "-c", "source /x/shell-snapshots/s.sh && sleep 900"],
        parent=21,
    )
    process(proc, 40, ["/x/bin/codex"], start="700")
    process(proc, 41, ["/x/bin/codex", "exec", "-m", "model"], start="700")
    # A registry entry whose process id now belongs to another process.
    (config / "sessions" / "99.json").write_text(
        json.dumps(
            {"pid": 30, "sessionId": "stale", "procStart": "1", "kind": "interactive"}
        )
    )
    used = {"/dev/pts/7": STAMP - 4 * 3600, "/dev/pts/9": STAMP - 300}
    facts = sessions.collect(
        config_dir=config,
        proc=proc,
        cgroup_root=tmp_path / "cgroup",
        terminal_used=lambda path: used.get(path or ""),
        now=STAMP,
    )
    rows = sessions.judge(
        facts,
        job_sessions={ids["queued"]: ["#5 fixture:check"]},
        now=STAMP,
        idle_seconds=7200,
        touched_seconds=1800,
    )
    return {"ids": ids, "facts": facts, "rows": {row["name"]: row for row in rows}}


def test_only_an_idle_top_level_session_waiting_on_nothing_is_a_candidate(
    machine: dict[str, object],
) -> None:
    """Breaks if parking would end a session that runs a tool call, waits on a
    job, a hosted check or another agent, was started by another session, was
    touched recently, or is not idle long enough."""
    rows = machine["rows"]  # type: ignore[assignment]
    reasons = {name: "; ".join(row["keep_because"]) for name, row in rows.items()}

    assert [name for name, row in rows.items() if row["candidate"]] == ["finished"]
    assert "running tool call: Bash" in reasons["toolcall"]
    assert "last turn waits on Bash: agentctl job wait 7" in reasons["jobwait"]
    assert "last turn waits on Bash: gh pr checks 5" in reasons["checkwait"]
    assert "last turn waits on Agent" in reasons["agentwait"]
    assert "started by claude session coordina, not by the operator" in reasons["child"]
    assert "started by claude process 30" in reasons["nested"]
    assert "has unfinished job(s): #5 fixture:check" in reasons["queued"]
    assert "idle 20m, under the 2.0h limit" in reasons["recent"]
    assert "terminal used 5m ago" in reasons["touched"]
    assert "working (status busy)" in reasons["busy"]
    assert "1 background command(s) running" in reasons["background"]
    assert "not attached to a terminal" in reasons["headless"]
    assert rows["finished"]["memory_bytes"] == 300000 * 1024
    assert rows["finished"]["idle_seconds"] == 300 * 60
    # The Codex exec worker and the stale registry entry are not sessions.
    codex = [row for row in rows.values() if row["harness"] == "codex"]
    assert [row["pid"] for row in codex] == [40]
    assert "reported only" in codex[0]["keep_because"][0]


def test_an_unreadable_job_queue_keeps_every_session(
    machine: dict[str, object],
) -> None:
    rows = sessions.judge(
        machine["facts"],  # type: ignore[arg-type]
        job_sessions=None,
        now=STAMP,
        idle_seconds=7200,
        touched_seconds=1800,
    )
    assert not any(row["candidate"] for row in rows)


BOX = "─" * 40


def screen(text_: str) -> str:
    return f"● earlier output\n\n{BOX} name ─\n❯\xa0{text_}\n{BOX}\n  status line\n"


def test_input_box_reading() -> None:
    assert sessions.input_line(screen("")) == "empty"
    assert sessions.input_line(screen("half a sentence")) == "text"
    assert sessions.input_line(screen('\x1b[22;2mTry "a suggestion"')) == "empty"
    assert sessions.input_line(screen("\x1b[38:2:255:255:255mtyped")) == "text"
    assert sessions.input_line("no box on this screen\n") == "unknown"


def test_park_is_a_dry_run_and_never_ends_a_session_with_unsent_input(
    machine: dict[str, object], tmp_path: Path
) -> None:
    """Breaks if a dry run ends a process, if unsent or unreadable input is
    parked, or if a parked session is listed without its resume command."""
    facts = machine["facts"]  # type: ignore[assignment]
    rows = list(machine["rows"].values())  # type: ignore[union-attr]
    ended: list[int] = []

    def end(fact: dict[str, object]) -> None:
        ended.append(int(fact["pid"]))  # type: ignore[arg-type]

    log = tmp_path / "parked.jsonl"
    parking = tmp_path / "parking"
    dry = sessions.park(
        facts,
        rows,
        apply=False,
        screen=lambda _: screen(""),
        end=end,
        log=log,
        parking=parking,
    )
    assert [entry["name"] for entry in dry["parked"]] == ["finished"] and ended == []
    assert not log.exists() and not parking.exists()

    for shown, reason in (
        (screen("draft"), "unsent input"),
        (None, "could not be read"),
    ):
        kept = sessions.park(
            facts,
            rows,
            apply=True,
            screen=lambda _, shown=shown: shown,
            end=end,
            log=log,
            parking=parking,
        )
        assert kept["parked"] == [] and ended == []
        assert any(reason in " ".join(row["keep_because"]) for row in kept["kept"])

    sid = machine["ids"]["finished"]  # type: ignore[index]
    # The session's end hook must find the marker while the process exits.
    marked_at_end: list[bool] = []

    def end_marked(fact: dict[str, object]) -> None:
        marked_at_end.append((parking / sid).exists())
        end(fact)

    done = sessions.park(
        facts,
        rows,
        apply=True,
        screen=lambda _: screen(""),
        end=end_marked,
        log=log,
        parking=parking,
    )
    assert ended == [10] and marked_at_end == [True]
    assert done["parked"][0]["resume"] == f"cd /x/project && claude --resume {sid}"
    assert json.loads(log.read_text())["session"] == sid


def test_a_session_that_does_not_end_leaves_no_parking_marker(
    machine: dict[str, object], tmp_path: Path
) -> None:
    """Breaks if a failed park leaves the marker that keeps scratch at the
    session's next real end."""
    parking = tmp_path / "parking"
    result = sessions.park(
        machine["facts"],  # type: ignore[arg-type]
        list(machine["rows"].values()),  # type: ignore[union-attr]
        apply=True,
        screen=lambda _: screen(""),
        end=lambda _: "asked to exit but still running",
        log=None,
        parking=parking,
    )
    assert result["parked"] == [] and list(parking.iterdir()) == []


def test_ending_refuses_a_process_whose_id_was_reused(tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    process(proc, 10, ["/x/bin/claude"], start="900")
    assert "reused" in str(
        sessions.end_session({"pid": 10, "process_start": "500"}, proc=proc)
    )


# ---------------------------------------------------------------- state


def test_state_shows_activations_claims_sessions_and_a_deferred_job(
    machine: dict[str, object],
) -> None:
    """Breaks if `sinnix state` stops showing who holds an activation, an
    overlap between claims, why a discretionary job waits, or why a session
    is or is not a parking candidate."""
    job = {
        "project": "host",
        "operation": "switch",
        "label": "host:switch",
        "task_id": 4,
        "phase": "running",
        "group": "system-build",
        "started_at": engine.iso(NOW - timedelta(minutes=3)),
        "announce": True,
        "revision": {"commit": "c" * 40, "dirty": True},
        "caller": {"harness": "claude", "session": "alpha-session"},
        "working_directory": "/x/host",
    }
    held = {
        "project": "alpha",
        "operation": "research",
        "label": "alpha:research",
        "task_id": 5,
        "phase": "stashed",
        "group": "normal",
        "enqueued_at": engine.iso(NOW),
        "caller": {"harness": "claude", "session": machine["ids"]["queued"]},  # type: ignore[index]
        "deferred": {
            "reason": "Claude weekly usage 91% is above 85%",
            "until": "2026-03-05T06:01:00+00:00",
        },
    }
    claim = {
        "path": "/x/host/modules",
        "purpose": "memory settings",
        "claimed_at": engine.iso(NOW),
        "expires_at": engine.iso(NOW + timedelta(hours=1)),
    }
    state = engine.compute(
        {
            "jobs": {"jobs": [job, held]},
            "claims": [
                {**claim, **ALPHA, "id": "c-1"},
                {**claim, **BETA, "id": "c-2", "path": "/x/host/modules/memory.nix"},
                {**claim, **BETA, "id": "c-3", "expires_at": engine.iso(NOW)},
            ],
            "agent_sessions": machine["facts"],
        },
        {},
        NOW,
    )

    assert state["counts"]["activations"] == 1
    assert state["counts"]["claims"] == 2 and state["counts"]["claims_overlapping"] == 1
    assert state["counts"]["parking_candidates"] == 1
    assert state["muted"] is None and state["small_next_move"] is None
    rendered = text.render_text(state)
    assert (
        "host:switch #4 running 3m, commit ccccccccc with uncommitted changes, "
        "in /x/host; for claude session alpha-se"
    ) in rendered
    assert "overlap: /x/host/modules (claude session alpha-se" in rendered
    assert (
        "deferred until 2026-03-05T06:01:00+00:00: Claude weekly usage 91% is above 85%"
        in rendered
    )
    assert "parking candidate(s))" in rendered
    assert (
        "claude finished finished in /x/project: 293 MiB, idle 5.0h; parking candidate"
        in rendered
    )
    assert "stays: running tool call: Bash" in rendered
    lines = text.summary_lines(state)
    assert lines["activations"] and lines["claims"] and lines["sessions"]
