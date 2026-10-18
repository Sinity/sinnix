from pathlib import Path
import json
import multiprocessing
import os

import pytest
from sinnix_capture.query import discover_lanes, lane_delta, query
from sinnix_capture.writer import CaptureWriter


def test_lane_delta_on_missing_lane_returns_zeroed_result(tmp_path: Path) -> None:
    result = lane_delta(tmp_path, "missing-lane", since_ts=0.0)
    assert result == {
        "lane": "missing-lane",
        "records_since": 0,
        "newest_ts": None,
        "gap_records": 0,
    }


def test_lane_delta_counts_records_since_and_newest_ts(tmp_path: Path) -> None:
    writer = CaptureWriter(tmp_path, "lane-a")
    writer.write({"n": 1}, ts=100.0)
    writer.write({"n": 2}, ts=200.0)
    writer.write({"n": 3}, ts=300.0)

    result = lane_delta(tmp_path, "lane-a", since_ts=150.0)
    assert result["records_since"] == 2
    assert result["newest_ts"] == 300.0
    assert result["gap_records"] == 0


def test_lane_delta_detects_seq_gaps(tmp_path: Path) -> None:
    writer = CaptureWriter(tmp_path, "lane-b")
    writer.write({"n": 1}, ts=100.0)
    writer.write({"n": 2}, ts=200.0)
    # Simulate a lost record: seq jumps from 2 straight to 5.
    (tmp_path / "lane-b" / "lane-b.seq").write_text("4")
    writer.write({"n": 5}, ts=300.0)

    result = lane_delta(tmp_path, "lane-b", since_ts=0.0)
    assert result["gap_records"] == 2


def test_discover_lanes_lists_directories(tmp_path: Path) -> None:
    CaptureWriter(tmp_path, "lane-x").write({"n": 1})
    CaptureWriter(tmp_path, "lane-y").write({"n": 1})
    (tmp_path / "not-a-lane.txt").write_text("stray file")

    assert discover_lanes(tmp_path) == ["lane-x", "lane-y"]


def test_query_returns_delta_per_discovered_lane(tmp_path: Path) -> None:
    CaptureWriter(tmp_path, "lane-x").write({"n": 1}, ts=100.0)
    CaptureWriter(tmp_path, "lane-y").write({"n": 1}, ts=200.0)

    results = query(tmp_path, since_ts=0.0)
    by_lane = {r["lane"]: r for r in results}
    assert set(by_lane) == {"lane-x", "lane-y"}
    assert by_lane["lane-x"]["newest_ts"] == 100.0
    assert by_lane["lane-y"]["newest_ts"] == 200.0


def test_query_restricted_to_explicit_lanes(tmp_path: Path) -> None:
    CaptureWriter(tmp_path, "lane-x").write({"n": 1})
    CaptureWriter(tmp_path, "lane-y").write({"n": 1})

    results = query(tmp_path, since_ts=0.0, lanes=["lane-x"])
    assert [r["lane"] for r in results] == ["lane-x"]


def test_query_ignores_only_an_interrupted_final_index_line(tmp_path: Path) -> None:
    writer = CaptureWriter(tmp_path, "lane-x")
    writer.write({"n": 1}, ts=100.0)
    with writer._index_path.open("ab") as handle:
        handle.write(b'{"ts":')
    assert lane_delta(tmp_path, "lane-x")["records_since"] == 1
    writer.write({"n": 2}, ts=200.0)
    assert lane_delta(tmp_path, "lane-x")["records_since"] == 2


def test_query_refuses_a_terminated_malformed_index_line(tmp_path: Path) -> None:
    writer = CaptureWriter(tmp_path, "lane-x")
    writer.write({"n": 1}, ts=100.0)
    with writer._index_path.open("ab") as handle:
        handle.write(b"not json\n")
    with pytest.raises(ValueError):
        lane_delta(tmp_path, "lane-x")


@pytest.mark.parametrize("patch", [
    {"ts": float("nan")}, {"ts": float("inf")}, {"ts": True}, {"ts": "100"},
    {"seq": True}, {"seq": 0}, {"seq": -1}, {"seq": 1.5},
])
def test_query_rejects_invalid_index_fields(tmp_path, patch):
    writer = CaptureWriter(tmp_path, "lane")
    writer.write({"synthetic": True}, ts=100)
    entry = json.loads(writer._index_path.read_text())
    entry.update(patch)
    writer._index_path.write_text(json.dumps(entry) + "\n")
    with pytest.raises(ValueError, match="capture index"):
        lane_delta(tmp_path, "lane")


@pytest.mark.parametrize("seq", [1, 0])
def test_query_rejects_duplicate_or_reversed_sequence(tmp_path, seq):
    writer = CaptureWriter(tmp_path, "lane")
    writer.write({"synthetic": True}, ts=100)
    entry = json.loads(writer._index_path.read_text())
    entry["seq"] = seq
    with writer._index_path.open("a") as handle:
        handle.write(json.dumps(entry) + "\n")
    with pytest.raises(ValueError, match="capture index"):
        lane_delta(tmp_path, "lane")


def test_query_refuses_fifo_index_without_blocking(tmp_path):
    writer = CaptureWriter(tmp_path, "lane")
    os.mkfifo(writer._index_path)
    ctx = multiprocessing.get_context("fork")
    parent, child = ctx.Pipe(duplex=False)

    def query_fifo():
        try:
            lane_delta(tmp_path, "lane")
        except ValueError:
            child.send("refused")

    process = ctx.Process(target=query_fifo)
    try:
        process.start()
        process.join(1)
        assert not process.is_alive(), "capture query blocked opening a FIFO index"
        assert parent.poll(1) and parent.recv() == "refused"
    finally:
        if process.is_alive():
            process.terminate()
            process.join(5)
        parent.close()
        child.close()


@pytest.mark.parametrize("since", [float("nan"), float("inf"), True, "100", 2 ** 1024])
@pytest.mark.parametrize("operation", ["lane_delta", "query"])
def test_query_rejects_invalid_since_timestamp_even_for_empty_lane(tmp_path, since, operation):
    with pytest.raises(ValueError, match="since timestamp"):
        if operation == "lane_delta":
            lane_delta(tmp_path, "missing-lane", since)
        else:
            query(tmp_path, since)


@pytest.mark.parametrize("kind", ["index", "lane"])
def test_query_does_not_treat_broken_entrance_as_empty(tmp_path, kind):
    writer = CaptureWriter(tmp_path, "lane")
    path = writer._index_path if kind == "index" else writer.lane_dir
    if kind == "lane":
        path.rmdir()
    path.symlink_to(tmp_path / "missing-target")
    with pytest.raises(FileNotFoundError):
        lane_delta(tmp_path, "lane")


def test_query_preserves_working_index_link(tmp_path):
    writer = CaptureWriter(tmp_path, "lane")
    writer.write({"synthetic": True}, ts=100)
    retained = tmp_path / "retained-index"
    writer._index_path.rename(retained)
    writer._index_path.symlink_to(retained)
    assert lane_delta(tmp_path, "lane")["records_since"] == 1


def test_query_closes_descriptor_when_index_is_a_directory(tmp_path):
    writer = CaptureWriter(tmp_path, "lane")
    writer._index_path.mkdir()
    before = set(os.listdir("/proc/self/fd"))
    with pytest.raises(ValueError, match="not a regular file"):
        lane_delta(tmp_path, "lane")
    assert set(os.listdir("/proc/self/fd")) == before


@pytest.mark.parametrize("operation", ["lane_delta", "discover"])
def test_query_refuses_inaccessible_source_instead_of_reporting_zero(tmp_path, operation):
    writer = CaptureWriter(tmp_path, "clipboard")
    writer.write({"fixture": True}, ts=100)
    blocked = writer.lane_dir if operation == "lane_delta" else writer.lane_dir.parent
    blocked.chmod(0)
    try:
        with pytest.raises(PermissionError):
            if operation == "lane_delta":
                lane_delta(tmp_path, "clipboard")
            else:
                discover_lanes(tmp_path)
    finally:
        blocked.chmod(0o700)


def test_discovery_refuses_regular_file_root(tmp_path):
    root = tmp_path / "not-a-directory"
    root.touch()
    with pytest.raises(NotADirectoryError):
        discover_lanes(root)


def test_accessible_empty_root_has_no_lanes(tmp_path):
    assert discover_lanes(tmp_path) == []


@pytest.mark.parametrize("operation", ["discover", "delta", "query", "explicit-query"])
def test_broken_capture_root_is_not_empty_data(tmp_path, operation):
    root = tmp_path / "capture"
    root.symlink_to(tmp_path / "unavailable-target", target_is_directory=True)
    with pytest.raises(FileNotFoundError):
        if operation == "discover":
            discover_lanes(root)
        elif operation == "delta":
            lane_delta(root, "clipboard")
        else:
            query(root, lanes=["clipboard"] if operation == "explicit-query" else None)


def test_missing_and_working_link_roots_keep_their_meaning(tmp_path):
    missing = tmp_path / "absent"
    assert discover_lanes(missing) == []
    assert lane_delta(missing, "clipboard")["records_since"] == 0
    target = tmp_path / "retained"
    CaptureWriter(target, "clipboard").write({"fixture": True}, ts=100)
    root = tmp_path / "capture"
    root.symlink_to(target, target_is_directory=True)
    assert discover_lanes(root) == ["clipboard"]
    assert query(root)[0]["records_since"] == 1


@pytest.mark.parametrize("index_state", ["missing", "empty", "torn-first-record"])
def test_retained_payload_without_complete_index_is_not_measured_zero(tmp_path, index_state):
    writer = CaptureWriter(tmp_path, "lane")
    writer.write({"retained": True}, ts=100)
    if index_state == "missing":
        writer._index_path.unlink()
    else:
        writer._index_path.write_bytes(b"" if index_state == "empty" else b'{"ts":')
    with pytest.raises(ValueError, match="no complete records"):
        lane_delta(tmp_path, "lane")
    writer.write({"next": True}, ts=200)
    assert lane_delta(tmp_path, "lane")["records_since"] == 2


@pytest.mark.parametrize("empty_payload_file", [False, True])
def test_empty_lane_without_index_still_reports_zero(tmp_path, empty_payload_file):
    writer = CaptureWriter(tmp_path, "lane")
    if empty_payload_file:
        writer._record_path(100).touch()
    assert lane_delta(tmp_path, "lane")["records_since"] == 0


@pytest.mark.parametrize("kind", ["file", "broken-link"])
def test_discovery_refuses_unusable_declared_lane(tmp_path, kind):
    from sinnix_lib.layout import capture_lane_path

    path = capture_lane_path(tmp_path, "clipboard")
    path.parent.mkdir(parents=True)
    if kind == "file":
        path.touch()
        error = NotADirectoryError
    else:
        path.symlink_to(tmp_path / "missing-target", target_is_directory=True)
        error = FileNotFoundError
    with pytest.raises(error):
        discover_lanes(tmp_path)


def test_discovery_keeps_working_declared_directory_link(tmp_path):
    from sinnix_lib.layout import capture_lane_path

    root = tmp_path / "capture"
    target = tmp_path / "retained-lane"
    target.mkdir()
    path = capture_lane_path(root, "clipboard")
    path.parent.mkdir(parents=True)
    path.symlink_to(target, target_is_directory=True)
    assert "clipboard" in discover_lanes(root)
