from pathlib import Path

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
