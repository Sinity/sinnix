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

import json
import socket
import time
from pathlib import Path

import pytest

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
    raise TimeoutError(f"no index file appeared under {lane_dir}")


def test_envelope_seq_is_continuous_across_lines(running_server: _PhoneStreamServer, tmp_path: Path) -> None:
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
        oversized = json.dumps({"kind": "battery", "pad": "x" * (_PHONE_STREAM_READ_LIMIT + 1000)})
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
