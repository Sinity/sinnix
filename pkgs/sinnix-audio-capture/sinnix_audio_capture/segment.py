"""Hour-aligned Opus segment writer.

Design departure from the audio-capture bead's original sketch (recorded on
sinnix-nm7): there is no lossless intermediate tier. `pw-record` output is
piped directly into `opusenc` in raw-PCM mode -- Opus itself IS the raw/
archive tier. `opusenc` has no `--application`/`--dtx` command-line flags
(verified against opus-tools v0.2 source, gitlab.xiph.org/xiph/opus-tools);
both are set via `--set-ctl-int <request>=<value>` using the numeric
request/value constants from upstream libopus's opus_defines.h:

    OPUS_SET_APPLICATION_REQUEST = 4000   OPUS_APPLICATION_VOIP  = 2048
    OPUS_SET_DTX_REQUEST         = 4016   OPUS_APPLICATION_AUDIO = 2049

Live-verified on sinnix-prime 2026-08-12: encoding 2s of raw silence at
16kHz/mono/24kbps with `--set-ctl-int 4000=2048 --set-ctl-int 4016=1`
produced "Encoding using libopus 1.6.1 (VoIP)" and collapsed the actual
bitrate to ~1.7kbit/s -- DTX is doing its job at the codec level, exactly as
the bead's supersession note requires ("silence collapses via Opus DTX+VBR,
not gating logic").

Segment rotation: `opusenc` finalizes a complete, valid Ogg Opus file only
when its stdin reaches EOF, so the natural fsync-on-close point is closing
that stdin pipe. Each segment is written to `<name>.opus.partial` while
`opusenc` owns it; on clean rotation (or shutdown) the writer waits for
`opusenc` to exit, fsyncs the finished file, and renames away the
`.partial` suffix, then fsyncs the containing directory so the rename is
durable. If the recorder is killed mid-hour, the `.partial` file is exactly
the "partial hour survives" crash-safety property the bead asks for --
downstream consumers (the indexer) simply skip anything still named
`*.opus.partial`.
"""

from __future__ import annotations

import calendar
import os
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

SEGMENT_SECONDS = 3600

OPUS_SET_APPLICATION_REQUEST = 4000
OPUS_SET_DTX_REQUEST = 4016
OPUS_APPLICATION_CTL_VALUE = {
    "voip": 2048,
    "audio": 2049,
}


@dataclass(frozen=True)
class ChannelProfile:
    rate: int
    channels: int
    bitrate_kbps: int
    application: str  # "voip" | "audio" -- see OPUS_APPLICATION_CTL_VALUE


# The two canonical channels (sinnix-nm7 supersession note): mic favors
# speech intelligibility at a low bitrate/mono, sink-monitor favors
# faithfulness to mixed system/app audio at stereo.
CHANNEL_PROFILES: dict[str, ChannelProfile] = {
    "mic": ChannelProfile(rate=16000, channels=1, bitrate_kbps=24, application="voip"),
    "sink-monitor": ChannelProfile(
        rate=48000, channels=2, bitrate_kbps=64, application="audio"
    ),
}


def hour_bucket_start(ts: float) -> float:
    """Wall-clock (UTC) hour boundary at or before ts, as a Unix timestamp."""
    tm = time.gmtime(ts)
    return float(calendar.timegm((tm.tm_year, tm.tm_mon, tm.tm_mday, tm.tm_hour, 0, 0)))


def segment_filename(channel: str, bucket_start_ts: float) -> str:
    stamp = time.strftime("%Y%m%dT%H0000Z", time.gmtime(bucket_start_ts))
    return f"audio-{channel}-{stamp}.opus"


def opusenc_argv(
    opusenc_bin: str, profile: ChannelProfile, output_path: Path
) -> list[str]:
    return [
        str(opusenc_bin),
        "--quiet",
        "--raw",
        "--raw-rate",
        str(profile.rate),
        "--raw-chan",
        str(profile.channels),
        "--raw-bits",
        "16",
        "--bitrate",
        str(profile.bitrate_kbps),
        "--vbr",
        "--set-ctl-int",
        f"{OPUS_SET_APPLICATION_REQUEST}={OPUS_APPLICATION_CTL_VALUE[profile.application]}",
        "--set-ctl-int",
        f"{OPUS_SET_DTX_REQUEST}=1",
        "-",
        str(output_path),
    ]


def opusenc_argv_builder(
    opusenc_bin: str, profile: ChannelProfile
) -> Callable[[Path], list[str]]:
    return lambda output_path: opusenc_argv(opusenc_bin, profile, output_path)


class OpusSegmentWriter:
    """Feeds raw PCM bytes into hour-rotated `opusenc` subprocesses.

    `argv_builder(output_path) -> argv` is injected so tests can substitute
    a trivial stdin-to-file copier instead of a real `opusenc` binary.
    """

    def __init__(
        self,
        *,
        output_dir: Path,
        channel: str,
        argv_builder: Callable[[Path], list[str]],
        popen: Callable[..., subprocess.Popen] = subprocess.Popen,
        now_fn: Callable[[], float] = time.time,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.channel = channel
        self._argv_builder = argv_builder
        self._popen = popen
        self._now = now_fn
        self._proc: subprocess.Popen | None = None
        self._current_bucket: float | None = None
        self._final_path: Path | None = None
        self._partial_path: Path | None = None

    @property
    def is_open(self) -> bool:
        return self._proc is not None

    def _open_segment(self, ts: float) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        bucket = hour_bucket_start(ts)
        final_path = self.output_dir / segment_filename(self.channel, bucket)
        partial_path = final_path.with_suffix(final_path.suffix + ".partial")
        argv = self._argv_builder(partial_path)
        proc = self._popen(argv, stdin=subprocess.PIPE)
        self._proc = proc
        self._current_bucket = bucket
        self._final_path = final_path
        self._partial_path = partial_path

    def write(self, data: bytes, ts: float | None = None) -> None:
        ts = self._now() if ts is None else ts
        bucket = hour_bucket_start(ts)
        if self._proc is None:
            self._open_segment(ts)
        elif bucket != self._current_bucket:
            self.close()
            self._open_segment(ts)
        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write(data)

    def maybe_rotate(self, ts: float) -> Path | None:
        """Rotate on an hour boundary even with no pending data -- otherwise
        a quiet hour (DTX collapses it to near-nothing but the *segment
        file* boundary should still be wall-clock aligned) would bleed into
        the next hour's file."""
        if self._proc is not None and hour_bucket_start(ts) != self._current_bucket:
            return self.close()
        return None

    def close(self) -> Path | None:
        """Finalize the open segment: close stdin, wait for opusenc to exit,
        fsync the finished file and its directory, then atomically drop the
        `.partial` suffix. Returns the finished path, or None if nothing
        was open or the encoder failed (the `.partial` file is left in
        place either way -- never silently discarded)."""
        if self._proc is None:
            return None
        proc = self._proc
        partial_path = self._partial_path
        final_path = self._final_path
        assert partial_path is not None and final_path is not None
        try:
            if proc.stdin is not None:
                proc.stdin.close()
        except BrokenPipeError:
            pass
        proc.wait()

        finished_path: Path | None = None
        if proc.returncode == 0 and partial_path.exists():
            fd = os.open(partial_path, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(partial_path, final_path)
            dir_fd = os.open(self.output_dir, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
            finished_path = final_path

        self._proc = None
        self._current_bucket = None
        self._final_path = None
        self._partial_path = None
        return finished_path
