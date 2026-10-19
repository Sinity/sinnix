from __future__ import annotations

import io
import json
import sys
from email.message import Message
from types import SimpleNamespace

import pytest
from conftest import load_script

daemon = load_script("sinnix-capture-browser-nav")


def test_large_capture_payload_uses_stdin(capture_writer):
    payload = {"title": "synthetic title " * 12000, "url": "https://example.test/"}
    daemon.sinnix_capture_write("browser-nav-edges", payload)
    observed = json.loads(capture_writer.read_text())
    assert observed["payload"] == payload
    assert "--payload" not in observed["argv"]
    assert payload["title"] not in observed["argv"]


def test_large_browser_push_reaches_stack_and_capture(
    tmp_path, monkeypatch, capture_writer
):
    owner = load_script("sinnix-reading-stack")
    runner = tmp_path / "bin" / "sinnix-reading-stack"
    runner.write_text(
        f"#!{sys.executable}\nimport os,sys\n"
        f"os.execv(sys.executable, [sys.executable, {owner.__file__!r}, *sys.argv[1:]])\n"
    )
    runner.chmod(0o700)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    payload = {
        "target_url": "https://example.test/",
        "target_title": "synthetic title " * 12000,
        "note": 'Unicode Łódź 🙂\nwith quotes " and spaces',
    }
    daemon.reading_stack_push(payload)
    (entry,) = json.loads((tmp_path / "state/sinnix/reading-stack.json").read_text())
    assert entry["title"] == payload["target_title"]
    assert entry["note"] == payload["note"]
    capture = json.loads(capture_writer.read_text())["payload"]
    assert capture == {"event": "push", **entry}


def setup_handler(handler):
    headers = Message()
    for key, value in handler.headers.items():
        headers[key] = value
    headers["Host"] = "127.0.0.1:8767"
    headers["Content-Type"] = "application/json"
    handler.headers = headers
    handler.server = SimpleNamespace(
        server_port=8767, extension_origin="chrome-extension://" + "a" * 32
    )


@pytest.mark.parametrize(
    ("length", "raw"),
    [
        ("invalid", b"{}"),
        ("-1", b"{}"),
        ("9", b"{}"),
        ("2", b"[]"),
        ("4", b"null"),
        ("1", b"\xff"),
    ],
)
def test_invalid_body_returns_400_without_capture(length, raw, monkeypatch):
    handler = object.__new__(daemon.Handler)
    handler.headers = {"Content-Length": length}
    handler.rfile = io.BytesIO(raw)
    handler.path = "/v1/link-event"
    responses = []
    handler._respond = responses.append
    calls = []
    monkeypatch.setattr(
        daemon, "sinnix_capture_write", lambda *args: calls.append(args)
    )
    setup_handler(handler)
    handler.do_POST()
    assert responses == [400]
    assert calls == []
    if length in ("invalid", "-1"):
        assert handler.rfile.tell() == 0


def test_valid_body_reaches_capture(monkeypatch):
    handler = object.__new__(daemon.Handler)
    handler.headers = {"Content-Length": "17"}
    handler.rfile = io.BytesIO(b'{"trigger":"tap"}')
    handler.path = "/v1/link-event"
    responses = []
    handler._respond = responses.append
    calls = []
    monkeypatch.setattr(
        daemon, "sinnix_capture_write", lambda *args: calls.append(args)
    )
    setup_handler(handler)
    handler.do_POST()
    assert responses == [204]
    assert calls == [("browser-nav-edges", {"trigger": "tap"})]


def test_reading_stack_push_passes_provenance_and_note(monkeypatch):
    calls = []
    monkeypatch.setattr(
        daemon.subprocess,
        "run",
        lambda command, **kwargs: calls.append((command, kwargs)),
    )

    daemon.reading_stack_push(
        {
            "target_url": "https://target.example/article",
            "target_title": "Target article",
            "source_url": "https://source.example/list",
            "source_title": "Source list",
            "anchor_text": "Read this next",
            "note": "Compare with the earlier report",
        }
    )

    assert len(calls) == 1
    command, options = calls[0]
    assert command == ["sinnix-reading-stack", "push", "--json-stdin"]
    assert json.loads(options.pop("input")) == {
        "url": "https://target.example/article",
        "title": "Target article",
        "source_url": "https://source.example/list",
        "source_title": "Source list",
        "anchor_text": "Read this next",
        "note": "Compare with the earlier report",
    }
    assert options == {"text": True, "check": True, "capture_output": True}


@pytest.mark.parametrize(
    "framing",
    [
        [("Content-Length", "2"), ("Content-Length", "3")],
        [("Content-Length", "2"), ("Transfer-Encoding", "chunked")],
        [("Transfer-Encoding", "chunked")],
    ],
)
def test_conflicting_framing_refuses_before_capture(framing, monkeypatch):
    from email.message import Message

    handler = object.__new__(daemon.Handler)
    handler.headers = Message()
    for key, value in framing:
        handler.headers[key] = value
    handler.rfile = io.BytesIO(b"{}")
    handler.path = "/v1/link-event"
    responses, calls = [], []
    handler._respond = responses.append
    monkeypatch.setattr(
        daemon, "sinnix_capture_write", lambda *args: calls.append(args)
    )
    setup_handler(handler)
    handler.do_POST()
    assert responses == [400]
    assert calls == []
    assert handler.rfile.tell() == 0


def test_short_reads_are_completed_before_capture(monkeypatch):
    class ShortReader(io.BytesIO):
        def read(self, size=-1):
            return super().read(min(size, 1))

    handler = object.__new__(daemon.Handler)
    handler.headers = {"Content-Length": "2"}
    handler.rfile = ShortReader(b"{}")
    handler.path = "/v1/link-event"
    responses, calls = [], []
    handler._respond = responses.append
    monkeypatch.setattr(
        daemon, "sinnix_capture_write", lambda *args: calls.append(args)
    )
    setup_handler(handler)
    handler.do_POST()
    assert responses == [204]
    assert calls == [("browser-nav-edges", {})]


@pytest.mark.parametrize(
    "extra,status",
    [
        ([("Origin", "https://foreign.example")], 403),
        ([("Origin", "null")], 403),
        ([("Origin", "chrome-extension://" + "b" * 32)], 403),
        ([("Host", "rebound.example:8767")], 403),
        ([("Host", "127.0.0.1:8767")], 403),
        ([("Sec-Fetch-Site", "cross-site")], 403),
        ([("Content-Type", "text/plain")], 415),
    ],
)
def test_forged_request_refused_before_body(extra, status, monkeypatch):
    handler = object.__new__(daemon.Handler)
    handler.headers = {"Content-Length": "2"}
    setup_handler(handler)
    for key, value in extra:
        handler.headers[key] = value
    handler.rfile = io.BytesIO(b"{}")
    handler.path = "/v1/link-event"
    responses, calls = [], []
    handler._respond = responses.append
    monkeypatch.setattr(
        daemon, "sinnix_capture_write", lambda *args: calls.append(args)
    )
    handler.do_POST()
    assert responses == [status]
    assert calls == []
    assert handler.rfile.tell() == 0
    assert handler.close_connection


def test_extension_origin_allows_privileged_cross_site_fetch(monkeypatch):
    handler = object.__new__(daemon.Handler)
    handler.headers = {"Content-Length": "2"}
    setup_handler(handler)
    handler.headers["Origin"] = handler.server.extension_origin
    handler.headers["Sec-Fetch-Site"] = "cross-site"
    handler.rfile = io.BytesIO(b"{}")
    handler.path = "/v1/reading-stack/push"
    responses, calls = [], []
    handler._respond = responses.append
    monkeypatch.setattr(daemon, "reading_stack_push", lambda *args: calls.append(args))
    handler.do_POST()
    assert responses == [204]
    assert calls == [({},)]


def test_extension_identity_validation(tmp_path, monkeypatch):
    identity = tmp_path / "extension-id"
    monkeypatch.setenv("SINNIX_NAV_CAPTURE_EXTENSION_ID_FILE", str(identity))
    identity.write_text("a" * 32)
    assert daemon.extension_origin() == "chrome-extension://" + "a" * 32
    identity.write_text("foreign.example")
    with pytest.raises(ValueError):
        daemon.extension_origin()


def test_live_http_cors_and_routes(monkeypatch):
    from http.client import HTTPConnection
    from threading import Thread

    calls = []
    monkeypatch.setattr(
        daemon, "sinnix_capture_write", lambda *args: calls.append(args)
    )
    server = daemon.ThreadingHTTPServer(("127.0.0.1", 0), daemon.Handler)
    server.extension_origin = "chrome-extension://" + "a" * 32
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:

        def request(method, headers, body=None):
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
            try:
                connection.request(method, "/v1/link-event", body, headers)
                response = connection.getresponse()
                response.read()
                return response.status, dict(response.getheaders())
            finally:
                connection.close()

        origin = server.extension_origin
        status, headers = request(
            "OPTIONS",
            {
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert status == 204
        assert headers["Access-Control-Allow-Origin"] == origin
        assert headers["Access-Control-Allow-Methods"] == "POST"
        assert headers["Access-Control-Allow-Headers"] == "Content-Type"
        status, headers = request(
            "OPTIONS",
            {
                "Origin": "https://foreign.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert status == 403
        assert "Access-Control-Allow-Origin" not in headers
        assert (
            request(
                "OPTIONS", {"Origin": origin, "Access-Control-Request-Method": "DELETE"}
            )[0]
            == 403
        )
        assert (
            request(
                "POST",
                {
                    "Origin": "https://foreign.example",
                    "Content-Type": "application/json",
                },
                "{}",
            )[0]
            == 403
        )
        assert calls == []
        assert (
            request(
                "POST", {"Origin": origin, "Content-Type": "application/json"}, "{}"
            )[0]
            == 204
        )
        assert request("POST", {"Content-Type": "application/json"}, "{}")[0] == 204
        assert calls == [("browser-nav-edges", {}), ("browser-nav-edges", {})]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
