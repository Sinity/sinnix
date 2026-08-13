"""Record EVERY PipeWire audio source, minus a configured blacklist.

There is no "the microphone" on this host. Sources come and go (USB
capture devices, Bluetooth headsets, virtual sources created by
WirePlumber filters), and any single-device channel has to pick one of
them -- a choice that is wrong the moment the picked device is unplugged.
A source that is not recorded is data that does not exist, so the lane
records all of them concurrently and lets a blacklist remove the ones
known to carry nothing (a line-in jack on a DAC that only drives
speakers).

Discovery is a `pw-dump` poll (POLL_INTERVAL_SECONDS), not a `pw-mon`
subscription. `pw-mon`'s `removed:` blocks carry only an object id, so a
subscription would need its own id->node.name cache to know WHICH source
disappeared (topology.py keeps exactly that cache and still cannot
classify removals that predate its own start). A poll re-derives the full
truth every cycle and cannot drift; the cost is that a hotplugged device
goes unrecorded for up to one poll interval, and that bound is the
deliberate trade.

Per-source channel naming: the directory is `src-<sanitized node.name>`.
`node.name` is the only identifier that is stable across both reboot and
replug (it is derived from the ALSA card id / USB path, and carries the
device serial when the device reports one), which is what keeps a
device's segments in one directory over years. `node.description` ("Yeti
Nano Analog Stereo") reads better but changes when a device's profile
changes, which would silently split one device's archive across two
directories. Human- and indexer-facing identity is served instead by a
`device.json` sidecar written into each source directory, plus the
`audio-sources` lane, both of which carry the unsanitized node.name,
description and nick.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from .pipewire_defaults import DefaultTargets, resolve_node_serial
from .recorder import DefaultWatcher, run_capture_stream
from .segment import OpusSegmentWriter, opusenc_argv_builder, source_profile
from .tee import SeqpacketTee

logger = logging.getLogger("sinnix_audio_capture.sources")

SOURCES_LANE = "audio-sources"
CHANNEL_PREFIX = "src-"
DEVICE_SIDECAR_NAME = "device.json"

# Both real capture devices and WirePlumber's virtual sources (echo-cancel,
# loopbacks). A virtual source is derived data, but it is still a source
# nothing else archives, and the blacklist is the mechanism for dropping
# sources that turn out to be noise.
SOURCE_MEDIA_CLASSES = ("Audio/Source", "Audio/Source/Virtual")

POLL_INTERVAL_SECONDS = 10.0
HEARTBEAT_SECONDS = 600.0
# A source whose recorder thread died is retried on a poll cycle, but not
# every cycle: a device that fails to open (permissions, a driver in a bad
# state) would otherwise spin pw-record several times a minute forever.
FAILURE_RETRY_SECONDS = 60.0
# Coverage probe budget. Far below the hourly segment rotation: even a
# fully silent stream's DTX output flushes an Ogg page well inside this,
# so a source directory whose newest file has not been touched in this
# long is not being written to.
PROBE_MAX_AGE_SECONDS = 600.0

_SANITIZE_RE = re.compile(r"[^a-z0-9]+")


def channel_name(node_name: str) -> str:
    """Directory/segment channel name for a PipeWire source node name.

    Lossy (dots and underscores both collapse to `-`); `device.json` and
    the audio-sources lane carry the exact node.name.
    """
    slug = _SANITIZE_RE.sub("-", node_name.lower()).strip("-")
    return f"{CHANNEL_PREFIX}{slug}"


@dataclass(frozen=True)
class AudioSource:
    node_name: str
    media_class: str
    description: str | None = None
    nick: str | None = None
    serial: str | None = None
    channels: int | None = None

    @property
    def channel(self) -> str:
        return channel_name(self.node_name)

    def device_record(self) -> dict:
        return {
            "node_name": self.node_name,
            "media_class": self.media_class,
            "description": self.description,
            "nick": self.nick,
            "channels": self.channels,
            "channel": self.channel,
        }


def parse_sources(objects: Iterable) -> list[AudioSource]:
    """Extract capture sources from parsed `pw-dump` output."""
    sources: list[AudioSource] = []
    for obj in objects:
        if not isinstance(obj, dict) or obj.get("type") != "PipeWire:Interface:Node":
            continue
        props = (obj.get("info") or {}).get("props") or {}
        if props.get("media.class") not in SOURCE_MEDIA_CLASSES:
            continue
        node_name = props.get("node.name")
        if not node_name:
            continue
        channels = props.get("audio.channels")
        sources.append(
            AudioSource(
                node_name=str(node_name),
                media_class=str(props["media.class"]),
                description=props.get("node.description"),
                nick=props.get("node.nick"),
                serial=(
                    None
                    if props.get("object.serial") is None
                    else str(props["object.serial"])
                ),
                channels=int(channels) if isinstance(channels, int) else None,
            )
        )
    return sorted(sources, key=lambda s: s.node_name)


def list_sources(
    pw_dump_bin: str,
    *,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> list[AudioSource] | None:
    """Live sources, or None if the graph could not be read at all.

    None and `[]` are different answers: `[]` means PipeWire is reachable
    and has no sources, None means we do not know. Callers must not treat
    an unreadable graph as "everything disappeared" and reap recorders.
    """
    try:
        proc = run([pw_dump_bin], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    try:
        objects = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(objects, list):
        return None
    return parse_sources(objects)


def excluded_by(source: AudioSource, patterns: Iterable[str]) -> str | None:
    """The first blacklist pattern matching this source, or None.

    Patterns are case-insensitive regex searches against `node.name` and
    `node.description`. Matching on node.name (not object.serial, which is
    reassigned on every replug) is what makes an exclusion survive a
    device being unplugged and plugged back in.
    """
    haystacks = [source.node_name]
    if source.description:
        haystacks.append(source.description)
    for pattern in patterns:
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error:
            logger.warning(
                "sinnix-audio-capture: ignoring invalid exclude pattern %r", pattern
            )
            continue
        if any(compiled.search(h) for h in haystacks):
            return pattern
    return None


def write_device_sidecar(output_dir: Path, source: AudioSource) -> None:
    """Record which physical device a `src-*` directory belongs to."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / DEVICE_SIDECAR_NAME
    record = source.device_record() | {"updated": time.time()}
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def probe_coverage(
    *,
    capture_root: Path,
    pw_dump_bin: str,
    exclude_patterns: Iterable[str],
    max_age_seconds: float = PROBE_MAX_AGE_SECONDS,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    now_fn: Callable[[], float] = time.time,
) -> tuple[int, dict]:
    """Upstream-liveness probe: is every non-excluded live source actually
    being written to right now?

    Returns `(exit_code, detail)` under the sentinel's probe contract:
    0 = every included source has a freshly-written segment, 1 = at least
    one source is live and unrecorded (the exact failure a per-unit
    is-active check cannot see), anything else = unknown.
    """
    patterns = list(exclude_patterns)
    sources = list_sources(pw_dump_bin, run=run)
    if sources is None:
        return 2, {"error": "pw-dump unavailable"}
    audio_dir = Path(capture_root) / "audio"
    now = now_fn()
    covered: list[str] = []
    uncovered: list[str] = []
    excluded: list[str] = []
    for source in sources:
        if excluded_by(source, patterns) is not None:
            excluded.append(source.node_name)
            continue
        channel_dir = audio_dir / source.channel
        newest = 0.0
        if channel_dir.is_dir():
            for path in channel_dir.glob("audio-*.opus*"):
                try:
                    newest = max(newest, path.stat().st_mtime)
                except OSError:
                    continue
        if newest and (now - newest) <= max_age_seconds:
            covered.append(source.node_name)
        else:
            uncovered.append(source.node_name)
    detail = {"covered": covered, "uncovered": uncovered, "excluded": excluded}
    return (1 if uncovered else 0), detail


class _SourceRecorder(threading.Thread):
    """One live source -> one hour-rotated Opus channel directory."""

    def __init__(
        self,
        source: AudioSource,
        *,
        capture_root: Path,
        pw_record_bin: str,
        pw_dump_bin: str,
        opusenc_bin: str,
        chunk_sink: Callable[[str, bytes], None] | None,
        popen,
        run,
    ) -> None:
        super().__init__(daemon=True, name=f"sinnix-audio-source-{source.channel}")
        self.source = source
        self.started_at = time.time()
        self.error: str | None = None
        self._capture_root = Path(capture_root)
        self._pw_record_bin = pw_record_bin
        self._pw_dump_bin = pw_dump_bin
        self._opusenc_bin = opusenc_bin
        self._chunk_sink = chunk_sink
        self._popen = popen
        self._run = run
        self._stop_event = threading.Event()

    @property
    def output_dir(self) -> Path:
        return self._capture_root / "audio" / self.source.channel

    def stop(self) -> None:
        self._stop_event.set()

    def _resolve_target(self) -> str | None:
        # Serial only, never the node name: `--target <name>` silently falls
        # back to WirePlumber's default-object auto-link, which lands on the
        # wrong device and is serviced off the real-time graph. See
        # pipewire_defaults.resolve_node_serial.
        return resolve_node_serial(
            self._pw_dump_bin, self.source.node_name, run=self._run
        )

    def run(self) -> None:
        profile = source_profile(self.source.channels)
        writer = OpusSegmentWriter(
            output_dir=self.output_dir,
            channel=self.source.channel,
            argv_builder=opusenc_argv_builder(self._opusenc_bin, profile),
            popen=self._popen,
        )
        sink = (
            None
            if self._chunk_sink is None
            else (lambda data: self._chunk_sink(self.source.node_name, data))
        )
        try:
            write_device_sidecar(self.output_dir, self.source)
            run_capture_stream(
                profile=profile,
                writer=writer,
                target_provider=self._resolve_target,
                stop_event=self._stop_event,
                restart_event=threading.Event(),
                pw_record_bin=self._pw_record_bin,
                popen=self._popen,
                chunk_sink=sink,
                allow_untargeted=False,
            )
        except Exception as exc:  # thread death must be reported, not silent
            self.error = f"{type(exc).__name__}: {exc}"
            logger.exception(
                "sinnix-audio-capture: recorder for %s failed", self.source.node_name
            )
        finally:
            writer.close()


class SourceSupervisor:
    """Keeps one recorder alive per non-excluded live source."""

    def __init__(
        self,
        *,
        capture_root: Path,
        pw_record_bin: str = "pw-record",
        pw_dump_bin: str = "pw-dump",
        pw_metadata_bin: str = "pw-metadata",
        opusenc_bin: str = "opusenc",
        exclude_patterns: Iterable[str] = (),
        tee_socket_path: Path | None = None,
        poll_interval: float = POLL_INTERVAL_SECONDS,
        heartbeat_interval: float = HEARTBEAT_SECONDS,
        popen=subprocess.Popen,
        run=subprocess.run,
        writer_factory=None,
    ) -> None:
        self.capture_root = Path(capture_root)
        self.exclude_patterns = list(exclude_patterns)
        self._pw_record_bin = pw_record_bin
        self._pw_dump_bin = pw_dump_bin
        self._pw_metadata_bin = pw_metadata_bin
        self._opusenc_bin = opusenc_bin
        self._poll_interval = poll_interval
        self._heartbeat_interval = heartbeat_interval
        self._popen = popen
        self._run = run
        self._writer_factory = writer_factory
        self._recorders: dict[str, _SourceRecorder] = {}
        self._failed: dict[str, tuple[float, str]] = {}
        self._excluded: dict[str, str] = {}
        self._tee = None if tee_socket_path is None else SeqpacketTee(tee_socket_path)
        self._tee_socket_path = tee_socket_path
        self._targets = DefaultTargets()
        self._primary: str | None = None
        self._last_state: dict | None = None
        self._last_heartbeat = 0.0

    # -- tee routing -------------------------------------------------
    #
    # The tee mirrors ONE source: whichever is PipeWire's current default
    # source, i.e. the microphone the desktop itself would use. Its PCM
    # format therefore follows that device rather than being fixed, so the
    # supervisor publishes the live format in a sidecar next to the socket
    # for consumers to read.

    def _on_default_change(self, kind: str) -> None:
        if kind == "source":
            self._update_primary()

    def _update_primary(self) -> None:
        primary = self._targets.source
        if primary == self._primary:
            return
        self._primary = primary
        self._write_tee_format()

    def _write_tee_format(self) -> None:
        if self._tee_socket_path is None:
            return
        recorder = self._recorders.get(self._primary or "")
        profile = source_profile(recorder.source.channels if recorder else None)
        payload = {
            "node_name": self._primary,
            "format": "s16le",
            "rate": profile.rate,
            "channels": profile.channels,
            "updated": time.time(),
        }
        path = Path(str(self._tee_socket_path) + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    def _tee_chunk(self, node_name: str, data: bytes) -> None:
        if self._tee is not None and node_name == self._primary:
            self._tee.send_nonblocking(data)

    # -- state lane --------------------------------------------------

    def state_payload(self, reason: str) -> dict:
        return {
            "kind": "sources-state",
            "reason": reason,
            "primary": self._primary,
            "recording": [
                {
                    "node_name": name,
                    "channel": rec.source.channel,
                    "description": rec.source.description,
                    "since": rec.started_at,
                }
                for name, rec in sorted(self._recorders.items())
            ],
            "excluded": [
                {"node_name": name, "pattern": pattern}
                for name, pattern in sorted(self._excluded.items())
            ],
            "failed": [
                {"node_name": name, "error": error, "at": at}
                for name, (at, error) in sorted(self._failed.items())
            ],
        }

    def _emit_state(self, writer, now: float) -> None:
        """Write the lane record on every state change, plus an unconditional
        heartbeat: without one, an idle-but-healthy supervisor is
        indistinguishable from a dead one to the staleness budget."""
        payload = self.state_payload("change")
        comparable = {k: v for k, v in payload.items() if k != "reason"}
        changed = comparable != self._last_state
        heartbeat_due = (now - self._last_heartbeat) >= self._heartbeat_interval
        if not changed and not heartbeat_due:
            return
        if not changed:
            payload["reason"] = "heartbeat"
        writer.write(payload)
        self._last_state = comparable
        self._last_heartbeat = now

    # -- supervision -------------------------------------------------

    def _start(self, source: AudioSource) -> None:
        recorder = _SourceRecorder(
            source,
            capture_root=self.capture_root,
            pw_record_bin=self._pw_record_bin,
            pw_dump_bin=self._pw_dump_bin,
            opusenc_bin=self._opusenc_bin,
            chunk_sink=self._tee_chunk if self._tee is not None else None,
            popen=self._popen,
            run=self._run,
        )
        self._recorders[source.node_name] = recorder
        recorder.start()
        logger.info(
            "sinnix-audio-capture: recording %s -> %s",
            source.node_name,
            source.channel,
        )

    def _reap(self, node_name: str, *, now: float, reason: str) -> None:
        recorder = self._recorders.pop(node_name, None)
        if recorder is None:
            return
        recorder.stop()
        recorder.join(timeout=10.0)
        if recorder.error is not None:
            self._failed[node_name] = (now, recorder.error)
        logger.info(
            "sinnix-audio-capture: stopped recording %s (%s)", node_name, reason
        )

    def reconcile(self, sources: list[AudioSource], *, now: float) -> None:
        live = {source.node_name: source for source in sources}
        self._excluded = {}
        wanted: dict[str, AudioSource] = {}
        for node_name, source in live.items():
            pattern = excluded_by(source, self.exclude_patterns)
            if pattern is None:
                wanted[node_name] = source
            else:
                self._excluded[node_name] = pattern

        for node_name in list(self._recorders):
            recorder = self._recorders[node_name]
            if node_name not in wanted:
                self._reap(node_name, now=now, reason="source gone or excluded")
            elif not recorder.is_alive():
                self._reap(node_name, now=now, reason="recorder thread exited")

        for node_name, source in wanted.items():
            if node_name in self._recorders:
                self._failed.pop(node_name, None)
                continue
            failed_at = self._failed.get(node_name)
            if failed_at is not None and (now - failed_at[0]) < FAILURE_RETRY_SECONDS:
                continue
            self._start(source)
        self._update_primary()

    def run(self, *, stop_event: threading.Event) -> int:
        from sinnix_capture.writer import CaptureWriter

        writer_factory = self._writer_factory or (
            lambda: CaptureWriter(self.capture_root, SOURCES_LANE)
        )
        writer = writer_factory()
        watcher = DefaultWatcher(
            self._pw_metadata_bin,
            self._targets,
            self._on_default_change,
            popen=self._popen,
        )
        watcher.start()
        try:
            while not stop_event.is_set():
                now = time.time()
                sources = list_sources(self._pw_dump_bin, run=self._run)
                if sources is None:
                    logger.warning(
                        "sinnix-audio-capture: pw-dump unreadable; keeping current recorders"
                    )
                else:
                    self.reconcile(sources, now=now)
                self._emit_state(writer, now)
                if stop_event.wait(self._poll_interval):
                    break
        finally:
            watcher.stop()
            for node_name in list(self._recorders):
                self._reap(node_name, now=time.time(), reason="shutdown")
            if self._tee is not None:
                self._tee.close()
        return 0


def run_sources(
    *,
    capture_root: Path,
    exclude_patterns: Iterable[str] = (),
    pw_record_bin: str = "pw-record",
    pw_dump_bin: str = "pw-dump",
    pw_metadata_bin: str = "pw-metadata",
    opusenc_bin: str = "opusenc",
    tee_socket_path: Path | None = None,
    poll_interval: float = POLL_INTERVAL_SECONDS,
    stop_event: threading.Event | None = None,
) -> int:
    from .recorder import _install_signal_stop_event

    supervisor = SourceSupervisor(
        capture_root=capture_root,
        exclude_patterns=exclude_patterns,
        pw_record_bin=pw_record_bin,
        pw_dump_bin=pw_dump_bin,
        pw_metadata_bin=pw_metadata_bin,
        opusenc_bin=opusenc_bin,
        tee_socket_path=tee_socket_path,
        poll_interval=poll_interval,
    )
    stop_event = stop_event if stop_event is not None else _install_signal_stop_event()
    return supervisor.run(stop_event=stop_event)
