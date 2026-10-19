import http.server
import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path


class PollerTest(unittest.TestCase):
    def poll(self, body, length=True):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                if length:
                    self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *_args):
                pass

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            temporary = root / "tmp"
            temporary.mkdir()
            captured = root / "captured"
            sink = root / "sink"
            sink.write_text('#!/bin/sh\ncat > "$CAPTURED"\n')
            sink.chmod(0o700)
            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                proc = subprocess.run(
                    [
                        os.environ["AWAIR_POLLER"],
                        f"127.0.0.1:{server.server_port}",
                        str(sink),
                        str(root),
                    ],
                    env={
                        **os.environ,
                        "TMPDIR": str(temporary),
                        "CAPTURED": str(captured),
                    },
                    capture_output=True,
                    timeout=15,
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
            self.assertEqual(list(temporary.iterdir()), [])
            return proc, captured.read_bytes() if captured.exists() else None

    def test_ordinary_response_preserves_all_fields(self):
        body = b'{"score":83,"co2":600,"future":{"value":2}}\n'
        proc, result = self.poll(body)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(result), json.loads(body))

    def test_response_at_limit_is_preserved(self):
        prefix, suffix = b'{"score":83,"padding":"', b'"}'
        body = prefix + b"x" * (1048576 - len(prefix) - len(suffix)) + suffix
        proc, result = self.poll(body, length=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(result, body)

    def test_malformed_response_never_reaches_capture(self):
        for body in [b"{", b'{"co2":600}']:
            with self.subTest(body=body):
                proc, result = self.poll(body)
                self.assertNotEqual(proc.returncode, 0)
                self.assertIsNone(result)

    def test_oversized_response_never_reaches_capture(self):
        body = b'{"score":83,"padding":"' + b"x" * (1048576 + 1) + b'"}'
        for length in [True, False]:
            with self.subTest(content_length=length):
                proc, result = self.poll(body, length)
                self.assertNotEqual(proc.returncode, 0)
                self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
