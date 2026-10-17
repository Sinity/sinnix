"""Exercise Caddy's actual generated route without loading a model."""

import base64
import hashlib
import http.client
import os
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


class Backend(socketserver.StreamRequestHandler):
    def handle(self):
        self.server.connections += 1
        first = self.rfile.readline()
        if not first:
            return
        headers = {}
        while (line := self.rfile.readline()) != b"\r\n":
            key, value = line.decode().split(":", 1)
            headers[key.lower()] = value.strip()
        path = first.split()[1]
        if path == b"/stream":
            self.wfile.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nConnection: close\r\n\r\ndata: first\n\n")
            self.wfile.flush()
            assert self.server.stream_release.wait(timeout=5), "stream was buffered"
            self.wfile.write(b"data: last\n\n")
        elif path == b"/websocket":
            key = headers["sec-websocket-key"] + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
            accept = base64.b64encode(hashlib.sha1(key.encode()).digest())
            self.wfile.write(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: " + accept + b"\r\n\r\n")
            self.wfile.flush()
            assert self.rfile.read(2) == b"\x81\x84"
            mask = self.rfile.read(4)
            payload = self.rfile.read(4)
            assert bytes(x ^ mask[i % 4] for i, x in enumerate(payload)) == b"ping"
            self.wfile.write(b"\x81\x04pong")
        else:
            body = self.rfile.read(int(headers.get("content-length", "0")))
            payload = body or b"native response"
            self.wfile.write(b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(payload)).encode() + b"\r\nConnection: close\r\n\r\n" + payload)


def connect(headers=(), method="GET", path="/", body=b"", incomplete=False, port=24821, chunked=False):
    connection = socket.create_connection(("127.0.0.1", port), timeout=2)
    fields = list(headers)
    if not any(key.lower() == "host" for key, _ in fields):
        fields.append(("Host", f"127.0.0.1:{port}"))
    fields.append(("Connection", "close"))
    if incomplete and chunked:
        fields.append(("Transfer-Encoding", "chunked"))
    elif body or incomplete:
        fields.append(("Content-Length", "4" if incomplete else str(len(body))))
    request = f"{method} {path} HTTP/1.1\r\n" + "".join(f"{key}: {value}\r\n" for key, value in fields) + "\r\n"
    connection.sendall(request.encode() + body)
    return connection


def response(connection):
    # Connection: close does not make TCP EOF the response-body delimiter
    # when Content-Length is present. Complete the HTTP response before
    # closing the client, including when its request body was withheld.
    with connection:
        incoming = http.client.HTTPResponse(connection)
        incoming.begin()
        body = incoming.read()
        headers = b"\r\n".join(f"{key}: {value}".encode() for key, value in incoming.getheaders())
        return incoming.status, headers + b"\r\n\r\n" + body


def run(config):
    with tempfile.TemporaryDirectory() as directory:
        os.environ["TEST_UPSTREAM"] = directory + "/activation.sock"
        with socketserver.ThreadingUnixStreamServer(os.environ["TEST_UPSTREAM"], Backend) as server:
            server.connections = 0
            server.stream_release = threading.Event()
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            with open(Path(directory) / "caddy.log", "w+") as log:
                process = subprocess.Popen(["caddy", "run", "--config", config, "--adapter", "caddyfile"], stdout=log, stderr=log)
                try:
                    for _ in range(100):
                        if process.poll() is not None:
                            log.seek(0)
                            raise AssertionError(log.read())
                        try:
                            with socket.create_connection(("127.0.0.1", 24821), timeout=0.1):
                                break
                        except OSError:
                            time.sleep(0.05)
                    else:
                        raise AssertionError("Caddy did not listen")
                    origin = "http://127.0.0.1:24821"
                    denied = [
                        [("Host", "foreign.invalid:24821")],
                        [("Host", "127.0.0.1:24823")],
                        [("Origin", "https://foreign.invalid")],
                        [("Origin", "null")],
                        [("Origin", "")],
                        [("Origin", origin), ("Origin", origin)],
                        [("Origin", origin), ("Origin", "https://foreign.invalid")],
                        [("Sec-Fetch-Site", "cross-site")],
                        [("Sec-Fetch-Site", "")],
                        [("Sec-Fetch-Mode", "cors")],
                        [("Sec-Fetch-Site", "same-site")],
                        [("Sec-Fetch-Site", "none")],
                        [("Sec-Fetch-Site", "cross-site"), ("Sec-Fetch-Mode", "navigate"), ("Sec-Fetch-Dest", "document")],
                    ]
                    for header in ["Sec-Fetch-Site", "Sec-Fetch-Mode", "Sec-Fetch-Dest", "Sec-Fetch-User"]:
                        denied.append([("Origin", origin), (header, "same-origin"), (header, "same-origin")])
                    for fields in denied:
                        for chunked in (False, True):
                            try:
                                status, data = response(connect(fields, method="POST", incomplete=True, chunked=chunked))
                            except AssertionError as error:
                                raise AssertionError((fields, chunked, server.connections)) from error
                            assert status == 403, (fields, status, data)
                            assert b"connection: close" in data.lower(), data
                            assert server.connections == 0, (fields, server.connections)
                    for fields in [[("Origin", "http://127.0.0.1:24823")], [("Sec-Fetch-Site", "same-origin")], [("Sec-Fetch-Mode", "navigate"), ("Sec-Fetch-Dest", "document"), ("Sec-Fetch-User", "?1")]]:
                        status, _ = response(connect(fields, method="POST", incomplete=True, port=24823))
                        assert status == 403, fields
                        assert server.connections == 0, fields
                    assert response(connect(port=24823))[0] == 200
                    for fields in [[], [("Origin", origin)], [("Origin", "http://localhost:24822")], [("Sec-Fetch-Site", "same-origin")], [("Sec-Fetch-Site", "cross-site"), ("Sec-Fetch-Mode", "navigate"), ("Sec-Fetch-Dest", "document"), ("Sec-Fetch-User", "?1")]]:
                        assert response(connect(fields))[0] == 200, fields
                    payload = b"\x00binary multipart\xff" * 100
                    assert response(connect(method="POST", body=payload))[1].endswith(payload)
                    assert response(connect([("Origin", origin), ("Access-Control-Request-Method", "POST")], method="OPTIONS"))[0] == 200
                    connection = connect(path="/stream")
                    first = b""
                    while b"data: first" not in first:
                        first += connection.recv(4096)
                    server.stream_release.set()
                    assert b"data: last" in response_stream_tail(connection)
                    with socket.create_connection(("127.0.0.1", 24821), timeout=2) as connection:
                        connection.sendall(("GET /websocket HTTP/1.1\r\nHost: 127.0.0.1:24821\r\nOrigin: " + origin + "\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
                        stream = connection.makefile("rb")
                        assert b"101" in stream.readline()
                        while stream.readline() != b"\r\n":
                            pass
                        connection.sendall(b"\x81\x84\x00\x00\x00\x00ping")
                        assert stream.read(6) == b"\x81\x04pong"
                    print(f"{len(denied) * 2 + 3} refusals opened zero upstream connections; native/UI/navigation/preflight/binary/stream/WebSocket passed")
                finally:
                    process.terminate()
                    process.wait(timeout=10)
                    server.shutdown()


def response_stream_tail(connection):
    chunks = []
    with connection:
        while chunk := connection.recv(4096):
            chunks.append(chunk)
    return b"".join(chunks)


if __name__ == "__main__":
    run(sys.argv[1])
