"""Queue ordering and masked byte pages shared by the CLI and gateway."""

from __future__ import annotations

import base64
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from agentctl import artifacts, job_queries, pueue
from agentctl.config import Config


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return Config(
        project_roots=(),
        event_spool=tmp_path / "events.jsonl",
        state_dir=tmp_path / "state",
        agentctl_executable="agentctl",
    )


def task(
    config, number, *, status="Queued", group="normal", priority=0, dependencies=()
):
    name = f"fixture-job-{number}"
    config.inputs_dir.mkdir(parents=True, exist_ok=True)
    path = config.inputs_dir / f"{name}.json"
    path.write_text(
        json.dumps(
            {
                "job_id": name,
                "queue_task_id": number,
                "project_root": f"/fixture/project-{number}",
                "working_directory": f"/fixture/project-{number}",
                "pool": group,
                "log_path": str(config.jobs_dir / f"{name}.log"),
                "result_path": str(config.jobs_dir / f"{name}.result"),
            }
        )
    )
    return pueue.Task(
        task_id=number,
        label=f"fixture-{number}:check",
        group=group,
        status=status,
        result="Success" if status == "Done" else None,
        exit_code=0 if status == "Done" else None,
        path=f"/fixture/project-{number}",
        dependencies=dependencies,
        command=f"agentctl-run {path}",
        enqueued_at="2026-01-01T00:00:00+00:00",
        started_at="2026-01-01T00:00:00+00:00" if status == "Running" else None,
        priority=priority,
    )


def test_queue_orders_by_priority_and_reports_running_jobs(config, monkeypatch):
    ended = task(config, 1, status="Done")
    running = task(config, 2, status="Running")
    first = task(config, 3)
    urgent = task(config, 4, priority=50)
    current = pueue.Status(
        {entry.task_id: entry for entry in (ended, running, first, urgent)},
        {"normal": {"status": "Running", "parallel_tasks": 1}},
    )
    monkeypatch.setattr(pueue, "live", lambda: current)
    answer = job_queries.job_queue(
        config, job_queries.job_view(first), now=datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
    )
    assert answer["position"] == 2 and answer["ahead"] == [4]
    assert answer["reason"] == "pool-full"
    assert [row["task_id"] for row in answer["occupied_by"]] == [2]
    assert [row["priority"] for row in answer["queued"]] == [50, 0]
    assert answer["occupied_by"][0]["working_directory"] == "/fixture/project-2"
    assert answer["oldest_queued_seconds"] == 60
    assert (
        job_queries.job_queue(config, job_queries.job_view(running))["reason"]
        == "running"
    )
    assert job_queries.job_queue(config, job_queries.job_view(ended)) is None
    missing = job_queries.queue_state(config, ["absent"])["absent"]
    assert missing["known"] is False and missing["running"] == []


def test_queue_reports_dependencies_pauses_and_available_slots(config, monkeypatch):
    dependency = task(config, 1, status="Running", group="bulk")
    blocked = task(config, 2, dependencies=(1,), priority=100)
    ready = task(config, 3)
    current = pueue.Status(
        {entry.task_id: entry for entry in (dependency, blocked, ready)},
        {"normal": {"status": "Running", "parallel_tasks": 1}},
    )
    monkeypatch.setattr(pueue, "live", lambda: current)
    answer = job_queries.job_queue(config, job_queries.job_view(blocked))
    assert answer["reason"] == "dependencies" and answer["waiting_for"] == [1]
    assert (
        job_queries.job_queue(config, job_queries.job_view(ready))["reason"] == "ready"
    )
    current.groups["normal"]["status"] = "Paused"
    assert (
        job_queries.job_queue(config, job_queries.job_view(ready))["reason"]
        == "group-paused"
    )
    current.groups["normal"]["status"] = "Running"
    current.tasks[3] = replace(ready, status="Paused")
    queued = task(config, 4)
    current.tasks[4] = queued
    answer = job_queries.job_queue(config, job_queries.job_view(queued))
    assert answer["reason"] == "pool-full"
    assert answer["occupied_by"][0]["phase"] == "paused"
    current.tasks[3] = replace(ready, status="Stashed")
    assert (
        job_queries.job_queue(config, job_queries.job_view(current.tasks[3]))["reason"]
        == "stashed"
    )


def test_queue_job_id_is_a_filter_without_searching_other_tasks(config, monkeypatch):
    first = task(config, 1)
    second = task(config, 2)
    current = pueue.Status(
        {1: second, 2: first},
        {"normal": {"status": "Running", "parallel_tasks": 1}},
    )
    monkeypatch.setattr(pueue, "live", lambda: current)
    answer = job_queries.job_queue(config, job_queries.job_view(first))
    assert answer["reason"] == "not-in-live-queue"
    assert answer["position"] is None and answer["occupied_by"] == []


def output(config, monkeypatch, *, content=b"", result=False):
    selected = task(config, 1, status="Running")
    document = job_queries.read_launch_input(config, selected)
    current = artifacts.begin(document, str(job_queries.launch_input_path(selected)))
    path = Path(current["result_path" if result else "log_path"])
    path.write_bytes(content)
    monkeypatch.setattr(pueue, "task", lambda number: selected if number == 1 else None)
    return selected, document, path


def test_byte_pages_mask_secrets_crossing_page_boundaries(config, monkeypatch):
    secret = "fixture-secret-value"
    monkeypatch.setenv("FIXTURE_API_KEY", secret)
    original = ("before " + secret + " after\n").encode()
    selected, _, _ = output(config, monkeypatch, content=original)
    split = original.index(secret.encode()) + 5
    first = job_queries.read_job_artifact(config, selected.task_id, limit=split)
    second = job_queries.read_job_artifact(
        config, selected.task_id, offset=first["next_offset"], limit=1000
    )
    joined = base64.b64decode(first["base64"]) + base64.b64decode(second["base64"])
    assert first["offset"] == 0 and second["offset"] == split
    assert first["returned_bytes"] == split
    assert second["next_offset"] is None
    assert len(joined) == len(original) and b"[REDACTED" in joined
    assert secret[:5].encode() not in joined and secret[5:].encode() not in joined
    assert first["text"].encode() + second["text"].encode() == joined


def test_result_pages_pin_the_attempt_and_preserve_all_bytes(config, monkeypatch):
    original = json.dumps({"message": "żółw" * 50}, ensure_ascii=False).encode()
    selected, document, _ = output(config, monkeypatch, content=original, result=True)
    first = job_queries.result(config, selected.task_id, limit=17)
    assert first["attempt"] == first["page"]["attempt"] == 1
    assert first["value"] is None and first["page"]["complete"] is False
    following = artifacts.begin(document, str(job_queries.launch_input_path(selected)))
    Path(following["result_path"]).write_text('{"next": true}')
    restored = bytearray()
    offset = 0
    while True:
        page = job_queries.read_job_artifact(
            config,
            selected.task_id,
            attempt=1,
            artifact="result",
            offset=offset,
            limit=17,
        )
        restored.extend(base64.b64decode(page["base64"]))
        if page["next_offset"] is None:
            break
        offset = page["next_offset"]
    assert bytes(restored) == original
    assert job_queries.result(config, selected.task_id)["value"] == {"next": True}
    assert job_queries.result(config, selected.task_id, attempt=1)[
        "value"
    ] == json.loads(original)


def test_result_page_uses_the_attempt_selected_before_a_retry_starts(
    config, monkeypatch
):
    selected = task(config, 1, status="Running")
    monkeypatch.setattr(pueue, "task", lambda number: selected)
    original_view = job_queries.artifact_view

    def start_after_view(config, current, attempt=None):
        view = original_view(config, current, attempt)
        if not view["attempts"]:
            document = job_queries.read_launch_input(config, current)
            started = artifacts.begin(
                document, str(job_queries.launch_input_path(current))
            )
            Path(started["result_path"]).write_text('{"started": true}')
        return view

    monkeypatch.setattr(job_queries, "artifact_view", start_after_view)
    before = job_queries.result(config, selected.task_id)
    assert before["attempt"] == before["page"]["attempt"] == 0
    assert before["page"]["available"] is False
    after = job_queries.result(config, selected.task_id)
    assert after["attempt"] == 1 and after["value"] == {"started": True}


@pytest.mark.parametrize(
    "arguments",
    [
        {"offset": -1},
        {"offset": True},
        {"limit": 0},
        {"limit": True},
        {"limit": 8_000_001},
        {"artifact": "other"},
    ],
)
def test_output_page_rejects_invalid_ranges(config, monkeypatch, arguments):
    selected, _, _ = output(config, monkeypatch, content=b"fixture")
    with pytest.raises(job_queries.JobError):
        job_queries.read_job_artifact(config, selected.task_id, **arguments)
