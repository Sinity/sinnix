import json
import time
from pathlib import Path

from sinnix_capture.envelope import SCHEMA, SCHEMA_VERSION
from sinnix_capture.writer import CaptureWriter


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
    envelope = writer.write({"n": 1}, raw_ref="/realm/data/captures/lane-d/raw/1.bin")
    assert envelope["raw_ref"] == "/realm/data/captures/lane-d/raw/1.bin"
