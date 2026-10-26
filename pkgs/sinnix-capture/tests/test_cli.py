import json
import os
import threading
import time
from pathlib import Path

import pytest
from sinnix_capture.cli import main, stream_batches


def _pipe_stdin(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    """Feed ``text`` through a real pipe; the stream batcher selects on it."""
    read_fd, write_fd = os.pipe()
    os.write(write_fd, text.encode())
    os.close(write_fd)
    stdin = os.fdopen(read_fd)
    monkeypatch.setattr("sys.stdin", stdin)


def _records(capture_root: Path, lane: str) -> list[dict]:
    lane_dir = capture_root / lane
    return [
        json.loads(line)
        for path in sorted(lane_dir.glob(f"{lane}-2*.jsonl"))
        for line in path.read_text().splitlines()
    ]


def test_write_is_silent_by_default(tmp_path: Path, capsys) -> None:
    rc = main(
        [
            "write",
            "--capture-root",
            str(tmp_path),
            "--lane",
            "quiet-lane",
            "--payload",
            '{"n": 1}',
        ]
    )
    assert rc == 0
    assert capsys.readouterr().out == ""
    assert [r["payload"] for r in _records(tmp_path, "quiet-lane")] == [{"n": 1}]


def test_print_envelope_opts_back_in(tmp_path: Path, capsys) -> None:
    rc = main(
        [
            "write",
            "--capture-root",
            str(tmp_path),
            "--lane",
            "loud-lane",
            "--payload",
            '{"n": 1}',
            "--print-envelope",
        ]
    )
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["payload"] == {"n": 1}


def test_stream_writes_one_record_per_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pipe_stdin(monkeypatch, '{"n": 1}\n\n{"n": 2}\n{"n": 3}\n')
    rc = main(
        ["write", "--capture-root", str(tmp_path), "--lane", "stream-lane", "--stream"]
    )

    assert rc == 0
    records = _records(tmp_path, "stream-lane")
    assert [r["payload"] for r in records] == [{"n": 1}, {"n": 2}, {"n": 3}]
    assert [r["seq"] for r in records] == [1, 2, 3]


def test_stream_survives_a_malformed_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    _pipe_stdin(monkeypatch, '{"n": 1}\nnot json\n{"n": 2}\n')
    rc = main(
        ["write", "--capture-root", str(tmp_path), "--lane", "torn-lane", "--stream"]
    )

    assert rc == 0
    # The malformed record is lost -- that is unavoidable -- but it is reported
    # and the two good records either side of it still land.
    assert [r["payload"] for r in _records(tmp_path, "torn-lane")] == [
        {"n": 1},
        {"n": 2},
    ]
    assert "dropped a record" in capsys.readouterr().err


def test_stream_rejects_a_payload_argument(tmp_path: Path) -> None:
    rc = main(
        [
            "write",
            "--capture-root",
            str(tmp_path),
            "--lane",
            "conflict-lane",
            "--stream",
            "--payload",
            '{"n": 1}',
        ]
    )
    assert rc == 2


def test_queued_record_preserves_observed_timestamp(tmp_path):
    ts = 1767225600.25
    assert (
        main(
            [
                "write",
                "--capture-root",
                str(tmp_path),
                "--lane",
                "fixture",
                "--payload",
                '{"event":"track"}',
                "--ts",
                str(ts),
            ]
        )
        == 0
    )
    records = _records(tmp_path, "fixture")
    assert len(records) == 1 and records[0]["ts"] == ts
    assert records[0]["schema"] == "sinnix-capture-v1"


@pytest.mark.parametrize("ts", ["nan", "inf", "1e300"])
def test_invalid_queued_timestamp_refuses_before_reserving(tmp_path, ts):
    assert (
        main(
            [
                "write",
                "--capture-root",
                str(tmp_path),
                "--lane",
                "fixture",
                "--payload",
                "{}",
                "--ts",
                ts,
            ]
        )
        == 2
    )
    assert not list(tmp_path.rglob("*.seq"))


def test_stream_batches_split_at_the_record_cap_and_keep_an_unterminated_tail() -> None:
    read_fd, write_fd = os.pipe()
    os.write(write_fd, b"a\nb\nc\nd\ne")
    os.close(write_fd)
    try:
        batches = list(stream_batches(read_fd, max_seconds=60, max_records=2))
    finally:
        os.close(read_fd)
    assert [[line for line, _ in batch] for batch in batches] == [
        ["a", "b"],
        ["c", "d"],
        ["e"],
    ]


def test_stream_batch_is_written_after_its_wait_while_input_stays_open() -> None:
    """Fails if a quiet stream holds a record until more input or EOF."""
    read_fd, write_fd = os.pipe()
    batches = stream_batches(read_fd, max_seconds=0.05, max_records=1000)
    os.write(write_fd, b"first\nsecond\n")
    began = time.monotonic()
    try:
        first = next(batches)
        waited = time.monotonic() - began
        later = threading.Timer(0.1, lambda: os.write(write_fd, b"third\n"))
        later.start()
        second = next(batches)
        later.join()
    finally:
        os.close(write_fd)
    assert list(batches) == []
    os.close(read_fd)
    assert [line for line, _ in first] == ["first", "second"]
    assert [line for line, _ in second] == ["third"]
    assert 0.04 <= waited < 5
    assert second[0][1] > first[0][1]  # Each line keeps its own arrival time.


def test_stream_writes_one_batch_with_arrival_timestamps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pipe_stdin(monkeypatch, "".join(f'{{"n": {n}}}\n' for n in range(5)))
    syncs = 0
    real_fsync = os.fsync

    def counted(fd):
        nonlocal syncs
        syncs += 1
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", counted)
    before = time.time()
    assert (
        main(["write", "--capture-root", str(tmp_path), "--lane", "b", "--stream"])
        == 0
    )
    records = _records(tmp_path, "b")
    assert [r["seq"] for r in records] == [1, 2, 3, 4, 5]
    assert all(before <= r["ts"] <= time.time() for r in records)
    # One batch: counter publication (file and directory), the daily file,
    # its high-water sidecar and the index -- not four syncs per record.
    assert syncs == 5
