"""Exercise the deployed Caddy routes against a neutral proxy owner."""
from __future__ import annotations

import http.client
import json
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
    protocol_version = "HTTP/1.1"
    calls = []
    def handle_request(self):
        self.calls.append(self.path)
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if self.headers.get("Upgrade", "").lower() == "websocket":
            self.send_response(101)
            self.send_header("Connection", "Upgrade")
            self.send_header("Upgrade", "websocket")
            self.end_headers()
            self.close_connection = True
            return
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
    # Exercise the rendered startup owner with synthetic interface/status
    # processes. Rejected identities must not overwrite the last environment.
    resolver_source = Path(sys.argv[2]).read_text()
    ip_fixture = root / "ip-fixture"
    ip_fixture.write_text(f"#!{sys.executable}\nprint('1: tailscale0 inet 127.0.0.2/32 scope global tailscale0')\n")
    ip_fixture.chmod(0o700)
    status_fixture = root / "status-fixture"
    status_fixture.write_text(f"#!{sys.executable}\nimport os,sys\nif os.environ.get('STATUS_FAIL'): sys.exit(7)\nprint(os.environ['STATUS_JSON'])\n")
    status_fixture.chmod(0o700)
    resolver_source = re.sub(r"/nix/store/[^\s]+/bin/ip", str(ip_fixture), resolver_source)
    resolver_source = re.sub(r"/nix/store/[^\s]+/bin/tailscale", str(status_fixture), resolver_source)
    resolver_script = root / "resolver"
    resolver_script.write_text(resolver_source)
    resolver_script.chmod(0o700)
    bind_environment = root / "bind.env"
    valid_status = {"Self": {"TailscaleIPs": ["127.0.0.2"], "DNSName": "neutral.tailnet.invalid."}}
    status_cases = [
        (valid_status, False, True),
        ({"Self": {"TailscaleIPs": ["127.0.0.3"], "DNSName": "neutral.tailnet.invalid"}}, False, False),
        ({"Self": {"TailscaleIPs": ["127.0.0.2"], "DNSName": "bad\nname"}}, False, False),
        ({"Self": {"TailscaleIPs": ["127.0.0.2"], "DNSName": "bad..name"}}, False, False),
        ({"Self": {"TailscaleIPs": ["127.0.0.2"]}}, False, False),
        (valid_status, True, False),
    ]
    for status, fail, valid in status_cases:
        preimage = b"previous verified environment\n"
        bind_environment.write_bytes(preimage)
        env = {**os.environ, "STATUS_JSON": json.dumps(status)}
        env.pop("STATUS_FAIL", None)
        if fail: env["STATUS_FAIL"] = "1"
        result = subprocess.run([str(resolver_script), str(bind_environment)], env=env, capture_output=True, timeout=10)
        assert (result.returncode == 0) == valid, result.stderr
        if valid:
            assert bind_environment.read_text() == "SINNIX_HUB_TAILNET_IP=127.0.0.2\nSINNIX_HUB_DNS_NAME=neutral.tailnet.invalid\n"
        else:
            assert bind_environment.read_bytes() == preimage
        assert not list(root.glob(".SINNIX_HUB_TAILNET_IP.tmp.*"))
    port = free_port()
    report_port = int(sys.argv[3])
    source = Path(sys.argv[1]).read_text()
    frontend_ports = [int(value) for value in re.findall(r"http://:(\d+)\s*\{", source) if int(value) not in (8880, report_port)]
    # Only the transport addresses and log destination change. Guards and
    # route ordering remain those rendered for the real host.
    source = source.replace(":8880", f":{port}")
    source = re.sub(r"reverse_proxy [^\s]+", f"reverse_proxy 127.0.0.1:{owner.server_port}", source)
    source = re.sub(r"output file [^\s]+", f"output file {root / 'access.log'}", source)
    reports = root / 'reports'
    reports.mkdir()
    (reports / 'neutral.html').write_text('<script>window.neutralReport=true</script><img src="asset.svg">')
    (reports / 'asset.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    source = re.sub(r"root \* [^\s]+", f"root * {reports}", source)
    config = root / "Caddyfile"
    config.write_text(source)
    environment = {**os.environ, "SINNIX_HUB_TAILNET_IP": "127.0.0.2", "SINNIX_HUB_DNS_NAME": "neutral.tailnet.invalid"}
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

            def request(path, headers, expected, *, send_body=True, method="POST", request_port=port):
                before = len(Owner.calls)
                client = http.client.HTTPConnection("127.0.0.1", request_port, timeout=2)
                client.putrequest(method, path, skip_host="Host" in headers)
                headers = {"Content-Type": "application/json", **headers}
                for name, value in headers.items():
                    for item in ([value] if isinstance(value, str) else value):
                        client.putheader(name, item)
                client.putheader("Content-Length", "2" if send_body else "100")
                client.endheaders()
                if send_body:
                    client.send(b"{}")
                try:
                    response = client.getresponse()
                except TimeoutError as error:
                    raise AssertionError((path, headers, Owner.calls[before:])) from error
                response.read()
                client.close()
                assert response.status == expected, (path, headers, response.status)
                assert len(Owner.calls) - before == (1 if expected in (200, 101) else 0), (path, headers, Owner.calls)

            for path in ("/ops/v1/actions", "/terminals/not-a-terminal", "/v1/actions", "/feedback", "/phone/v1/ping", "/reports/missing"):
                request(path, {"Host": f"rebound.example.invalid:{port}"}, 403)
            for name in ("localhost", "127.0.0.1", "127.0.0.2", "neutral.tailnet.invalid"):
                request("/v1/actions", {"Host": f"{name}:{port}", "Origin": f"http://{name}:{port}"}, 200)
            for frontend_port in frontend_ports:
                request("/", {"Host": f"rebound.example.invalid:{frontend_port}"}, 403, request_port=frontend_port)
                request("/", {"Host": f"neutral.tailnet.invalid:{frontend_port}"}, 200, request_port=frontend_port)
                for host in ("127.0.0.1", "neutral.tailnet.invalid"):
                    request("/", {"Host": f"{host}:{frontend_port}", "Origin": f"http://{host}:{frontend_port}", "Sec-Fetch-Site": "same-origin"}, 200, request_port=frontend_port)
                request("/", {"Origin": "https://foreign.example.invalid"}, 403, request_port=frontend_port)
                request("/", {"Origin": f"http://127.0.0.1:{report_port}"}, 403, request_port=frontend_port)
                request("/", {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Dest": "empty"}, 403, request_port=frontend_port)
                request("/", {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document", "Sec-Fetch-User": "?1"}, 200, method="GET", request_port=frontend_port)
                request("/", {"Host": f"neutral.tailnet.invalid:{frontend_port}", "Origin": f"http://neutral.tailnet.invalid:{frontend_port}", "Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "websocket", "Connection": "Upgrade", "Upgrade": "websocket"}, 101, method="GET", request_port=frontend_port)
                request("/", {"Origin": "https://foreign.example.invalid"}, 403, send_body=False, request_port=frontend_port)
            before = len(Owner.calls)
            for path in ('/ops/v1/actions', '/v1/actions', '/terminals/', '/phone/v1/ping', '/private/file-catalog'):
                request(path, {}, 404, request_port=report_port)
            assert len(Owner.calls) == before
            client = http.client.HTTPConnection('127.0.0.1', report_port, timeout=2)
            client.request('GET', '/reports/neutral.html')
            response = client.getresponse()
            assert response.status == 200 and response.read() == (reports / 'neutral.html').read_bytes()
            client.close()
            client = http.client.HTTPConnection('127.0.0.1', report_port, timeout=2)
            client.request('GET', '/reports/asset.svg')
            response = client.getresponse(); assert response.status == 200; response.read(); client.close()
            request('/feedback', {'Origin': f'http://127.0.0.1:{report_port}', 'Sec-Fetch-Site': 'same-origin'}, 200, request_port=report_port)
            request('/feedback', {'Origin': 'https://example.invalid'}, 403, request_port=report_port)
            request('/ops/v1/actions', {'Origin': f'http://127.0.0.1:{report_port}'}, 403)
            request('/feedback', {'Origin': f'http://127.0.0.1:{report_port}', 'Sec-Fetch-Site': 'same-site'}, 200)
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
            request("/terminals/v1/windows/1/2/send", {"Origin": "https://example.invalid", "Content-Type": "text/plain"}, 403, send_body=False)
            for path in ('/ops/v1/actions', '/ops/v1/actions/prepare', '/v1/health/failure', '/terminals/v1/windows/1/2/send', '/feedback', '/phone/v1/intent', '/phone/v1/job-answer/', '/phone/intent///'):
                for media in ([], 'text/plain', ['application/json', 'application/json']):
                    request(path, {'Content-Type': media}, 415, send_body=False)
                request(path, {'Content-Type': 'Application/JSON; charset=utf-8'}, 200)
            request('/feedback', {'Content-Type': 'text/plain', 'Origin': f'http://127.0.0.1:{report_port}'}, 415, send_body=False, request_port=report_port)
            print("hub browser boundary: native, same-origin and local-report routes preserved; forged requests never reached owner")
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=5)
            owner.shutdown(); owner.server_close(); thread.join(timeout=2)
