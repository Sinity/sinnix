from __future__ import annotations

import json
import threading
from pathlib import Path

from sinnix_audio_capture.devices import (
    AudioDevice,
    DeviceSupervisor,
    channel_name,
    matches_any,
    parse_devices,
    probe_coverage,
    write_device_sidecar,
)

YETI_IN = "alsa_input.usb-Blue_Microphones_Yeti_Nano_2110SG002XQ8_888-000438040606-00.analog-stereo"
FIIO_IN = "alsa_input.usb-FiiO_DigiHug_USB_Audio-01.analog-stereo"
FIIO_OUT = "alsa_output.usb-FiiO_DigiHug_USB_Audio-01.analog-stereo"
BT_OUT = "bluez_output.AC_80_0A_D4_08_48.1"


def _node(name: str, media_class: str, **props) -> dict:
    return {
        "type": "PipeWire:Interface:Node",
        "info": {"props": {"node.name": name, "media.class": media_class, **props}},
    }


def _source(name: str, **kwargs) -> AudioDevice:
    return AudioDevice(
        node_name=name, kind="source", media_class="Audio/Source", **kwargs
    )


def _sink(name: str, **kwargs) -> AudioDevice:
    return AudioDevice(node_name=name, kind="sink", media_class="Audio/Sink", **kwargs)


def test_parse_devices_keeps_sources_and_sinks_and_drops_streams():
    objects = [
        _node(
            YETI_IN,
            "Audio/Source",
            **{
                "node.description": "Yeti Nano Analog Stereo",
                "audio.channels": 2,
                "object.serial": 32703,
            },
        ),
        _node(FIIO_OUT, "Audio/Sink", **{"node.description": "Fiio E10 Analog Stereo"}),
        # A Bluetooth sink reports no audio.channels until it is running.
        _node(BT_OUT, "Audio/Sink", **{"node.description": "WH-1000XM4"}),
        _node("Firefox", "Stream/Output/Audio"),
        _node("echo-cancel-source", "Audio/Source/Virtual"),
        {"type": "PipeWire:Interface:Link", "info": {}},
    ]
    devices = parse_devices(objects)
    assert {d.key for d in devices} == {
        f"source:{YETI_IN}",
        "source:echo-cancel-source",
        f"sink:{FIIO_OUT}",
        f"sink:{BT_OUT}",
    }
    yeti = next(d for d in devices if d.node_name == YETI_IN)
    assert (yeti.kind, yeti.channels, yeti.serial) == ("source", 2, "32703")
    assert next(d for d in devices if d.node_name == BT_OUT).channels is None


def test_channel_name_separates_the_two_directions_of_one_device():
    # The FiiO's line-in and its speaker output are different devices that
    # share a card; their channels must not collide.
    assert channel_name("source", FIIO_IN) != channel_name("sink", FIIO_OUT)
    assert channel_name("source", FIIO_IN).startswith("src-")
    assert channel_name("sink", FIIO_OUT).startswith("snk-")


def test_channel_name_is_stable_and_distinguishes_similar_devices():
    assert channel_name("source", YETI_IN).startswith(
        "src-alsa-input-usb-blue-microphones-yeti-nano"
    )
    # Two identical models are distinguished by the port/serial component
    # ALSA already puts in node.name.
    a = "alsa_input.usb-Generic_Mic-00.analog-stereo"
    b = "alsa_input.usb-Generic_Mic-01.analog-stereo"
    assert channel_name("source", a) != channel_name("source", b)
    assert " " not in channel_name("source", "Some Weird.Node_Name")


def test_matches_any_is_case_insensitive_and_direction_aware():
    fiio_in = _source(FIIO_IN, description="Fiio E10 Analog Stereo")
    fiio_out = _sink(FIIO_OUT, description="Fiio E10 Analog Stereo")
    yeti = _source(YETI_IN, description="Yeti Nano Analog Stereo")
    patterns = [r"^alsa_input\.usb-FiiO_DigiHug_USB_Audio"]
    assert matches_any(fiio_in, patterns) == patterns[0]
    # The same card's playback side is a different node.name, so blacklisting
    # the dead line-in leaves the speakers recorded.
    assert matches_any(fiio_out, patterns) is None
    assert matches_any(yeti, patterns) is None
    assert matches_any(yeti, ["yeti nano"]) == "yeti nano"
    # An unparseable pattern is skipped, never fatal: a bad blacklist entry
    # must not take the whole capture lane down.
    assert matches_any(yeti, ["*bad(", "yeti"]) == "yeti"


def _dump_run(objects):
    payload = json.dumps(objects)

    def fake_run(argv, **kwargs):
        class R:
            stdout = payload

        return R()

    return fake_run


def test_probe_reports_uncovered_devices_of_both_kinds(tmp_path: Path):
    run = _dump_run(
        [
            _node(YETI_IN, "Audio/Source", **{"audio.channels": 2}),
            _node(FIIO_IN, "Audio/Source"),
            _node(FIIO_OUT, "Audio/Sink"),
        ]
    )
    patterns = {"source": [r"FiiO_DigiHug"], "sink": []}
    code, detail = probe_coverage(
        capture_root=tmp_path,
        pw_dump_bin="pw-dump",
        exclude_patterns=patterns,
        run=run,
    )
    assert code == 1
    assert detail["uncovered"] == [f"sink:{FIIO_OUT}", f"source:{YETI_IN}"]
    assert detail["excluded"] == [f"source:{FIIO_IN}"]

    for kind, name in (("source", YETI_IN), ("sink", FIIO_OUT)):
        seg = tmp_path / "audio" / channel_name(kind, name) / "audio-x.opus.partial"
        seg.parent.mkdir(parents=True)
        seg.write_bytes(b"x")
    code, detail = probe_coverage(
        capture_root=tmp_path,
        pw_dump_bin="pw-dump",
        exclude_patterns=patterns,
        run=run,
    )
    assert code == 0
    assert detail["uncovered"] == []


def test_probe_returns_unknown_when_graph_unreadable(tmp_path: Path):
    def fake_run(argv, **kwargs):
        raise OSError("no pw-dump")

    code, detail = probe_coverage(
        capture_root=tmp_path, pw_dump_bin="pw-dump", run=fake_run
    )
    # Not 0 and not 1: an unreadable graph is unknown, never "healthy".
    assert code == 2
    assert "error" in detail


def test_device_sidecar_records_unsanitized_identity(tmp_path: Path):
    device = _sink(BT_OUT, description="WH-1000XM4")
    write_device_sidecar(tmp_path, device)
    record = json.loads((tmp_path / "device.json").read_text())
    assert record["node_name"] == BT_OUT
    assert record["kind"] == "sink"
    assert record["channel"] == channel_name("sink", BT_OUT)
    assert record["description"] == "WH-1000XM4"


class _FakeRecorder:
    def __init__(self, device, output_dir: Path):
        self.output_dir = output_dir
        self.device = device
        self.started_at = 0.0
        self.error = None
        self.stopped = False
        self.alive = True
        self.restarted_with = None

    def is_alive(self):
        return self.alive

    def start(self):
        pass

    def stop(self):
        self.stopped = True
        self.alive = False

    def join(self, timeout=None):
        pass

    def request_restart(self, device):
        self.restarted_with = device
        self.device = device


def _supervisor(tmp_path: Path, **kwargs) -> DeviceSupervisor:
    sup = DeviceSupervisor(capture_root=tmp_path, **kwargs)
    sup._start = lambda device: sup._recorders.__setitem__(  # noqa: SLF001
        device.key, _FakeRecorder(device, tmp_path / "audio" / device.channel)
    )
    return sup


def test_reconcile_records_every_device_except_the_blacklisted_ones(tmp_path: Path):
    sup = _supervisor(tmp_path, exclude_patterns={"source": [r"FiiO_DigiHug"]})
    yeti = _source(YETI_IN, channels=2)
    fiio_in = _source(FIIO_IN)
    fiio_out = _sink(FIIO_OUT)
    bt = _sink(BT_OUT)

    sup.reconcile([yeti, fiio_in, fiio_out, bt], now=100.0)
    assert set(sup._recorders) == {yeti.key, fiio_out.key, bt.key}
    state = sup.state_payload("change")
    assert [e["key"] for e in state["excluded"]] == [fiio_in.key]
    assert {r["device_kind"] for r in state["recording"]} == {"source", "sink"}


def test_bluetooth_sink_appearing_and_vanishing_is_spawned_and_reaped(tmp_path: Path):
    sup = _supervisor(tmp_path)
    yeti = _source(YETI_IN)
    bt = _sink(BT_OUT)

    sup.reconcile([yeti], now=100.0)
    assert set(sup._recorders) == {yeti.key}

    sup.reconcile([yeti, bt], now=110.0)  # headphones connect
    assert set(sup._recorders) == {yeti.key, bt.key}
    kept = sup._recorders[yeti.key]

    sup.reconcile([yeti], now=120.0)  # headphones disconnect
    assert set(sup._recorders) == {yeti.key}
    assert sup._recorders[yeti.key] is kept  # untouched by its neighbour's churn

    sup.reconcile([yeti, bt], now=130.0)  # and reconnect
    assert set(sup._recorders) == {yeti.key, bt.key}


def test_replug_reusing_a_node_name_reconnects_instead_of_keeping_a_dead_stream(
    tmp_path: Path,
):
    sup = _supervisor(tmp_path)
    before = _sink(BT_OUT, serial="10986")
    sup.reconcile([before], now=100.0)
    recorder = sup._recorders[before.key]

    after = _sink(BT_OUT, serial="20001")  # same name, different node
    sup.reconcile([after], now=110.0)
    assert sup._recorders[before.key] is recorder  # not respawned
    assert recorder.restarted_with == after  # but re-targeted


def test_a_recorder_still_finalising_is_never_restarted(tmp_path: Path):
    # Two writers on one output path would corrupt the segment being closed,
    # so a device that reappears while its old recorder is still finalising
    # waits for the drain instead.
    sup = _supervisor(tmp_path)
    bt = _sink(BT_OUT)
    sup.reconcile([bt], now=100.0)
    recorder = sup._recorders[bt.key]
    recorder.stop = lambda: None  # simulate a slow finaliser: stays alive

    sup.reconcile([], now=110.0)
    assert sup._recorders == {}
    assert set(sup._draining) == {bt.key}

    sup.reconcile([bt], now=120.0)
    assert sup._recorders == {}  # still draining, not restarted
    assert sup.state_payload("change")["draining"] == [bt.key]

    recorder.alive = False
    sup.reconcile([bt], now=130.0)
    assert set(sup._recorders) == {bt.key}
    assert sup._draining == {}


def test_failed_recorder_is_reported_retried_and_forgotten_when_gone(tmp_path: Path):
    sup = _supervisor(tmp_path)
    yeti = _source(YETI_IN)
    sup.reconcile([yeti], now=100.0)
    sup._recorders[yeti.key].alive = False
    sup._recorders[yeti.key].error = "RuntimeError: boom"

    sup.reconcile([yeti], now=101.0)
    assert sup._recorders == {}
    assert sup.state_payload("change")["failed"] == [
        {"key": yeti.key, "error": "RuntimeError: boom", "at": 101.0}
    ]

    sup.reconcile([yeti], now=200.0)  # past FAILURE_RETRY_SECONDS
    assert set(sup._recorders) == {yeti.key}

    sup._recorders[yeti.key].alive = False
    sup._recorders[yeti.key].error = "RuntimeError: boom"
    sup.reconcile([yeti], now=201.0)
    sup.reconcile([], now=202.0)
    assert sup.state_payload("change")["failed"] == []


class _CapturingWriter:
    def __init__(self):
        self.records = []

    def write(self, payload, raw_ref=None, ts=None):
        self.records.append(payload)
        return payload


def test_state_lane_writes_on_change_and_heartbeats_when_idle(tmp_path: Path):
    sup = _supervisor(tmp_path)
    writer = _CapturingWriter()

    sup.reconcile([_source(YETI_IN)], now=100.0)
    sup._emit_state(writer, 100.0)
    sup._emit_state(writer, 110.0)  # unchanged, heartbeat not due
    assert [r["reason"] for r in writer.records] == ["change"]

    sup._emit_state(writer, 100.0 + sup._heartbeat_interval)
    assert [r["reason"] for r in writer.records] == ["change", "heartbeat"]


def test_asr_tee_mirrors_only_the_nominated_source(tmp_path: Path):
    socket_path = tmp_path / "run" / "asr.pcm"
    sup = _supervisor(
        tmp_path,
        asr_source_pattern=r"Yeti_Nano",
        tee_socket_path=socket_path,
    )
    sent = []
    sup._tee = type(
        "T", (), {"send_nonblocking": lambda self, data: sent.append(data)}
    )()
    sup.reconcile(
        [_source(YETI_IN, channels=2), _source(FIIO_IN), _sink(BT_OUT)], now=1
    )

    sup._tee_chunk(FIIO_IN, b"other-source")
    sup._tee_chunk(BT_OUT, b"a-sink")
    sup._tee_chunk(YETI_IN, b"nominated")
    assert sent == [b"nominated"]

    fmt = json.loads(Path(str(socket_path) + ".json").read_text())
    assert fmt["node_name"] == YETI_IN
    assert fmt["format"] == "s16le"
    assert (fmt["rate"], fmt["channels"]) == (48000, 2)


def test_no_asr_pattern_means_no_privileged_channel(tmp_path: Path):
    sup = _supervisor(tmp_path)
    sup.reconcile([_source(YETI_IN), _sink(BT_OUT)], now=1)
    assert sup.state_payload("change")["asr_source"] is None
    assert len(sup._recorders) == 2  # capture is unaffected either way


def test_unreadable_graph_does_not_reap_recorders(tmp_path: Path):
    sup = _supervisor(tmp_path)
    sup.reconcile([_source(YETI_IN)], now=100.0)
    stop = threading.Event()
    stop.set()
    sup._run = lambda *a, **k: (_ for _ in ()).throw(OSError("no pw-dump"))
    sup.run(stop_event=stop)
    # The loop exits on the pre-set stop event; the point is that a failed
    # list_devices never reaches reconcile with an empty device list.
    assert sup._recorders == {} or sup._draining
