import os
import sys
import threading

from previews import PERCENTAGES, PreviewWorker
from session import Item


def test_worker_delivers_normalized_percentages(tmp_path, monkeypatch):
    script = tmp_path / "media-preview-cache"
    script.write_text(
        f"#!{sys.executable}\nimport sys\nprint('/fixture/' + sys.argv[-1] + '.jpg')\n"
    )
    script.chmod(0o700)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    completed = threading.Event()
    received = []

    def collect(item_id, frames):
        assert item_id == "sample"
        received.append(frames)
        if len(frames) == len(PERCENTAGES):
            completed.set()

    worker = PreviewWorker()
    try:
        worker.request(
            Item("sample", "Grid", path="/fixture/grid.mp4", kind="video"), collect
        )
        assert completed.wait(3)
        assert [percentage for percentage, _path in received[-1]] == list(PERCENTAGES)
        assert all(
            path == f"/fixture/{percentage}.jpg" for percentage, path in received[-1]
        )
    finally:
        worker.close()
