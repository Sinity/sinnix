"""Hyprland IPC glue: socket2 event classification + hyprctl JSON readers.

The socket2 line-classification function is pure (string in, bool out) and
directly pytest-covered. The hyprctl/socket readers are thin IO wrappers
with the subprocess/socket call injected as a callable -- testable by
passing a fake reader.
"""

from __future__ import annotations

import json
import os
import select
import socket
import subprocess
import threading
from typing import Any, Callable

# Hyprland socket2 event lines this lane treats as capture triggers: any
# window/workspace/monitor change that could put new content on screen.
# Deliberately excludes high-frequency/no-visual-change events (e.g.
# `moveresize>>`, `activelayout>>`) -- those churn out multiple times per
# second during a window drag and would defeat the point of event-driven
# capture (screenpipe-style: state changes, not continuous polling).
TRIGGER_EVENT_PREFIXES = (
    "workspace>>",
    "workspacev2>>",
    "focusedmon>>",
    "activewindow>>",
    "activewindowv2>>",
    "openwindow>>",
    "closewindow>>",
    "fullscreen>>",
)


def is_trigger_event(line: str) -> bool:
    """True when a raw Hyprland socket2 line should trigger a capture."""
    return line.startswith(TRIGGER_EVENT_PREFIXES)


def socket2_path(runtime_dir: str, instance_signature: str) -> str:
    return os.path.join(runtime_dir, "hypr", instance_signature, ".socket2.sock")


def connect_socket2(path: str) -> socket.socket:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(path)
    except OSError:
        sock.close()
        raise
    return sock


class SocketEventPump:
    """Drain socket2 during slow captures, coalescing triggers without payloads."""

    def __init__(self, sock: socket.socket):
        self._sock = sock
        self._condition = threading.Condition()
        self._stop = threading.Event()
        self._pending = False
        self._error: str | None = None
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def _read(self) -> None:
        buffer = b""
        try:
            while not self._stop.is_set():
                ready, _, _ = select.select([self._sock], [], [], 0.25)
                if not ready:
                    continue
                try:
                    chunk = self._sock.recv(65536)
                except BlockingIOError:
                    continue
                if not chunk:
                    raise EOFError("Hyprland socket2 closed")
                buffer += chunk
                trigger = False
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    trigger |= is_trigger_event(line.decode("utf-8", "replace"))
                if trigger:
                    with self._condition:
                        self._pending = True
                        self._condition.notify_all()
        except (OSError, EOFError) as exc:
            with self._condition:
                self._error = str(exc)
                self._condition.notify_all()

    def poll(self, timeout: float) -> tuple[bool, str | None]:
        with self._condition:
            self._condition.wait_for(
                lambda: self._pending or self._error is not None, timeout=timeout
            )
            pending = self._pending
            self._pending = False
            return pending, self._error

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)


HyprctlJsonReader = Callable[[list[str]], str | None]


def make_hyprctl_json_reader(
    hyprctl_bin: str, timeout: float = 1.0
) -> HyprctlJsonReader:
    def _read(args: list[str]) -> str | None:
        try:
            proc = subprocess.run(
                [hyprctl_bin, *args, "-j"],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return proc.stdout

    return _read


def _parse_json(raw: str | None) -> Any | None:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def get_active_window(read_json: HyprctlJsonReader) -> dict | None:
    """Resolve focused-window class/title/workspace/geometry/monitor id via
    `hyprctl activewindow -j`. Returns None if hyprctl fails or no window is
    focused (empty desktop)."""
    data = _parse_json(read_json(["activewindow"]))
    if not isinstance(data, dict) or not data:
        return None
    workspace = data.get("workspace")
    at = data.get("at") or [None, None]
    size = data.get("size") or [None, None]
    return {
        "class": data.get("class") or None,
        "title": data.get("title") or None,
        "workspace": workspace.get("name") if isinstance(workspace, dict) else None,
        "monitor_id": data.get("monitor"),
        "geometry": {
            "x": at[0] if len(at) > 0 else None,
            "y": at[1] if len(at) > 1 else None,
            "width": size[0] if len(size) > 0 else None,
            "height": size[1] if len(size) > 1 else None,
        },
    }


def get_monitors(read_json: HyprctlJsonReader) -> list[dict]:
    data = _parse_json(read_json(["monitors"]))
    return data if isinstance(data, list) else []


def monitor_name_for_id(monitors: list[dict], monitor_id: Any) -> str | None:
    for monitor in monitors:
        if monitor.get("id") == monitor_id:
            return monitor.get("name")
    return None


def get_cursor_pos(read_json: HyprctlJsonReader) -> tuple[int, int] | None:
    data = _parse_json(read_json(["cursorpos"]))
    if not isinstance(data, dict):
        return None
    x, y = data.get("x"), data.get("y")
    if not isinstance(x, int) or not isinstance(y, int):
        return None
    return (x, y)
