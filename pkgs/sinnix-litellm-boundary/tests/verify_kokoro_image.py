"""Use the pinned image's real app without lifespan or synthesis."""

import asyncio
import hashlib
import importlib
import json
import sys
from pathlib import Path

sys.path[:0] = ["/run/sinnix-kokoro", "/app"]
kokoro = importlib.import_module("sinnix_kokoro")
public, backend, internal = map(int, sys.argv[1:])
source = Path("/app/entrypoint.sh").read_text()
assert (
    kokoro.startup_script(source).replace(
        "sinnix_kokoro:create_app --factory", "api.src.main:app"
    )
    == source
)


async def request(app, headers, *, method="POST", path="/fixture"):
    messages, reads = [], []

    async def receive():
        reads.append(True)
        return {"type": "http.request", "body": b"neutral fixture", "more_body": False}

    async def send(message):
        messages.append(message)

    await asyncio.wait_for(
        app(
            {
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
            },
            receive,
            send,
        ),
        timeout=5,
    )
    return messages, reads


main = importlib.import_module("api.src.main")
Request = importlib.import_module("fastapi").Request


@main.app.post("/fixture")
async def fixture(request: Request):
    return {"bytes": len(await request.body())}


host = (b"host", f"127.0.0.1:{public}".encode())
bad = [
    [host, (b"origin", b"https://foreign.invalid"), (b"sec-fetch-site", b"cross-site")],
    [(b"host", f"foreign.invalid:{public}".encode())],
]
for headers in bad:
    messages, reads = asyncio.run(request(main.app, headers))
    assert messages[0]["status"] == 200 and reads

# A fresh actual vendor app, before its first request, matches server startup.
importlib.reload(main)
app = kokoro.create_app()
cases = []
for headers in bad + [
    [host, (b"origin", b"null")],
    [host, (b"sec-fetch-site", b"cross-site")],
    [host, host],
    [host, (b"origin", f"http://127.0.0.1:{backend}".encode())],
]:
    messages, reads = asyncio.run(request(app, headers, path="/v1/audio/speech"))
    assert messages[0]["status"] == 403 and not reads
    cases.append({"status": 403, "body_reads": 0})
for headers in [
    [host],
    [
        (b"host", f"localhost:{backend}".encode()),
        (b"origin", f"http://localhost:{backend}".encode()),
    ],
    [(b"host", f"127.0.0.1:{internal}".encode())],
]:
    messages, reads = asyncio.run(request(app, headers, method="GET", path="/health"))
    assert messages[0]["status"] == 200
    assert (b"access-control-allow-origin", b"*") not in messages[0]["headers"]
    cases.append({"status": 200, "native_or_same_origin": True})
print(
    json.dumps(
        {
            "cases": cases,
            "vendor_source_sha256": hashlib.sha256(
                Path(main.__file__).read_bytes()
            ).hexdigest(),
            "startup_preserved": True,
            "models_or_lifespan_started": False,
        }
    )
)
