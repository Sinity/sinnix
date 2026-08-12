from __future__ import annotations

from pathlib import Path

import pytest

from sinnix_audio_capture.pause import build_gap_payload, parse_duration, write_gap_record


@pytest.mark.parametrize(
    ("text", "expected_seconds"),
    [
        ("30", 30.0),
        ("30s", 30.0),
        ("5m", 300.0),
        ("2h", 7200.0),
        ("1.5h", 5400.0),
    ],
)
def test_parse_duration(text: str, expected_seconds: float):
    assert parse_duration(text) == expected_seconds


def test_parse_duration_rejects_garbage():
    with pytest.raises(ValueError):
        parse_duration("not-a-duration")


def test_build_gap_payload_shape():
    payload = build_gap_payload(start_ts=100.0, end_ts=400.0, reason="lunch")
    assert payload == {"kind": "gap", "start": 100.0, "end": 400.0, "reason": "lunch"}


class _FakeWriter:
    def __init__(self) -> None:
        self.writes: list[dict] = []

    def write(self, payload: dict) -> dict:
        self.writes.append(payload)
        return payload


def test_write_gap_record_uses_now_and_duration(tmp_path: Path):
    fake_writer = _FakeWriter()
    record = write_gap_record(
        capture_root=tmp_path,
        duration_seconds=60.0,
        reason="mic muted",
        now_fn=lambda: 1000.0,
        writer_factory=lambda: fake_writer,
    )
    assert record == {"kind": "gap", "start": 1000.0, "end": 1060.0, "reason": "mic muted"}
    assert fake_writer.writes == [record]
