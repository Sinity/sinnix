"""Exercise the factory reached by Kokoro's vendor uvicorn entrypoint."""

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("kokoro", ROOT / "kokoro.py")
kokoro = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kokoro)
spec = importlib.util.spec_from_file_location(
    "sinnix_ai_browser_boundary", ROOT / "boundary.py"
)
boundary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boundary)


async def request(monkeypatch, headers):
    monkeypatch.setenv("SINNIX_KOKORO_PORTS", "8123,8124,8880")
    monkeypatch.setitem(sys.modules, "sinnix_ai_browser_boundary", boundary)
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["*"])
    calls, reads, messages = [], [], []

    @app.middleware("http")
    async def vendor_reader(request, next_handler):
        calls.append("vendor")
        await request.body()
        return await next_handler(request)

    @app.post("/fixture")
    async def handler(request: Request):
        calls.append("handler")
        return {"bytes": len(await request.body())}

    for name in ("api", "api.src", "api.src.main"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    sys.modules["api.src.main"].app = app
    guarded = kokoro.create_app()
    assert guarded is app

    async def receive():
        reads.append(True)
        return {"type": "http.request", "body": b"neutral fixture", "more_body": False}

    async def send(message):
        messages.append(message)

    await guarded(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "scheme": "http",
            "method": "POST",
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
    return messages, calls, reads


@pytest.mark.parametrize(
    "headers",
    [
        [(b"host", b"foreign.invalid:8123")],
        [(b"host", b"127.0.0.1:8123"), (b"origin", b"https://foreign.invalid")],
        [(b"host", b"127.0.0.1:8123"), (b"origin", b"null")],
        [(b"host", b"127.0.0.1:8123"), (b"sec-fetch-site", b"cross-site")],
        [(b"host", b"127.0.0.1:8123"), (b"host", b"localhost:8123")],
    ],
)
def test_browser_refusal_precedes_vendor_reads(monkeypatch, headers):
    messages, calls, reads = asyncio.run(request(monkeypatch, headers))
    assert messages[0]["status"] == 403
    assert not calls and not reads


@pytest.mark.parametrize(
    "headers",
    [
        [(b"host", b"127.0.0.1:8123")],
        [(b"host", b"localhost:8124"), (b"origin", b"http://localhost:8124")],
        [(b"host", b"127.0.0.1:8880")],
    ],
)
def test_native_same_origin_and_internal_clients(monkeypatch, headers):
    messages, calls, reads = asyncio.run(request(monkeypatch, headers))
    assert messages[0]["status"] == 200
    assert calls == ["vendor", "handler"] and len(reads) == 1
    assert (b"access-control-allow-origin", b"*") not in messages[0]["headers"]


def test_startup_keeps_vendor_model_and_uv_arguments():
    source = 'if [ "$DOWNLOAD_MODEL" = true ]; then python download_model.py; fi\nexec uv run --extra $DEVICE --no-sync python -m uvicorn api.src.main:app --port 8880'
    assert kokoro.startup_script(source) == source.replace(
        "api.src.main:app", "sinnix_kokoro:create_app --factory"
    )


@pytest.mark.parametrize(
    "source", ["exec another-server", "api.src.main:app api.src.main:app"]
)
def test_incompatible_vendor_entrypoint_refuses(source):
    with pytest.raises(ValueError, match="unsupported Kokoro entrypoint"):
        kokoro.startup_script(source)


@pytest.mark.parametrize("value", ["0", "65536", "invalid", ""])
def test_bad_ports_refuse_before_importing_vendor(monkeypatch, value):
    monkeypatch.setitem(sys.modules, "sinnix_ai_browser_boundary", boundary)
    monkeypatch.setenv("SINNIX_KOKORO_PORTS", value)
    with pytest.raises(ValueError):
        kokoro.create_app()
