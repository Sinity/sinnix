from __future__ import annotations

import calendar
import os
from pathlib import Path

from sinnix_audio_capture.indexer import (
    SpeechSpan,
    build_index_payload,
    list_segments,
    segment_start_ts,
)


def test_list_segments_skips_partial_and_respects_since(tmp_path: Path):
    channel_dir = tmp_path / "mic"
    channel_dir.mkdir()
    old = channel_dir / "audio-mic-20260812T100000Z.opus"
    new = channel_dir / "audio-mic-20260812T140000Z.opus"
    partial = channel_dir / "audio-mic-20260812T150000Z.opus.partial"
    for p, mtime in ((old, 100), (new, 500), (partial, 900)):
        p.write_bytes(b"x")
        os.utime(p, (mtime, mtime))

    result = list_segments(channel_dir, since_ts=200)
    assert result == [new]


def test_list_segments_missing_dir_returns_empty(tmp_path: Path):
    assert list_segments(tmp_path / "does-not-exist", since_ts=0) == []


def test_segment_start_ts_parses_filename_stamp():
    path = Path("/tmp/audio/mic/audio-mic-20260812T140000Z.opus")
    ts = segment_start_ts(path)
    assert calendar.timegm((2026, 8, 12, 14, 0, 0)) == ts


def test_segment_start_ts_falls_back_for_unparseable_name(tmp_path: Path):
    path = tmp_path / "renamed-file.opus"
    path.write_bytes(b"x")
    mtime = calendar.timegm((2026, 8, 12, 14, 37, 0))
    os.utime(path, (mtime, mtime))
    ts = segment_start_ts(path)
    assert ts == calendar.timegm((2026, 8, 12, 14, 0, 0))


def test_build_index_payload_converts_spans_to_absolute_time():
    payload = build_index_payload(
        channel="mic",
        segment_path=Path("audio-mic-20260812T140000Z.opus"),
        segment_start=1000.0,
        speech_spans=[SpeechSpan(start=1.5, end=3.0), SpeechSpan(start=10.0, end=12.0)],
    )
    assert payload == {
        "kind": "speech-index",
        "channel": "mic",
        "segment": "audio-mic-20260812T140000Z.opus",
        "segment_start": 1000.0,
        "speech_spans": [
            {"start": 1001.5, "end": 1003.0},
            {"start": 1010.0, "end": 1012.0},
        ],
    }
