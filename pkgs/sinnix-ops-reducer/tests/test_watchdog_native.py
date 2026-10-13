"""Real FIFO blocking and sd_notify datagrams, without touching live services."""

import os
import signal
import socket
import subprocess
import sys
import time


def test_native_watchdog_survives_io_and_stops_with_the_process(tmp_path):
    fifo = tmp_path / "blocked-input"
    entered = tmp_path / "entered"
    address = tmp_path / "notify"
    os.mkfifo(fifo)
    code = """
import sys
from pathlib import Path
from sinnix_ops_reducer.server import serve
class BlockedReducer:
    def refresh(self):
        Path(sys.argv[2]).touch()
        with Path(sys.argv[1]).open('rb') as source:
            source.read(1)
serve(BlockedReducer(), 'neutral', [], 0.1, None)
"""
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as receiver:
        receiver.bind(str(address))
        env = {**os.environ, "NOTIFY_SOCKET": str(address), "WATCHDOG_USEC": "200000"}
        child = subprocess.Popen([sys.executable, "-c", code, str(fifo), str(entered)], env=env)
        try:
            deadline = time.monotonic() + 5
            while not entered.exists():
                assert child.poll() is None
                assert time.monotonic() < deadline
                time.sleep(0.01)
            receiver.settimeout(2)
            for _ in range(4):
                assert receiver.recv(1024) == b"WATCHDOG=1"
            assert child.poll() is None
            child.send_signal(signal.SIGSTOP)
            _, status = os.waitpid(child.pid, os.WUNTRACED)
            assert os.WIFSTOPPED(status)
            receiver.setblocking(False)
            while True:
                try:
                    receiver.recv(1024)
                except BlockingIOError:
                    break
            receiver.settimeout(0.5)
            try:
                receiver.recv(1024)
            except TimeoutError:
                pass
            else:
                raise AssertionError("stopped process continued to claim liveness")
            child.send_signal(signal.SIGCONT)
            receiver.settimeout(2)
            assert receiver.recv(1024) == b"WATCHDOG=1"
        finally:
            child.kill()
            child.wait(timeout=5)
