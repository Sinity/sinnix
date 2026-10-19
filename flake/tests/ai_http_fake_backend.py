"""Small VM-only model substitute, with one durable counter per start."""

import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/event-stream" if self.path == "/hold" else "text/plain",
        )
        self.end_headers()
        if self.path == "/hold":
            while True:
                self.wfile.write(b"data: still running\n\n")
                self.wfile.flush()
                time.sleep(0.1)
        else:
            self.wfile.write(b"native fixture response\n")


with Path(sys.argv[2]).open("a") as file:
    file.write("start\n")
# Exercise the production readiness wait, rather than assuming Type=simple
# has made the backend port ready when the unit becomes active.
time.sleep(1)
ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
