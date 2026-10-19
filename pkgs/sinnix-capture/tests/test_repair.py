import hashlib
import json
import os
import tracemalloc
from pathlib import Path

import pytest
from sinnix_capture.query import lane_delta
from sinnix_capture.repair import repair_index
from sinnix_capture.writer import CaptureWriter


def fixture_index(tmp_path):
    writer = CaptureWriter(tmp_path, "lane")
    for n in range(3):
        writer.write({"synthetic": n}, ts=100 + n)
    ordered = writer._index_path.read_bytes().splitlines(keepends=True)
    writer._index_path.write_bytes(ordered[2] + ordered[0] + ordered[1])
    return writer, ordered


def repair(tmp_path, writer, before):
    return repair_index(
        tmp_path,
        "lane",
        expected_sha256=hashlib.sha256(before).hexdigest(),
        expected_size=len(before),
    )


def test_repair_preserves_every_line_payload_counter_and_preimage(tmp_path):
    writer, ordered = fixture_index(tmp_path)
    before = writer._index_path.read_bytes()
    identity = writer._index_path.stat()
    payload = writer._record_path(100).read_bytes()
    counter = writer._seq_path.read_bytes()
    result = repair(tmp_path, writer, before)
    assert result["changed"] and result["records"] == 3
    assert writer._index_path.read_bytes() == b"".join(ordered)
    backup = Path(result["backup"])
    assert backup.read_bytes() == before and backup.stat().st_ino == identity.st_ino
    after = writer._index_path.stat()
    assert (after.st_mode, after.st_uid, after.st_gid) == (
        identity.st_mode,
        identity.st_uid,
        identity.st_gid,
    )
    assert writer._record_path(100).read_bytes() == payload
    assert writer._seq_path.read_bytes() == counter
    assert lane_delta(tmp_path, "lane")["records_since"] == 3
    result = repair(tmp_path, writer, writer._index_path.read_bytes())
    assert not result["changed"]
    assert writer._index_path.stat().st_ino == after.st_ino
    assert len(list((writer.lane_dir / ".index-repairs").iterdir())) == 1
    assert not list(writer.lane_dir.glob(".index-order-*"))


@pytest.mark.parametrize(
    "failure", ["digest", "size", "duplicate", "torn", "malformed"]
)
def test_refused_repair_keeps_original_and_cleans_scratch(tmp_path, failure):
    writer, _ = fixture_index(tmp_path)
    before = writer._index_path.read_bytes()
    if failure == "duplicate":
        before += before.splitlines(keepends=True)[0]
    elif failure == "torn":
        before += b'{"seq":'
    elif failure == "malformed":
        before += b'{"seq":4,"ts":NaN}\n'
    writer._index_path.write_bytes(before)
    expected = hashlib.sha256(before).hexdigest() if failure != "digest" else "0" * 64
    with pytest.raises(ValueError):
        repair_index(
            tmp_path,
            "lane",
            expected_sha256=expected,
            expected_size=len(before) + (1 if failure == "size" else 0),
        )
    assert writer._index_path.read_bytes() == before
    assert not (writer.lane_dir / ".index-repairs").exists()
    assert not list(writer.lane_dir.glob(".index-order-*"))


def test_publication_failure_retains_index_and_durable_preimage(tmp_path, monkeypatch):
    writer, _ = fixture_index(tmp_path)
    before = writer._index_path.read_bytes()

    def fail(*args):
        raise OSError("synthetic publication failure")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError, match="publication failure"):
        repair(tmp_path, writer, before)
    assert writer._index_path.read_bytes() == before
    assert next((writer.lane_dir / ".index-repairs").iterdir()).read_bytes() == before
    assert not list(writer.lane_dir.glob(".index-order-*"))


def test_order_repair_uses_bounded_memory_and_exact_large_integers(tmp_path):
    directory = tmp_path / "lane"
    directory.mkdir()
    index = directory / "lane-index.jsonl"
    count = 30000
    with index.open("wb") as stream:
        for seq in range(count, 0, -1):
            stream.write(
                json.dumps(
                    {"seq": seq + 2**80, "ts": 100, "file": "lane-19700101.jsonl"}
                ).encode()
                + b"\n"
            )
    with index.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    tracemalloc.start()
    try:
        result = repair_index(
            tmp_path, "lane", expected_sha256=digest, expected_size=index.stat().st_size
        )
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert result["records"] == count
    with index.open() as stream:
        assert json.loads(next(stream))["seq"] == 2**80 + 1
        *_, last = stream
        assert json.loads(last)["seq"] == 2**80 + count
    assert peak < 4 * 1024 * 1024, peak


def test_missing_index_does_not_create_an_entrance(tmp_path):
    with pytest.raises(FileNotFoundError):
        repair_index(tmp_path, "missing", expected_sha256="0" * 64, expected_size=0)
    assert list(tmp_path.iterdir()) == []


def test_preimage_directory_link_is_refused_without_external_writes(tmp_path):
    writer, _ = fixture_index(tmp_path)
    before = writer._index_path.read_bytes()
    outside = tmp_path / "outside"
    outside.mkdir()
    (writer.lane_dir / ".index-repairs").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="physical directory"):
        repair(tmp_path, writer, before)
    assert list(outside.iterdir()) == []
    assert writer._index_path.read_bytes() == before
    assert not list(writer.lane_dir.glob(".index-order-*"))


def missing_entry(tmp_path):
    writer, ordered = fixture_index(tmp_path)
    writer._index_path.write_bytes(ordered[0] + ordered[2])
    payload = writer._record_path(100)
    lines = payload.read_bytes().splitlines(keepends=True)
    evidence = {
        "seq": 2,
        "ts": 101,
        "file": payload.name,
        "offset": len(lines[0]),
        "sha256": hashlib.sha256(lines[1]).hexdigest(),
    }
    return writer, ordered, payload, evidence


def test_restore_verified_missing_record_without_changing_existing_data(tmp_path):
    writer, ordered, payload, evidence = missing_entry(tmp_path)
    before = writer._index_path.read_bytes()
    raw_before = payload.read_bytes()
    counter = writer._seq_path.read_bytes()
    result = repair_index(
        tmp_path,
        "lane",
        expected_sha256=hashlib.sha256(before).hexdigest(),
        expected_size=len(before),
        restore_entries=[evidence],
    )
    assert (
        result["changed"] and result["restored_records"] == 1 and result["records"] == 3
    )
    assert writer._index_path.read_bytes() == b"".join(ordered)
    assert (
        payload.read_bytes() == raw_before and writer._seq_path.read_bytes() == counter
    )
    assert Path(result["backup"]).read_bytes() == before
    assert lane_delta(tmp_path, "lane")["records_since"] == 3
    assert lane_delta(tmp_path, "lane")["gap_records"] == 0


@pytest.mark.parametrize(
    "failure", ["digest", "seq", "offset", "path", "duplicate-input"]
)
def test_refused_restoration_is_atomic(tmp_path, failure):
    writer, _, payload, evidence = missing_entry(tmp_path)
    before = writer._index_path.read_bytes()
    raw_before = payload.read_bytes()
    if failure == "digest":
        evidence["sha256"] = "0" * 64
    elif failure == "seq":
        evidence["seq"] = 99
    elif failure == "offset":
        evidence["offset"] += 1
    elif failure == "path":
        evidence["file"] = "../outside.jsonl"
    entries = [evidence, evidence] if failure == "duplicate-input" else [evidence]
    with pytest.raises(ValueError):
        repair_index(
            tmp_path,
            "lane",
            expected_sha256=hashlib.sha256(before).hexdigest(),
            expected_size=len(before),
            restore_entries=entries,
        )
    assert (
        writer._index_path.read_bytes() == before and payload.read_bytes() == raw_before
    )
    assert not (writer.lane_dir / ".index-repairs").exists()
    assert not list(writer.lane_dir.glob(".index-order-*"))
