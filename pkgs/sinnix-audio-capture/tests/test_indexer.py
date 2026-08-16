from __future__ import annotations

import calendar
import os
from pathlib import Path

from sinnix_audio_capture import indexer
from sinnix_audio_capture.indexer import (
    SpeechSpan,
    build_index_payload,
    decoded_seconds_from_pcm,
    list_segments,
    observed_span_seconds,
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


def test_decoded_seconds_from_pcm_counts_s16le_mono_16k():
    # One second of 16kHz mono s16le is 32000 bytes.
    assert decoded_seconds_from_pcm(b"\x00" * 32000) == 1.0
    assert decoded_seconds_from_pcm(b"") == 0.0


def test_observed_span_uses_close_time_minus_start(tmp_path: Path):
    seg = tmp_path / "audio-mic-20260812T140000Z.opus"
    seg.write_bytes(b"x")
    start = calendar.timegm((2026, 8, 12, 14, 0, 0))
    os.utime(seg, (start + 3600, start + 3600))
    assert observed_span_seconds(seg, start) == 3600.0


def test_observed_span_is_none_for_a_part_file(tmp_path: Path):
    # A -pN file's stamp is the hour bucket, not when the recorder restarted,
    # so any span derived from it would overstate the window and report a
    # shortfall that never happened.
    seg = tmp_path / "audio-mic-p2-20260812T140000Z.opus"
    seg.write_bytes(b"x")
    start = calendar.timegm((2026, 8, 12, 14, 0, 0))
    os.utime(seg, (start + 1800, start + 1800))
    assert observed_span_seconds(seg, start) is None


def test_payload_reports_coverage_when_the_span_is_known():
    payload = build_index_payload(
        channel="mic",
        segment_path=Path("audio-mic-20260812T140000Z.opus"),
        segment_start=1000.0,
        speech_spans=[],
        decoded_seconds=3567.9,
        span_seconds=3600.0,
    )
    assert payload["decoded_seconds"] == 3567.9
    assert payload["span_seconds"] == 3600.0
    assert payload["coverage"] == 0.9911


def test_payload_reports_the_sinnix_500c_shortfall_as_near_zero_coverage():
    # The regression this field exists to make visible: an hourly segment
    # holding 37.5s of audio while every other health signal looked fine.
    payload = build_index_payload(
        channel="mic",
        segment_path=Path("audio-mic-20260812T140000Z.opus"),
        segment_start=1000.0,
        speech_spans=[],
        decoded_seconds=37.5,
        span_seconds=3600.0,
    )
    assert payload["coverage"] == 0.0104


def test_payload_omits_coverage_rather_than_inventing_a_denominator():
    payload = build_index_payload(
        channel="mic",
        segment_path=Path("audio-mic-p2-20260812T140000Z.opus"),
        segment_start=1000.0,
        speech_spans=[],
        decoded_seconds=540.0,
        span_seconds=None,
    )
    assert payload["decoded_seconds"] == 540.0
    assert "coverage" not in payload
    assert "span_seconds" not in payload


def _fake_vad(monkeypatch):
    """Neutralize the parts of a pass that need torch and ffmpeg.

    Everything else -- segment listing, the raw_ref the writer records, and
    the skip decision under test -- runs for real, including the actual
    CaptureWriter, because the de-duplication reads the lane files that
    writer produces.
    """
    monkeypatch.setattr(indexer, "_load_model", lambda: object())
    monkeypatch.setattr(
        indexer, "decode_to_pcm16k_mono", lambda _bin, _path: b"\x00" * 32000
    )
    monkeypatch.setattr(indexer, "_speech_spans_for_segment", lambda _model, _pcm: [])


def _write_segment(capture_root: Path, name: str) -> Path:
    channel_dir = capture_root / "audio" / "mic"
    channel_dir.mkdir(parents=True, exist_ok=True)
    path = channel_dir / name
    path.write_bytes(b"x")
    return path


def _lane_records(capture_root: Path) -> list[str]:
    lane_dir = capture_root / "audio-index"
    return [
        line
        for path in sorted(lane_dir.glob("audio-index-2*.jsonl"))
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def test_index_pass_does_not_reindex_a_segment_it_already_wrote(
    tmp_path: Path, monkeypatch
):
    """The lookback window is not a de-duplicator.

    The timer fires hourly with a 26-hour lookback, so without this every
    pass re-decoded a full day of audio: 4481 records over 431 distinct
    segments in one day on 2026-08-16, with a pass taking longer than the
    interval that triggered it.
    """
    _fake_vad(monkeypatch)
    _write_segment(tmp_path, "audio-mic-20260812T100000Z.opus")

    first = indexer.run_index_pass(capture_root=tmp_path, channels=("mic",), since_ts=0)
    second = indexer.run_index_pass(
        capture_root=tmp_path, channels=("mic",), since_ts=0
    )

    assert first == 1
    assert second == 0
    assert len(_lane_records(tmp_path)) == 1


def test_index_pass_still_indexes_a_segment_it_has_not_seen(
    tmp_path: Path, monkeypatch
):
    """Anti-vacuity for the test above: the skip must be per-segment.

    A de-duplication that skipped everything once the lane was non-empty
    would satisfy the previous test perfectly while silently ending
    indexing forever.
    """
    _fake_vad(monkeypatch)
    _write_segment(tmp_path, "audio-mic-20260812T100000Z.opus")
    indexer.run_index_pass(capture_root=tmp_path, channels=("mic",), since_ts=0)

    _write_segment(tmp_path, "audio-mic-20260812T110000Z.opus")
    added = indexer.run_index_pass(capture_root=tmp_path, channels=("mic",), since_ts=0)

    assert added == 1
    assert len(_lane_records(tmp_path)) == 2
