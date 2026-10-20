"""Native cleanup retains exact historical job evidence without a controller."""

import json
from pathlib import Path

import pytest
from agentctl import batch_history, job_queries, launch
from agentctl.projects import load_project_adapter
from conftest import read_launch


def completed(fake, config, root):
    project = load_project_adapter(root)
    started = launch.start_operation(config, project, project.operation("verify"))
    task = fake.task(started["task_id"])
    written = read_launch(config, task)
    log = Path(written["log_path"])
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("original output\n")
    result = Path(written["result_path"])
    result.write_bytes(b'{"original": 9223372036854775807}')
    fake.succeed(task.task_id)
    return task, log, result


def original_run(
    config, task, *, terminal=None, legacy=False, landing=None, worktree=None
):
    run_id = "fixture-20260101-000000-abcdef01"
    worker = {
        "id": "worker",
        "beads": ["fixture-1"],
        "task_id": task.task_id,
        "worktree": str(worktree) if worktree else None,
    }
    if not legacy:
        worker["job_id"] = job_queries.job_id_of(task)
    document = {
        "run_id": run_id,
        "project": "fixture",
        "created_at": "2026-01-01T00:00:00Z",
        "base_commit": "a" * 40,
        "harness": "queued",
        "workers": [worker],
        "landing": landing or {},
    }
    if terminal:
        document[terminal] = {"at": "fixture"}
    path = batch_history.manifest_path(config, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document))
    return path


@pytest.mark.parametrize("legacy", [False, True])
def test_live_history_keeps_original_worker_outputs(
    fake_pueue, config, project_root, legacy
):
    task, log, result = completed(fake_pueue, config, project_root)
    original_run(config, task, legacy=legacy)
    other, _, _ = completed(fake_pueue, config, project_root)
    before = (log.read_bytes(), result.read_bytes())
    cleaned = launch.clean_terminal(config)
    assert [row["task_id"] for row in cleaned] == [other.task_id]
    assert fake_pueue.task(task.task_id) is not None
    assert (log.read_bytes(), result.read_bytes()) == before


@pytest.mark.parametrize("terminal", ["acceptance", "abandoned"])
def test_terminal_history_releases_queue_only_preserving_raw_outputs(
    fake_pueue, config, project_root, terminal
):
    task, log, result = completed(fake_pueue, config, project_root)
    original_run(config, task, terminal=terminal)
    input_path = job_queries.launch_input_path(task)
    before = (input_path.read_bytes(), log.read_bytes(), result.read_bytes())
    cleaned = launch.clean_terminal(config)
    assert [row["task_id"] for row in cleaned] == [task.task_id]
    assert fake_pueue.task(task.task_id) is None
    assert (input_path.read_bytes(), log.read_bytes(), result.read_bytes()) == before
    assert (
        job_queries.logs(config, task.task_id, job_id=job_queries.job_id_of(task))
        == "original output\n"
    )


@pytest.mark.parametrize("reference", ["job_id", "worktree", "verification"])
def test_native_history_protection_uses_exact_native_reference(
    fake_pueue, config, project_root, reference
):
    task, _, _ = completed(fake_pueue, config, project_root)
    if reference == "job_id":
        original_run(config, task)
        other, _, _ = completed(fake_pueue, config, project_root)
        fake_pueue.queue(task.task_id)
        fake_pueue.queue(other.task_id)
        fake_pueue.switch(task.task_id, other.task_id)
        fake_pueue.succeed(task.task_id)
        fake_pueue.succeed(other.task_id)
        cleaned = launch.clean_terminal(config)
        assert [row["task_id"] for row in cleaned] == [task.task_id]
        assert job_queries.job_id_of(
            fake_pueue.task(other.task_id)
        ) == job_queries.job_id_of(task)
    else:
        # No direct worker task identity; protect a native check by its checkout or recorded receipt.
        path = original_run(
            config,
            task,
            worktree=project_root if reference == "worktree" else None,
            landing={
                "verify_run": {
                    "task_id": task.task_id,
                    "job_id": job_queries.job_id_of(task),
                }
            }
            if reference == "verification"
            else None,
        )
        document = json.loads(path.read_text())
        document["workers"][0].pop("task_id")
        document["workers"][0].pop("job_id")
        path.write_text(json.dumps(document))
        assert launch.clean_terminal(config) == []
        assert fake_pueue.task(task.task_id) is not None


@pytest.mark.parametrize(
    "failure", ["corrupt", "partial", "directory_unavailable", "record_unavailable"]
)
def test_native_bulk_cleanup_needs_complete_history(
    fake_pueue, config, project_root, monkeypatch, failure
):
    task, log, result = completed(fake_pueue, config, project_root)
    path = original_run(config, task)
    before = (log.read_bytes(), result.read_bytes())
    if failure in {"corrupt", "partial"}:
        path.write_text("{" if failure == "corrupt" else '{"run_id":"fixture"}')
    elif failure == "directory_unavailable":
        original = Path.iterdir

        def denied(directory):
            if directory == path.parent:
                raise PermissionError("synthetic unavailable inventory")
            return original(directory)

        monkeypatch.setattr(Path, "iterdir", denied)
    else:
        original = Path.read_text

        def denied(record, *args, **kwargs):
            if record == path:
                raise PermissionError("synthetic unavailable record")
            return original(record, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", denied)
    with pytest.raises(batch_history.HistoryError):
        launch.clean_terminal(config)
    assert fake_pueue.removed == []
    assert (log.read_bytes(), result.read_bytes()) == before
