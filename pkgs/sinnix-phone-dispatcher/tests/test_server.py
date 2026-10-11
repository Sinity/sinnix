"""HTTP framing at the phone dispatcher's domain boundary."""

from __future__ import annotations

import hashlib
import io
import json
from email.message import Message
from http import HTTPStatus
from types import MethodType

import sinnix_phone_dispatcher.execute as execute_mod
import sinnix_phone_dispatcher.server as server_mod
import sinnix_phone_dispatcher.uploads as uploads_mod


def _handler(path: str, body: bytes, content_length: str | None):
    handler = object.__new__(server_mod.Handler)
    handler.path = path
    handler.rfile = io.BytesIO(body)
    headers = Message()
    if content_length is not None:
        headers["Content-Length"] = content_length
    handler.headers = headers
    sent: list[tuple[HTTPStatus, object]] = []
    handler._send = MethodType(
        lambda self, status, payload: sent.append((status, payload)), handler
    )
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
    monkeypatch.setattr(
        server_mod, "execute", lambda payload: received.append(payload) or {"ok": True}
    )

    handler.do_POST()

    assert received == [{"kind": "ping"}]
    assert sent == [(HTTPStatus.OK, {"ok": True})]


def test_chunk_body_is_framed_before_upload(monkeypatch):
    handler, sent = _handler("/v1/chunk?lane=ambient&name=clip", b"abc", "3")
    received = []
    monkeypatch.setattr(
        server_mod,
        "store_upload",
        lambda lane, name, body, digest: (
            received.append((lane, name, body, digest)) or (HTTPStatus.OK, {"ok": True})
        ),
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


def _post_json(path: str, payload: dict):
    body = json.dumps(payload).encode()
    handler, sent = _handler(path, body, str(len(body)))
    handler.do_POST()
    return sent[0]


def test_http_intent_outcomes_are_200_with_typed_refusals(monkeypatch):
    """The phone app treats any non-2xx as "unreachable" and re-posts the head
    of its outbox forever; refusals must arrive as 200 + ok:false so it can set
    them aside. Anti-vacuity: the conflicting post must not reach steer."""
    calls = []
    monkeypatch.setattr(
        execute_mod, "steer", lambda *args: calls.append(args) or (0, "ok")
    )

    def resolve(item):
        return {
            "kind": "steering_resolve",
            "id": item,
            "outcome": "done",
            "send_token": "http-token",
        }

    first = _post_json("/v1/intent", resolve("a"))
    conflict = _post_json("/v1/intent", resolve("b"))
    repeat = _post_json("/v1/intent", resolve("a"))
    unknown = _post_json("/v1/intent", {"kind": "nope", "send_token": "t2"})

    assert first[0] == conflict[0] == repeat[0] == unknown[0] == HTTPStatus.OK
    assert first[1]["ok"] is True and first[1]["outcome"] == "completed"
    assert conflict[1]["ok"] is False and conflict[1]["outcome"] == "conflict"
    assert conflict[1].get("duplicate") is not True
    assert repeat[1]["ok"] is True and repeat[1]["duplicate"] is True
    assert unknown[1]["ok"] is False and unknown[1]["outcome"] == "failed"
    assert len(calls) == 1


def test_http_job_answer_needs_no_send_token(monkeypatch, tmp_path):
    """HubClient.answerJob posts only job_id and answer."""
    monkeypatch.setenv("SINNIX_AGENT_ANSWER_DIR", str(tmp_path / "answers"))
    status, answer = _post_json("/v1/job-answer", {"job_id": "42", "answer": "yes"})
    assert status == HTTPStatus.OK and answer["ok"] is True
    assert json.loads((tmp_path / "answers" / "42.json").read_text())["answer"] == "yes"


def _post_chunk(name: str, body: bytes):
    handler, sent = _handler(f"/v1/chunk?lane=camera&name={name}", body, str(len(body)))
    handler.headers["X-Sinnix-Sha256"] = hashlib.sha256(body).hexdigest()
    handler.do_POST()
    return sent[0]


def test_http_upload_receipt_describes_retained_bytes(monkeypatch, tmp_path):
    """A same-length different payload under a taken name is kept beside the
    original, never folded into it. Anti-vacuity: the old size-only duplicate
    check answered ok for `other` while retaining only `first`."""
    lane = tmp_path / "camera"
    monkeypatch.setattr(uploads_mod, "UPLOAD_LANES", {"camera": lane})

    status, landed = _post_chunk("clip", b"first")
    assert status == HTTPStatus.OK and landed["duplicate"] is False
    status, conflict = _post_chunk("clip", b"other")
    assert status == HTTPStatus.OK and conflict["conflict"] is True
    status, retry = _post_chunk("clip", b"first")
    assert status == HTTPStatus.OK and retry["duplicate"] is True
    status, conflict_retry = _post_chunk("clip", b"other")
    assert status == HTTPStatus.OK and conflict_retry["duplicate"] is True

    assert (lane / "clip").read_bytes() == b"first"
    kept = lane / f"clip.conflict-{hashlib.sha256(b'other').hexdigest()}"
    assert kept.read_bytes() == b"other"
    for receipt, path in (
        (landed, lane / "clip"),
        (retry, lane / "clip"),
        (conflict, kept),
        (conflict_retry, kept),
    ):
        retained = path.read_bytes()
        assert receipt["path"] == str(path)
        assert receipt["bytes"] == len(retained)
        assert receipt["sha256"] == hashlib.sha256(retained).hexdigest()
    assert conflict["conflicts_with"] == hashlib.sha256(b"first").hexdigest()


def test_camera_configured_home_over_unix_socket(monkeypatch, tmp_path):
    import http.client
    import runpy
    import socket
    import threading
    import sinnix_phone_dispatcher.state as state

    camera = tmp_path / "photo" / "DCIM"
    lake = tmp_path / "telemetry"
    monkeypatch.setenv("SINNIX_PHONE_CAMERA_DIR", str(camera))
    monkeypatch.setenv("SINNIX_PHONE_LAKE", str(lake))
    configured = runpy.run_path(state.__file__)["UPLOAD_LANES"]
    assert configured["camera"] == camera
    assert configured["ambient"] == lake / "ambient"
    monkeypatch.setattr(uploads_mod, "UPLOAD_LANES", configured)
    address = str(tmp_path / "api.sock")
    server = server_mod.UnixHTTPServer(address, server_mod.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = http.client.HTTPConnection("localhost", timeout=5)
    try:
        connection.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.sock.connect(address)
        body = b"synthetic camera payload"
        digest = hashlib.sha256(body).hexdigest()
        connection.request("POST", "/v1/chunk?lane=camera&name=Camera/fixture.jpg",
                           body, {"X-Sinnix-Sha256": digest})
        response = connection.getresponse()
        receipt = json.loads(response.read())
        assert response.status == HTTPStatus.OK
        assert receipt["path"] == str(camera / "Camera" / "fixture.jpg")
        assert (camera / "Camera" / "fixture.jpg").read_bytes() == body
        assert not (lake / "camera").exists()
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_camera_default_is_independent_of_telemetry_root(monkeypatch, tmp_path):
    import runpy
    import sinnix_phone_dispatcher.state as state

    monkeypatch.delenv("SINNIX_PHONE_CAMERA_DIR", raising=False)
    monkeypatch.setenv("SINNIX_PHONE_LAKE", str(tmp_path / "telemetry"))
    configured = runpy.run_path(state.__file__)["UPLOAD_LANES"]
    assert str(configured["camera"]) == "/realm/personal/photo/phone-dispatcher/DCIM"
    assert configured["download"] == tmp_path / "telemetry" / "download"
