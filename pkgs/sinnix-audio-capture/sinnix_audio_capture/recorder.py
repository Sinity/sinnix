"""`pw-record` -> [tee] -> OpusSegmentWriter: the byte-moving loop.

No VAD, no gating, no silence detection here at all -- the loop's job is
to move bytes from PipeWire into the Opus archive (and, for the nominated
ASR device, into the low-latency mirror) continuously. Silence is handled
entirely by Opus DTX inside the encoder (see segment.py); this loop has no
opinion about whether a chunk is speech or not.

Which device a stream targets is not decided here. devices.py enumerates
the graph and owns one loop per device; there is no channel that follows
PipeWire's idea of a default, because a default is a role and a role is
not a device.
"""

from __future__ import annotations

import logging
import signal
import subprocess
import threading
import time
from collections.abc import Callable

from .segment import ChannelProfile, OpusSegmentWriter

logger = logging.getLogger("sinnix_audio_capture.recorder")

# 100ms chunks: small enough to keep the ASR tee's latency low, large enough
# not to spend most of the loop in Python-level syscall overhead.
_CHUNK_MS = 100


def _chunk_bytes(profile: ChannelProfile) -> int:
    return (profile.rate * profile.channels * 2 * _CHUNK_MS) // 1000


def pw_record_argv(
    pw_record_bin: str, profile: ChannelProfile, target: str | None
) -> list[str]:
    argv = [
        str(pw_record_bin),
        "--rate",
        str(profile.rate),
        "--channels",
        str(profile.channels),
        "--format",
        "s16",
        "-a",  # raw mode: no WAV header on stdout
    ]
    if target:
        argv += ["--target", target]
    argv.append("-")
    return argv


def install_signal_stop_event() -> threading.Event:
    stop_event = threading.Event()

    def _handler(signum, frame):  # noqa: ARG001
        stop_event.set()

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)
    return stop_event


def run_capture_stream(
    *,
    profile: ChannelProfile,
    writer: OpusSegmentWriter,
    target_provider: Callable[[], str | None],
    stop_event: threading.Event,
    restart_event: threading.Event,
    pw_record_bin: str = "pw-record",
    popen=subprocess.Popen,
    chunk_sink: Callable[[bytes], None] | None = None,
    allow_untargeted: bool = True,
    on_child: Callable[[subprocess.Popen | None], None] | None = None,
    idle_sleep: float = 1.0,
) -> None:
    """Move PCM from `pw-record` into `writer` until stopped, reconnecting
    whenever the child exits or `restart_event` fires.

    `allow_untargeted=False` refuses to start `pw-record` while the target
    is unresolved instead of letting PipeWire pick: for a recorder pinned
    to one specific node, an auto-linked stream would silently archive a
    DIFFERENT device's audio under that node's name.

    `on_child` is handed each live child so the owner can terminate it out
    of band; the read below blocks, so an owner that only sets `stop_event`
    could otherwise wait indefinitely on a device that has stopped
    producing without closing its stream.
    """
    chunk_size = _chunk_bytes(profile)
    while not stop_event.is_set():
        target = target_provider()
        if target is None and not allow_untargeted:
            if stop_event.wait(idle_sleep):
                break
            continue
        argv = pw_record_argv(pw_record_bin, profile, target)
        proc = popen(argv, stdout=subprocess.PIPE)
        if on_child is not None:
            on_child(proc)
        restart_event.clear()
        received = False
        try:
            assert proc.stdout is not None
            while not stop_event.is_set() and not restart_event.is_set():
                chunk = proc.stdout.read(chunk_size)
                if not chunk:
                    break
                received = True
                now = time.time()
                if chunk_sink is not None:
                    chunk_sink(chunk)
                writer.write(chunk, ts=now)
                writer.maybe_rotate(now)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            if on_child is not None:
                on_child(None)
        if not received and not stop_event.is_set() and not restart_event.is_set():
            # A child that produced nothing and exited (device vanished mid-read,
            # node not ready) must not be respawned in a tight loop.
            stop_event.wait(idle_sleep)
