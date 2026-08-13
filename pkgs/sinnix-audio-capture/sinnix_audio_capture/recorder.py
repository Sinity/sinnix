"""`pw-record` -> [tee] -> OpusSegmentWriter: the byte-moving loop, plus
the sink-monitor channel that follows PipeWire's default sink.

No VAD, no gating, no silence detection here at all -- the recorder's job
is to move bytes from PipeWire into the Opus archive (and, for the tee'd
stream, into the low-latency mirror) continuously. Silence is handled
entirely by Opus DTX inside the encoder (see segment.py); this loop has no
opinion about whether a chunk is speech or not.

`run_capture_stream` is shared by two callers with different target
policies: the sink-monitor channel resolves PipeWire's *default* sink via
`pw-metadata -n default` (pipewire_defaults.py) and restarts `pw-record`
when the operator switches outputs, while each per-source recorder
(sources.py) is pinned to one fixed node for its whole life. Capture
sources are enumerated and supervised in sources.py -- there is no single
"the microphone" channel, because no single device can be it.
"""

from __future__ import annotations

import logging
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path

from .pipewire_defaults import (
    DefaultTargets,
    parse_default_line,
    resolve_node_serial,
    resolve_target,
)
from .segment import (
    CHANNEL_PROFILES,
    ChannelProfile,
    OpusSegmentWriter,
    opusenc_argv_builder,
)

logger = logging.getLogger("sinnix_audio_capture.recorder")

# 100ms chunks: small enough to keep the mic tee's latency low, large enough
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


class DefaultWatcher(threading.Thread):
    """Runs `pw-metadata -n default` for the process lifetime and calls
    `on_change(kind)` (kind: "sink" | "source") whenever the resolved
    default actually changes."""

    def __init__(
        self,
        pw_metadata_bin: str,
        targets: DefaultTargets,
        on_change,
        *,
        popen=subprocess.Popen,
    ) -> None:
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
                [self._pw_metadata_bin, "-n", "default"],
                stdout=subprocess.PIPE,
                text=True,
            )
        except Exception:
            logger.exception(
                "sinnix-audio-capture: failed to start pw-metadata default watcher"
            )
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
                    logger.exception(
                        "sinnix-audio-capture: default-change callback failed"
                    )

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
    idle_sleep: float = 1.0,
) -> None:
    """Move PCM from `pw-record` into `writer` until stopped, reconnecting
    whenever the child exits or `restart_event` fires.

    `allow_untargeted=False` refuses to start `pw-record` while the target
    is unresolved instead of letting PipeWire pick: for a recorder pinned
    to one specific node, an auto-linked stream would silently archive a
    DIFFERENT device's audio under that node's name.
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
        if not received and not stop_event.is_set() and not restart_event.is_set():
            # A child that produced nothing and exited (device vanished mid-read,
            # node not ready) must not be respawned in a tight loop.
            stop_event.wait(idle_sleep)


def run_recorder(
    *,
    channel: str,
    capture_root: Path,
    pw_record_bin: str = "pw-record",
    pw_metadata_bin: str = "pw-metadata",
    pw_dump_bin: str = "pw-dump",
    opusenc_bin: str = "opusenc",
    stop_event: threading.Event | None = None,
    popen=subprocess.Popen,
    run=subprocess.run,
) -> int:
    if channel not in CHANNEL_PROFILES:
        raise ValueError(f"unknown canonical audio channel: {channel!r}")
    profile = CHANNEL_PROFILES[channel]
    writer = OpusSegmentWriter(
        output_dir=Path(capture_root) / "audio" / channel,
        channel=channel,
        argv_builder=opusenc_argv_builder(opusenc_bin, profile),
        popen=popen,
    )

    targets = DefaultTargets()
    restart_requested = threading.Event()

    def on_default_change(kind: str) -> None:
        if kind == "sink":
            restart_requested.set()

    watcher = DefaultWatcher(pw_metadata_bin, targets, on_default_change, popen=popen)
    watcher.start()

    stop_event = stop_event if stop_event is not None else _install_signal_stop_event()

    def target_provider() -> str | None:
        target_name = resolve_target(channel, targets)
        if not target_name:
            return None
        # Resolve to a stable object.serial rather than targeting by name:
        # `--target <name>` does not reliably attach to the right node on
        # reconnect and, even when it does, is serviced by a slow fallback
        # path instead of the real-time graph -- see resolve_node_serial's
        # docstring. Fall back to the raw name if resolution fails (pw-dump
        # error, or the node isn't visible yet).
        return resolve_node_serial(pw_dump_bin, target_name, run=run) or target_name

    try:
        # Give the watcher a moment to learn the current default before the
        # first connect attempt (falls back to PipeWire's own "auto" target
        # resolution -- see pw_record_argv -- if nothing has arrived yet).
        time.sleep(0.2)
        run_capture_stream(
            profile=profile,
            writer=writer,
            target_provider=target_provider,
            stop_event=stop_event,
            restart_event=restart_requested,
            pw_record_bin=pw_record_bin,
            popen=popen,
        )
    finally:
        watcher.stop()
        writer.close()
    return 0
