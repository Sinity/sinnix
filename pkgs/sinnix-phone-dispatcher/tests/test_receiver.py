"""The always-on TCP telemetry receiver: envelope seq continuity through
CaptureWriter (the real pkgs/sinnix-capture writer, not a private port), and
the malformed/oversized-line resilience that keeps one bad line from taking
down a connection carrying everything else the phone sends.

A mutation that would fail these: dropping the `continue` after an oversized
or malformed line (so the connection closes instead of surviving to the next
line) fails test_oversized_line_is_dropped_but_connection_survives and
test_malformed_line_is_dropped_but_connection_survives; breaking
CaptureWriter's persisted seq counter (e.g. reverting to a fresh counter per
write) fails test_envelope_seq_is_continuous_across_lines.
"""

from __future__ import annotations

import base64
import faulthandler
import io
import json
import socket
import time
from pathlib import Path

import pytest
from sinnix_phone_dispatcher import receiver
from sinnix_phone_dispatcher.receiver import (
    _PHONE_STREAM_READ_LIMIT,
    _PhoneStreamDemuxer,
    _PhoneStreamServer,
)


def _connect(server: _PhoneStreamServer) -> socket.socket:
    sock = socket.create_connection(server.server_address, timeout=5)
    return sock


@pytest.fixture
def running_server(tmp_path: Path):
    server = _PhoneStreamServer("127.0.0.1", 0, tmp_path)
    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def _wait_for_lane_file(lane_dir: Path, timeout: float = 5.0) -> Path:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        files = sorted(lane_dir.glob("*-index.jsonl"))
        if files:
            return files[0]
        time.sleep(0.02)
    faulthandler.dump_traceback()
    raise TimeoutError(f"no index file appeared under {lane_dir}")


def test_envelope_seq_is_continuous_across_lines(
    running_server: _PhoneStreamServer, tmp_path: Path
) -> None:
    sock = _connect(running_server)
    try:
        for i in range(3):
            sock.sendall((json.dumps({"kind": "battery", "n": i}) + "\n").encode())
        index_path = _wait_for_lane_file(tmp_path / "phone-battery")
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            lines = [ln for ln in index_path.read_text().splitlines() if ln.strip()]
            if len(lines) >= 3:
                break
            time.sleep(0.02)
        seqs = [json.loads(ln)["seq"] for ln in lines]
    finally:
        sock.close()
    assert seqs == [1, 2, 3]


def test_malformed_line_is_dropped_but_connection_survives(
    running_server: _PhoneStreamServer, tmp_path: Path
) -> None:
    sock = _connect(running_server)
    try:
        sock.sendall(b"not json at all\n")
        sock.sendall((json.dumps({"kind": "battery", "n": 1}) + "\n").encode())
        index_path = _wait_for_lane_file(tmp_path / "phone-battery")
        lines = [ln for ln in index_path.read_text().splitlines() if ln.strip()]
    finally:
        sock.close()
    # Exactly one record made it through: the malformed line produced no
    # envelope, and the valid line behind it was still ingested on the same
    # connection.
    assert len(lines) == 1


def test_oversized_line_is_dropped_but_connection_survives(
    running_server: _PhoneStreamServer, tmp_path: Path
) -> None:
    sock = _connect(running_server)
    try:
        oversized = json.dumps(
            {"kind": "battery", "pad": "x" * (_PHONE_STREAM_READ_LIMIT + 1000)}
        )
        sock.sendall(oversized.encode() + b"\n")
        sock.sendall((json.dumps({"kind": "battery", "n": 1}) + "\n").encode())
        index_path = _wait_for_lane_file(tmp_path / "phone-battery")
        lines = [ln for ln in index_path.read_text().splitlines() if ln.strip()]
    finally:
        sock.close()
    assert len(lines) == 1


def test_ingest_line_demuxes_by_kind_into_separate_lanes(tmp_path: Path) -> None:
    demux = _PhoneStreamDemuxer(tmp_path)
    demux.ingest_line(json.dumps({"kind": "battery", "level": 90}))
    demux.ingest_line(json.dumps({"kind": "notification", "title": "x"}))
    assert (tmp_path / "phone-battery").is_dir()
    assert (tmp_path / "phone-notification").is_dir()


def test_speech_recording_is_durably_published_before_transcription(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(receiver, "_phone_stream_transcribe", lambda _wav: None)
    lane = receiver._PhoneSpeechLane(tmp_path)

    result = lane.ingest(
        {
            "audio_b64": base64.b64encode(b"\x00\x00").decode(),
            "rate": 16000,
            "seconds": 0.1,
        }
    )

    recording = lane.blob_dir / result["audio_file"]
    assert recording.read_bytes().startswith(b"RIFF")
    assert recording.stat().st_mode & 0o777 == 0o600
    assert not list(lane.blob_dir.glob("*.part"))
    assert not list(lane.blob_dir.glob(".*.atomic-tmp-*"))


@pytest.mark.parametrize(
    "response, transcribed",
    [
        (value, False)
        for value in [
            None,
            [],
            "invalid",
            42,
            {},
            {"text": None},
            {"text": []},
            {"text": {"bad": "value"}},
            {"text": 42},
            {"text": True},
        ]
    ]
    + [({"text": ""}, True), ({"text": "synthetic"}, True)],
)
def test_stt_response_validation_retains_speech_envelope(
    tmp_path, monkeypatch, response, transcribed
):
    monkeypatch.setattr(
        receiver.urllib.request,
        "urlopen",
        lambda *_a, **_kw: io.BytesIO(json.dumps(response).encode()),
    )
    demux = _PhoneStreamDemuxer(tmp_path)
    demux.ingest_line(
        json.dumps(
            {
                "kind": "speech",
                "audio_b64": base64.b64encode(b"\x00\x00").decode(),
                "rate": 16000,
                "seconds": 0.1,
            }
        )
    )
    records = [
        p
        for p in (tmp_path / "phone-speech").glob("phone-speech-*.jsonl")
        if not p.name.endswith("-index.jsonl")
    ]
    assert len(records) == 1
    envelope = json.loads(records[0].read_text())
    payload = envelope["payload"]
    assert payload["transcribed"] is transcribed
    if transcribed:
        assert payload["text"] == response["text"]
    recording = tmp_path / "phone" / "speech" / payload["audio_file"]
    assert recording.read_bytes()[44:] == b"\x00\x00"


def test_speech_publish_failure_leaves_no_claimed_recording(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lane = receiver._PhoneSpeechLane(tmp_path)

    def fail(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(receiver, "atomic_publish", fail)
    with pytest.raises(OSError, match="disk full"):
        lane.ingest({"audio_b64": base64.b64encode(b"\x00\x00").decode()})
    assert list(lane.blob_dir.iterdir()) == []


@pytest.mark.parametrize("existing", [False, True])
def test_speech_directory_is_private_under_permissive_umask(tmp_path, existing):
    import os

    target = tmp_path / "phone" / "speech"
    if existing:
        target.mkdir(parents=True)
        target.chmod(0o755)
        (target / "retained.wav").write_bytes(b"neutral retained fixture")
    previous = os.umask(0o022)
    try:
        lane = receiver._PhoneSpeechLane(tmp_path)
    finally:
        os.umask(previous)
    assert lane.blob_dir.stat().st_mode & 0o777 == 0o700
    if existing:
        assert (target / "retained.wav").read_bytes() == b"neutral retained fixture"


def test_phone_stream_bounds_handlers_without_dropping_queued_bytes(
    running_server, monkeypatch
):
    import threading

    lock = threading.Lock()
    four_started = threading.Event()
    overflow = threading.Event()
    release = threading.Event()
    complete = threading.Event()
    active = 0
    peak = 0
    received = []

    def handle(self):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            if active == 4:
                four_started.set()
            if active > 4:
                overflow.set()
        try:
            assert release.wait(5)
            line = self.rfile.readline()
            with lock:
                received.append(line)
                if len(received) == 5:
                    complete.set()
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(receiver._PhoneStreamHandler, "handle", handle)
    clients = []
    try:
        for i in range(4):
            client = _connect(running_server)
            clients.append(client)
            client.sendall(f"synthetic-{i}\n".encode())
        assert four_started.wait(3)
        client = _connect(running_server)
        clients.append(client)
        client.sendall(b"synthetic-4\n")
        assert not overflow.wait(1), "excess connection spawned another handler"
        release.set()
        assert complete.wait(3)
        assert peak <= 4
        assert sorted(received) == [f"synthetic-{i}\n".encode() for i in range(5)]
    finally:
        release.set()
        for client in clients:
            client.close()


def test_phone_stream_shutdown_does_not_wait_for_a_handler_slot(
    running_server, monkeypatch
):
    import threading

    lock = threading.Lock()
    four_started = threading.Event()
    release = threading.Event()
    entered = 0

    def handle(self):
        nonlocal entered
        with lock:
            entered += 1
            if entered == 4:
                four_started.set()
        release.wait(5)

    monkeypatch.setattr(receiver._PhoneStreamHandler, "handle", handle)
    pending = threading.Event()
    original_process = running_server.process_request
    requests = 0

    def process(request, address):
        nonlocal requests
        requests += 1
        if requests == 5:
            pending.set()
        original_process(request, address)

    monkeypatch.setattr(running_server, "process_request", process)
    clients = []
    stopper = None
    try:
        for _ in range(4):
            clients.append(_connect(running_server))
        assert four_started.wait(3)
        clients.append(_connect(running_server))
        assert pending.wait(3)
        stopped = threading.Event()

        def stop():
            running_server.shutdown()
            stopped.set()

        stopper = threading.Thread(target=stop, daemon=True)
        stopper.start()
        assert stopped.wait(2), "shutdown blocked behind active connections"
    finally:
        release.set()
        for client in clients:
            client.close()
        if stopper is not None:
            stopper.join(3)
            assert not stopper.is_alive()


def test_phone_stream_probes_unreachable_peers_without_an_idle_read_deadline(
    running_server, monkeypatch
):
    import threading

    checked = threading.Event()
    observed = {}

    def handle(self):
        observed["keepalive"] = self.request.getsockopt(
            socket.SOL_SOCKET, socket.SO_KEEPALIVE
        )
        for option in (socket.TCP_KEEPIDLE, socket.TCP_KEEPINTVL, socket.TCP_KEEPCNT):
            observed[option] = self.request.getsockopt(socket.IPPROTO_TCP, option)
        observed["timeout"] = self.request.gettimeout()
        checked.set()

    monkeypatch.setattr(receiver._PhoneStreamHandler, "handle", handle)
    with _connect(running_server):
        assert checked.wait(3)
    assert observed == {
        "keepalive": 1,
        socket.TCP_KEEPIDLE: 60,
        socket.TCP_KEEPINTVL: 10,
        socket.TCP_KEEPCNT: 3,
        "timeout": None,
    }
