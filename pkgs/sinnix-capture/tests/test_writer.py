import json
import time
from pathlib import Path

from sinnix_capture.envelope import SCHEMA, SCHEMA_VERSION
from sinnix_capture.writer import HW_WIDTH, CaptureWriter


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
