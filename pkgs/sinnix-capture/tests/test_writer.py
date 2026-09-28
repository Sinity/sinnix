import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sinnix_capture.envelope import SCHEMA, SCHEMA_VERSION, build_envelope
from sinnix_capture.writer import HW_WIDTH, CaptureWriter
from sinnix_lib import ledger
from sinnix_lib.atomic import atomic_publish


def test_write_produces_envelope_and_daily_file(tmp_path: Path) -> None:
    writer = CaptureWriter(tmp_path, "test-lane", host="fixture-host")
    ts = 1_700_000_000.0
    envelope = writer.write({"k": "v"}, ts=ts)

    assert envelope["schema"] == SCHEMA
    assert envelope["schema_version"] == SCHEMA_VERSION
    assert envelope["lane"] == "test-lane"
    assert envelope["host"] == "fixture-host"
    assert envelope["seq"] == 1
    assert envelope["payload"] == {"k": "v"}
    assert envelope["raw_ref"] is None

    day = time.strftime("%Y%m%d", time.gmtime(ts))
    record_path = tmp_path / "test-lane" / f"test-lane-{day}.jsonl"
    assert record_path.exists()
    lines = record_path.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == envelope


def test_seq_is_monotonic_and_persisted_across_instances(tmp_path: Path) -> None:
    first = CaptureWriter(tmp_path, "lane-a")
    e1 = first.write({"n": 1})
    e2 = first.write({"n": 2})
    assert (e1["seq"], e2["seq"]) == (1, 2)
    assert (tmp_path / "lane-a" / "lane-a.seq").stat().st_mode & 0o777 == 0o600

    second = CaptureWriter(tmp_path, "lane-a")
    e3 = second.write({"n": 3})
    assert e3["seq"] == 3


def test_rotation_splits_by_day(tmp_path: Path) -> None:
    writer = CaptureWriter(tmp_path, "lane-b")
    writer.write({"n": 1}, ts=1_700_000_000.0)
    writer.write({"n": 2}, ts=1_700_000_000.0 + 86400)

    lane_dir = tmp_path / "lane-b"
    day_files = sorted(p.name for p in lane_dir.glob("lane-b-2*.jsonl"))
    assert len(day_files) == 2


def test_index_sidecar_has_one_entry_per_write(tmp_path: Path) -> None:
    writer = CaptureWriter(tmp_path, "lane-c")
    for i in range(5):
        writer.write({"n": i}, ts=1_700_000_000.0 + i)

    index_path = tmp_path / "lane-c" / "lane-c-index.jsonl"
    entries = [json.loads(line) for line in index_path.read_text().splitlines()]
    assert [e["seq"] for e in entries] == [1, 2, 3, 4, 5]
    assert all("file" in e and "ts" in e for e in entries)


def test_raw_ref_is_preserved(tmp_path: Path) -> None:
    writer = CaptureWriter(tmp_path, "lane-d")
    envelope = writer.write({"n": 1}, raw_ref="/realm/activity/lane-d/raw/1.bin")
    assert envelope["raw_ref"] == "/realm/activity/lane-d/raw/1.bin"


def test_empty_seq_file_recovers_from_index_without_reusing_numbers(
    tmp_path: Path,
) -> None:
    # Reproduces the 2026-08-16 lane bricking: a process killed between
    # truncating and writing the counter leaves it zero-byte, and every
    # later write died on int(''), which Restart=on-failure escalated into
    # a start-limit-hit that never started again.
    writer = CaptureWriter(tmp_path, "lane-r")
    for i in range(3):
        writer.write({"n": i})
    (tmp_path / "lane-r" / "lane-r.seq").write_text("")

    recovered = CaptureWriter(tmp_path, "lane-r").write({"n": "after"})

    # 4, not 1: restarting the sequence would hand out numbers already on
    # disk, which downstream cannot tell apart from a replayed record.
    assert recovered["seq"] == 4
    index_path = tmp_path / "lane-r" / "lane-r-index.jsonl"
    seqs = [json.loads(line)["seq"] for line in index_path.read_text().splitlines()]
    assert seqs == [1, 2, 3, 4]
    assert len(seqs) == len(set(seqs))


def test_unparsable_seq_file_recovers_from_index(tmp_path: Path) -> None:
    writer = CaptureWriter(tmp_path, "lane-s")
    writer.write({"n": 1})
    writer.write({"n": 2})
    (tmp_path / "lane-s" / "lane-s.seq").write_text("not a number")

    assert CaptureWriter(tmp_path, "lane-s").write({"n": 3})["seq"] == 3


def _checkpoints(path: Path) -> list[tuple[int, float]]:
    data = path.with_name(path.name + ".hw").read_bytes()
    assert len(data) % HW_WIDTH == 0
    rows = [data[i : i + HW_WIDTH].split() for i in range(0, len(data), HW_WIDTH)]
    return [(int(offset), float(high)) for offset, high in rows]


def test_high_water_sidecar_stays_monotonic_over_unordered_ts(tmp_path: Path) -> None:
    """Fails if a late record's ts can sit behind a checkpoint below it."""
    writer = CaptureWriter(tmp_path, "lane", host="h")
    base = 1_700_000_000.0
    for offset in (10.0, 50.0, 20.0, 60.0, 5.0):
        writer.write({"n": offset}, ts=base + offset)
    day = time.strftime("%Y%m%d", time.gmtime(base))
    path = tmp_path / "lane" / f"lane-{day}.jsonl"
    checkpoints = _checkpoints(path)
    assert [high - base for _, high in checkpoints] == [10.0, 50.0, 50.0, 60.0, 60.0]
    ends = [offset for offset, _ in checkpoints]
    assert ends[-1] == path.stat().st_size
    lines = path.read_bytes().splitlines(keepends=True)
    assert ends == [sum(map(len, lines[: i + 1])) for i in range(len(lines))]


def test_high_water_folds_a_record_that_missed_its_checkpoint(tmp_path: Path) -> None:
    """Fails if a crash between the two appends hides a record's ts."""
    writer = CaptureWriter(tmp_path, "lane", host="h")
    base = 1_700_000_000.0
    writer.write({}, ts=base + 1)
    day = time.strftime("%Y%m%d", time.gmtime(base))
    path = tmp_path / "lane" / f"lane-{day}.jsonl"
    with path.open("a") as handle:
        handle.write(json.dumps({"ts": base + 500, "seq": 99}) + "\n")
    writer.write({}, ts=base + 2)
    assert _checkpoints(path)[-1][1] == base + 500


def test_daily_file_that_predates_its_sidecar_stays_unindexed(tmp_path: Path) -> None:
    """Fails if an index starting mid-file claims a prefix it never saw."""
    base = 1_700_000_000.0
    day = time.strftime("%Y%m%d", time.gmtime(base))
    lane_dir = tmp_path / "lane"
    lane_dir.mkdir()
    path = lane_dir / f"lane-{day}.jsonl"
    path.write_text(json.dumps({"ts": base + 900, "seq": 1}) + "\n")
    CaptureWriter(tmp_path, "lane", host="h").write({}, ts=base + 1)
    assert not path.with_name(path.name + ".hw").exists()
    assert len(path.read_text().splitlines()) == 2


def test_payload_failure_keeps_allocated_sequence_and_index_behind(
    tmp_path: Path, monkeypatch
) -> None:
    writer = CaptureWriter(tmp_path, "lane-f")
    original = ledger.append_jsonl

    def fail_payload(path, record, **kwargs):
        if Path(path).name.startswith("lane-f-2"):
            raise OSError("synthetic payload failure")
        return original(path, record, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(ledger, "append_jsonl", fail_payload)
        with pytest.raises(OSError, match="payload failure"):
            writer.write({"n": 1}, ts=1_700_000_000.0)
    assert (tmp_path / "lane-f" / "lane-f.seq").read_text() == "1\n"
    assert not writer._index_path.exists()
    assert (
        CaptureWriter(tmp_path, "lane-f").write({"n": 2}, ts=1_700_000_001.0)["seq"]
        == 2
    )


def test_index_failure_recovers_retained_payload_before_retry(
    tmp_path: Path, monkeypatch
) -> None:
    writer = CaptureWriter(tmp_path, "lane-i")
    original = ledger.append_jsonl

    def fail_index(path, record, **kwargs):
        if Path(path) == writer._index_path:
            raise OSError("synthetic index failure")
        return original(path, record, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(ledger, "append_jsonl", fail_index)
        with pytest.raises(OSError, match="index failure"):
            writer.write({"n": 1}, ts=1_700_000_000.0)
    second = CaptureWriter(tmp_path, "lane-i").write({"n": 2}, ts=1_700_000_001.0)
    assert second["seq"] == 2
    assert [entry["seq"] for entry in ledger.iter_jsonl(writer._index_path)] == [1, 2]
    payloads = list(ledger.iter_jsonl(writer._record_path(1_700_000_000.0)))
    assert [record["payload"]["n"] for record in payloads] == [1, 2]


def test_recovery_refuses_malformed_complete_payload(tmp_path: Path) -> None:
    writer = CaptureWriter(tmp_path, "lane-bad")
    writer._seq_path.write_text("1")
    writer._record_path(1_700_000_000.0).write_bytes(b"not json\n")
    with pytest.raises(ValueError):
        writer.write({"n": 2})
    assert not writer._index_path.exists()  # No index claims the bad payload.


def test_counter_sync_failure_does_not_reuse_visible_allocation(
    tmp_path: Path, monkeypatch
) -> None:
    writer = CaptureWriter(tmp_path, "lane-counter")
    writer.write({"n": 1})
    real_fsync = os.fsync
    failed = False

    def fail_once(fd):
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("synthetic counter sync failure")
        return real_fsync(fd)

    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", fail_once)
        with pytest.raises(OSError, match="counter sync failure"):
            writer.write({"n": 2})
    assert failed  # The allocation reached the injected sync boundary.
    assert CaptureWriter(tmp_path, "lane-counter").write({"n": 3})["seq"] == 3
    assert [row["seq"] for row in ledger.iter_jsonl(writer._index_path)] == [1, 3]


def test_two_instances_share_lane_order_without_blocking_another_lane(
    tmp_path: Path,
) -> None:
    first = CaptureWriter(tmp_path, "same")
    second = CaptureWriter(tmp_path, "same")
    other = CaptureWriter(tmp_path, "other")
    jobs = [(first, n) if n % 2 else (second, n) for n in range(1, 11)]
    jobs.append((other, 100))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda job: job[0].write({"n": job[1]}), jobs))
    assert sorted(row["seq"] for row in results[:-1]) == list(range(1, 11))
    assert [row["seq"] for row in ledger.iter_jsonl(first._index_path)] == list(
        range(1, 11)
    )
    assert results[-1]["seq"] == 1  # The other lane has its own allocation.


def test_bounded_writer_cost_fixture_reports_old_and_new_protocol(
    tmp_path: Path, monkeypatch
) -> None:
    # Ten deterministic envelopes make a steady-state counter sync reduction
    # observable without relying on host writeback timing or a live lane.
    corpus = [{"n": n, "body": "x" * 40} for n in range(10)]
    ts = 1_700_000_000.0
    real_fsync = os.fsync
    syncs = 0
    synced_sizes = 0
    sync_ns = 0

    def measured_fsync(fd):
        nonlocal syncs, synced_sizes, sync_ns
        syncs += 1
        synced_sizes += os.fstat(fd).st_size
        begin = time.perf_counter_ns()
        try:
            return real_fsync(fd)
        finally:
            sync_ns += time.perf_counter_ns() - begin

    monkeypatch.setattr(os, "fsync", measured_fsync)

    def run(label: str, old: bool):
        nonlocal syncs, synced_sizes, sync_ns
        root = tmp_path / label
        writer = CaptureWriter(root, "lane", host="fixture-host")
        begin_syncs, begin_bytes, begin_sync_ns = syncs, synced_sizes, sync_ns
        begin = time.perf_counter_ns()
        for n, payload in enumerate(corpus, 1):
            if old:
                # Previous counter protocol with the same high-water work
                # as the merged writer, so only sequence cost differs.
                atomic_publish(
                    writer._seq_path, str(n).encode(), fsync=True, mode=0o600
                )
                record = build_envelope(
                    lane="lane",
                    ts=ts + n,
                    host="fixture-host",
                    seq=n,
                    payload=payload,
                    raw_ref=None,
                )
                path = writer._record_path(ts + n)
                writer._append_with_high_water(path, record, ts + n)
                ledger.append_jsonl(
                    writer._index_path,
                    {"ts": ts + n, "seq": n, "file": path.name},
                    fsync=True,
                )
            else:
                writer.write(payload, ts=ts + n)
        elapsed = time.perf_counter_ns() - begin
        index_bytes = writer._index_path.stat().st_size
        rows = list(ledger.iter_jsonl(writer._record_path(ts + 1)))
        assert [row["payload"] for row in rows] == corpus
        logical_bytes = sum(
            path.stat().st_size
            for path in writer.lane_dir.iterdir()
            if path.is_file() and path.suffix in {".seq", ".jsonl"}
        )
        return (
            syncs - begin_syncs,
            synced_sizes - begin_bytes,
            sync_ns - begin_sync_ns,
            elapsed,
            index_bytes,
            logical_bytes,
        )

    before = run("before", True)
    after = run("after", False)
    print(
        f"fixture=10 fixed events; host_pressure=not measured; old={before}; new={after}; fields=(syncs,synced_size_sum,sync_latency_ns,append_latency_ns,index_bytes,logical_bytes); divide by 10 for per_event"
    )
    assert before[0] == 50  # Four prior syncs plus the high-water checkpoint.
    assert after[0] == 41  # First counter publication costs two, then one.
    assert after[4] == before[4]
