"""HTTP framing at the phone dispatcher's domain boundary."""

from __future__ import annotations

import io
from email.message import Message
from http import HTTPStatus
from types import MethodType

import sinnix_phone_dispatcher.server as server_mod


def _handler(path: str, body: bytes, content_length: str | None):
    handler = object.__new__(server_mod.Handler)
    handler.path = path
    handler.rfile = io.BytesIO(body)
    headers = Message()
    if content_length is not None:
        headers["Content-Length"] = content_length
    handler.headers = headers
    sent: list[tuple[HTTPStatus, object]] = []
    handler._send = MethodType(lambda self, status, payload: sent.append((status, payload)), handler)
    return handler, sent


def test_malformed_content_length_is_rejected_before_intent(monkeypatch):
    handler, sent = _handler("/v1/intent", b'{"kind":"ping"}', "wat")
    called = False

    def execute(_payload):
        nonlocal called
        called = True
        return {"ok": True}

    monkeypatch.setattr(server_mod, "execute", execute)
    handler.do_POST()

    assert sent == [
        (HTTPStatus.BAD_REQUEST, {"ok": False, "detail": "invalid Content-Length"})
    ]
    assert not called


def test_negative_content_length_is_rejected_before_intent(monkeypatch):
    handler, sent = _handler("/v1/intent", b'{"kind":"ping"}', "-1")
    monkeypatch.setattr(
        server_mod,
        "execute",
        lambda _payload: (_ for _ in ()).throw(AssertionError("domain was called")),
    )

    handler.do_POST()

    assert sent[0][0] == HTTPStatus.BAD_REQUEST
    assert sent[0][1]["ok"] is False

def test_intent_uses_bounded_json_reader(monkeypatch):
    handler, sent = _handler("/v1/intent", b'{"kind":"ping"}', "15")
    received = []
    monkeypatch.setattr(server_mod, "execute", lambda payload: received.append(payload) or {"ok": True})

    handler.do_POST()

    assert received == [{"kind": "ping"}]
    assert sent == [(HTTPStatus.OK, {"ok": True})]


def test_chunk_body_is_framed_before_upload(monkeypatch):
    handler, sent = _handler("/v1/chunk?lane=ambient&name=clip", b"abc", "3")
    received = []
    monkeypatch.setattr(
        server_mod,
        "store_upload",
        lambda lane, name, body, digest: received.append((lane, name, body, digest))
        or (HTTPStatus.OK, {"ok": True}),
    )
    handler.headers["X-Sinnix-Sha256"] = "digest"

    handler.do_POST()

    assert received == [("ambient", "clip", b"abc", "digest")]
    assert sent == [(HTTPStatus.OK, {"ok": True})]


def test_truncated_chunk_never_reaches_upload(monkeypatch):
    handler, sent = _handler("/v1/chunk?lane=ambient&name=clip", b"ab", "3")
    monkeypatch.setattr(
        server_mod,
        "store_upload",
        lambda *_args: (_ for _ in ()).throw(AssertionError("upload was called")),
    )

    handler.do_POST()

    assert sent[0][0] == HTTPStatus.BAD_REQUEST
    assert sent[0][1]["ok"] is False
