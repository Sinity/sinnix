"""Compaction preserves unverified evidence and serializes with real appenders."""

import hashlib
import json
import os
import threading

import pytest
from agentctl import event_compaction
from agentctl.run import append_event


def fixture_log(tmp_path):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    outcome = {
        "attempt": 1,
        "outcome": "succeeded",
        "exit_code": 0,
        "execution_receipt": {"inventory": ["synthetic"] * 100},
    }
    payload = json.dumps(outcome, sort_keys=True).encode()
    path = jobs / "fixture.outcome"
    path.write_bytes(payload)
    event = {
        "kind": "queue-task",
        "phase": "finished",
        "job_id": "fixture",
        "label": "fixture:check",
        **outcome,
    }
    raw = json.dumps(event).encode() + b"\n"
    spool = tmp_path / "events.jsonl"
    spool.write_bytes(raw)
    return spool, jobs, path, event, raw


def test_verified_compaction_preserves_mismatches_and_invalid_records(tmp_path):
    spool, jobs, path, event, raw = fixture_log(tmp_path)
    mismatch = {**event, "exit_code": 9}
    missing = {**event, "job_id": "missing"}
    kept = [
        json.dumps(mismatch).encode() + b"\n",
        json.dumps(missing).encode() + b"\n",
        b"not json\n",
        b"\xff\n",
        b"[]\n",
        b'{"kind":"pressure"}\n',
    ]
    spool.write_bytes(raw + b"".join(kept))
    spool.chmod(0o640)
    snapshot = tmp_path / "events.jsonl.snapshot"
    snapshot.write_bytes(b"keeper")
    old_inode = spool.stat().st_ino
    with spool.open("rb") as follower:
        summary = event_compaction.compact_events(spool, jobs)
        assert follower.read() == raw + b"".join(kept)
    lines = spool.read_bytes().splitlines(keepends=True)
    rewritten = json.loads(lines[0])
    assert "execution_receipt" not in rewritten
    assert rewritten["exit_code"] == 0 and rewritten["label"] == "fixture:check"
    assert rewritten["outcome_ref"] == {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    assert lines[1:] == kept
    assert summary == {
        "bytes_before": len(raw + b"".join(kept)),
        "bytes_after": spool.stat().st_size,
        "events_rewritten": 1,
        "events_kept": 6,
        "receipts_unresolved": 2,
    }
    assert summary["bytes_after"] < summary["bytes_before"]
    assert spool.stat().st_ino != old_inode
    assert spool.stat().st_mode & 0o777 == 0o640
    assert snapshot.read_bytes() == b"keeper"
    assert event_compaction.compact_events(spool, jobs)["events_rewritten"] == 0


def test_append_waits_through_verification_and_rename(tmp_path, monkeypatch):
    spool, jobs, _, _, _ = fixture_log(tmp_path)
    real_rewrite = event_compaction._rewrite
    writer = None
    calls = 0

    def observed(raw, root):
        nonlocal writer, calls
        calls += 1
        if calls == 2:  # verification, after the candidate was fsynced
            writer = threading.Thread(
                target=append_event, args=(spool, {"kind": "after"})
            )
            writer.start()
            writer.join(timeout=0.2)
            assert writer.is_alive()
        return real_rewrite(raw, root)

    monkeypatch.setattr(event_compaction, "_rewrite", observed)
    result = event_compaction.compact_events(spool, jobs)
    assert writer is not None
    writer.join(timeout=5)
    assert not writer.is_alive()
    assert result["events_rewritten"] == 1
    assert [json.loads(raw)["kind"] for raw in spool.read_bytes().splitlines()] == [
        "queue-task",
        "after",
    ]


@pytest.mark.parametrize("failure", ["tail", "missing_outcome", "fsync", "line_count"])
def test_failure_retains_original_and_removes_temporary(tmp_path, monkeypatch, failure):
    spool, jobs, path, _, raw = fixture_log(tmp_path)
    if failure == "tail":
        spool.write_bytes(raw + b'{"torn":')
    elif failure == "missing_outcome":
        real_rewrite = event_compaction._rewrite

        def remove_after_rewrite(raw, root):
            result = real_rewrite(raw, root)
            path.unlink(missing_ok=True)
            return result

        monkeypatch.setattr(event_compaction, "_rewrite", remove_after_rewrite)
    elif failure == "fsync":

        def fail(_fd):
            raise OSError("synthetic fsync failure")

        monkeypatch.setattr(os, "fsync", fail)
    else:
        real_fsync = os.fsync

        def truncate(fd):
            os.ftruncate(fd, 0)
            real_fsync(fd)

        monkeypatch.setattr(os, "fsync", truncate)
    original = spool.read_bytes()
    inode = spool.stat().st_ino
    with pytest.raises(event_compaction.CompactionError):
        event_compaction.compact_events(spool, jobs)
    assert spool.read_bytes() == original
    assert spool.stat().st_ino == inode
    assert not list(tmp_path.glob(".events.jsonl.compact-*"))


def test_canonical_attempt_wins_over_latest_alias(tmp_path):
    spool, jobs, path, _, _ = fixture_log(tmp_path)
    canonical = jobs / "fixture.attempts" / "1" / "output.outcome"
    canonical.parent.mkdir(parents=True)
    path.rename(canonical)
    path.write_text('{"attempt":2}')
    event_compaction.compact_events(spool, jobs)
    assert json.loads(spool.read_bytes())["outcome_ref"]["path"] == str(canonical)
