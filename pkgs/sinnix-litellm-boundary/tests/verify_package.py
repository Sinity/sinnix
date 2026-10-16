"""Exercise the patched real app without startup, providers, models or sockets."""
import asyncio
import os
from pathlib import Path
import runpy

package = Path(os.environ["LITELLM_PACKAGE"])
runpy.run_path(package / "bin/.litellm-wrapped", run_name="sinnix_boundary_probe")
from litellm.proxy.proxy_server import app
from litellm.proxy.sinnix_browser_boundary import BrowserBoundary

assert app.user_middleware[0].cls is BrowserBoundary


async def probe(headers, method, path):
    events = []
    async def receive():
        raise AssertionError("guarded/absent route must not consume a request body")
    async def send(event):
        events.append(event)
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "scheme": "http", "method": method, "path": path, "raw_path": path.encode(),
             "root_path": "", "query_string": b"", "headers": headers,
             "server": ("127.0.0.1", 8123), "client": ("127.0.0.1", 12345)}
    await app(scope, receive, send)
    return events[0]


async def main():
    host = [(b"host", b"127.0.0.1:8123")]
    for headers in (host + [(b"origin", b"https://foreign.example")],
                    host + [(b"sec-fetch-site", b"cross-site")],
                    [(b"host", b"foreign.example:8123")]):
        denied = await probe(headers + [(b"content-length", b"1000000000")],
                             "POST", "/v1/chat/completions")
        assert denied["status"] == 403, denied
        assert b"access-control-allow-origin" not in dict(denied["headers"])
    native = await probe(host, "GET", "/sinnix-boundary-fixture-does-not-exist")
    assert native["status"] == 404, native


asyncio.run(main())
print("patched LiteLLM app rejects foreign requests before body reads; native route preserved")
