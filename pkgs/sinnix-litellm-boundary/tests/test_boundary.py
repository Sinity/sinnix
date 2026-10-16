import asyncio
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("boundary", Path(__file__).resolve().parents[1] / "boundary.py")
boundary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boundary)


def request(headers, *, method="POST", kind="http", ports=None):
    messages, calls, reads = [], [], []
    scope = {"type": kind, "method": method, "headers": headers}
    async def receive():
        reads.append(True)
        return {"type": "http.request", "body": b"neutral body", "more_body": False}
    async def send(message):
        messages.append(message)
    async def owner(actual, incoming, outgoing):
        calls.append(actual)
        assert incoming is receive and outgoing is send
        assert await incoming() == {"type": "http.request", "body": b"neutral body", "more_body": False}
        await outgoing({"type": "http.response.start", "status": 200, "headers": []})
        await outgoing({"type": "http.response.body", "body": b"chunk", "more_body": True})
        await outgoing({"type": "http.response.body", "body": b"end", "more_body": False})
    middleware = boundary.BrowserBoundary(owner, allowed_ports=ports or {8123, 8124})
    asyncio.run(middleware(scope, receive, send))
    return messages, calls, reads


@pytest.mark.parametrize("headers", [
    [(b"host", b"127.0.0.1:8123")],
    [(b"host", b"localhost:8124"), (b"origin", b"http://localhost:8124")],
    [(b"host", b"[::1]:8123"), (b"sec-fetch-site", b"same-origin")],
])
def test_native_and_same_origin_streams_pass_unchanged(headers):
    messages, calls, reads = request(headers)
    assert len(calls) == len(reads) == 1
    assert [message.get("body") for message in messages[1:]] == [b"chunk", b"end"]


@pytest.mark.parametrize("headers", [
    [], [(b"host", b"foreign.example:8123")], [(b"host", b"127.0.0.1:9999")],
    [(b"host", b"127.0.0.1:8123"), (b"origin", b"https://foreign.example")],
    [(b"host", b"127.0.0.1:8123"), (b"origin", b"null")],
    [(b"host", b"127.0.0.1:8123"), (b"origin", b"http://127.0.0.1:8124")],
    [(b"host", b"127.0.0.1:8123"), (b"sec-fetch-site", b"cross-site")],
    [(b"host", b"127.0.0.1:8123"), (b"sec-fetch-mode", b"cors")],
    [(b"host", b"127.0.0.1:8123"), (b"host", b"127.0.0.1:8123")],
    [(b"host", b"127.0.0.1:8123"), (b"origin", b"http://127.0.0.1:8123/path")],
    [(b"host", b"127.0.0.1:8123"), (b"origin", b"http://user@127.0.0.1:8123")],
    [(b"host", b"127.0.0.1:8123"), (b"origin", b"http://127.0.0.1:8123"), (b"origin", b"null")],
    [(b"host", b"127.0.0.1:8123"), (b"sec-fetch-site", b"same-origin"), (b"sec-fetch-site", b"cross-site")],
    [(b"host", b"127.0.0.1:8123\t")],
])
def test_refused_before_body_or_owner(headers):
    messages, calls, reads = request(headers)
    assert messages[0]["status"] == 403
    assert not calls and not reads


def test_user_activated_document_navigation_is_preserved():
    messages, calls, reads = request([(b"host", b"127.0.0.1:8123"),
        (b"sec-fetch-site", b"cross-site"), (b"sec-fetch-mode", b"navigate"),
        (b"sec-fetch-dest", b"document"), (b"sec-fetch-user", b"?1")], method="GET")
    assert messages[0]["status"] == 200 and calls and reads


def test_foreign_websocket_refused_without_owner():
    messages, calls, reads = request([(b"host", b"127.0.0.1:8123"), (b"origin", b"https://foreign.example")], kind="websocket")
    assert messages == [{"type": "websocket.close", "code": 1008}]
    assert not calls and not reads


def test_ports_come_from_owner_configuration(monkeypatch):
    monkeypatch.setenv("SINNIX_LITELLM_PORTS", "9234,9235")
    assert boundary.BrowserBoundary(None).ports == {9234, 9235}
    monkeypatch.delenv("SINNIX_LITELLM_PORTS")
    with pytest.raises(KeyError):
        boundary.BrowserBoundary(None)
