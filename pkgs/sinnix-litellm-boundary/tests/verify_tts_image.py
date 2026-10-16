"""Replay the actual image app without lifespan, model initialization or network."""

import asyncio
import hashlib
import importlib
import json
import sys
from pathlib import Path

sys.path[:0] = ["/run/sinnix-tts", "/app"]
tts = importlib.import_module("tts")

public, backend = map(int, sys.argv[1:])
startup = Path("/app/startup.sh").read_text()
assert (
    tts.startup_script(startup, Path("/run/sinnix-tts/tts.py")).replace(
        "exec python /run/sinnix-tts/tts.py serve ", "python speech.py "
    )
    == startup
)


async def request(app, headers, *, method="POST", path="/fixture"):
    reads, messages = [], []

    async def receive():
        reads.append(True)
        return {"type": "http.request", "body": b"neutral fixture", "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "scheme": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "server": ("127.0.0.1", public),
        "client": ("127.0.0.1", 12345),
    }
    await app(scope, receive, send)
    return messages, reads


def fixture_app(cls):
    from fastapi import Request

    app = cls()

    @app.post("/fixture")
    async def fixture(request: Request):
        return {"bytes": len(await request.body())}

    return app


openedai = importlib.import_module("openedai")

host = (b"host", f"127.0.0.1:{public}".encode())
bad = [
    [host, (b"origin", b"https://foreign.invalid"), (b"sec-fetch-site", b"cross-site")],
    [(b"host", f"foreign.invalid:{public}".encode())],
]
baseline = fixture_app(openedai.OpenAIStub)
for headers in bad:
    messages, reads = asyncio.run(request(baseline, headers))
    assert messages[0]["status"] == 200 and reads

tts.install(openedai, {public, backend})
# Import the real speech module after installing the same constructor used
# by the launcher. __main__/lifespan are deliberately not executed.
speech = importlib.import_module("speech")
guarded = speech.app
cases = []
for headers in bad + [
    [host, (b"origin", b"null")],
    [host, (b"sec-fetch-site", b"cross-site")],
    [host, host],
    [host, (b"origin", f"http://127.0.0.1:{backend}".encode())],
]:
    messages, reads = asyncio.run(request(guarded, headers, path="/v1/audio/speech"))
    assert messages[0]["status"] == 403 and not reads
    cases.append({"status": 403, "body_reads": 0})
for headers in [
    [host],
    [
        (b"host", f"localhost:{backend}".encode()),
        (b"origin", f"http://localhost:{backend}".encode()),
    ],
]:
    messages, reads = asyncio.run(
        request(guarded, headers, method="GET", path="/v1/models")
    )
    assert messages[0]["status"] == 200
    assert (b"access-control-allow-origin", b"*") not in messages[0]["headers"]
    cases.append({"status": 200, "native_or_same_origin": True})
print(
    json.dumps(
        {
            "cases": cases,
            "startup_preserved": True,
            "vendor_source_sha256": hashlib.sha256(
                Path(openedai.__file__).read_bytes()
            ).hexdigest(),
            "models_or_lifespan_started": False,
        }
    )
)
