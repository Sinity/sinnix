from __future__ import annotations

import socket
from pathlib import Path

from sinnix_audio_capture.tee import SeqpacketTee


def test_send_nonblocking_drops_when_no_listener(tmp_path: Path):
    tee = SeqpacketTee(tmp_path / "mic.pcm")
    try:
        assert tee.send_nonblocking(b"frame") is False
    finally:
        tee.close()


def test_send_nonblocking_delivers_once_a_reader_connects(tmp_path: Path):
    socket_path = tmp_path / "mic.pcm"
    tee = SeqpacketTee(socket_path)
    reader = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    try:
        reader.connect(str(socket_path))
        assert tee.send_nonblocking(b"frame-1") is True
        assert reader.recv(1024) == b"frame-1"
    finally:
        reader.close()
        tee.close()


def test_close_removes_socket_file(tmp_path: Path):
    socket_path = tmp_path / "mic.pcm"
    tee = SeqpacketTee(socket_path)
    assert socket_path.exists()
    tee.close()
    assert not socket_path.exists()


def test_reopening_over_a_stale_socket_path_does_not_raise(tmp_path: Path):
    socket_path = tmp_path / "mic.pcm"
    first = SeqpacketTee(socket_path)
    # Simulate a crashed prior instance: the socket file is left behind but
    # nothing is listening on it (first is still alive here, so unlink it to
    # mimic an actually-dead socket file rather than double-binding a live one).
    first.close()
    socket_path.touch()
    second = SeqpacketTee(socket_path)
    try:
        assert socket_path.exists()
    finally:
        second.close()
