"""The always-on recorder loop for one canonical channel (mic or
sink-monitor): `pw-record` -> [tee, for mic] -> OpusSegmentWriter.

No VAD, no gating, no silence detection here at all -- the recorder's job
is to move bytes from PipeWire into the Opus archive (and, for mic, into
the low-latency tee) continuously. Silence is handled entirely by Opus DTX
inside the encoder (see segment.py); this loop has no opinion about
whether a chunk is speech or not.

Default-device tracking: both channels resolve their PipeWire target via
`pw-metadata -n default` (pipewire_defaults.py) rather than a hardcoded
node name, and a background thread watches for changes for as long as the
recorder runs. On a relevant change (source changed for the mic channel,
sink changed for sink-monitor) the current `pw-record` child is restarted
against the new target; the OpusSegmentWriter is untouched by this, so a
device switch costs at most the brief gap while pw-record reconnects, not a
segment boundary.
"""

from __future__ import annotations

import logging
import signal
import subprocess
import threading
import time
from pathlib import Path

from .pipewire_defaults import DefaultTargets, parse_default_line, resolve_target
from .segment import CHANNEL_PROFILES, ChannelProfile, OpusSegmentWriter, opusenc_argv_builder
from .tee import SeqpacketTee

logger = logging.getLogger("sinnix_audio_capture.recorder")

# 100ms chunks: small enough to keep the mic tee's latency low, large enough
# not to spend most of the loop in Python-level syscall overhead.
_CHUNK_MS = 100


def _chunk_bytes(profile: ChannelProfile) -> int:
    return (profile.rate * profile.channels * 2 * _CHUNK_MS) // 1000


def pw_record_argv(pw_record_bin: str, profile: ChannelProfile, target: str | None) -> list[str]:
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


class DefaultWatcher(threading.Thread):
    """Runs `pw-metadata -n default` for the process lifetime and calls
    `on_change(kind)` (kind: "sink" | "source") whenever the resolved
    default actually changes."""

    def __init__(self, pw_metadata_bin: str, targets: DefaultTargets, on_change, *, popen=subprocess.Popen) -> None:
        super().__init__(daemon=True, name="sinnix-audio-default-watcher")
        self._pw_metadata_bin = pw_metadata_bin
        self._targets = targets
        self._on_change = on_change
        self._popen = popen
        self._proc: subprocess.Popen | None = None
        self._stopped = threading.Event()

    def run(self) -> None:
        try:
            self._proc = self._popen(
                [self._pw_metadata_bin, "-n", "default"], stdout=subprocess.PIPE, text=True
            )
        except Exception:
            logger.exception("sinnix-audio-capture: failed to start pw-metadata default watcher")
            return
        assert self._proc.stdout is not None
        for line in self._proc.stdout:
            if self._stopped.is_set():
                break
            parsed = parse_default_line(line)
            if parsed is None:
                continue
            kind, name = parsed
            if self._targets.apply(kind, name):
                try:
                    self._on_change(kind)
                except Exception:
                    logger.exception("sinnix-audio-capture: default-change callback failed")

    def stop(self) -> None:
        self._stopped.set()
        if self._proc is not None:
            self._proc.terminate()


def _install_signal_stop_event() -> threading.Event:
    stop_event = threading.Event()

    def _handler(signum, frame):  # noqa: ARG001
        stop_event.set()

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)
    return stop_event


def run_recorder(
    *,
    channel: str,
    capture_root: Path,
    pw_record_bin: str = "pw-record",
    pw_metadata_bin: str = "pw-metadata",
    opusenc_bin: str = "opusenc",
    tee_socket_path: Path | None = None,
    stop_event: threading.Event | None = None,
    popen=subprocess.Popen,
) -> int:
    if channel not in CHANNEL_PROFILES:
        raise ValueError(f"unknown canonical audio channel: {channel!r}")
    profile = CHANNEL_PROFILES[channel]
    output_dir = Path(capture_root) / "audio" / channel
    writer = OpusSegmentWriter(
        output_dir=output_dir,
        channel=channel,
        argv_builder=opusenc_argv_builder(opusenc_bin, profile),
        popen=popen,
    )
    tee = SeqpacketTee(tee_socket_path) if (channel == "mic" and tee_socket_path is not None) else None

    targets = DefaultTargets()
    restart_requested = threading.Event()

    def on_default_change(kind: str) -> None:
        wants_restart = (channel == "mic" and kind == "source") or (
            channel == "sink-monitor" and kind == "sink"
        )
        if wants_restart:
            restart_requested.set()

    watcher = DefaultWatcher(pw_metadata_bin, targets, on_default_change, popen=popen)
    watcher.start()

    stop_event = stop_event if stop_event is not None else _install_signal_stop_event()
    chunk_size = _chunk_bytes(profile)

    try:
        # Give the watcher a moment to learn the current default before the
        # first connect attempt (falls back to PipeWire's own "auto" target
        # resolution -- see pw_record_argv -- if nothing has arrived yet).
        time.sleep(0.2)
        while not stop_event.is_set():
            target = resolve_target(channel, targets)
            argv = pw_record_argv(pw_record_bin, profile, target)
            proc = popen(argv, stdout=subprocess.PIPE)
            restart_requested.clear()
            try:
                assert proc.stdout is not None
                while not stop_event.is_set() and not restart_requested.is_set():
                    chunk = proc.stdout.read(chunk_size)
                    if not chunk:
                        break
                    now = time.time()
                    if tee is not None:
                        tee.send_nonblocking(chunk)
                    writer.write(chunk, ts=now)
                    writer.maybe_rotate(now)
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
    finally:
        watcher.stop()
        writer.close()
        if tee is not None:
            tee.close()
    return 0
