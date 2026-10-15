from pathlib import Path

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
