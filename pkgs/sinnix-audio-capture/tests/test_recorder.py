from __future__ import annotations

import pytest

from sinnix_audio_capture.recorder import _chunk_bytes, pw_record_argv
from sinnix_audio_capture.segment import CHANNEL_PROFILES


def test_pw_record_argv_mic_no_target():
    argv = pw_record_argv("pw-record", CHANNEL_PROFILES["mic"], None)
    assert argv == [
        "pw-record",
        "--rate",
        "16000",
        "--channels",
        "1",
        "--format",
        "s16",
        "-a",
        "-",
    ]


def test_pw_record_argv_includes_target_when_given():
    argv = pw_record_argv("pw-record", CHANNEL_PROFILES["sink-monitor"], "bluez_output.foo.monitor")
    assert "--target" in argv
    assert argv[argv.index("--target") + 1] == "bluez_output.foo.monitor"
    assert argv[-1] == "-"


@pytest.mark.parametrize("channel", sorted(CHANNEL_PROFILES))
def test_chunk_bytes_is_100ms_of_s16_pcm(channel: str):
    profile = CHANNEL_PROFILES[channel]
    expected = profile.rate * profile.channels * 2 // 10  # 100ms, 2 bytes/sample
    assert _chunk_bytes(profile) == expected
