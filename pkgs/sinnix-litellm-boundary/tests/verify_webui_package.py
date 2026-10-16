"""Verify final middleware registration from the built package without starting its database or models."""
import ast
import asyncio
import importlib.util
import os
import runpy
import shlex
from pathlib import Path

package = Path(os.environ["OPEN_WEBUI_PACKAGE"])
unit = Path(os.environ["OPEN_WEBUI_UNIT"]).read_text()
assert "RuntimeDirectory=open-webui" in unit
assert "RestrictAddressFamilies=AF_NETLINK" in unit
assert "EnvironmentFile=-/run/open-webui/bind.env" in unit
assert "open-webui-resolve-identity" in unit
source = next(package.glob("lib/python*/site-packages/open_webui/main.py"))
module = source.with_name("sinnix_browser_boundary.py")
spec = importlib.util.spec_from_file_location("webui_boundary", module)
boundary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boundary)
registration = ast.parse(source.read_text()).body[-1]
assert isinstance(registration, ast.Expr)
assert isinstance(registration.value, ast.Call)
assert ast.unparse(registration.value.func) == "app.add_middleware"
registered = []
class App:
    def add_middleware(self, cls, **kwargs):
        registered.append((cls, kwargs))
exec(compile(ast.Module(body=[registration], type_ignores=[]), str(source), "exec"),
     {"app": App(), "BrowserBoundary": boundary.BrowserBoundary, "os": os})
cls, options = registered.pop()
assert cls is boundary.BrowserBoundary
assert options["allowed_ports"] == {8080, 8881}
assert options["allowed_hosts"] == {"localhost", "127.0.0.1", "::1", "neutral", "100.64.0.9", "neutral.tailnet.invalid"}
async def probe(headers, expected, kind="http"):
    calls, messages = [], []
    async def receive():
        raise AssertionError("request body must not be consumed")
    async def send(message):
        messages.append(message)
    async def owner(scope, incoming, outgoing):
        calls.append(scope)
    await cls(owner, **options)({"type": kind, "method": "POST", "headers": headers}, receive, send)
    assert bool(calls) == expected
    if not expected:
        assert messages[0] == {"type": "websocket.close", "code": 1008} if kind == "websocket" else messages[0]["status"] == 403
async def main():
    for port in (8080, 8881):
        for host in ("localhost", "100.64.0.9", "neutral.tailnet.invalid"):
            base = [(b"host", f"{host}:{port}".encode())]
            await probe(base, True)
            for kind in ("http", "websocket"):
                await probe(base + [(b"origin", f"http://{host}:{port}".encode())], True, kind)
                for origin in ("https://foreign.example", "http://127.0.0.1:8883"):
                    await probe(base + [(b"origin", origin.encode())], False, kind)
            await probe(base + [(b"sec-fetch-site", b"cross-site")], False)
asyncio.run(main())
print("Built Open WebUI final middleware wiring and native/peer/browser/WebSocket admission passed; app not started")

# Use the package's dependency paths, then load the real ASGI app. Lifespan is
# deliberately not started: all database/import state is in the check sandbox.
frontend_assignment = next(line for line in (package / "bin/open-webui").read_text().splitlines()
                           if line.startswith("export FRONTEND_BUILD_DIR="))
key, value = shlex.split(frontend_assignment)[1].split("=", 1)
assert key == "FRONTEND_BUILD_DIR" and Path(value, "index.html").is_file()
os.environ[key] = value
runpy.run_path(package / "bin/.open-webui-wrapped", run_name="sinnix_webui_probe")
app = __import__("open_webui.main", fromlist=["app"]).app
assert app.user_middleware[0].cls.__name__ == "BrowserBoundary"
async def real_probe(headers, expected, path="/health"):
    messages, reads = [], []
    async def receive():
        reads.append(True)
        return {"type": "http.request", "body": b"", "more_body": False}
    async def send(message):
        messages.append(message)
    scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
             "http_version": "1.1", "scheme": "http", "method": "GET", "path": path,
             "raw_path": path.encode(), "root_path": "", "query_string": b"", "headers": headers,
             "server": ("127.0.0.1", 8080), "client": ("127.0.0.1", 12345)}
    await app(scope, receive, send)
    assert messages[0]["status"] == expected
    if expected == 403:
        assert not reads
async def real_main():
    base = [(b"host", b"127.0.0.1:8080")]
    await real_probe(base, 200)
    await real_probe(base, 200, "/")
    await real_probe(base + [(b"origin", b"https://foreign.example")], 403)
    await real_probe(base + [(b"sec-fetch-site", b"cross-site")], 403)
    await real_probe([(b"host", b"neutral.tailnet.invalid:8881"),
                      (b"origin", b"http://neutral.tailnet.invalid:8881")], 200)
asyncio.run(real_main())
print("Real Open WebUI ASGI health/native/peer/refusal checks passed without lifespan or models")
