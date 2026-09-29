"""Secret environment values reach the command, never persisted job records.

Launch inputs and job logs live under the backed-up state directory. A
secret-named variable's value is held on the runtime tmpfs and masked out of
what the job wrote; the command still receives it.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest
from agentctl import launch
from agentctl.config import Config
from agentctl.launch_input import read_input, secret_environment, write_input
from agentctl.projects import load_project_adapter
from agentctl.run import main
from conftest import FakePueue, read_launch

# Synthetic, shaped like a real key so every masking rule applies to it.
SECRET = "sk-fixture-" + "0123456789abcdef" * 2


@pytest.fixture
def runtime_dir(secret_env_dir: Path) -> Path:
    return secret_env_dir


def launch_document(tmp_path: Path, argv: list[str]) -> dict[str, object]:
    return {
        "job_id": "job-a",
        "project_id": "fixture",
        "operation": "check",
        "argv": argv,
        "environment": {"PATH": os.environ["PATH"], "FIXTURE_API_KEY": SECRET},
        "working_directory": str(tmp_path),
        "timeout_seconds": 30,
        "result_kind": "exit",
        "label": "fixture:check:job-a",
        "log_path": str(tmp_path / "job-a.log"),
        "event_spool_path": str(tmp_path / "events.jsonl"),
    }


def test_a_launch_input_keeps_secret_names_and_no_secret_values(
    tmp_path: Path, runtime_dir: Path
) -> None:
    """Fails if a secret value is written into the persisted launch input."""
    path = tmp_path / "inputs" / "job-a.json"

    write_input(path, launch_document(tmp_path, ["true"]))

    assert SECRET not in path.read_text()
    stored = read_input(path)
    assert "FIXTURE_API_KEY" not in stored["environment"]
    assert stored["secret_environment"] == ["FIXTURE_API_KEY"]
    assert secret_environment(path, stored) == ({"FIXTURE_API_KEY": SECRET}, [])
    sidecar = runtime_dir / "job-a.json"
    assert stat.S_IMODE(sidecar.stat().st_mode) == 0o600
    assert stat.S_IMODE(runtime_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700

    # A later rewrite of the stored form (a hold release, a retry) keeps the
    # names and leaves the held values alone.
    write_input(path, {**stored, "queue_task_id": 7})
    assert read_input(path)["secret_environment"] == ["FIXTURE_API_KEY"]
    assert secret_environment(path, read_input(path))[0] == {"FIXTURE_API_KEY": SECRET}


def test_the_command_gets_the_secret_and_its_log_keeps_only_a_mask(
    tmp_path: Path,
) -> None:
    """Fails if the child loses the value or the finished log still holds it."""
    path = tmp_path / "inputs" / "job-a.json"
    write_input(
        path,
        launch_document(
            tmp_path,
            [
                "sh",
                "-c",
                'printf "key=%s len=%s" "$FIXTURE_API_KEY" "${#FIXTURE_API_KEY}"',
            ],
        ),
    )

    assert main([str(path)]) == 0

    log = (tmp_path / "job-a.log").read_text()
    assert SECRET not in log
    assert log == f"key=[REDACTED{'*' * (len(SECRET) - 10)}] len={len(SECRET)}"


def test_a_secret_lost_with_the_runtime_directory_is_reported(
    tmp_path: Path, runtime_dir: Path
) -> None:
    """Fails if a job silently runs without a secret it was launched with."""
    path = tmp_path / "inputs" / "job-a.json"
    write_input(
        path,
        launch_document(tmp_path, ["sh", "-c", 'printf "[%s]" "${FIXTURE_API_KEY:-}"']),
    )
    (runtime_dir / "job-a.json").unlink()

    assert main([str(path)]) == 0

    log = (tmp_path / "job-a.log").read_text()
    assert "secret environment no longer held" in log
    assert "FIXTURE_API_KEY" in log and log.endswith("[]")


def test_job_log_reads_mask_a_secret_written_before_masking(
    fake_pueue: FakePueue,
    config: Config,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fails if a log read or page returns a secret the reader holds.

    Logs from before masking existed, and a running job's log, are masked as
    they are read, including a value split across two pages.
    """
    monkeypatch.setenv("FIXTURE_API_KEY", SECRET)
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("verify"))
    written = read_launch(config, fake_pueue.task(started["job_id"]))
    log_path = Path(written["log_path"])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    text = f"before {SECRET} after\n"
    log_path.write_text(text)
    fake_pueue.succeed(started["job_id"])

    assert SECRET not in launch.logs(config, started["job_id"])
    split = text.index(SECRET) + 5
    first = launch.read_job_artifact(config, started["job_id"], limit=split)
    second = launch.read_job_artifact(
        config, started["job_id"], offset=first["next_offset"], limit=1000
    )
    joined = first["text"] + second["text"]
    assert SECRET[:5] not in first["text"] and SECRET[5:] not in second["text"]
    assert len(joined) == len(text) and "[REDACTED" in joined
    assert json.loads(json.dumps(first)) == first
