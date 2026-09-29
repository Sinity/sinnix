"""Serve the streamable-HTTP app with a bounded, logged shutdown.

On SIGTERM uvicorn stops accepting requests and, left to its defaults, waits
for every in-flight request without limit. Synchronous handler work runs in
non-daemon worker threads that cancellation cannot interrupt, so one long read
kept the process alive until systemd's stop timeout killed it and every
in-flight call with it. Here in-flight calls get DRAIN_SECONDS to answer, the
lifespan closes the brokered MCP children, and a daemon timer ends the
process at EXIT_DEADLINE_SECONDS whatever is still running, inside the unit's
TimeoutStopSec.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from types import FrameType
from typing import Any, Callable

import uvicorn

from . import calllog

DRAIN_SECONDS = 5
EXIT_DEADLINE_SECONDS = 8


def _busy_worker_threads() -> int:
    return sum(
        1
        for thread in threading.enumerate()
        if thread is not threading.main_thread() and not thread.daemon
    )


class DrainingServer(uvicorn.Server):
    def __init__(
        self,
        config: uvicorn.Config,
        *,
        exit_deadline_seconds: float = EXIT_DEADLINE_SECONDS,
        hard_exit: Callable[[int], Any] = os._exit,
    ):
        super().__init__(config)
        self._exit_deadline_seconds = exit_deadline_seconds
        self._hard_exit = hard_exit
        self._deadline: threading.Timer | None = None

    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        if self._deadline is None:
            calllog.emit(
                {
                    "event": "gateway.shutdown",
                    "phase": "draining",
                    "signal": int(sig),
                    "drain_s": self.config.timeout_graceful_shutdown,
                    "connections": len(self.server_state.connections),
                }
            )
            self._deadline = threading.Timer(self._exit_deadline_seconds, self._expire)
            self._deadline.daemon = True
            self._deadline.start()
        super().handle_exit(sig, frame)

    def _expire(self) -> None:
        calllog.emit(
            {
                "event": "gateway.shutdown",
                "phase": "forced",
                "after_s": self._exit_deadline_seconds,
                "worker_threads": _busy_worker_threads(),
            }
        )
        self._hard_exit(0)


def serve_unix(app: Any, socket_path: Path) -> None:
    config = uvicorn.Config(
        calllog.RequestContextMiddleware(app),
        uds=str(socket_path),
        log_level="warning",
        timeout_graceful_shutdown=DRAIN_SECONDS,
    )
    DrainingServer(config).run()
