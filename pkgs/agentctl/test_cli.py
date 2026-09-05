"""The CLI: every verb reaches its function in-process and prints one document."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest
from agentctl import batch, cli
from agentctl.config import Config
from conftest import FakePueue, read_launch


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
    assert json.loads(captured.out)["state"] == "stopped"
    assert captured.err.count("\n") == 1 and "; stopped" in captured.err
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
    from agentctl import backpressure

    monkeypatch.setattr(
        backpressure,
        "read_pressure",
        lambda _root: {"io_full_avg60": 0.0, "memory_full_avg60": 0.0},
    )
    monkeypatch.setattr(
        backpressure.pueue, "groups_status", lambda: {"agent": "Running"}
    )

    assert cli.main(["backpressure", "tick"]) == 0
    assert json.loads(capsys.readouterr().out)["action"] == "hold"


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
    from agentctl import batch

    batch.runs_dir(config).mkdir(parents=True, exist_ok=True)
    batch.manifest_path(config, run_id).write_text(
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


def test_batch_list_reads_each_run_pr_through_the_project(
    fake_pueue: FakePueue,
    cli_config: Config,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = "fixture-20260903-080000-0123abcd"
    _manifest(cli_config, run_id)
    path = batch.manifest_path(cli_config, run_id)
    document = json.loads(path.read_text())
    document["landing"]["pr_number"] = 41
    path.write_text(json.dumps(document))
    asked: list[tuple[str, int]] = []
    monkeypatch.setattr(
        cli.batch.github,
        "pull_request",
        lambda root, number: asked.append((str(root), number))
        or {"number": number, "state": "MERGED"},
    )

    assert cli.main(["batch", "list", "fixture", "--json"]) == 0

    assert asked == [(str(cli_config.project_roots[0]), 41)]
    assert json.loads(capsys.readouterr().out)[0]["landing"]["pr"]["state"] == "MERGED"


def test_job_clean_daemon_era_removes_only_the_listed_subtrees_and_is_idempotent(
    cli_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    state = cli_config.state_dir
    for name in (
        "leases",
        "locks",
        "workspaces",
        "logs",
        "results",
        "jobs-archive",
        "jobs",
        "inputs",
        "runs",
    ):
        (state / name).mkdir(parents=True, exist_ok=True)
    (state / "leases" / "held.json").write_text("{}")
    (state / "logs" / "old.log").write_text("")
    for name in (
        "active-jobs.json",
        "capacity.json",
        "task-sinnix.lock",
        "schedules.json",
    ):
        (state / name).write_text("")
    (state / "jobs" / "fixture-check-1.log").write_text("kept")
    (state / "jobs" / "fixture-check-1.log.pgid").write_text("123")

    assert cli.main(["job", "clean", "--daemon-era"]) == 0
    captured = capsys.readouterr()
    removed = json.loads(captured.out)["removed"]
    assert {Path(item).name for item in removed} == {
        "leases",
        "locks",
        "workspaces",
        "logs",
        "results",
        "jobs-archive",
        "active-jobs.json",
        "capacity.json",
        "task-sinnix.lock",
        "schedules.json",
        "fixture-check-1.log.pgid",
    }
    assert captured.err.startswith("removed 11 daemon-era path(s) under ")
    assert (state / "jobs" / "fixture-check-1.log").read_text() == "kept"
    assert (state / "inputs").is_dir() and (state / "runs").is_dir()

    assert cli.main(["job", "clean", "--daemon-era"]) == 0
    assert json.loads(capsys.readouterr().out)["removed"] == []


def test_job_start_passes_arguments_after_a_bare_double_dash(
    fake_pueue: FakePueue, cli_config: Config, tmp_path: Path
) -> None:
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
                "x.py",
                "-n",
                "0",
            ]
        )
        == 0
    )
    launch_input = json.loads(Path(fake_pueue.added[0]["command"][1]).read_text())
    assert tuple(launch_input["argv"])[-3:] == ("x.py", "-n", "0")


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
