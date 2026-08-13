from __future__ import annotations

import json
from pathlib import Path

from sinnix_audio_capture.sources import (
    AudioSource,
    SourceSupervisor,
    channel_name,
    excluded_by,
    parse_sources,
    probe_coverage,
    write_device_sidecar,
)

YETI = "alsa_input.usb-Blue_Microphones_Yeti_Nano_2110SG002XQ8_888-000438040606-00.analog-stereo"
FIIO = "alsa_input.usb-FiiO_DigiHug_USB_Audio-01.analog-stereo"


def _node(name: str, media_class: str = "Audio/Source", **props) -> dict:
    return {
        "type": "PipeWire:Interface:Node",
        "info": {"props": {"node.name": name, "media.class": media_class, **props}},
    }


def test_parse_sources_keeps_sources_and_drops_sinks_and_streams():
    objects = [
        _node(
            YETI,
            **{
                "node.description": "Yeti Nano Analog Stereo",
                "audio.channels": 2,
                "object.serial": 32703,
            },
        ),
        _node("alsa_output.pci-0000_00_1f.3.analog-stereo", "Audio/Sink"),
        _node("Firefox", "Stream/Output/Audio"),
        _node("echo-cancel-source", "Audio/Source/Virtual"),
        {"type": "PipeWire:Interface:Link", "info": {}},
    ]
    sources = parse_sources(objects)
    assert [s.node_name for s in sources] == [YETI, "echo-cancel-source"]
    yeti = sources[0]
    assert yeti.channels == 2
    assert yeti.serial == "32703"
    assert yeti.description == "Yeti Nano Analog Stereo"


def test_channel_name_is_stable_and_distinguishes_similar_devices():
    assert channel_name(YETI).startswith(
        "src-alsa-input-usb-blue-microphones-yeti-nano"
    )
    assert channel_name(YETI) != channel_name(FIIO)
    # Two identical models are distinguished by the port/serial component
    # ALSA already puts in node.name.
    a = "alsa_input.usb-Generic_Mic-00.analog-stereo"
    b = "alsa_input.usb-Generic_Mic-01.analog-stereo"
    assert channel_name(a) != channel_name(b)
    assert " " not in channel_name("Some Weird.Node_Name")


def test_excluded_by_matches_node_name_and_description_case_insensitively():
    fiio = AudioSource(
        node_name=FIIO, media_class="Audio/Source", description="Fiio E10 Analog Stereo"
    )
    yeti = AudioSource(
        node_name=YETI,
        media_class="Audio/Source",
        description="Yeti Nano Analog Stereo",
    )
    patterns = [r"^alsa_input\.usb-FiiO_DigiHug_USB_Audio"]
    assert excluded_by(fiio, patterns) == patterns[0]
    assert excluded_by(yeti, patterns) is None
    assert excluded_by(yeti, ["yeti nano"]) == "yeti nano"
    # An unparseable pattern is skipped, never fatal: a bad blacklist entry
    # must not take the whole capture lane down.
    assert excluded_by(yeti, ["*bad(", "yeti"]) == "yeti"


def test_probe_reports_uncovered_source(tmp_path: Path):
    dump = json.dumps(
        [
            _node(YETI, **{"audio.channels": 2}),
            _node(FIIO, **{"node.description": "Fiio E10 Analog Stereo"}),
        ]
    )

    def fake_run(argv, **kwargs):
        class R:
            stdout = dump

        return R()

    patterns = [r"FiiO_DigiHug"]
    code, detail = probe_coverage(
        capture_root=tmp_path,
        pw_dump_bin="pw-dump",
        exclude_patterns=patterns,
        run=fake_run,
    )
    assert code == 1  # confirmed absent: the Yeti is live and unrecorded
    assert detail["uncovered"] == [YETI]
    assert detail["excluded"] == [FIIO]

    seg = (
        tmp_path
        / "audio"
        / channel_name(YETI)
        / "audio-x-20260813T200000Z.opus.partial"
    )
    seg.parent.mkdir(parents=True)
    seg.write_bytes(b"x")
    code, detail = probe_coverage(
        capture_root=tmp_path,
        pw_dump_bin="pw-dump",
        exclude_patterns=patterns,
        run=fake_run,
    )
    assert code == 0
    assert detail["covered"] == [YETI]


def test_probe_returns_unknown_when_graph_unreadable(tmp_path: Path):
    def fake_run(argv, **kwargs):
        raise OSError("no pw-dump")

    code, detail = probe_coverage(
        capture_root=tmp_path, pw_dump_bin="pw-dump", exclude_patterns=[], run=fake_run
    )
    # Not 0 and not 1: an unreadable graph is unknown, never "healthy".
    assert code == 2
    assert "error" in detail


def test_device_sidecar_records_unsanitized_identity(tmp_path: Path):
    source = AudioSource(
        node_name=YETI,
        media_class="Audio/Source",
        description="Yeti Nano Analog Stereo",
        channels=2,
    )
    write_device_sidecar(tmp_path, source)
    record = json.loads((tmp_path / "device.json").read_text())
    assert record["node_name"] == YETI
    assert record["channel"] == channel_name(YETI)
    assert record["description"] == "Yeti Nano Analog Stereo"


class _FakeRecorder:
    def __init__(self, source):
        self.source = source
        self.started_at = 0.0
        self.error = None
        self.stopped = False

    def is_alive(self):
        return not self.stopped

    def start(self):
        pass

    def stop(self):
        self.stopped = True

    def join(self, timeout=None):
        pass


def _supervisor(tmp_path: Path, patterns) -> SourceSupervisor:
    sup = SourceSupervisor(capture_root=tmp_path, exclude_patterns=patterns)
    sup._start = lambda source: sup._recorders.__setitem__(  # noqa: SLF001
        source.node_name, _FakeRecorder(source)
    )
    return sup


def test_reconcile_starts_reaps_and_never_records_excluded(tmp_path: Path):
    patterns = [r"FiiO_DigiHug"]
    sup = _supervisor(tmp_path, patterns)
    yeti = AudioSource(node_name=YETI, media_class="Audio/Source", channels=2)
    fiio = AudioSource(node_name=FIIO, media_class="Audio/Source")
    builtin = AudioSource(
        node_name="alsa_input.pci-0000_00_1f.3.analog-stereo",
        media_class="Audio/Source",
    )

    sup.reconcile([yeti, fiio, builtin], now=100.0)
    assert set(sup._recorders) == {YETI, builtin.node_name}
    state = sup.state_payload("change")
    assert [e["node_name"] for e in state["excluded"]] == [FIIO]
    assert {e["node_name"] for e in state["recording"]} == {YETI, builtin.node_name}

    # Unplug: the recorder is stopped and reaped, and the remaining source
    # keeps its own recorder untouched.
    kept = sup._recorders[builtin.node_name]
    sup.reconcile([builtin, fiio], now=200.0)
    assert set(sup._recorders) == {builtin.node_name}
    assert sup._recorders[builtin.node_name] is kept

    # Replug: recorded again.
    sup.reconcile([yeti, builtin, fiio], now=300.0)
    assert set(sup._recorders) == {YETI, builtin.node_name}


def test_failed_recorder_is_reported_and_retried_with_backoff(tmp_path: Path):
    sup = _supervisor(tmp_path, [])
    yeti = AudioSource(node_name=YETI, media_class="Audio/Source")
    sup.reconcile([yeti], now=100.0)
    recorder = sup._recorders[YETI]
    recorder.stopped = True  # thread died
    recorder.error = "RuntimeError: boom"

    sup.reconcile([yeti], now=101.0)
    assert sup._recorders == {}
    assert sup.state_payload("change")["failed"] == [
        {"node_name": YETI, "error": "RuntimeError: boom", "at": 101.0}
    ]

    sup.reconcile([yeti], now=200.0)  # past FAILURE_RETRY_SECONDS
    assert set(sup._recorders) == {YETI}


def test_failure_record_is_dropped_when_the_device_goes_away(tmp_path: Path):
    sup = _supervisor(tmp_path, [])
    yeti = AudioSource(node_name=YETI, media_class="Audio/Source")
    sup.reconcile([yeti], now=100.0)
    sup._recorders[YETI].stopped = True
    sup._recorders[YETI].error = "RuntimeError: boom"
    sup.reconcile([yeti], now=101.0)
    assert sup.state_payload("change")["failed"]

    sup.reconcile([], now=102.0)
    assert sup.state_payload("change")["failed"] == []


class _CapturingWriter:
    def __init__(self):
        self.records = []

    def write(self, payload, raw_ref=None, ts=None):
        self.records.append(payload)
        return payload


def test_state_lane_writes_on_change_and_heartbeats_when_idle(tmp_path: Path):
    sup = _supervisor(tmp_path, [])
    writer = _CapturingWriter()
    yeti = AudioSource(node_name=YETI, media_class="Audio/Source")

    sup.reconcile([yeti], now=100.0)
    sup._emit_state(writer, 100.0)
    sup._emit_state(writer, 110.0)  # unchanged, heartbeat not due
    assert [r["reason"] for r in writer.records] == ["change"]

    sup._emit_state(writer, 100.0 + sup._heartbeat_interval)
    assert [r["reason"] for r in writer.records] == ["change", "heartbeat"]


def test_tee_only_mirrors_the_default_source(tmp_path: Path):
    socket_path = tmp_path / "run" / "mic.pcm"
    sup = SourceSupervisor(capture_root=tmp_path, tee_socket_path=socket_path)
    sent = []
    sup._tee = type(
        "T", (), {"send_nonblocking": lambda self, data: sent.append(data)}
    )()
    sup._targets.source = YETI
    sup._update_primary()

    sup._tee_chunk(FIIO, b"other-device")
    sup._tee_chunk(YETI, b"primary")
    assert sent == [b"primary"]

    fmt = json.loads(Path(str(socket_path) + ".json").read_text())
    assert fmt["node_name"] == YETI
    assert fmt["format"] == "s16le"
    assert fmt["rate"] and fmt["channels"]
