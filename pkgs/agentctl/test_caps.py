"""Cross-pool caps, the I/O pressure refusal, and failure lines after a wait."""

from __future__ import annotations

import io
import json
from dataclasses import replace
from pathlib import Path

import pytest
from agentctl import cli, launch, run
from agentctl.config import Config, ConfigError, load_config
from agentctl.job_queries import JobError
from agentctl.projects import ProjectConfigError, load_project_adapter
from conftest import FakePueue, read_launch


def _declare(project_root: Path, extra: str) -> None:
    descriptor = project_root / ".agentctl/project.toml"
    descriptor.write_text(
        descriptor.read_text().replace(
            'exec = ["fixture-verify"]', 'exec = ["fixture-verify"]\n' + extra
        )
    )


def test_an_operation_names_a_cap_and_a_pressure_limit(project_root: Path) -> None:
    _declare(project_root, 'cap = "cargo"\nmax_io_pressure = 5')

    verify = load_project_adapter(project_root).operation("verify")

    assert (verify.cap, verify.max_io_pressure) == ("cargo", 5.0)
    assert verify.catalog_row()["cap"] == "cargo"
    assert load_project_adapter(project_root).operation("check").cap is None


@pytest.mark.parametrize(
    "extra",
    ['cap = "Cargo"', "cap = 3", "max_io_pressure = 101", 'max_io_pressure = "5"'],
)
def test_malformed_caps_and_pressure_limits_are_refused(
    project_root: Path, extra: str
) -> None:
    _declare(project_root, extra)
    with pytest.raises(ProjectConfigError):
        load_project_adapter(project_root)


def test_the_host_declares_caps(tmp_path: Path) -> None:
    location = tmp_path / "agentctl.json"
    location.write_text(json.dumps({"caps": {"cargo": 3}}))
    assert load_config(location).caps == {"cargo": 3}
    location.write_text(json.dumps({"caps": {"cargo": 0}}))
    with pytest.raises(ConfigError, match="caps.cargo"):
        load_config(location)


def test_a_launch_records_its_cap_and_refuses_an_undeclared_one(
    fake_pueue: FakePueue, config: Config, project_root: Path
) -> None:
    _declare(project_root, 'cap = "cargo"\nmax_io_pressure = 5')
    project = load_project_adapter(project_root)

    with pytest.raises(JobError, match="does not declare"):
        launch.start_operation(config, project, project.operation("verify"))

    declared = replace(config, caps={"cargo": 3})
    started = launch.start_operation(declared, project, project.operation("verify"))
    written = read_launch(declared, fake_pueue.task(started["task_id"]))
    assert (written["cap"], written["max_io_pressure"]) == ("cargo", 5.0)


def test_a_cap_admits_its_width_and_the_next_job_waits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if a place is not exclusive, or if a full cap does not wait."""
    monkeypatch.setattr(run, "CAP_POLL_SECONDS", 0.0)
    directory = tmp_path / "caps" / "cargo"
    log = io.BytesIO()
    first = run.hold_cap_place(directory, 1, cancelled=lambda: False, log=log)
    assert first is not None

    checks = iter([False, True])
    waiting = run.hold_cap_place(directory, 1, cancelled=lambda: next(checks), log=log)
    assert waiting is None
    assert b"waiting for one of the 1 places of cap 'cargo'" in log.getvalue()

    first.close()
    second = run.hold_cap_place(directory, 1, cancelled=lambda: True, log=log)
    assert second is not None
    second.close()


def test_a_measurement_refuses_to_start_under_io_pressure(tmp_path: Path) -> None:
    root = tmp_path / "pressure"
    root.mkdir()
    (root / "memory").write_text(
        "some avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
        "full avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
    )
    (root / "io").write_text(
        "some avg10=30.00 avg60=26.54 avg300=18.99 total=1\n"
        "full avg10=28.00 avg60=24.65 avg300=17.52 total=1\n"
    )
    reason = run.io_pressure_refusal(5.0, root)
    assert reason is not None and "24.6%" in reason and "limit of 5%" in reason
    assert run.io_pressure_refusal(30.0, root) is None


def test_a_failed_wait_prints_the_failure_lines_and_the_history_pointer(
    fake_pueue: FakePueue,
    config: Config,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    location = tmp_path / "agentctl.json"
    location.write_text(
        json.dumps(
            {
                "project_roots": [str(root) for root in config.project_roots],
                "event_spool": str(config.event_spool),
                "state_dir": str(config.state_dir),
            }
        )
    )
    monkeypatch.setenv("AGENTCTL_CONFIG", str(location))
    output = "\n".join(
        [
            "   Compiling polylogue-store v0.1.0",
            *[f"        PASS [   0.1s] store tests::case_{n}" for n in range(60)],
            "        FAIL [   0.2s] polylogue-store tests::broken_case",
            "thread 'tests::broken_case' panicked at crates/store/src/tests.rs:9:5:",
            "assertion failed: rows.is_empty()",
            *[f"        PASS [   0.1s] store tests::later_{n}" for n in range(20)],
            "     Summary [   2.0s] 81 tests run: 80 passed, 1 failed",
            "polylogue test: FAILED in 9.0s (test build 7.0s, test 2.0s)",
            "  recorded as run 2703; details: xtask history failures 2703",
        ]
    )

    def fail(fake: FakePueue) -> None:
        fake.set_log(1, output)
        fake.fail(1, exit_code=1)

    fake_pueue.finish_when_waited(1, fail)
    assert (
        cli.main(["job", "start", "fixture", "check", "--wait"])
        == cli.EXIT_JOB_NOT_SUCCEEDED
    )
    err = capsys.readouterr().err
    assert "FAIL [   0.2s] polylogue-store tests::broken_case" in err
    assert "assertion failed: rows.is_empty()" in err
    assert "recorded as run 2703; details: xtask history failures 2703" in err
    assert "full log: agentctl job logs 1" in err
    assert "case_3" not in err
