"""The CLI: every verb reaches its function in-process and prints one document."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

import pytest
from agentctl import cli, github, manifest, operator_view, pueue
from agentctl.config import Config
from conftest import SELF_REVIEW, FakePueue, read_launch


@pytest.fixture
def cli_config(
    tmp_path: Path, config: Config, monkeypatch: pytest.MonkeyPatch
) -> Config:
    location = tmp_path / "agentctl.json"
    location.write_text(
        json.dumps(
            {
                "project_roots": [str(root) for root in config.project_roots],
                "agent_runner": str(config.agent_runner),
                "event_spool": str(config.event_spool),
                "state_dir": str(config.state_dir),
                "agentctl": config.agentctl_executable,
            }
        )
    )
    monkeypatch.setenv("AGENTCTL_CONFIG", str(location))
    return config


def test_job_start_get_logs_and_wait_round_trip(
    fake_pueue: FakePueue, cli_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["job", "start", "fixture", "check", "--", "--flag"]) == 0
    captured = capsys.readouterr()
    started = json.loads(captured.out)
    assert started["job_id"] == 1 and started["phase"] == "running"
    assert captured.err.startswith("job 1 fixture:check running since ")
    assert fake_pueue.added[0]["label"] == "fixture:check"

    assert cli.main(["job", "list", "--project", "fixture"]) == 0
    listed = capsys.readouterr().out
    assert "fixture:check" in listed and "age" in listed
    assert cli.main(["job", "list", "--project", "fixture", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["label"] == "fixture:check"

    fake_pueue.finish_when_waited(1, lambda fake: fake.succeed(1))
    assert cli.main(["--json", "job", "wait", "1"]) == 0
    assert json.loads(capsys.readouterr().out)["phase"] == "succeeded"

    assert cli.main(["job", "get", "1"]) == 0
    line = capsys.readouterr().out
    assert line.startswith("job 1 fixture:check succeeded finished ")


@pytest.mark.parametrize("verb", ["cancel", "retry"])
def test_job_controls_refuse_discarded_operation_arguments(
    monkeypatch: pytest.MonkeyPatch, verb: str
) -> None:
    def dispatch(*_args: object) -> int:
        pytest.fail("invalid command reached a mutation")

    monkeypatch.setattr(cli, "_dispatch", dispatch)
    with pytest.raises(SystemExit) as refused:
        cli.main(["job", verb, "42", "--", "unexpected"])
    assert refused.value.code == 2


@pytest.mark.parametrize(
    ("overrides", "expected_error"),
    [
        ({"schema_version": 99}, "schema_version"),
        ({"attempt": 0}, "attempt"),
    ],
)
def test_result_validate_worker_uses_owner_contract(
    tmp_path: Path,
    cli_config: Config,
    capsys: pytest.CaptureFixture[str],
    overrides: dict[str, object],
    expected_error: str,
) -> None:
    result = {
        "candidate_sha": "a" * 40,
        "beads": [
            {
                "id": "fixture-1",
                "criteria": [
                    {
                        "text": "synthetic criterion",
                        "status": "satisfied",
                        "evidence": "synthetic verification",
                    }
                ],
            }
        ],
        "unresolved": [],
        "verification": [
            {"command": "synthetic check", "receipt": "synthetic receipt"}
        ],
        "self_review": deepcopy(SELF_REVIEW),
        **overrides,
    }
    path = tmp_path / "worker-result.json"
    path.write_text(json.dumps(result))

    assert cli.main(["result", "validate-worker", str(path)]) == cli.EXIT_REFUSED
    assert expected_error in capsys.readouterr().err


def test_result_validate_worker_accepts_a_valid_synthetic_result(
    tmp_path: Path,
    cli_config: Config,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "worker-result.json"
    path.write_text(
        json.dumps(
            {
                "candidate_sha": "a" * 40,
                "beads": [
                    {
                        "id": "fixture-1",
                        "criteria": [
                            {
                                "text": "synthetic criterion",
                                "status": "satisfied",
                                "evidence": "synthetic verification",
                            }
                        ],
                    }
                ],
                "unresolved": [],
                "verification": [
                    {"command": "synthetic check", "receipt": "synthetic receipt"}
                ],
                "self_review": deepcopy(SELF_REVIEW),
            }
        )
    )

    assert cli.main(["result", "validate-worker", str(path)]) == cli.EXIT_OK
    assert capsys.readouterr().out.strip() == "worker result is valid"


def test_cli_cancel_before_start_retains_not_started_across_reads(
    fake_pueue: FakePueue, cli_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["job", "start", "fixture", "check"]) == 0
    started = json.loads(capsys.readouterr().out)
    fake_pueue.queue(started["job_id"])
    assert (
        cli.main(
            [
                "job",
                "cancel",
                str(started["job_id"]),
                "--reference",
                started["reference"],
            ]
        )
        == 0
    )
    cancelled = json.loads(capsys.readouterr().out)
    assert cancelled["phase"] == "cancelled" and cancelled["started"] is False
    for _ in range(2):
        assert (
            cli.main(
                [
                    "--json",
                    "job",
                    "get",
                    str(started["job_id"]),
                    "--reference",
                    started["reference"],
                ]
            )
            == 0
        )
        document = json.loads(capsys.readouterr().out)
        assert document["phase"] == "cancelled"
        assert document["started"] is False
        assert document["disposition"] == {"outcome": "cancelled", "started": False}


def test_job_list_is_newest_first_and_bounded_unless_all(
    fake_pueue: FakePueue, cli_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    from agentctl.operator_view import DEFAULT_JOB_ROWS

    for _ in range(DEFAULT_JOB_ROWS + 3):
        assert cli.main(["job", "start", "fixture", "check"]) == 0
        capsys.readouterr()
    assert cli.main(["--json", "job", "list"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert [row["job_id"] for row in listed][:3] == [
        DEFAULT_JOB_ROWS + 3,
        DEFAULT_JOB_ROWS + 2,
        DEFAULT_JOB_ROWS + 1,
    ]
    assert len(listed) == DEFAULT_JOB_ROWS
    assert cli.main(["--json", "job", "list", "--all"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == DEFAULT_JOB_ROWS + 3
    assert cli.main(["job", "list"]) == 0
    # The fixture tasks started on 2026-09-03, which is not today: the date shows.
    assert "09-03 " in capsys.readouterr().out


def test_job_snapshot_bounds_terminal_history_without_hiding_active_jobs(
    fake_pueue: FakePueue,
    cli_config: Config,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for _ in range(80):
        task_id = fake_pueue.add(
            group="normal",
            label="fixture:history",
            command=("true",),
            working_directory=cli_config.project_roots[0],
        )
        fake_pueue.succeed(task_id)
    running = fake_pueue.add(
        group="agent",
        label="fixture:worker:run",
        command=("true",),
        working_directory=cli_config.project_roots[0],
    )
    queued = fake_pueue.add(
        group="agent",
        label="fixture:queued",
        command=("true",),
        working_directory=cli_config.project_roots[0],
        after=(running,),
    )
    monkeypatch.setattr(
        pueue,
        "status",
        lambda: pueue.Status(
            fake_pueue.tasks(),
            {
                name: {
                    "status": "Paused" if name in fake_pueue.paused else "Running",
                    "parallel_tasks": parallel,
                }
                for name, parallel in fake_pueue.groups.items()
            },
        ),
    )

    assert cli.main(["--json", "job", "snapshot", "--limit", "3"]) == 0
    snapshot = json.loads(capsys.readouterr().out)
    assert [row["job_id"] for row in snapshot["jobs"][:2]] == [queued, running]
    assert snapshot["groups"]["agent"]["running"] == 1
    assert snapshot["groups"]["agent"]["queued"] == 1
    assert snapshot["groups"]["normal"]["terminal"] == 80
    assert snapshot["coverage"] == {
        "active": {"total": 2, "returned": 2},
        "terminal": {"total": 80, "returned": 1},
    }
    assert snapshot["omitted"] == {"total": 79, "active": 0, "terminal": 79}
    assert cli.main(["job", "snapshot", "--limit", "101"]) == cli.EXIT_REFUSED
    assert "between 1 and 100" in capsys.readouterr().err


def test_job_start_infers_the_project_from_the_working_directory(
    fake_pueue: FakePueue,
    cli_config: Config,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(cli_config.project_roots[0])
    assert cli.main(["job", "start", "check", "--", "--flag"]) == 0
    assert json.loads(capsys.readouterr().out)["label"] == "fixture:check"
    assert read_launch(cli_config, fake_pueue.task(1))["argv"][-1] == "--flag"
    assert cli.main(["job", "start", "--project", "fixture", "check"]) == 0
    assert json.loads(capsys.readouterr().out)["label"] == "fixture:check"
    assert cli.main(["job", "start", str(cli_config.project_roots[0]), "check"]) == 0
    assert json.loads(capsys.readouterr().out)["label"] == "fixture:check"


def test_job_start_with_wait_reports_a_failure_in_the_exit_status(
    fake_pueue: FakePueue, cli_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_pueue.finish_when_waited(1, lambda fake: fake.fail(1, exit_code=3))
    assert (
        cli.main(["job", "start", "fixture", "check", "--wait"])
        == cli.EXIT_JOB_NOT_SUCCEEDED
    )
    captured = capsys.readouterr()
    assert json.loads(captured.out)["phase"] == "failed"
    assert "failed exit 3" in captured.err


def test_job_fire_with_wait_reports_failure(
    fake_pueue: FakePueue, cli_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_pueue.finish_when_waited(1, lambda fake: fake.fail(1, exit_code=3))
    assert (
        cli.main(["job", "fire", "fixture", "check", "--wait"])
        == cli.EXIT_JOB_NOT_SUCCEEDED
    )
    captured = capsys.readouterr()
    assert json.loads(captured.out)["phase"] == "failed"
    assert "failed exit 3" in captured.err


def test_retained_run_diagnostics_reach_json_and_human_errors(
    cli_config: Config,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = cli.JobError("worker provisioning stopped")
    error.run_id = "fixture-run"
    error.unprovisioned = [
        {"worker": "review", "beads": ["fx-1"], "reason": "queue uncertain"}
    ]
    monkeypatch.setattr(cli, "_dispatch", lambda *_args: (_ for _ in ()).throw(error))

    assert cli.main(["--json", "job", "list"]) == cli.EXIT_REFUSED
    assert json.loads(capsys.readouterr().out) == {
        "error": "worker provisioning stopped",
        "retained_run": "fixture-run",
        "unprovisioned": [
            {"worker": "review", "beads": ["fx-1"], "reason": "queue uncertain"}
        ],
    }
    assert cli.main(["job", "list"]) == cli.EXIT_REFUSED
    assert "retained run fixture-run" in capsys.readouterr().err


def test_job_get_renders_the_scratch_footprint(
    fake_pueue: FakePueue, cli_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["job", "start", "fixture", "check"]) == 0
    capsys.readouterr()
    reference = Path(fake_pueue.added[0]["command"][1]).stem
    outcome = cli_config.jobs_dir / f"{reference}.outcome"
    outcome.parent.mkdir(parents=True, exist_ok=True)
    outcome.write_text(
        json.dumps(
            {
                "outcome": "success",
                "exit_code": 0,
                "scratch": {
                    "kind": "tmpfs",
                    "path": "/dev/shm/agentctl/ref",
                    "bytes": 4096,
                    "files": 2,
                    "truncated": False,
                },
            }
        )
    )
    fake_pueue.succeed(1)

    assert cli.main(["job", "get", "1"]) == 0

    assert "scratch tmpfs 4096 bytes in 2 file(s)" in capsys.readouterr().out
    assert cli.main(["job", "get", "1", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["scratch"]["files"] == 2


def test_write_verbs_print_json_and_one_summary_line_on_stderr(
    fake_pueue: FakePueue,
    cli_config: Config,
    capsys: pytest.CaptureFixture[str],
    recording_systemctl: Callable[[], list[list[str]]],
) -> None:
    assert cli.main(["job", "start", "fixture", "check"]) == 0
    capsys.readouterr()
    assert cli.main(["job", "cancel", "1"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["state"] == "unresolved"
    assert captured.err.count("\n") == 1 and "; unresolved" in captured.err
    assert cli.main(["job", "clean", "1"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["cleaned"] is True
    assert captured.err.endswith("; cleaned\n")


def test_exit_codes_are_the_documented_table() -> None:
    assert (
        cli.EXIT_OK,
        cli.EXIT_REFUSED,
        cli.EXIT_USAGE,
        cli.EXIT_SUBSTRATE,
        cli.EXIT_JOB_NOT_SUCCEEDED,
    ) == (0, 1, 2, 3, 4)
    with pytest.raises(SystemExit) as usage:
        cli.main(["job", "get"])
    assert usage.value.code == cli.EXIT_USAGE


def test_errors_are_one_line_on_stderr_and_a_nonzero_status(
    fake_pueue: FakePueue, cli_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["job", "start", "fixture", "missing"]) == cli.EXIT_REFUSED
    assert "unknown project operation" in capsys.readouterr().err
    assert cli.main(["job", "get", "99"]) == cli.EXIT_REFUSED
    assert "no task 99" in capsys.readouterr().err
    assert cli.main(["project", "get", "nowhere"]) == cli.EXIT_REFUSED
    assert "nowhere" in capsys.readouterr().err
    assert cli.main(["batch", "status", "no-such-run"]) == cli.EXIT_REFUSED
    assert "no run no-such-run" in capsys.readouterr().err
    fake_pueue.fail_tasks = True
    assert cli.main(["job", "list"]) == cli.EXIT_SUBSTRATE
    assert "fixture pueue status failed" in capsys.readouterr().err


def test_project_verbs_read_the_catalog(
    cli_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["--json", "project", "list"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert [row["id"] for row in listed["projects"]] == ["fixture"]
    assert cli.main(["project", "operations", "fixture"]) == 0
    assert "nightly" in capsys.readouterr().out


def test_batch_cleanup_refuses_unknown_positional_owner(
    cli_config: Config,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(cli_config.project_roots[0])
    monkeypatch.setattr(
        cli.batch, "clean", lambda *_: pytest.fail("wrong owner cleanup")
    )
    assert cli.main(["batch", "clean", "nowhere"]) == cli.EXIT_REFUSED
    assert (
        "could not resolve an AgentCTL project for nowhere" in capsys.readouterr().err
    )


def test_events_tail_prints_the_last_lines_filtered_by_project(
    cli_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    cli_config.event_spool.write_text(
        '{"kind":"queue-task","emitted_at":"2026-09-03T08:00:00+00:00","label":"fixture:check","phase":"started","task_id":null}\n'
        '{"kind":"queue-task","emitted_at":"2026-09-03T08:05:00+00:00","label":"fixture:check","phase":"finished","outcome":"failed","exit_code":2,"task_id":4}\n'
        '{"kind":"queue-task","emitted_at":"2026-09-03T08:06:00+00:00","label":"other:check","phase":"finished","outcome":"success","exit_code":0,"task_id":5}\n'
        '{"kind":"backpressure","emitted_at":"2026-09-03T08:07:00+00:00","action":"closed","group":"agent"}\n'
    )
    assert cli.main(["events", "tail", "--project", "fixture"]) == 0
    out = capsys.readouterr().out
    assert "fixture:check started\n" in out
    assert "fixture:check finished failed exit 2 (task 4)" in out
    assert "other:check" not in out
    assert cli.main(["events", "tail", "--lines", "1"]) == 0
    assert "backpressure closed agent" in capsys.readouterr().out
    assert cli.main(["--json", "events", "tail", "--lines", "1"]) == 0
    assert capsys.readouterr().out.strip().startswith('{"kind":"backpressure"')


def test_last_matching_lines_match_a_full_scan_across_block_boundaries(
    tmp_path: Path,
) -> None:
    # Lines of varied length straddle the 64 KiB read blocks; the backward
    # reader must agree exactly with a forward scan, including the file's
    # first line and a missing trailing newline.
    lines = [
        f'{{"n":{i},"project":"{"a" if i % 3 else "b"}","pad":"{"x" * (i % 997)}"}}'
        for i in range(4000)
    ]
    spool = tmp_path / "events.jsonl"
    spool.write_text("\n".join(lines))
    for count in (1, 7, 1500, 5000):
        for wanted in (lambda line: True, lambda line: '"project":"b"' in line):
            with spool.open("rb") as handle:
                got = cli._last_matching_lines(handle, count, wanted)
            expected = [line for line in lines if wanted(line)][-count:]
            assert got == expected


def test_events_tail_memory_is_bounded_by_the_requested_lines(tmp_path: Path) -> None:
    # Anti-vacuity: reading the whole spool (the former list comprehension)
    # holds the file's size in memory; the bound below is ~1/10 of it.
    import tracemalloc

    spool = tmp_path / "events.jsonl"
    record = (
        '{"kind":"queue-task","label":"fixture:check","phase":"finished","pad":"'
        + "x" * 400
        + '"}\n'
    )
    with spool.open("w") as handle:
        for _ in range(50_000):
            handle.write(record)
    size = spool.stat().st_size
    tracemalloc.start()
    with spool.open("rb") as handle:
        got = cli._last_matching_lines(handle, 40, lambda line: True)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert len(got) == 40
    assert peak < size // 10, (peak, size)


def test_tail_reports_an_oversized_record_without_retaining_it(tmp_path: Path) -> None:
    spool = tmp_path / "events.jsonl"
    spool.write_bytes(b"a\n" + b"x" * (2 * cli.MAX_EVENT_LINE_BYTES) + b"\nb\n")
    with spool.open("rb") as handle:
        lines = cli._last_matching_lines(handle, 3, lambda line: True)
    assert lines[0] == "a" and lines[-1] == "b"
    assert json.loads(lines[1]) == {
        "schema_version": 1,
        "kind": "event-gap",
        "reason": "oversized_record",
        "record_bytes": 2 * cli.MAX_EVENT_LINE_BYTES,
        "scope": "unattributed",
    }


@pytest.mark.parametrize("follow", [False, True])
def test_event_reader_reports_unattributed_gaps_and_resumes(
    cli_config: Config,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    follow: bool,
) -> None:
    records = (
        b'{"kind":"queue-task","project":"other","label":"other:check"}\n'
        + b'{"kind":"queue-task","project":"fixture","label":"fixture:check","phase":"started"}\n'
        + b"x" * (2 * cli.MAX_EVENT_LINE_BYTES)
        + b"\n"
        + b"not-json\n"
        + b'"non-object"\n'
        + b'{"kind":"queue-task","label":"fixture:check","bad":"\xff"}\n'
        + b'{"kind":"queue-task", "project": "fixture", "label":"fixture:check","phase":"finished","outcome":"success"}\n'
    )
    cli_config.event_spool.touch()
    idle = 0

    def append_on_idle(_seconds: float) -> None:
        nonlocal idle
        idle += 1
        if idle == 1:
            with cli_config.event_spool.open("ab") as handle:
                handle.write(records)
        else:
            raise KeyboardInterrupt

    if follow:
        monkeypatch.setattr(cli, "time", SimpleNamespace(sleep=append_on_idle))
    else:
        cli_config.event_spool.write_bytes(records)
    arguments = ["--json", "events", "tail", "--project", "fixture"]
    if follow:
        arguments += ["--follow", "--lines", "0"]
    assert cli.main(arguments) == 0
    observed = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert observed[0]["phase"] == "started" and observed[0]["project"] == "fixture"
    assert [event.get("reason") for event in observed[1:-1]] == [
        "oversized_record",
        "invalid_json",
        "non_object_record",
        "invalid_utf8",
    ]
    assert all(
        event["scope"] == "unattributed" and "project" not in event
        for event in observed[1:-1]
    )
    assert observed[1]["record_bytes"] == 2 * cli.MAX_EVENT_LINE_BYTES
    assert observed[-1]["phase"] == "finished" and observed[-1]["project"] == "fixture"


def test_follow_tail_process_rss_stays_bounded_on_large_spool(
    cli_config: Config,
) -> None:
    record = (
        b'{"kind":"queue-task","label":"fixture:check","pad":"' + b"x" * 400 + b'"}\n'
    )
    with cli_config.event_spool.open("wb") as spool:
        for _ in range(50_000):
            spool.write(record)
    child = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "agentctl.cli",
            "events",
            "tail",
            "--follow",
            "--lines",
            "1",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env=os.environ.copy(),
    )
    try:
        time.sleep(0.5)
        assert child.poll() is None, child.stderr.read().decode()
        status = Path(f"/proc/{child.pid}/status").read_text()
        rss = int(status.split("VmRSS:")[1].splitlines()[0].split()[0])
        assert rss < 80_000
        duplicate = subprocess.run(
            [
                sys.executable,
                "-m",
                "agentctl.cli",
                "events",
                "tail",
                "--follow",
                "--lines",
                "1",
            ],
            capture_output=True,
            env=os.environ.copy(),
            timeout=5,
        )
        assert duplicate.returncode == cli.EXIT_REFUSED
        assert b"already running" in duplicate.stderr
    finally:
        child.terminate()
        child.wait(timeout=5)


def test_a_missing_spool_is_reported(
    cli_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["events", "tail"]) == cli.EXIT_REFUSED
    assert "no event spool" in capsys.readouterr().err


def test_view_json_is_the_snapshot(
    fake_pueue: FakePueue,
    cli_config: Config,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cli.operator_view,
        "SubprocessBdReader",
        lambda root: type("R", (), {"ready": lambda self: []})(),
    )
    assert cli.main(["--json", "view", "fixture"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["project"] == "fixture"
    assert cli.main(["view", "fixture"]) == 0
    assert "== fixture at" in capsys.readouterr().out
    monkeypatch.chdir(cli_config.project_roots[0])
    assert cli.main(["view"]) == 0
    assert "== fixture at" in capsys.readouterr().out


def test_backpressure_tick_reports_the_decision(
    cli_config: Config, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    from agentctl import backpressure, launch

    monkeypatch.setattr(
        backpressure,
        "read_pressure",
        lambda _root: {"io_full_avg60": 0.0, "memory_full_avg60": 0.0},
    )
    monkeypatch.setattr(
        backpressure.pueue, "groups_status", lambda: {"agent": "Running"}
    )

    calls = []
    monkeypatch.setattr(
        launch, "release_holds",
        lambda config: calls.append(config) or {"released": [7], "waiting": []},
    )
    assert cli.main(["backpressure", "tick"]) == 0
    output = capsys.readouterr()
    decision = json.loads(output.out)
    assert decision["action"] == "clear"
    assert decision["holds_released"] == [7]
    assert len(calls) == 1
    assert calls[0].event_spool == cli_config.event_spool
    assert "backpressure clear" in output.err


def test_default_state_dir_moves_the_previous_directory_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    from agentctl.config import default_state_dir

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    previous = tmp_path / "sinnixd"
    (previous / "jobs").mkdir(parents=True)

    assert default_state_dir() == tmp_path / "agentctl"
    assert (tmp_path / "agentctl" / "jobs").is_dir()
    assert not previous.exists()
    assert "moved state" in capsys.readouterr().err

    (previous / "jobs").mkdir(parents=True)
    assert default_state_dir() == tmp_path / "agentctl"
    assert previous.is_dir()
    assert capsys.readouterr().err == ""


def _manifest(config: Config, run_id: str) -> None:
    manifest.runs_dir(config).mkdir(parents=True, exist_ok=True)
    manifest.manifest_path(config, run_id).write_text(
        json.dumps(
            {
                "run_id": run_id,
                "project": "fixture",
                "base_commit": "a" * 40,
                "created_at": "2026-09-03T08:00:00+00:00",
                "harness": "external",
                "workers": [
                    {
                        "id": "w1",
                        "beads": ["fixture-1"],
                        "branch": f"batch/{run_id}/w1",
                        "worktree": "/nowhere",
                        "task_id": None,
                    }
                ],
                "landing": {"task_id": None, "candidate_sha": "b" * 40},
                "acceptance": None,
                "prepared": True,
            }
        )
    )


def test_batch_reads_accept_the_run_suffix_and_shorten_ids_unless_full(
    fake_pueue: FakePueue, cli_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    _manifest(cli_config, "fixture-20260903-080000-0123abcd")
    assert cli.main(["batch", "status", "0123abcd"]) == 0
    text = capsys.readouterr().out
    assert text.startswith("run 0123abcd fixture external base aaaaaaaa stage")
    assert "started 2026" not in text and "candidate bbbbbbbb" in text
    assert "  w1: prompt /nowhere/.agentctl/prompt.md\n" in text
    assert (
        "    next: agentctl batch result fixture-20260903-080000-0123abcd w1 "
        "/nowhere/.agentctl/prompt.result.json\n" in text
    )
    assert cli.main(["batch", "status", "0123abcd", "--full"]) == 0
    text = capsys.readouterr().out
    assert "run fixture-20260903-080000-0123abcd" in text and "b" * 40 in text
    assert cli.main(["batch", "list", "fixture"]) == 0
    listed = capsys.readouterr().out
    assert listed.splitlines()[0].split() == [
        "run",
        "harness",
        "stage",
        "started",
        "age",
        "workers",
        "candidate",
        "abandonment",
    ]
    assert "0123abcd" in listed and "fixture-20260903" not in listed
    assert cli.main(["batch", "list", "fixture", "--json"]) == 0
    assert (
        json.loads(capsys.readouterr().out)[0]["run_id"]
        == "fixture-20260903-080000-0123abcd"
    )
    _manifest(cli_config, "fixture-20260903-090000-0123abcd")
    assert cli.main(["batch", "status", "0123abcd"]) == cli.EXIT_REFUSED
    assert "names 2 runs" in capsys.readouterr().err


def test_batch_status_renders_requested_dispatch_and_abandonment(
    fake_pueue: FakePueue, cli_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    run_id = "fixture-20260903-080000-0123abcd"
    _manifest(cli_config, run_id)
    path = manifest.manifest_path(cli_config, run_id)
    document = json.loads(path.read_text())
    document["workers"][0].update(
        {
            "task_reference": "worker-launch",
            "attempts": [
                {
                    "number": 2,
                    "task_id": 41,
                    "task_reference": "worker-launch",
                    "backend": "fixture-backend",
                    "model": "fixture-model",
                    "effort": "high",
                }
            ],
        }
    )
    document["landing"].update(
        {
            "task_reference": "landing-launch",
            "verify_run": {"job_id": 42, "reference": "verify-launch"},
            "review_verdict": {"policy": "none"},
            "agent_attempts": [
                {
                    "kind": "review",
                    "job_id": 43,
                    "launch_reference": "review-launch",
                    "requested": {
                        "backend": "fixture-backend",
                        "model": "fixture-model",
                        "effort": "high",
                    },
                }
            ],
        }
    )
    document["abandoned"] = {
        "at": "2026-09-03T09:00:00+00:00",
        "reason": "canary failed",
        "residual": ["batch/run/w1: worktree kept"],
    }
    path.write_text(json.dumps(document))

    assert cli.main(["batch", "status", "0123abcd"]) == 0
    text = capsys.readouterr().out
    assert (
        "dispatch: attempt 2; requested backend=fixture-backend "
        "model=fixture-model effort=high; task 41; ref worker-launch" in text
    )
    assert "landing: task None ref landing-launch" in text
    assert "evidence: verify task 42 ref verify-launch; review policy none" in text
    assert (
        "landing agent: review; requested backend=fixture-backend "
        "model=fixture-model effort=high; task 43; ref review-launch" in text
    )
    assert "abandoned: " in text and "canary failed" in text
    assert "residual: batch/run/w1: worktree kept" in text

    assert cli.main(["batch", "list", "fixture"]) == 0
    assert "canary failed; 1 residual" in capsys.readouterr().out


def test_batch_list_reads_each_run_pr_through_the_project(
    fake_pueue: FakePueue,
    cli_config: Config,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = "fixture-20260903-080000-0123abcd"
    _manifest(cli_config, run_id)
    path = manifest.manifest_path(cli_config, run_id)
    document = json.loads(path.read_text())
    document["landing"]["pr_number"] = 41
    path.write_text(json.dumps(document))
    asked: list[tuple[str, int]] = []
    monkeypatch.setattr(
        github,
        "pull_request",
        lambda root, number: (
            asked.append((str(root), number)) or {"number": number, "state": "MERGED"}
        ),
    )

    assert cli.main(["batch", "list", "fixture", "--json"]) == 0

    assert asked == [(str(cli_config.project_roots[0]), 41)]
    assert json.loads(capsys.readouterr().out)[0]["landing"]["pr"]["state"] == "MERGED"


def test_retired_destructive_cleanup_is_refused_before_touching_evidence(
    cli_config: Config, tmp_path: Path
) -> None:
    state = cli_config.state_dir
    historical = state / "jobs-archive" / "history.json"
    current = state / "jobs" / "fixture.attempts" / "1" / "output.log"
    historical.parent.mkdir(parents=True)
    current.parent.mkdir(parents=True)
    historical.write_bytes(b"historical evidence")
    current.write_bytes(b"current attempt")
    external = tmp_path / "external-evidence"
    external.write_bytes(b"external evidence")
    retained_link = state / "native"
    retained_link.symlink_to(external)

    with pytest.raises(SystemExit) as usage:
        cli.main(["job", "clean", "--daemon-era"])

    assert usage.value.code == cli.EXIT_USAGE
    assert historical.read_bytes() == b"historical evidence"
    assert current.read_bytes() == b"current attempt"
    assert retained_link.is_symlink()
    assert external.read_bytes() == b"external evidence"


def test_job_start_passes_arguments_after_a_bare_double_dash(
    fake_pueue: FakePueue, cli_config: Config, tmp_path: Path
) -> None:
    """Breaks if arguments are joined: several selected files must reach the
    operation as several words, so one job runs the whole selection."""
    workspace = cli_config.project_roots[0]
    assert (
        cli.main(
            [
                "job",
                "start",
                "fixture",
                "check",
                "--workspace",
                str(workspace),
                "--",
                "a.py",
                "b.py",
                "-n",
                "0",
            ]
        )
        == 0
    )
    launch_input = json.loads(Path(fake_pueue.added[0]["command"][1]).read_text())
    assert tuple(launch_input["argv"])[-4:] == ("a.py", "b.py", "-n", "0")


def test_an_unknown_operation_is_a_refusal_and_a_key_error_is_not(
    fake_pueue: FakePueue,
    cli_config: Config,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert cli.main(["job", "start", "fixture", "nope"]) == cli.EXIT_REFUSED
    assert "unknown project operation: fixture.nope" in capsys.readouterr().err
    assert cli.main(["job", "fire", "fixture", "nope"]) == cli.EXIT_REFUSED
    assert "unknown project operation: fixture.nope" in capsys.readouterr().err

    def broken(project_id: str | None = None) -> list[dict[str, object]]:
        raise KeyError("phase")

    monkeypatch.setattr(cli.launch, "list_jobs", broken)
    with pytest.raises(KeyError):
        cli.main(["job", "list"])


def _lost_landing(config: Config, run_id: str, *, filed: bool) -> Path:
    """A run whose recorded landing task the queue no longer has."""
    _manifest(config, run_id)
    path = manifest.manifest_path(config, run_id)
    document = json.loads(path.read_text())
    document["landing"]["task_id"] = 4547
    document["landing"]["task_reference"] = "land-4547"
    if filed:
        document["workers"][0]["result"] = {
            "candidate_sha": "c" * 40,
            "beads": [],
            "unresolved": [],
            "verification": [],
            "self_review": deepcopy(SELF_REVIEW),
        }
    path.write_text(json.dumps(document))
    return path


def test_batch_status_asks_for_the_outstanding_result_not_a_landing(
    fake_pueue: FakePueue, cli_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    """mzw2: a landing queued while a worker owes a result only refuses it.

    The phantom stage read `ready to land`; naming `batch queue` in its place
    would buy a task that fails `worker_not_done` the moment it runs.
    """
    run_id = "fixture-20260903-080000-0123abcd"
    _lost_landing(cli_config, run_id, filed=False)

    assert cli.main(["batch", "status", "0123abcd"]) == 0
    text = capsys.readouterr().out
    assert "stage landing vanished" in text
    assert "landing: task 4547 (pueue no longer has it)" in text
    assert (
        f"    next: agentctl batch result {run_id} w1 "
        "/nowhere/.agentctl/prompt.result.json\n" in text
    )
    assert "agentctl batch queue" not in text
    assert "  next: the worker commands above" in text
    assert cli.main(["--json", "batch", "status", "0123abcd"]) == 0
    assert json.loads(capsys.readouterr().out)["landing"]["vanished"] == 4547

    # A caller that queues one anyway gets a task that waits for the result
    # rather than one that runs into a refusal.
    assert cli.main(["batch", "queue", "0123abcd"]) == 0
    stashed = json.loads(capsys.readouterr().out)["landing_task_id"]
    assert fake_pueue.task(stashed).status == "Stashed"


def test_batch_queue_replaces_a_lost_landing_once_the_results_are_in(
    fake_pueue: FakePueue, cli_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    """mzw2: with every result filed, the landing is all that is missing."""
    run_id = "fixture-20260903-080000-0123abcd"
    path = _lost_landing(cli_config, run_id, filed=True)

    assert cli.main(["batch", "status", "0123abcd"]) == 0
    text = capsys.readouterr().out
    assert "stage landing vanished" in text
    assert "landing: task 4547 (pueue no longer has it)" in text
    assert f"  next: agentctl batch queue {run_id}\n" in text

    assert cli.main(["batch", "queue", "0123abcd"]) == 0
    printed, summary = capsys.readouterr()
    queued = json.loads(printed)["landing_task_id"]
    task = fake_pueue.task(queued)
    assert task.label == f"fixture:land:{run_id}"
    # Nothing is left to wait for, so the replacement runs.
    assert task.status != "Stashed" and task.dependencies == ()
    assert summary == f"queued landing task {queued} for 0123abcd\n"
    stored = json.loads(path.read_text())["landing"]
    assert stored["task_id"] == queued and stored["task_reference"] is not None

    assert cli.main(["batch", "status", "0123abcd"]) == 0
    assert "pueue no longer has it" not in capsys.readouterr().out


def test_wait_reports_elapsed_age_after_blocking(
    fake_pueue: FakePueue, cli_config: Config,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    clock = datetime(2026, 1, 1, 12, tzinfo=UTC)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock

    monkeypatch.setattr(operator_view, "datetime", Clock)

    def wait(*args, **kwargs):
        nonlocal clock
        started = clock.isoformat()
        clock += timedelta(minutes=10)
        return {"job_id": 1, "label": "fixture:check", "phase": "running",
                "started_at": started, "wait_timed_out": True}

    monkeypatch.setattr(cli.launch, "wait", wait)
    assert cli.main(["job", "wait", "1"]) == cli.EXIT_JOB_NOT_SUCCEEDED
    text = capsys.readouterr().out
    assert "(10m) (wait timed out)" in text


@pytest.mark.parametrize("verb", ["start", "fire"])
def test_job_launch_wait_timeout_is_not_success(
    verb: str, fake_pueue: FakePueue, cli_config: Config,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["job", verb, "fixture", "check", "--wait",
                     "--timeout-seconds", "1"]) == cli.EXIT_JOB_NOT_SUCCEEDED
    observed = json.loads(capsys.readouterr().out)
    assert observed["wait_timed_out"] is True
    assert observed["phase"] == "running"
    assert fake_pueue.task(observed["job_id"]).status == "Running"


@pytest.mark.parametrize("verb", ["start", "fire"])
def test_job_launch_wait_success_is_success(
    verb: str, fake_pueue: FakePueue, cli_config: Config,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_pueue.finish_when_waited(1, lambda fake: fake.succeed(1))
    assert cli.main(["job", verb, "fixture", "check", "--wait"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["phase"] == "succeeded"
