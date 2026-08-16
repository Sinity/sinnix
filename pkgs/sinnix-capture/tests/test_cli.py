import json
from pathlib import Path

import pytest
from sinnix_capture.cli import main


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
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO('{"n": 1}\n\n{"n": 2}\n{"n": 3}\n'))
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
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO('{"n": 1}\nnot json\n{"n": 2}\n'))
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
