from __future__ import annotations

import threading

import pytest
from sinnix_ops_reducer import server


@pytest.mark.parametrize("blocked_work", ["initial_refresh", "refresh", "sweep"])
def test_watchdog_remains_on_main_loop_during_blocking_io(monkeypatch, blocked_work):
    main_thread = threading.get_ident()
    entered = threading.Event()
    release = threading.Event()
    pings = []

    class Finished(Exception):
        pass

    def block():
        entered.set()
        assert release.wait(1), "blocking I/O starved the main-loop watchdog"

    class Reducer:
        calls = 0

        def refresh(self):
            self.calls += 1
            if self.calls == 1:  # Initial snapshot before READY.
                if blocked_work == "initial_refresh":
                    block()
                return
            if self.calls == 2:
                if blocked_work == "refresh":
                    block()
                return
            raise Finished("refresh failures must reach the main loop")

    class Listener:
        def __init__(self, *args, **kwargs):
            pass

        def serve_forever(self):
            pass

        def shutdown(self):
            pass

        def server_close(self):
            pass

    def notify(message):
        assert threading.get_ident() == main_thread
        if message == "WATCHDOG=1" and entered.is_set():
            pings.append(message)
            if len(pings) == 2:
                release.set()

    monkeypatch.setattr(server, "ThreadingHTTPServer", Listener)
    monkeypatch.setattr(server, "watchdog_period", lambda: 0.01)
    monkeypatch.setattr(server, "sd_notify", notify)
    monkeypatch.setattr(
        server, "run_sweep", lambda *args: block() if blocked_work == "sweep" else None
    )
    try:
        with pytest.raises(Finished, match="refresh failures"):
            server.serve(Reducer(), "fixture", [], 0.001, None, sweep_interval=60)
        assert len(pings) >= 2
    finally:
        release.set()
