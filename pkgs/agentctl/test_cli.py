"""The CLI: every verb reaches its function in-process and prints one document."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agentctl import cli
from agentctl.config import Config
from conftest import FakePueue


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
    assert cli.main(["--json", "job", "start", "fixture", "check", "--", "--flag"]) == 0
    started = json.loads(capsys.readouterr().out)
    assert started["job_id"] == 1 and started["phase"] == "running"
    assert fake_pueue.added[0]["label"] == "fixture:check"

    assert cli.main(["job", "list", "--project", "fixture"]) == 0
    listed = capsys.readouterr().out
    assert "fixture:check" in listed and "elapsed" in listed
    assert cli.main(["--json", "job", "list", "--project", "fixture"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["label"] == "fixture:check"

    fake_pueue.finish_when_waited(1, lambda fake: fake.succeed(1))
    assert cli.main(["--json", "job", "wait", "1"]) == 0
    assert json.loads(capsys.readouterr().out)["phase"] == "succeeded"

    assert cli.main(["job", "get", "1"]) == 0
    line = capsys.readouterr().out
    assert line.startswith("job 1 fixture:check succeeded finished ")


def test_job_start_with_wait_reports_a_failure_in_the_exit_status(
    fake_pueue: FakePueue, cli_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_pueue.finish_when_waited(1, lambda fake: fake.fail(1, exit_code=3))
    assert (
        cli.main(["job", "start", "fixture", "check", "--wait"])
        == cli.EXIT_JOB_NOT_SUCCEEDED
    )
    assert "failed exit 3" in capsys.readouterr().out


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
        '{"kind":"queue-task","emitted_at":"2026-09-03T08:00:00+00:00","label":"fixture:check","phase":"started"}\n'
        '{"kind":"queue-task","emitted_at":"2026-09-03T08:05:00+00:00","label":"fixture:check","result":"Failed","exit_code":"2","task_id":4}\n'
        '{"kind":"queue-task","emitted_at":"2026-09-03T08:06:00+00:00","label":"other:check","result":"Success","exit_code":"0","task_id":5}\n'
        '{"kind":"backpressure","emitted_at":"2026-09-03T08:07:00+00:00","action":"froze","group":"agent"}\n'
    )
    assert cli.main(["events", "tail", "--project", "fixture"]) == 0
    out = capsys.readouterr().out
    assert "fixture:check started" in out
    assert "fixture:check finished Failed exit 2 (task 4)" in out
    assert "other:check" not in out
    assert cli.main(["events", "tail", "--lines", "1"]) == 0
    assert "backpressure froze agent" in capsys.readouterr().out
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
