from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import json
import os
import stat
from pathlib import Path

import pytest


@pytest.fixture
def recordings(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[3] / "scripts" / "sinnix-stt"
    loader = importlib.machinery.SourceFileLoader("sinnix_stt_test", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    monkeypatch.setattr(module, "ACTIVITY", tmp_path / "activity")
    monkeypatch.setattr(module, "MACHINE", tmp_path / "machine")
    monkeypatch.setattr(module, "TRANSCRIPT_DIR", tmp_path / "transcripts")
    monkeypatch.setattr(module, "LEDGER", module.TRANSCRIPT_DIR / "transcribed.jsonl")
    monkeypatch.setattr(module, "models_present", lambda: True)
    monkeypatch.setenv("SINNIX_PHONE_LAKE", str(tmp_path / "phone"))
    calls = []

    def transcribe(path):
        calls.append(path)
        return {"file": str(path), "speech_seconds": 1, "text": path.read_text()}

    monkeypatch.setattr(module, "transcribe_file", transcribe)
    phone = tmp_path / "phone" / "ambient" / "same.opus"
    mic = module.ACTIVITY / "audio" / "recording" / "src-mic" / "same.opus"
    for path, text in ((phone, "room"), (mic, "desk")):
        path.parent.mkdir(parents=True)
        path.write_text(text)
    return module, calls, phone, mic


def run_recordings(module):
    assert module.cmd_recordings(argparse.Namespace(lane=None, limit=0)) == 0


def test_cli_creates_private_transcripts_under_a_permissive_parent_umask(recordings):
    module, calls, phone, mic = recordings
    previous = os.umask(0o022)
    try:
        assert module.main(["recordings"]) == 0
    finally:
        os.umask(previous)
    assert calls == [phone, mic]
    assert stat.S_IMODE(module.TRANSCRIPT_DIR.stat().st_mode) == 0o700
    outputs = list(module.TRANSCRIPT_DIR.iterdir())
    assert module.LEDGER in outputs
    assert module.TRANSCRIPT_DIR / ".recordings.lock" in outputs
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in outputs)


@pytest.mark.parametrize("kind", ["directory", "fifo", "broken-link"])
def test_unusable_history_refuses_before_transcription(recordings, kind):
    module, calls, phone, mic = recordings
    module.TRANSCRIPT_DIR.mkdir()
    if kind == "directory":
        module.LEDGER.mkdir()
    elif kind == "fifo":
        os.mkfifo(module.LEDGER)
    else:
        module.LEDGER.symlink_to("absent-ledger")
    with pytest.raises(OSError):
        run_recordings(module)
    assert calls == []
    assert not list(module.TRANSCRIPT_DIR.glob("20*.jsonl"))


def test_denied_history_is_not_empty(recordings, monkeypatch):
    module, calls, phone, mic = recordings
    module.TRANSCRIPT_DIR.mkdir()
    module.LEDGER.write_text("{}\n")
    original = os.open

    def denied(path, flags, *args, **kwargs):
        if Path(path) == module.LEDGER:
            raise PermissionError("synthetic denied ledger")
        return original(path, flags, *args, **kwargs)

    monkeypatch.setattr(module.os, "open", denied)
    with pytest.raises(PermissionError, match="synthetic denied ledger"):
        run_recordings(module)
    assert calls == []


def test_history_streams_and_accepts_regular_symlink(recordings, monkeypatch):
    module, calls, phone, mic = recordings
    module.TRANSCRIPT_DIR.mkdir()
    target = module.TRANSCRIPT_DIR / "retained-ledger"
    target.write_text(
        json.dumps({"lane": "phone", "file": phone.name, "bytes": 4}) + "\n"
    )
    module.LEDGER.symlink_to(target.name)

    def no_whole_file(*args, **kwargs):
        raise AssertionError("ledger must be read incrementally")

    monkeypatch.setattr(Path, "read_text", no_whole_file)
    assert module.ledger_seen() == {("phone", phone.name, 4)}


def test_same_name_and_size_in_different_lanes_transcribe_once_each(recordings):
    module, calls, phone, mic = recordings
    run_recordings(module)
    run_recordings(module)
    assert calls == [phone, mic]
    rows = [json.loads(line) for line in module.LEDGER.read_text().splitlines()]
    assert [(row["lane"], row["file"], row["bytes"]) for row in rows] == [
        ("phone", "same.opus", 4),
        ("src-mic", "same.opus", 4),
    ]
    transcripts = [
        json.loads(line)
        for path in module.TRANSCRIPT_DIR.glob("*.jsonl")
        if path != module.LEDGER
        for line in path.read_text().splitlines()
    ]
    assert {(row["lane"], row["text"]) for row in transcripts} == {
        ("phone", "room"),
        ("src-mic", "desk"),
    }


def test_legacy_row_without_lane_does_not_hide_current_sources(recordings):
    module, calls, phone, mic = recordings
    module.TRANSCRIPT_DIR.mkdir()
    legacy = json.dumps({"file": "same.opus", "bytes": 4}) + "\n"
    module.LEDGER.write_text(legacy)
    run_recordings(module)
    run_recordings(module)
    assert calls == [phone, mic]
    assert module.LEDGER.read_text().startswith(legacy)


def test_lane_qualified_history_and_repaired_size(recordings):
    module, calls, phone, mic = recordings
    module.TRANSCRIPT_DIR.mkdir()
    prior = json.dumps({"lane": "phone", "file": "same.opus", "bytes": 4}) + "\n"
    module.LEDGER.write_text(prior)
    run_recordings(module)
    assert calls == [mic]
    phone.write_text("repaired recording")
    run_recordings(module)
    run_recordings(module)
    assert calls == [mic, phone]
    assert module.LEDGER.read_text().startswith(prior)


@pytest.mark.parametrize(
    "framing, raw, success",
    [
        ([("Content-Length", "2"), ("Content-Length", "3")], b"{}", False),
        ([("Content-Length", "2"), ("Transfer-Encoding", "chunked")], b"{}", False),
        ([("Content-Length", "-1")], b"{}", False),
        ([("Content-Length", "3")], b"{}", False),
        ([("Content-Length", "2")], b"{}", True),
    ],
)
def test_http_framing_precedes_transcription(
    recordings, monkeypatch, framing, raw, success
):
    import io
    import socketserver
    from email.message import Message

    module = recordings[0]
    calls, statuses = [], []
    monkeypatch.setattr(
        module, "_multipart_file", lambda body, ctype: calls.append(body) or b"audio"
    )
    monkeypatch.setattr(module, "transcribe_file", lambda path: {"text": "neutral"})

    class ShortReader(io.BytesIO):
        def read(self, size=-1):
            return super().read(min(size, 1))

    class Server:
        def __init__(self, address, handler):
            self.handler = handler
            self.server_address = address

        def serve_forever(self):
            handler = object.__new__(self.handler)
            handler.server = self
            handler.headers = Message()
            handler.headers["Host"] = "127.0.0.1:0"
            for key, value in framing:
                handler.headers[key] = value
            handler.rfile = ShortReader(raw)
            handler.path = "/v1/audio/transcriptions"
            handler._json = lambda status, body: statuses.append(int(status))
            handler.do_POST()

        def server_close(self):
            pass

    monkeypatch.setattr(socketserver, "ThreadingTCPServer", Server)
    assert module.cmd_serve(argparse.Namespace(socket=None, listen="127.0.0.1:0")) == 0
    assert statuses == [200 if success else 400]
    assert calls == ([b"{}"] if success else [])


@pytest.mark.parametrize("failure", [None, "write", "transcribe"])
def test_upload_scratch_is_removed_even_after_partial_write(
    recordings, monkeypatch, tmp_path, failure
):
    import socketserver
    from email.message import Message

    module = recordings[0]
    scratch = tmp_path / "requests"
    scratch.mkdir()
    monkeypatch.setattr(module.tempfile, "tempdir", str(scratch))
    monkeypatch.setattr(module, "_multipart_file", lambda body, ctype: b"neutral audio")
    original_write = Path.write_bytes

    def write(path, data):
        if failure == "write":
            original_write(path, data[:3])
            raise OSError("synthetic storage failure")
        return original_write(path, data)

    monkeypatch.setattr(Path, "write_bytes", write)

    def transcribe(path):
        assert path.read_bytes() == b"neutral audio"
        if failure == "transcribe":
            raise OSError("synthetic transcription failure")
        return {"text": "neutral"}

    monkeypatch.setattr(module, "transcribe_file", transcribe)

    class Server:
        def __init__(self, address, handler):
            self.handler = handler
            self.server_address = address

        def serve_forever(self):
            import io

            handler = object.__new__(self.handler)
            handler.server = self
            handler.headers = Message()
            handler.headers["Host"] = "127.0.0.1:0"
            handler.headers["Content-Length"] = "2"
            handler.rfile = io.BytesIO(b"{}")
            handler.path = "/v1/audio/transcriptions"
            handler._json = lambda status, body: None
            handler.do_POST()

        def server_close(self):
            pass

    monkeypatch.setattr(socketserver, "ThreadingTCPServer", Server)
    args = argparse.Namespace(socket=None, listen="127.0.0.1:0")
    if failure:
        with pytest.raises(OSError, match="synthetic"):
            module.cmd_serve(args)
    else:
        assert module.cmd_serve(args) == 0
    assert list(scratch.iterdir()) == []


def test_native_http_guard_before_upload_and_transcription(recordings, monkeypatch):
    import http.client
    import socketserver
    import threading

    module, calls, _, _ = recordings
    monkeypatch.setenv("SINNIX_STT_PUBLIC_ENDPOINT", "127.0.0.1:18090")
    original = socketserver.ThreadingTCPServer
    statuses = []

    class Server(original):
        def serve_forever(self):
            worker = threading.Thread(target=super().serve_forever, daemon=True)
            worker.start()
            try:
                for name in (
                    "Origin",
                    "Sec-Fetch-Site",
                    "Sec-Fetch-Mode",
                    "Sec-Fetch-Dest",
                    "Sec-Fetch-User",
                ):
                    for method in ("GET", "POST"):
                        client = http.client.HTTPConnection(
                            "127.0.0.1", self.server_address[1], timeout=2
                        )
                        client.putrequest(method, "/v1/audio/transcriptions")
                        client.putheader(name, "")
                        client.putheader("Content-Length", "100")
                        client.endheaders()  # No body: refusal must precede reading.
                        response = client.getresponse()
                        response.read()
                        client.close()
                        assert response.status == 403
                        statuses.append(response.status)
                for hosts in (
                    [],
                    ["rebound.example.invalid:18090"],
                    ["127.0.0.1:18090", "localhost:18090"],
                    ["user@127.0.0.1:18090"],
                    ["127.0.0.1:80"],
                ):
                    client = http.client.HTTPConnection(
                        "127.0.0.1", self.server_address[1], timeout=2
                    )
                    client.putrequest("GET", "/health", skip_host=True)
                    for host in hosts:
                        client.putheader("Host", host)
                    client.endheaders()
                    response = client.getresponse()
                    response.read()
                    client.close()
                    assert response.status == 403
                assert calls == []
                for host in (f"127.0.0.1:{self.server_address[1]}", "localhost:18090"):
                    client = http.client.HTTPConnection(
                        "127.0.0.1", self.server_address[1], timeout=2
                    )
                    client.request("GET", "/health", headers={"Host": host})
                    response = client.getresponse()
                    response.read()
                    client.close()
                    assert response.status == 200
                body = (
                    b'--neutral\r\nContent-Disposition: form-data; name="file"; filename="neutral.wav"\r\n'
                    b"Content-Type: audio/wav\r\n\r\nneutral audio\r\n--neutral--\r\n"
                )
                client = http.client.HTTPConnection(
                    "127.0.0.1", self.server_address[1], timeout=2
                )
                client.request(
                    "POST",
                    "/v1/audio/transcriptions",
                    body,
                    {
                        "Host": "localhost:18090",
                        "Content-Type": "multipart/form-data; boundary=neutral",
                    },
                )
                response = client.getresponse()
                assert response.status == 200
                assert json.loads(response.read())["text"] == "neutral audio"
                client.close()
                assert len(calls) == 1
            finally:
                self.shutdown()
                worker.join(timeout=2)

    monkeypatch.setattr(socketserver, "ThreadingTCPServer", Server)
    assert module.cmd_serve(argparse.Namespace(socket=None, listen="127.0.0.1:0")) == 0
    assert statuses == [403] * 10
