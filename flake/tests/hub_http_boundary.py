"""Exercise the deployed Caddy routes against a neutral proxy owner."""
from __future__ import annotations

import http.client
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Owner(BaseHTTPRequestHandler):
    calls = []
    def handle_request(self):
        self.calls.append(self.path)
        body = b"neutral owner"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    do_GET = handle_request
    do_POST = handle_request
    def log_message(self, *_args):
        pass


owner = ThreadingHTTPServer(("127.0.0.1", 0), Owner)
thread = threading.Thread(target=owner.serve_forever, daemon=True)
thread.start()
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    port = free_port()
    source = Path(sys.argv[1]).read_text()
    # Only the transport addresses and log destination change. Guards and
    # route ordering remain those rendered for the real host.
    source = source.replace(":8880", f":{port}")
    source = re.sub(r"reverse_proxy unix/[^\s]+", f"reverse_proxy 127.0.0.1:{owner.server_port}", source)
    source = re.sub(r"output file [^\s]+", f"output file {root / 'access.log'}", source)
    config = root / "Caddyfile"
    config.write_text(source)
    environment = {**os.environ, "SINNIX_HUB_TAILNET_IP": "127.0.0.2"}
    with (root / "caddy.log").open("w") as log:
        process = subprocess.Popen(["caddy", "run", "--config", str(config), "--adapter", "caddyfile"], env=environment, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 10
            while True:
                assert process.poll() is None, (root / "caddy.log").read_text()
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=.2):
                        break
                except OSError:
                    assert time.monotonic() < deadline, (root / "caddy.log").read_text()
                    time.sleep(.05)

            def request(path, headers, expected, *, send_body=True, method="POST"):
                before = len(Owner.calls)
                client = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
                client.putrequest(method, path)
                for name, value in headers.items():
                    client.putheader(name, value)
                client.putheader("Content-Length", "2" if send_body else "1000000")
                client.endheaders()
                if send_body:
                    client.send(b"{}")
                response = client.getresponse()
                response.read()
                client.close()
                assert response.status == expected, (path, headers, response.status)
                assert len(Owner.calls) - before == (1 if expected == 200 else 0), (path, headers, Owner.calls)

            same_origin = f"http://127.0.0.1:{port}"
            for path in ("/ops/v1/actions", "/terminals/not-a-terminal", "/v1/actions", "/feedback"):
                request(path, {"Origin": "https://example.invalid"}, 403)
                request(path, {"Origin": same_origin, "Sec-Fetch-Site": "same-origin"}, 200)
                request(path, {}, 200)
                request(path, {"Sec-Fetch-Site": "cross-site"}, 403)
            for path in ("/ops/v1/actions", "/terminals/not-a-terminal", "/v1/actions"):
                request(path, {"Origin": "null"}, 403)
                request(path, {"Sec-Fetch-Site": "same-site"}, 403)
            request("/feedback", {"Origin": "null", "Sec-Fetch-Site": "cross-site"}, 200)
            navigation = {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document", "Sec-Fetch-User": "?1"}
            request("/terminals/not-a-terminal", navigation, 200, method="GET")
            request("/terminals/not-a-terminal", navigation, 403)
            for header in ("Origin", "Sec-Fetch-Site", "Sec-Fetch-Mode", "Sec-Fetch-Dest", "Sec-Fetch-User"):
                request("/phone/v1/intent", {header: "same-origin"}, 403)
            request("/terminals/not-a-terminal", {"Origin": "https://example.invalid"}, 403, send_body=False)
            print("hub browser boundary: native, same-origin and local-report routes preserved; forged requests never reached owner")
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=5)
            owner.shutdown(); owner.server_close(); thread.join(timeout=2)
