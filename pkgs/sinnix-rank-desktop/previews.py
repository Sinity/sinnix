"""Prepare the current pair's video stills without blocking playback."""

import os
import signal
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor

PERCENTAGES = (5, 22, 39, 56, 73, 90)


class PreviewWorker:
    def __init__(self):
        self._pool = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="video-preview"
        )
        self._requests = {}
        self._lock = threading.Lock()

    def cancel_except(self, ids):
        with self._lock:
            for item_id in self._requests.keys() - set(ids):
                event, future = self._requests.pop(item_id)
                event.set()
                future.cancel()

    def request(self, item, callback):
        if item.kind != "video" or not item.path:
            return
        with self._lock:
            if item.id not in self._requests:
                cancelled = threading.Event()
                future = self._pool.submit(self._generate, item, callback, cancelled)
                self._requests[item.id] = (cancelled, future)

    def close(self):
        self.cancel_except(())
        self._pool.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def _generate(item, callback, cancelled):
        frames = []
        for percentage in PERCENTAGES:
            if cancelled.is_set():
                return
            try:
                with subprocess.Popen(
                    ["media-preview-cache", "ensure", item.path, str(percentage)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    start_new_session=True,
                ) as process:
                    while True:
                        try:
                            stdout, _ = process.communicate(timeout=0.15)
                            break
                        except subprocess.TimeoutExpired:
                            if cancelled.is_set():
                                try:
                                    os.killpg(process.pid, signal.SIGTERM)
                                except ProcessLookupError:
                                    pass
                                try:
                                    process.communicate(timeout=1)
                                except subprocess.TimeoutExpired:
                                    try:
                                        os.killpg(process.pid, signal.SIGKILL)
                                    except ProcessLookupError:
                                        pass
                                    process.communicate()
                                return
                    path = stdout.rstrip("\n")
                    if process.returncode == 0 and path:
                        frames.append((percentage, path))
            except FileNotFoundError:
                break
            if frames and not cancelled.is_set():
                callback(item.id, tuple(frames))
