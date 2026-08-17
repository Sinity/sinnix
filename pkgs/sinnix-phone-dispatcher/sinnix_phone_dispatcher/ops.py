"""Reads from the ops reducer's own Unix socket."""

from __future__ import annotations

import json
import os
import socket
from typing import Any


def ops_get(path: str) -> Any | None:
    """Read the ops reducer over its Unix socket.

    Straight to the socket rather than through the hub: this process runs on
    the same machine in the same user manager, and going out through Caddy to
    come back in would add a hop that can fail independently of the thing
    being asked about.
    """
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    sock_path = os.environ.get("SINNIX_OPS_SOCKET", f"{runtime}/sinnix/ops.sock")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(4)
            s.connect(sock_path)
            s.sendall(
                f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode()
            )
            chunks = []
            while True:
                data = s.recv(65536)
                if not data:
                    break
                chunks.append(data)
        raw = b"".join(chunks)
        head, _, body = raw.partition(b"\r\n\r\n")
        if b" 200 " not in head.split(b"\r\n", 1)[0]:
            return None
        return json.loads(body.decode("utf-8", "replace"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
