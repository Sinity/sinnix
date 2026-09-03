"""The CLI: every verb reaches its function in-process and prints one document."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import FakePueue
from sinnixd import cli
from sinnixd.config import Config


@pytest.fixture
def cli_config(tmp_path: Path, config: Config, monkeypatch: pytest.MonkeyPatch) -> Config:
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
    started = json.loads(capsys.readouterr().out)
    assert started["job_id"] == 1 and started["phase"] == "running"
    assert fake_pueue.added[0]["label"] == "fixture:check"

    assert cli.main(["--plain", "job", "list", "--project", "fixture"]) == 0
    assert "fixture:check" in capsys.readouterr().out

    fake_pueue.finish_when_waited(1, lambda fake: fake.succeed(1))
    assert cli.main(["job", "wait", "1"]) == 0
    assert json.loads(capsys.readouterr().out)["phase"] == "succeeded"

    assert cli.main(["job", "get", "1"]) == 0
    assert json.loads(capsys.readouterr().out)["terminal"] is True


def test_job_start_with_wait_reports_a_failure_in_the_exit_status(
    fake_pueue: FakePueue, cli_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_pueue.finish_when_waited(1, lambda fake: fake.fail(1, exit_code=3))
    assert cli.main(["job", "start", "fixture", "check", "--wait"]) == 1
    assert json.loads(capsys.readouterr().out)["phase"] == "failed"


def test_errors_are_one_line_on_stderr_and_a_nonzero_status(
    fake_pueue: FakePueue, cli_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["job", "start", "fixture", "missing"]) == 1
    assert "unknown project operation" in capsys.readouterr().err
    assert cli.main(["job", "get", "99"]) == 1
    assert "no task 99" in capsys.readouterr().err
    assert cli.main(["project", "get", "nowhere"]) == 1
    assert "nowhere" in capsys.readouterr().err


def test_project_verbs_read_the_catalog(cli_config: Config, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["project", "list"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert [row["id"] for row in listed["projects"]] == ["fixture"]
    assert cli.main(["--plain", "project", "operations", "fixture"]) == 0
    assert "nightly" in capsys.readouterr().out


def test_events_tail_prints_the_last_lines_filtered_by_project(
    cli_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    cli_config.event_spool.write_text(
        '{"kind":"queue-task","label":"fixture:check","result":"Success"}\n'
        '{"kind":"queue-task","label":"other:check","result":"Failed"}\n'
        '{"kind":"backpressure","action":"froze","group":"agent"}\n'
    )
    assert cli.main(["events", "tail", "--project", "fixture"]) == 0
    out = capsys.readouterr().out
    assert "fixture:check" in out and "other:check" not in out
    assert cli.main(["events", "tail", "--lines", "1"]) == 0
    assert capsys.readouterr().out.strip().startswith('{"kind":"backpressure"')


def test_a_missing_spool_is_reported(cli_config: Config, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["events", "tail"]) == 1
    assert "no event spool" in capsys.readouterr().err


def test_view_json_is_the_snapshot(
    fake_pueue: FakePueue, cli_config: Config, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli.operator_view, "lane_rows", lambda project, full=False: [])
    monkeypatch.setattr(cli.operator_view, "SubprocessBdReader", lambda root: type("R", (), {"ready": lambda self: []})())
    assert cli.main(["view", "fixture", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["project"] == "fixture"
    assert cli.main(["view", "fixture"]) == 0
    assert "== fixture at" in capsys.readouterr().out
