from __future__ import annotations

import pytest
from sinnix_audio_capture.recorder import _chunk_bytes, pw_record_argv
from sinnix_audio_capture.segment import CHANNEL_PROFILES, source_profile


def test_pw_record_argv_no_target():
    # Derived from the profile, not hardcoded: the invariant is that the
    # renderer passes the profile through faithfully, not that a source happens
    # to be at some particular rate. A pinned literal would only fossilise the
    # config and break on deliberate retunes.
    profile = source_profile(1)
    argv = pw_record_argv("pw-record", profile, None)
    assert argv == [
        "pw-record",
        "--rate",
        str(profile.rate),
        "--channels",
        str(profile.channels),
        "--format",
        "s16",
        "-a",
        "-",
    ]


def test_pw_record_argv_includes_target_when_given():
    argv = pw_record_argv(
        "pw-record", CHANNEL_PROFILES["sink-monitor"], "bluez_output.foo.monitor"
    )
    assert "--target" in argv
    assert argv[argv.index("--target") + 1] == "bluez_output.foo.monitor"
    assert argv[-1] == "-"


@pytest.mark.parametrize(
    "profile", [*CHANNEL_PROFILES.values(), source_profile(1), source_profile(2)]
)
def test_chunk_bytes_is_100ms_of_s16_pcm(profile):
    expected = profile.rate * profile.channels * 2 // 10  # 100ms, 2 bytes/sample
    assert _chunk_bytes(profile) == expected
