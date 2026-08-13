"""Record EVERY PipeWire audio device, minus a configured blacklist.

Capture sources and playback sinks are treated symmetrically here, because
they failed the same way: a channel bound to "the default source" recorded
a line-in with nothing plugged into it, and a channel bound to "the default
sink" recorded nothing at all whenever playback moved to Bluetooth
headphones. A role is not a device. This module enumerates devices and
records each one, so the archive stops depending on which device the
desktop happened to prefer at the time.

  - Sources are recorded directly.
  - Sinks are recorded through their monitor ports. There is no separate
    `<sink>.monitor` node in this graph -- verified against live `pw-dump`:
    no node's name ends in `.monitor`, while a sink node itself carries
    `monitor_FL`/`monitor_FR` ports with `port.monitor = true`. A
    Capture-direction stream resolved onto the sink node attaches to those
    ports, which is why the target here is the SINK's own object.serial.
    Targeting `<sink>.monitor` by name resolves to nothing and silently
    falls back to WirePlumber's auto-link onto an unrelated device.

Recording every sink monitor at once does duplicate audio when two sinks
carry the same stream. That is accepted deliberately: the duplicate costs
almost nothing (Opus DTX collapses the silent ones), each sink is a
distinct rendering at its own volume and DSP chain, and the alternative --
guessing which sink "really" played something -- is the same
role-over-device guess this module exists to remove.

Discovery is a `pw-dump` poll (POLL_INTERVAL_SECONDS), not a `pw-mon`
subscription. `pw-mon`'s `removed:` blocks carry only an object id, so a
subscription would need its own id->node.name cache to know WHICH device
disappeared (topology.py keeps exactly that cache and still cannot
classify removals that predate its own start). A poll re-derives the full
truth every cycle and cannot drift. It costs ~13ms of one core per cycle,
and the price paid for it is that a hotplugged device goes unrecorded for
up to one poll interval.

Per-device channel naming: the directory is `<prefix><sanitized
node.name>`, `src-` for sources and `snk-` for sink monitors.
`node.name` is the only identifier stable across both reboot and replug
(it is derived from the ALSA card id / USB path or the Bluetooth MAC, and
carries the device serial when the device reports one), which is what
keeps a device's segments in one directory over years.
`node.description` ("Yeti Nano Analog Stereo") reads better but changes
when a device's profile changes, which would silently split one device's
archive across two directories. Human- and indexer-facing identity is
served instead by a `device.json` sidecar written into each directory,
plus the `audio-devices` lane, both of which carry the unsanitized
node.name, description and nick.
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

from .recorder import run_capture_stream
from .segment import OpusSegmentWriter, device_profile, opusenc_argv_builder
from .tee import SeqpacketTee

logger = logging.getLogger("sinnix_audio_capture.devices")

DEVICES_LANE = "audio-devices"
DEVICE_SIDECAR_NAME = "device.json"

# Virtual sources (echo-cancel, loopbacks) are derived data, but they are
# still devices nothing else archives; the blacklist is the mechanism for
# dropping any that turn out to be noise.
MEDIA_CLASSES = {
    "source": ("Audio/Source", "Audio/Source/Virtual"),
    "sink": ("Audio/Sink",),
}
CHANNEL_PREFIX = {"source": "src-", "sink": "snk-"}

POLL_INTERVAL_SECONDS = 10.0
HEARTBEAT_SECONDS = 600.0
# A device whose recorder thread died is retried on a poll cycle, but not
# every cycle: a device that fails to open (permissions, a driver in a bad
# state) would otherwise spin pw-record several times a minute forever.
FAILURE_RETRY_SECONDS = 60.0
# Coverage probe budget. Far below the hourly segment rotation: even a
# fully silent stream's DTX output flushes an Ogg page well inside this,
# so a device directory whose newest file has not been touched in this
# long is not being written to.
PROBE_MAX_AGE_SECONDS = 600.0
# How long a reaped recorder gets to finalise its segment. opusenc only
# produces a valid Ogg file once its stdin reaches EOF, so an unplugged
# device must be given time to close the pipe and let the encoder exit --
# never killed at the first opportunity.
REAP_TIMEOUT_SECONDS = 15.0

_SANITIZE_RE = re.compile(r"[^a-z0-9]+")


def channel_name(kind: str, node_name: str) -> str:
    """Directory/segment channel name for a PipeWire node.

    Lossy (dots and underscores both collapse to `-`); `device.json` and
    the audio-devices lane carry the exact node.name.
    """
    slug = _SANITIZE_RE.sub("-", node_name.lower()).strip("-")
    return f"{CHANNEL_PREFIX[kind]}{slug}"


@dataclass(frozen=True)
class AudioDevice:
    node_name: str
    kind: str  # "source" | "sink"
    media_class: str
    description: str | None = None
    nick: str | None = None
    serial: str | None = None
    channels: int | None = None

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.node_name}"

    @property
    def channel(self) -> str:
        return channel_name(self.kind, self.node_name)

    def device_record(self) -> dict:
        return {
            "node_name": self.node_name,
            "kind": self.kind,
            "media_class": self.media_class,
            "description": self.description,
            "nick": self.nick,
            "channels": self.channels,
            "channel": self.channel,
        }


def parse_devices(objects: Iterable) -> list[AudioDevice]:
    """Extract recordable devices from parsed `pw-dump` output."""
    by_class = {
        media_class: kind
        for kind, classes in MEDIA_CLASSES.items()
        for media_class in classes
    }
    devices: list[AudioDevice] = []
    for obj in objects:
        if not isinstance(obj, dict) or obj.get("type") != "PipeWire:Interface:Node":
            continue
        props = (obj.get("info") or {}).get("props") or {}
        kind = by_class.get(props.get("media.class"))
        if kind is None:
            continue
        node_name = props.get("node.name")
        if not node_name:
            continue
        channels = props.get("audio.channels")
        devices.append(
            AudioDevice(
                node_name=str(node_name),
                kind=kind,
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
    return sorted(devices, key=lambda d: d.key)


def list_devices(
    pw_dump_bin: str,
    *,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> list[AudioDevice] | None:
    """Live devices, or None if the graph could not be read at all.

    None and `[]` are different answers: `[]` means PipeWire is reachable
    and has no devices, None means we do not know. Callers must not treat
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
    return parse_devices(objects)


def resolve_node_serial(
    pw_dump_bin: str,
    node_name: str,
    *,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> str | None:
    """Resolve a node name to its current `object.serial`, for use as a
    `pw-record --target` value.

    Do not pass a node name as `--target`. `pw-record --target <node-name>`
    does *string* name matching and does not reliably attach a
    Capture-direction stream to the right node once the connection is
    re-established mid-session: the stream falls back to WirePlumber's
    default-object auto-link, which silently lands on the wrong device, and
    even when the fallback picks the right device that link is serviced by
    a slow reconnect path rather than the real-time audio graph, delivering
    PCM in bursts seconds apart and losing most of the hour.

    The serial is deliberately re-resolved on every connect rather than
    cached: it is stable for a node's lifetime but NOT across a replug, and
    a hotplugged device can reuse a node name while being an entirely
    different node.

    Returns None if `pw-dump` fails or no node with that name is currently
    present.
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
    for obj in objects:
        if not isinstance(obj, dict) or obj.get("type") != "PipeWire:Interface:Node":
            continue
        props = (obj.get("info") or {}).get("props") or {}
        if props.get("node.name") == node_name:
            serial = props.get("object.serial")
            if serial is not None:
                return str(serial)
    return None


def matches_any(device: AudioDevice, patterns: Iterable[str]) -> str | None:
    """The first pattern matching this device, or None.

    Patterns are case-insensitive regex searches against `node.name` and
    `node.description`. Matching on node.name (not object.serial, which is
    reassigned on every replug) is what makes a match survive a device
    being unplugged and plugged back in. Note that node.name also encodes
    direction (`alsa_input.` vs `alsa_output.`), so one device's capture
    side can be excluded while its playback side keeps being recorded.
    """
    haystacks = [device.node_name]
    if device.description:
        haystacks.append(device.description)
    for pattern in patterns:
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error:
            logger.warning("sinnix-audio-capture: ignoring invalid pattern %r", pattern)
            continue
        if any(compiled.search(h) for h in haystacks):
            return pattern
    return None


def write_device_sidecar(output_dir: Path, device: AudioDevice) -> None:
    """Record which physical device a channel directory belongs to."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / DEVICE_SIDECAR_NAME
    record = device.device_record() | {"updated": time.time()}
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def probe_coverage(
    *,
    capture_root: Path,
    pw_dump_bin: str,
    exclude_patterns: dict[str, list[str]] | None = None,
    max_age_seconds: float = PROBE_MAX_AGE_SECONDS,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    now_fn: Callable[[], float] = time.time,
) -> tuple[int, dict]:
    """Upstream-liveness probe: is every non-excluded live device actually
    being written to right now?

    Returns `(exit_code, detail)` under the sentinel's probe contract:
    0 = every included device has a freshly-written segment, 1 = at least
    one device is live and unrecorded (the exact failure a per-unit
    is-active check cannot see), anything else = unknown.
    """
    patterns = exclude_patterns or {}
    devices = list_devices(pw_dump_bin, run=run)
    if devices is None:
        return 2, {"error": "pw-dump unavailable"}
    audio_dir = Path(capture_root) / "audio"
    now = now_fn()
    covered: list[str] = []
    uncovered: list[str] = []
    excluded: list[str] = []
    for device in devices:
        if matches_any(device, patterns.get(device.kind, [])) is not None:
            excluded.append(device.key)
            continue
        channel_dir = audio_dir / device.channel
        newest = 0.0
        if channel_dir.is_dir():
            for path in channel_dir.glob("audio-*.opus*"):
                try:
                    newest = max(newest, path.stat().st_mtime)
                except OSError:
                    continue
        if newest and (now - newest) <= max_age_seconds:
            covered.append(device.key)
        else:
            uncovered.append(device.key)
    detail = {"covered": covered, "uncovered": uncovered, "excluded": excluded}
    return (1 if uncovered else 0), detail


class _DeviceRecorder(threading.Thread):
    """One live device -> one hour-rotated Opus channel directory."""

    def __init__(
        self,
        device: AudioDevice,
        *,
        capture_root: Path,
        pw_record_bin: str,
        pw_dump_bin: str,
        opusenc_bin: str,
        chunk_sink: Callable[[str, bytes], None] | None,
        popen,
        run,
    ) -> None:
        super().__init__(daemon=True, name=f"sinnix-audio-{device.channel}")
        self.device = device
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
        self._restart_event = threading.Event()
        self._child: subprocess.Popen | None = None

    @property
    def output_dir(self) -> Path:
        return self._capture_root / "audio" / self.device.channel

    def _note_child(self, proc: subprocess.Popen | None) -> None:
        self._child = proc

    def stop(self) -> None:
        """Ask the thread to finish. The pw-record child is terminated so a
        blocking read returns: without that, a device that stops producing
        without closing its stream would leave the loop parked in read()
        and the segment unfinalised."""
        self._stop_event.set()
        child = self._child
        if child is not None:
            try:
                child.terminate()
            except OSError:
                pass

    def request_restart(self, device: AudioDevice) -> None:
        """Reconnect against `device`, which carries a new object.serial for
        the same node name -- a replug where the name was reused."""
        self.device = device
        self._restart_event.set()

    def _resolve_target(self) -> str | None:
        # Serial only, never the node name: `--target <name>` silently falls
        # back to WirePlumber's default-object auto-link, which lands on the
        # wrong device and is serviced off the real-time graph. For a sink
        # this is the SINK's serial -- its monitor ports live on the sink
        # node itself; see the module docstring.
        return resolve_node_serial(
            self._pw_dump_bin, self.device.node_name, run=self._run
        )

    def run(self) -> None:
        profile = device_profile(self.device.channels)
        writer = OpusSegmentWriter(
            output_dir=self.output_dir,
            channel=self.device.channel,
            argv_builder=opusenc_argv_builder(self._opusenc_bin, profile),
            popen=self._popen,
        )
        sink = (
            None
            if self._chunk_sink is None
            else (lambda data: self._chunk_sink(self.device.node_name, data))
        )
        try:
            write_device_sidecar(self.output_dir, self.device)
            run_capture_stream(
                profile=profile,
                writer=writer,
                target_provider=self._resolve_target,
                stop_event=self._stop_event,
                restart_event=self._restart_event,
                pw_record_bin=self._pw_record_bin,
                popen=self._popen,
                chunk_sink=sink,
                allow_untargeted=False,
                on_child=self._note_child,
            )
        except Exception as exc:  # thread death must be reported, not silent
            self.error = f"{type(exc).__name__}: {exc}"
            logger.exception(
                "sinnix-audio-capture: recorder for %s failed", self.device.key
            )
        finally:
            # Finalises the segment: closes opusenc's stdin, waits for it to
            # exit, then renames away `.partial`.
            writer.close()


class DeviceSupervisor:
    """Keeps one recorder alive per non-excluded live device."""

    def __init__(
        self,
        *,
        capture_root: Path,
        pw_record_bin: str = "pw-record",
        pw_dump_bin: str = "pw-dump",
        opusenc_bin: str = "opusenc",
        exclude_patterns: dict[str, list[str]] | None = None,
        asr_source_pattern: str | None = None,
        tee_socket_path: Path | None = None,
        poll_interval: float = POLL_INTERVAL_SECONDS,
        heartbeat_interval: float = HEARTBEAT_SECONDS,
        popen=subprocess.Popen,
        run=subprocess.run,
        writer_factory=None,
    ) -> None:
        self.capture_root = Path(capture_root)
        self.exclude_patterns = exclude_patterns or {}
        self.asr_source_pattern = asr_source_pattern
        self._pw_record_bin = pw_record_bin
        self._pw_dump_bin = pw_dump_bin
        self._opusenc_bin = opusenc_bin
        self._poll_interval = poll_interval
        self._heartbeat_interval = heartbeat_interval
        self._popen = popen
        self._run = run
        self._writer_factory = writer_factory
        self._recorders: dict[str, _DeviceRecorder] = {}
        # Recorders that were asked to stop but have not finished finalising
        # their segment. A key in here must never be restarted: two writers
        # on one output path corrupt the segment being closed.
        self._draining: dict[str, _DeviceRecorder] = {}
        self._failed: dict[str, tuple[float, str]] = {}
        self._excluded: dict[str, str] = {}
        self._tee = None if tee_socket_path is None else SeqpacketTee(tee_socket_path)
        self._tee_socket_path = tee_socket_path
        self._asr_node: str | None = None
        self._last_state: dict | None = None
        self._last_heartbeat = 0.0

    # -- ASR tee -----------------------------------------------------
    #
    # Capture is exhaustive; transcription is not. The tee mirrors exactly
    # one nominated source (asr_source_pattern) into a low-latency socket
    # for an ASR consumer. This is deliberately NOT a "primary" or
    # "default" channel: no lane is privileged, the archive treats every
    # device identically, and changing which device feeds ASR changes
    # nothing about what gets recorded.

    def _select_asr_node(self) -> None:
        node: str | None = None
        if self.asr_source_pattern:
            for recorder in sorted(
                self._recorders.values(), key=lambda r: r.device.key
            ):
                device = recorder.device
                if device.kind == "source" and matches_any(
                    device, [self.asr_source_pattern]
                ):
                    node = device.node_name
                    break
        if node == self._asr_node:
            return
        self._asr_node = node
        self._write_tee_format()

    def _write_tee_format(self) -> None:
        """Publish the tee's PCM format: it follows the nominated device, so
        a consumer cannot assume one."""
        if self._tee_socket_path is None:
            return
        recorder = next(
            (
                r
                for r in self._recorders.values()
                if r.device.node_name == self._asr_node
            ),
            None,
        )
        profile = device_profile(recorder.device.channels if recorder else None)
        payload = {
            "node_name": self._asr_node,
            "format": "s16le",
            "rate": profile.rate,
            "channels": profile.channels,
            "updated": time.time(),
        }
        path = Path(str(self._tee_socket_path) + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    def _tee_chunk(self, node_name: str, data: bytes) -> None:
        if self._tee is not None and node_name == self._asr_node:
            self._tee.send_nonblocking(data)

    # -- state lane --------------------------------------------------

    def state_payload(self, reason: str) -> dict:
        return {
            "kind": "devices-state",
            "reason": reason,
            "asr_source": self._asr_node,
            "recording": [
                {
                    "node_name": rec.device.node_name,
                    "device_kind": rec.device.kind,
                    "channel": rec.device.channel,
                    "description": rec.device.description,
                    "since": rec.started_at,
                }
                for _, rec in sorted(self._recorders.items())
            ],
            "excluded": [
                {"key": key, "pattern": pattern}
                for key, pattern in sorted(self._excluded.items())
            ],
            "draining": sorted(self._draining),
            "failed": [
                {"key": key, "error": error, "at": at}
                for key, (at, error) in sorted(self._failed.items())
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

    def _start(self, device: AudioDevice) -> None:
        recorder = _DeviceRecorder(
            device,
            capture_root=self.capture_root,
            pw_record_bin=self._pw_record_bin,
            pw_dump_bin=self._pw_dump_bin,
            opusenc_bin=self._opusenc_bin,
            chunk_sink=self._tee_chunk if self._tee is not None else None,
            popen=self._popen,
            run=self._run,
        )
        self._recorders[device.key] = recorder
        recorder.start()
        logger.info(
            "sinnix-audio-capture: recording %s -> %s", device.key, device.channel
        )

    def _reap(self, key: str, *, now: float, reason: str) -> None:
        recorder = self._recorders.pop(key, None)
        if recorder is None:
            return
        recorder.stop()
        recorder.join(timeout=REAP_TIMEOUT_SECONDS)
        if recorder.is_alive():
            # Still finalising (or wedged). Park it so the next cycle can
            # retire it, and keep the key un-restartable until it is gone.
            self._draining[key] = recorder
            logger.warning(
                "sinnix-audio-capture: %s still finalising after %.0fs",
                key,
                REAP_TIMEOUT_SECONDS,
            )
            return
        if recorder.error is not None:
            self._failed[key] = (now, recorder.error)
        logger.info("sinnix-audio-capture: stopped recording %s (%s)", key, reason)

    def _drain(self) -> None:
        for key, recorder in list(self._draining.items()):
            if not recorder.is_alive():
                del self._draining[key]
                logger.info("sinnix-audio-capture: %s finished finalising", key)

    def reconcile(self, devices: list[AudioDevice], *, now: float) -> None:
        self._drain()
        live = {device.key: device for device in devices}
        self._excluded = {}
        # A failure belongs to a device that is still here. Keeping the record
        # after the device is gone would report a permanently failed device
        # that nothing can retry.
        self._failed = {
            key: value for key, value in self._failed.items() if key in live
        }
        wanted: dict[str, AudioDevice] = {}
        for key, device in live.items():
            pattern = matches_any(device, self.exclude_patterns.get(device.kind, []))
            if pattern is None:
                wanted[key] = device
            else:
                self._excluded[key] = pattern

        for key in list(self._recorders):
            recorder = self._recorders[key]
            if key not in wanted:
                self._reap(key, now=now, reason="device gone or excluded")
            elif not recorder.is_alive():
                self._reap(key, now=now, reason="recorder thread exited")
            elif wanted[key].serial != recorder.device.serial:
                # Same node name, different node: a replug that reused the
                # name. The existing stream points at a serial that no longer
                # exists, so reconnect rather than keep a dead pipe open.
                logger.info(
                    "sinnix-audio-capture: %s changed serial %s -> %s, reconnecting",
                    key,
                    recorder.device.serial,
                    wanted[key].serial,
                )
                recorder.request_restart(wanted[key])
                write_device_sidecar(recorder.output_dir, wanted[key])

        for key, device in wanted.items():
            if key in self._recorders or key in self._draining:
                continue
            failed_at = self._failed.get(key)
            if failed_at is not None and (now - failed_at[0]) < FAILURE_RETRY_SECONDS:
                continue
            self._start(device)
        self._select_asr_node()

    def run(self, *, stop_event: threading.Event) -> int:
        from sinnix_capture.writer import CaptureWriter

        writer_factory = self._writer_factory or (
            lambda: CaptureWriter(self.capture_root, DEVICES_LANE)
        )
        writer = writer_factory()
        try:
            while not stop_event.is_set():
                now = time.time()
                devices = list_devices(self._pw_dump_bin, run=self._run)
                if devices is None:
                    logger.warning(
                        "sinnix-audio-capture: pw-dump unreadable; keeping current recorders"
                    )
                else:
                    self.reconcile(devices, now=now)
                self._emit_state(writer, now)
                if stop_event.wait(self._poll_interval):
                    break
        finally:
            for key in list(self._recorders):
                self._reap(key, now=time.time(), reason="shutdown")
            for recorder in self._draining.values():
                recorder.join(timeout=REAP_TIMEOUT_SECONDS)
            if self._tee is not None:
                self._tee.close()
        return 0


def run_devices(
    *,
    capture_root: Path,
    exclude_sources: Iterable[str] = (),
    exclude_sinks: Iterable[str] = (),
    asr_source_pattern: str | None = None,
    pw_record_bin: str = "pw-record",
    pw_dump_bin: str = "pw-dump",
    opusenc_bin: str = "opusenc",
    tee_socket_path: Path | None = None,
    poll_interval: float = POLL_INTERVAL_SECONDS,
    stop_event: threading.Event | None = None,
) -> int:
    from .recorder import install_signal_stop_event
    from .segment import promote_orphan_partials

    # Before any recorder opens a segment: whatever `.partial` files exist now
    # were left by a previous process, and only this window can tell them apart
    # from live ones.
    for path in promote_orphan_partials(Path(capture_root) / "audio"):
        print(f"promoted orphaned segment {path.name}", flush=True)

    supervisor = DeviceSupervisor(
        capture_root=capture_root,
        exclude_patterns={
            "source": list(exclude_sources),
            "sink": list(exclude_sinks),
        },
        asr_source_pattern=asr_source_pattern,
        pw_record_bin=pw_record_bin,
        pw_dump_bin=pw_dump_bin,
        opusenc_bin=opusenc_bin,
        tee_socket_path=tee_socket_path,
        poll_interval=poll_interval,
    )
    stop_event = stop_event if stop_event is not None else install_signal_stop_event()
    return supervisor.run(stop_event=stop_event)
