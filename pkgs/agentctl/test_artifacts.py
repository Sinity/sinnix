"""Execution preservation through the public launch/read/clean interfaces."""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

import pytest
from agentctl import launch, pueue, run
from agentctl.config import Config
from agentctl.projects import load_project_adapter
from conftest import FakePueue, read_launch


def execute(config, fake_pueue, project_root, *, stdout="first", exit_code=0):
    project = load_project_adapter(project_root)
    job = launch.enqueue(
        config,
        project=project,
        operation="verify",
        label="fixture:verify",
        group="pytest",
        argv=[
            sys.executable,
            "-c",
            f"import sys; print({stdout!r}); sys.exit({exit_code})",
        ],
        working_directory=project_root,
        timeout_seconds=30,
        result_kind="json",
        environment={"PATH": os.environ["PATH"]},
    )
    document = read_launch(config, fake_pueue.task(job["job_id"]))
    # Execute synthetic fixture commands without a systemd unit.
    document.pop("pool")
    return job, document


def test_retry_preserves_complete_outputs_outcomes_and_reads_after_clean(
    config: Config,
    fake_pueue: FakePueue,
    project_root: Path,
):
    job, document = execute(
        config,
        fake_pueue,
        project_root,
        stdout=json.dumps({"payload": "x" * 100_000}),
        exit_code=7,
    )
    input_path = str(launch.launch_input_path(fake_pueue.task(job["job_id"])))
    assert run.run(document, launch_input=input_path) == 7
    first = launch.result(config, job["job_id"])
    assert first["attempt"] == 1
    assert first["value"] is None
    assert not first["page"]["complete"]
    canonical = Path(first["artifacts"]["result"])
    original = canonical.read_bytes()
    assert json.loads(original) == {"payload": "x" * 100_000}
    first_outcome = Path(first["artifacts"]["outcome"]).read_bytes()
    document["argv"] = [
        sys.executable,
        "-c",
        "import sys; print('{\"second\": true}'); print('diagnostics', file=sys.stderr)",
    ]
    assert run.run(document, launch_input=input_path) == 0
    second = launch.result(config, job["job_id"])
    assert second["attempt"] == 2 and second["value"] == {"second": True}
    assert canonical.read_bytes() == original
    assert Path(first["artifacts"]["outcome"]).read_bytes() == first_outcome
    assert launch.result(config, job["job_id"], attempt=1)["outcome"]["exit_code"] == 7
    assert launch.logs(config, job["job_id"], attempt=2).strip() == "diagnostics"
    restored = bytearray()
    offset = 0
    while True:
        page = launch.read_job_artifact(
            config,
            job["job_id"],
            artifact="result",
            attempt=1,
            offset=offset,
            limit=17001,
        )
        restored.extend(base64.b64decode(page["base64"]))
        if page["next_offset"] is None:
            break
        offset = page["next_offset"]
    assert bytes(restored) == original
    fake_pueue.succeed(job["job_id"])
    cleaned = launch.clean(config, job["job_id"], job["reference"])
    assert cleaned["retained"]
    archived = launch.result(config, job["job_id"], job["reference"], attempt=1)
    assert archived["queue_present"] is False
    assert archived["attempt_count"] == 2
    assert archived["outcome"]["exit_code"] == 7
    assert canonical.read_bytes() == original


def test_retry_preserves_legacy_artifacts_before_upgrading(
    config: Config,
    fake_pueue: FakePueue,
    project_root: Path,
):
    job, document = execute(config, fake_pueue, project_root, stdout='{"new": true}')
    log = Path(document["log_path"])
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_bytes(b"legacy partial\xff")
    Path(document["result_path"]).write_text('{"legacy":true}')
    run.outcome_path_for(log).write_text('{"outcome":"failed","exit_code":3}')
    assert launch.result(config, job["job_id"])["value"] == {"legacy": True}
    assert run.run(document, launch_input="fixture-input") == 0
    assert launch.result(config, job["job_id"])["attempt"] == 2
    old = launch.result(config, job["job_id"], attempt=1)
    assert old["value"] == {"legacy": True}
    assert Path(old["artifacts"]["log"]).read_bytes() == b"legacy partial\xff"
    assert old["outcome"]["exit_code"] == 3


def test_interrupted_attempt_partial_output_survives_the_next_invocation(
    config: Config,
    fake_pueue: FakePueue,
    project_root: Path,
    monkeypatch,
):
    job, document = execute(config, fake_pueue, project_root)
    original = run._run_bare

    def interrupt(argv, launch_input, environment, stdout, log):
        stdout.write(b'{"partial":')
        log.write(b"interrupted diagnostics")
        raise KeyboardInterrupt

    monkeypatch.setattr(run, "_run_bare", interrupt)
    with pytest.raises(KeyboardInterrupt):
        run.run(document, launch_input="fixture-input")
    partial = launch.get_job(job["job_id"], config)
    monkeypatch.setattr(run, "_run_bare", original)
    assert run.run(document, launch_input="fixture-input") == 0
    assert Path(partial["artifacts"]["result"]).read_bytes() == b'{"partial":'
    assert Path(partial["artifacts"]["log"]).read_bytes() == b"interrupted diagnostics"
    assert not Path(partial["artifacts"]["outcome"]).exists()
    assert launch.get_job(job["job_id"], config)["attempt"] == 2


def test_attempt_reference_survives_pueue_reordering(
    config: Config,
    fake_pueue: FakePueue,
    project_root: Path,
):
    first, document = execute(config, fake_pueue, project_root, stdout='{"first":true}')
    second, _ = execute(config, fake_pueue, project_root)
    assert run.run(document, launch_input="fixture-input") == 0
    fake_pueue.queue(first["job_id"])
    fake_pueue.queue(second["job_id"])
    fake_pueue.switch(first["job_id"], second["job_id"])
    read = launch.result(config, first["job_id"], first["reference"], attempt=1)
    assert read["value"] == {"first": True}
    assert read["job_id"] == second["job_id"]


def test_durable_owner_request_reconciles_acceptance_and_survives_clean(
    config: Config,
    fake_pueue: FakePueue,
    project_root: Path,
):
    project = load_project_adapter(project_root)
    first = launch.start_operation(
        config,
        project,
        project.operation("verify"),
        owner_request_key="fixture-request",
    )
    again = launch.start_operation(
        config,
        project,
        project.operation("verify"),
        owner_request_key="fixture-request",
    )
    assert first["reference"] == again["reference"] and again["reused"]
    assert len(fake_pueue.added) == 1
    fake_pueue.succeed(first["job_id"])
    launch.clean(config, first["job_id"])
    retained = launch.lookup_operation_request(config, "fixture-request")
    assert retained["reference"] == first["reference"]
    assert retained["queue_present"] is False
    with pytest.raises(launch.JobError, match="different launch request"):
        launch.start_operation(
            config,
            project,
            project.operation("verify"),
            owner_request_key="fixture-request",
            extra_argv=("changed",),
        )


def test_owner_request_does_not_repeat_an_uncertain_submission(
    config: Config,
    fake_pueue: FakePueue,
    project_root: Path,
    monkeypatch,
):
    project = load_project_adapter(project_root)
    calls = []

    def uncertain(**kwargs):
        calls.append(kwargs)
        raise pueue.PueueError("connection lost")

    monkeypatch.setattr(pueue, "add", uncertain)
    for _ in range(2):
        with pytest.raises(launch.EnqueueUncertain):
            launch.start_operation(
                config,
                project,
                project.operation("verify"),
                owner_request_key="uncertain",
            )
    assert len(calls) == 1


def test_owner_request_recovers_lost_acknowledgement_without_duplicate(
    config: Config,
    fake_pueue: FakePueue,
    project_root: Path,
    monkeypatch,
):
    project = load_project_adapter(project_root)
    real_add = pueue.add

    def uncertain(**kwargs):
        real_add(**kwargs)
        raise pueue.PueueError("acknowledgement lost")

    monkeypatch.setattr(pueue, "add", uncertain)
    with pytest.raises(launch.EnqueueUncertain):
        launch.start_operation(
            config, project, project.operation("verify"), owner_request_key="accepted"
        )
    recovered = launch.start_operation(
        config, project, project.operation("verify"), owner_request_key="accepted"
    )
    assert recovered["reused"] and recovered["job_id"] == 1
    assert len(fake_pueue.added) == 1


def test_cancel_attempt_guard_rejects_a_newer_retry_before_mutating_queue(
    config: Config,
    fake_pueue: FakePueue,
    project_root: Path,
    monkeypatch,
):
    monkeypatch.setattr(pueue, "status", lambda: pueue.Status(fake_pueue.tasks(), {}))
    job, document = execute(config, fake_pueue, project_root)
    assert launch.get_job(job["job_id"], config)["attempt"] == 0
    assert launch.snapshot_jobs(10, config)["jobs"][0]["attempt"] == 0
    assert run.run(document, launch_input="fixture-input") == 0
    assert launch.snapshot_jobs(10, config)["jobs"][0]["attempt"] == 1
    with pytest.raises(launch.JobError, match="attempt changed"):
        launch.cancel(
            config, job["job_id"], reference=job["reference"], expected_attempt=0
        )
    assert not fake_pueue.killed and not fake_pueue.removed
    fake_pueue.queue(job["job_id"])
    cancelled = launch.cancel(
        config, job["job_id"], reference=job["reference"], expected_attempt=1
    )
    assert cancelled["state"] == "removed"
    assert launch.result(config, job["job_id"], job["reference"])["attempt"] == 1


def test_interrupted_legacy_migration_resumes_without_overwriting_remaining_files(
    config: Config,
    fake_pueue: FakePueue,
    project_root: Path,
    monkeypatch,
):
    job, document = execute(config, fake_pueue, project_root, stdout='{"new": true}')
    log = Path(document["log_path"])
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("legacy diagnostics")
    result_path = Path(document["result_path"])
    result_path.write_text('{"legacy":true}')
    original = Path.replace

    def interrupted(path, target):
        if path == result_path:
            raise KeyboardInterrupt
        return original(path, target)

    monkeypatch.setattr(Path, "replace", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run.run(document, launch_input="fixture-input")
    monkeypatch.setattr(Path, "replace", original)
    assert result_path.read_text() == '{"legacy":true}'
    assert run.run(document, launch_input="fixture-input") == 0
    first = launch.result(config, job["job_id"], attempt=1)
    assert first["value"] == {"legacy": True}
    assert launch.logs(config, job["job_id"], attempt=1) == "legacy diagnostics"
    assert launch.result(config, job["job_id"])["attempt"] == 2


def test_legacy_queue_entry_without_input_keeps_conventional_artifact_reads(
    config: Config,
    fake_pueue: FakePueue,
    project_root: Path,
):
    reference = "legacy-retained"
    input_path = config.jobs_dir / f"{reference}.json"
    task_id = fake_pueue.add(
        group="normal",
        label="fixture:legacy",
        command=("agentctl-run", str(input_path)),
        working_directory=project_root,
    )
    config.jobs_dir.mkdir(parents=True, exist_ok=True)
    log = config.jobs_dir / f"{reference}.log"
    log.write_text("retained legacy diagnostics")
    (config.jobs_dir / f"{reference}.result").write_text('{"legacy":true}')
    run.outcome_path_for(log).write_text('{"outcome":"success","exit_code":0}')
    assert not input_path.exists()

    page = launch.read_job_artifact(config, task_id, artifact="log", limit=8)
    assert page["available"] and page["text"] == "retained"
    assert page["attempt"] == 1 and page["next_offset"] == 8
    detail = launch.get_job(task_id, config, reference, attempt=page["attempt"])
    assert detail["artifacts"]["log"] == str(log)
    assert detail["outcome"]["outcome"] == "success"
    remainder = launch.read_job_artifact(
        config,
        task_id,
        reference,
        attempt=page["attempt"],
        offset=8,
    )
    assert page["text"] + remainder["text"] == log.read_text()
    result = launch.result(config, task_id, reference, attempt=page["attempt"])
    assert result["value"] == {"legacy": True}
