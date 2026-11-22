"""Stream six moments per video from the shared thumbnail cache."""

import os
import signal
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor

PERCENTAGES = (5, 22, 39, 56, 73, 90)


class PreviewWorker:
    def __init__(self):
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="video-preview")
        self._requests = {}
        self._lock = threading.Lock()

    def cancel_except(self, ids):
        with self._lock:
            for key in self._requests.keys() - set(ids):
                _, process = self._requests.pop(key)
                if process is not None and process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass

    def request(self, item, callback, *, background=False, cached_only=False):
        with self._lock:
            if item.id in self._requests or not item.path or item.kind != "video":
                return
            token = object()
            self._requests[item.id] = (token, None)
            self._pool.submit(self._generate, item, callback, background, token, cached_only)

    def close(self):
        self.cancel_except(())
        self._pool.shutdown(wait=True, cancel_futures=True)

    def _generate(self, item, callback, background, token, cached_only):
        missing = set(PERCENTAGES)
        command = ["media-preview-cache", "batch", item.path, *map(str, PERCENTAGES)]
        if cached_only:
            command.insert(2, "--cached")
        if background:
            command = ["nice", "-n", "10", *command]
        with self._lock:
            if self._requests.get(item.id) != (token, None):
                return
            try:
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                           text=True, start_new_session=True)
            except OSError:
                callback(item.id, tuple((pct, "") for pct in PERCENTAGES))
                return
            self._requests[item.id] = (token, process)
        with process:
            for line in process.stdout:
                number, sep, path = line.rstrip("\n").partition("\t")
                if sep and number.isdigit() and int(number) in missing:
                    pct = int(number)
                    missing.remove(pct)
                    callback(item.id, ((pct, path),))
        if missing and not cached_only:
            callback(item.id, tuple((pct, "") for pct in sorted(missing)))
