"""wait.for conditions and events.tail paging over real and recorded owners."""

from __future__ import annotations

from pathlib import Path

import pytest
from sinnix_agent_gateway.actions.waits import WaitInput
from test_actions_jobs import DONE, RUNNING, call, make_server


def test_wait_for_job_terminal_uses_the_queue_wait(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, _, fake = make_server(tmp_path, "observer", monkeypatch)
    fake.responses["job.wait"] = DONE
    done = call(
        server,
        "wait.for",
        {
            "condition": {"kind": "job_terminal", "target": {"job_id": 41}},
            "timeout_seconds": 3,
        },
    )
    assert done["result"]["outcome"] == "ok", done
    data = done["data"]
    assert data["outcome"] == "satisfied" and data["ref"] == "sinnix://jobs/41"
    assert data["job"]["state"]["phase"] == "succeeded" and data["continuation"] is None
    assert fake.calls[-1].arguments == {"job_id": "41", "timeout_seconds": 3}

    fake.responses["job.wait"] = {**RUNNING, "timed_out": True}
    late = call(
        server,
        "wait.for",
        {
            "condition": {
                "kind": "job_terminal",
                "target": {"ref": "sinnix://jobs/41"},
            },
            "timeout_seconds": 1,
        },
    )["data"]
    assert late["outcome"] == "timeout" and late["timed_out"] is True
    assert late["continuation"] and late["job"]["state"]["phase"] == "running"


def test_wait_for_file_exists_polls_until_the_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, _, _ = make_server(tmp_path, "observer", monkeypatch)
    target = tmp_path / "out.txt"
    missing = call(
        server,
        "wait.for",
        {
            "condition": {"kind": "file_exists", "target": {"path": str(target)}},
            "timeout_seconds": 1,
            "poll_seconds": 0.05,
        },
    )["data"]
    assert missing["outcome"] == "timeout" and missing["polls"] >= 1
    assert missing["evidence"] == {"path": str(target), "exists": False}
    assert missing["continuation"] and missing["affordances"] == ["wait.for"]

    target.write_text("x")
    present = call(
        server,
        "wait.for",
        {
            "condition": {"kind": "file_exists", "target": {"path": str(target)}},
            "timeout_seconds": 1,
        },
    )["data"]
    assert present["outcome"] == "satisfied" and present["polls"] == 0
    gone = call(
        server,
        "wait.for",
        {
            "condition": {
                "kind": "file_exists",
                "target": {"path": str(target)},
                "exists": False,
            },
            "timeout_seconds": 1,
            "poll_seconds": 0.05,
        },
    )["data"]
    assert gone["outcome"] == "timeout"


def test_wait_for_file_hash_and_receipt_use_the_runtime_resolver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, _, _ = make_server(tmp_path, "operator", monkeypatch)
    target = tmp_path / "hashed.txt"
    target.write_text("hello\n")
    digest = "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03"
    hashed = call(
        server,
        "wait.for",
        {
            "condition": {
                "kind": "file_hash",
                "target": {"path": str(target)},
                "sha256": digest,
            },
            "timeout_seconds": 1,
        },
    )["data"]
    assert hashed["outcome"] == "satisfied" and hashed["source_revision"] == digest

    receipt = call(
        server,
        "wait.for",
        {
            "condition": {"kind": "receipt_appearance", "receipt_id": "never"},
            "timeout_seconds": 1,
            "poll_seconds": 0.05,
        },
    )["data"]
    assert receipt["outcome"] == "timeout" and receipt["evidence"]["available"] is False


def test_wait_condition_union_rejects_mixed_fields() -> None:
    with pytest.raises(ValueError):
        WaitInput.model_validate(
            {"condition": {"kind": "file_hash", "target": {"path": "/x"}}}
        )
    with pytest.raises(ValueError):
        WaitInput.model_validate({"condition": {"kind": "nope"}})


def test_events_tail_pages_with_a_scope_bound_cursor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, _, fake = make_server(tmp_path, "observer", monkeypatch, with_git=True)
    fake.responses["job.list"] = {
        "jobs": [RUNNING],
        "total": 1,
        "truncated": False,
        "next_cursor": None,
        "snapshot": {"ordering": "created_at_desc_job_id_desc", "ceiling": ["x", "41"]},
    }
    first = call(
        server, "events.tail", {"limit": 50, "projects": [{"project": "fixture"}]}
    )
    assert first["result"]["outcome"] == "ok", first
    data = first["data"]
    assert data["project_refs"] == ["sinnix://projects/fixture"]
    assert data["next_cursor"] and "gateway.audit" in data["sources"]
    kinds = {event["kind"] for event in data["events"]}
    assert "job_state" in kinds

    second = call(
        server,
        "events.tail",
        {"cursor": data["next_cursor"], "projects": [{"project": "fixture"}]},
    )["data"]
    assert "job_state" not in {event["kind"] for event in second["events"]}

    tampered = data["next_cursor"][:-4] + "0000"
    stale = call(
        server,
        "events.tail",
        {"cursor": tampered, "projects": [{"project": "fixture"}]},
    )
    assert stale["error"]["code"] == "stale_cursor"
