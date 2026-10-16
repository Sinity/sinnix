"""TTS admission surrounds vendor body readers and preserves startup inputs."""

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tts = load("tts", ROOT / "tts.py")
sys.modules["sinnix_ai_browser_boundary"] = load("tts_boundary", ROOT / "boundary.py")


async def request(headers, method="POST"):
    calls, reads, messages = [], [], []

    class Vendor(FastAPI):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.add_middleware(CORSMiddleware, allow_origins=["*"])

            @self.middleware("http")
            async def body_reader(request, next_handler):
                calls.append("vendor")
                await request.body()
                return await next_handler(request)

    vendor = SimpleNamespace(OpenAIStub=Vendor)
    tts.install(vendor, {8123, 8124})
    app = vendor.OpenAIStub()

    @app.post("/fixture")
    async def handler(request: Request):
        calls.append("handler")
        return {"bytes": len(await request.body())}

    async def receive():
        reads.append(True)
        return {"type": "http.request", "body": b"neutral fixture", "more_body": False}

    async def send(message):
        messages.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "scheme": "http",
            "method": method,
            "path": "/fixture",
            "raw_path": b"/fixture",
            "query_string": b"",
            "root_path": "",
            "headers": headers,
            "server": ("127.0.0.1", 8123),
            "client": ("127.0.0.1", 12345),
        },
        receive,
        send,
    )
    return messages, reads, calls


@pytest.mark.parametrize(
    "headers",
    [
        [(b"host", b"foreign.invalid:8123")],
        [(b"host", b"127.0.0.1:8123"), (b"origin", b"https://foreign.invalid")],
        [(b"host", b"127.0.0.1:8123"), (b"origin", b"null")],
        [(b"host", b"127.0.0.1:8123"), (b"sec-fetch-site", b"cross-site")],
        [(b"host", b"127.0.0.1:8123"), (b"host", b"127.0.0.1:8123")],
    ],
)
def test_refusal_precedes_vendor_body_read(headers):
    messages, reads, calls = asyncio.run(request(headers))
    assert messages[0]["status"] == 403
    assert not reads and not calls


@pytest.mark.parametrize(
    "headers",
    [
        [(b"host", b"127.0.0.1:8123")],
        [(b"host", b"localhost:8124"), (b"origin", b"http://localhost:8124")],
    ],
)
def test_native_and_same_origin_preserve_body(headers):
    messages, reads, calls = asyncio.run(request(headers))
    assert messages[0]["status"] == 200
    assert len(reads) == 1 and calls == ["vendor", "handler"]
    assert (b"access-control-allow-origin", b"*") not in messages[0]["headers"]


def test_startup_preserves_vendor_arguments():
    source = "source speech.env\nbash download.sh\npython speech.py ${PRELOAD_MODEL:+--preload $PRELOAD_MODEL} $EXTRA_ARGS $@\n"
    result = tts.startup_script(source, Path("/run/tts guard.py"))
    assert result == source.replace(
        "python speech.py ", "exec python '/run/tts guard.py' serve "
    )


@pytest.mark.parametrize(
    "source", ["bash another-server.sh", "python speech.py a\npython speech.py b"]
)
def test_incompatible_startup_refuses(source):
    with pytest.raises(ValueError, match="unsupported TTS startup"):
        tts.startup_script(source, Path("/run/tts.py"))


@pytest.mark.parametrize("value", ["", "0", "65536", "not-a-port"])
def test_invalid_listener_configuration_refuses(monkeypatch, value):
    monkeypatch.setenv("SINNIX_TTS_PORTS", value)
    with pytest.raises(ValueError):
        tts.listener_ports()
