from __future__ import annotations

import calendar
import time
from pathlib import Path

from sinnix_audio_capture.segment import (
    OPUS_APPLICATION_CTL_VALUE,
    CHANNEL_PROFILES,
    OpusSegmentWriter,
    hour_bucket_start,
    opusenc_argv,
    segment_filename,
)


def test_hour_bucket_start_truncates_to_the_hour():
    ts = float(calendar.timegm((2026, 8, 12, 14, 37, 52)))
    bucket = hour_bucket_start(ts)
    assert time.gmtime(bucket)[:6] == (2026, 8, 12, 14, 0, 0)


def test_segment_filename_shape():
    bucket = float(calendar.timegm((2026, 8, 12, 14, 0, 0)))
    assert segment_filename("mic", bucket) == "audio-mic-20260812T140000Z.opus"


def test_opusenc_argv_sets_application_and_dtx_ctls():
    # DTX and the output path are true for every profile; the application CTL
    # is asserted against the profile's own setting rather than a literal,
    # because which application a CHANNEL uses is a tuning decision while the
    # RENDERING of that decision is the contract.
    profile = CHANNEL_PROFILES["mic"]
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


def test_opusenc_argv_renders_each_profiles_application():
    for name, profile in CHANNEL_PROFILES.items():
        argv = opusenc_argv("opusenc", profile, Path("/tmp/out.opus.partial"))
        expected = OPUS_APPLICATION_CTL_VALUE[profile.application]
        assert f"4000={expected}" in argv, f"{name} rendered the wrong application CTL"


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
    profile = CHANNEL_PROFILES["mic"]
    writer = OpusSegmentWriter(
        output_dir=tmp_path,
        channel="mic",
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
        "audio-mic-20260812T140000Z.opus",
        "audio-mic-20260812T150000Z.opus",
    ]
    assert not list(tmp_path.glob("*.partial"))


def test_opus_segment_writer_maybe_rotate_on_quiet_hour(tmp_path: Path):
    writer = OpusSegmentWriter(
        output_dir=tmp_path,
        channel="mic",
        argv_builder=lambda output_path: ["fake", str(output_path)],
        popen=_fake_popen,
    )
    hour0 = float(calendar.timegm((2026, 8, 12, 14, 0, 0)))
    hour1 = float(calendar.timegm((2026, 8, 12, 15, 0, 0)))

    writer.write(b"x", ts=hour0 + 1)
    finished = writer.maybe_rotate(hour1 + 1)
    assert finished is not None
    assert finished.name == "audio-mic-20260812T140000Z.opus"
    assert not writer.is_open
