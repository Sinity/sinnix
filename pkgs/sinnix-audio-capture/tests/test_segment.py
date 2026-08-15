from __future__ import annotations

import calendar
import time
from pathlib import Path

from sinnix_audio_capture.segment import (
    OPUS_APPLICATION_CTL_VALUE,
    OpusSegmentWriter,
    device_profile,
    hour_bucket_start,
    opusenc_argv,
    promote_orphan_partials,
    segment_filename,
)


def test_hour_bucket_start_truncates_to_the_hour():
    ts = float(calendar.timegm((2026, 8, 12, 14, 37, 52)))
    bucket = hour_bucket_start(ts)
    assert time.gmtime(bucket)[:6] == (2026, 8, 12, 14, 0, 0)


def test_segment_filename_shape():
    bucket = float(calendar.timegm((2026, 8, 12, 14, 0, 0)))
    # Per-source channel names contain dashes; the stamp is still the last
    # dash-separated component, which is what indexer.segment_start_ts parses.
    assert (
        segment_filename("src-alsa-input-yeti", bucket)
        == "audio-src-alsa-input-yeti-20260812T140000Z.opus"
    )


def test_opusenc_argv_sets_application_and_dtx_ctls():
    # DTX and the output path are true for every profile; the application CTL
    # is asserted against the profile's own setting rather than a literal,
    # because which application a CHANNEL uses is a tuning decision while the
    # RENDERING of that decision is the contract.
    profile = device_profile(2)
    argv = opusenc_argv("opusenc", profile, Path("/tmp/out.opus.partial"))
    assert "--set-ctl-int" in argv
    assert f"4000={OPUS_APPLICATION_CTL_VALUE[profile.application]}" in argv
    assert "4016=1" in argv  # OPUS_SET_DTX_REQUEST -> enabled
    assert argv[-1] == "/tmp/out.opus.partial"


def test_opusenc_application_ctl_mapping_is_correct():
    # The mapping itself IS a real external contract (libopus header
    # values), so it is pinned to literals on purpose -- unlike which
    # channel happens to select which application.
    assert OPUS_APPLICATION_CTL_VALUE["voip"] == 2048
    assert OPUS_APPLICATION_CTL_VALUE["audio"] == 2049


def test_opusenc_argv_renders_the_profiles_application():
    for channels in (1, 2):
        profile = device_profile(channels)
        argv = opusenc_argv("opusenc", profile, Path("/tmp/out.opus.partial"))
        expected = OPUS_APPLICATION_CTL_VALUE[profile.application]
        assert f"4000={expected}" in argv


class _FakeProc:
    def __init__(self, output_path: Path) -> None:
        self._output_path = output_path
        self._buf = bytearray()
        self.stdin = self
        self.returncode = None

    def write(self, data: bytes) -> None:
        self._buf += data

    def close(self) -> None:
        self._output_path.write_bytes(bytes(self._buf))

    def wait(self) -> None:
        self.returncode = 0


def _fake_popen(argv, stdin=None):
    # argv[-1] is the output path per opusenc_argv's layout.
    return _FakeProc(Path(argv[-1]))


def test_opus_segment_writer_rotates_on_hour_boundary(tmp_path: Path):
    profile = device_profile(2)
    writer = OpusSegmentWriter(
        output_dir=tmp_path,
        channel="src-alsa-input-yeti",
        argv_builder=lambda output_path: [
            "fake",
            *[f"noop-{k}={v}" for k, v in vars(profile).items()],
            str(output_path),
        ],
        popen=_fake_popen,
    )
    hour0 = float(calendar.timegm((2026, 8, 12, 14, 0, 0)))
    hour1 = float(calendar.timegm((2026, 8, 12, 15, 0, 0)))

    writer.write(b"abc", ts=hour0 + 60)
    assert writer.is_open
    writer.write(b"def", ts=hour1 + 5)  # crosses into the next hour -> rotates
    writer.close()

    finished = sorted(p.name for p in tmp_path.glob("*.opus"))
    assert finished == [
        "audio-src-alsa-input-yeti-20260812T140000Z.opus",
        "audio-src-alsa-input-yeti-20260812T150000Z.opus",
    ]
    assert not list(tmp_path.glob("*.partial"))


def test_opus_segment_writer_maybe_rotate_on_quiet_hour(tmp_path: Path):
    writer = OpusSegmentWriter(
        output_dir=tmp_path,
        channel="src-alsa-input-yeti",
        argv_builder=lambda output_path: ["fake", str(output_path)],
        popen=_fake_popen,
    )
    hour0 = float(calendar.timegm((2026, 8, 12, 14, 0, 0)))
    hour1 = float(calendar.timegm((2026, 8, 12, 15, 0, 0)))

    writer.write(b"x", ts=hour0 + 1)
    finished = writer.maybe_rotate(hour1 + 1)
    assert finished is not None
    assert finished.name == "audio-src-alsa-input-yeti-20260812T140000Z.opus"
    assert not writer.is_open


def test_a_second_segment_in_one_hour_never_overwrites_the_first(tmp_path: Path):
    # Any mid-hour restart (device replug, unit restart) opens a new segment
    # for the same channel-hour. The finalising rename must not clobber the
    # part already archived.
    hour = float(calendar.timegm((2026, 8, 12, 14, 0, 0)))

    def _write(payload: bytes) -> Path:
        writer = OpusSegmentWriter(
            output_dir=tmp_path,
            channel="src-x",
            argv_builder=lambda output_path: ["fake", str(output_path)],
            popen=_fake_popen,
        )
        writer.write(payload, ts=hour + 60)
        finished = writer.close()
        assert finished is not None
        return finished

    first = _write(b"first-part")
    second = _write(b"second-part")
    third = _write(b"third-part")

    assert first.name == "audio-src-x-20260812T140000Z.opus"
    assert second.name == "audio-src-x-p2-20260812T140000Z.opus"
    assert third.name == "audio-src-x-p3-20260812T140000Z.opus"
    assert first.read_bytes() == b"first-part"
    assert second.read_bytes() == b"second-part"


def test_part_marked_segments_still_carry_a_parseable_stamp():
    from sinnix_audio_capture.indexer import segment_start_ts

    hour = float(calendar.timegm((2026, 8, 12, 14, 0, 0)))
    name = segment_filename("src-x", hour, part=4)
    assert segment_start_ts(Path("/tmp") / name) == hour


def test_orphaned_partials_are_archived_without_overwriting(tmp_path):
    """A segment left by a dead recorder must reach the archive, and must not
    land on one that was finalised properly."""
    channel_dir = tmp_path / "src-x"
    channel_dir.mkdir()
    (channel_dir / "audio-src-x-20260812T140000Z.opus").write_bytes(b"archived")
    (channel_dir / "audio-src-x-20260812T140000Z.opus.partial").write_bytes(b"orphan-a")
    (channel_dir / "audio-src-x-p2-20260812T140000Z.opus.partial").write_bytes(
        b"orphan-b"
    )
    (channel_dir / "device.json").write_bytes(b"{}")

    promoted = promote_orphan_partials(tmp_path)

    assert (
        channel_dir / "audio-src-x-20260812T140000Z.opus"
    ).read_bytes() == b"archived"
    assert not list(channel_dir.glob("*.partial"))
    assert sorted(p.read_bytes() for p in channel_dir.glob("*.opus")) == [
        b"archived",
        b"orphan-a",
        b"orphan-b",
    ]
    assert all(p.name.startswith("audio-src-x-p") for p in promoted)
    assert (channel_dir / "device.json").exists()
