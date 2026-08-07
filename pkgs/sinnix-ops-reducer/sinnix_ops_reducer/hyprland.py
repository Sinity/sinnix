from __future__ import annotations

import time
import glob
import socket
from dataclasses import dataclass
from typing import Any

STATIC_COOLDOWN = 60.0


@dataclass
class HyprlandState:
    fullscreen_game: bool = False
    static_content: bool = False
    last_static_transition: float = 0.0
    diagnostics: int = 0


def reduce_socket_event(state: HyprlandState, line: str, *, now: float | None = None) -> dict[str, Any]:
    now = time.monotonic() if now is None else now
    event, _, payload = line.partition(">>")
    if event == "fullscreen":
        state.fullscreen_game = payload.strip() == "1"
    elif event == "activewindow":
        app = payload.split(",", 1)[0].strip().lower()
        candidate = app in {"mpv", "vlc", "gamescope"}
        if candidate != state.static_content and now - state.last_static_transition >= STATIC_COOLDOWN:
            state.static_content = candidate
            state.last_static_transition = now
    else:
        state.diagnostics = min(state.diagnostics + 1, 32)
    return {"fullscreen_game": state.fullscreen_game, "static_content": state.static_content, "diagnostics": state.diagnostics}


class Socket2Adapter:
    def __init__(self) -> None:
        self.socket: socket.socket | None = None
        self.buffer = b""

    def poll(self, state: HyprlandState) -> None:
        if self.socket is None:
            paths = glob.glob("/tmp/hypr/*/.socket2.sock")
            if not paths:
                return
            try:
                self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.socket.settimeout(0.05)
                self.socket.connect(paths[0])
            except OSError:
                self.socket = None
                return
        try:
            self.buffer += self.socket.recv(8192)
            while b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                reduce_socket_event(state, line.decode("utf-8", errors="replace"))
        except (OSError, TimeoutError):
            return
