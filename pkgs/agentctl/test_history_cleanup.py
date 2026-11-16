"""Queue cleanup removes terminal entries and keeps each job's retained bytes."""

from pathlib import Path

from agentctl import job_queries, launch
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


def test_terminal_cleanup_releases_queue_only_preserving_raw_outputs(
    fake_pueue, config, project_root
):
    task, log, result = completed(fake_pueue, config, project_root)
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


def test_hourly_cleanup_keeps_recent_ids_and_tasks_without_a_known_finish(
    fake_pueue, config, project_root
):
    from dataclasses import replace
    from datetime import UTC, datetime

    old, _, _ = completed(fake_pueue, config, project_root)
    recent, _, _ = completed(fake_pueue, config, project_root)
    boundary, _, _ = completed(fake_pueue, config, project_root)
    unknown, _, _ = completed(fake_pueue, config, project_root)
    running, _, _ = completed(fake_pueue, config, project_root)
    for task, stamp in [
        (old, "2026-11-15T11:59:59+00:00"),
        (recent, "2026-11-16T11:00:00+00:00"),
        (boundary, "2026-11-15T12:00:00+00:00"),
        (unknown, None),
    ]:
        fake_pueue._tasks[task.task_id] = replace(task, ended_at=stamp)
    fake_pueue.running(running.task_id)
    now = datetime(2026, 11, 16, 12, tzinfo=UTC)

    removed = launch.clean_terminal(config, now=now)

    assert [row["task_id"] for row in removed] == [old.task_id]
    assert set(fake_pueue._tasks) == {
        recent.task_id,
        boundary.task_id,
        unknown.task_id,
        running.task_id,
    }
    assert (
        job_queries.get_job(recent.task_id, config, job_queries.job_id_of(recent))[
            "task_id"
        ]
        == recent.task_id
    )
    project = load_project_adapter(project_root)
    next_job = launch.start_operation(config, project, project.operation("verify"))
    assert next_job["task_id"] > running.task_id
