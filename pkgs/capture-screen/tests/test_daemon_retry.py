from __future__ import annotations

import io
import time
from types import SimpleNamespace

import pytest
from PIL import Image
from sinnix_capture_screen import daemon


@pytest.mark.parametrize("unavailable", [{}, {"dpmsStatus": False}, {"disabled": True}])
def test_failed_frame_publication_does_not_suppress_identical_retry(
    tmp_path, monkeypatch, unavailable
):
    image = Image.new("RGB", (32, 32))
    for x in range(32):
        for y in range(32):
            image.putpixel((x, y), (255, 255, 255) if (x + y) % 2 else (0, 0, 0))
    png = io.BytesIO()
    image.save(png, format="PNG")
    iteration = 0
    now = time.time()

    class Socket:
        closed = False

        def setblocking(self, value):
            pass

        def recv(self, size):
            return b""

        def close(self):
            self.closed = True

    sock = Socket()

    def select(*args):
        nonlocal iteration
        iteration += 1
        return ([sock] if iteration == (5 if unavailable else 4) else []), [], []

    monkeypatch.setattr(daemon.select, "select", select)
    monkeypatch.setattr(
        daemon,
        "time",
        SimpleNamespace(
            time=lambda: now + iteration * 40,
            monotonic=lambda: iteration * 40,
            strftime=time.strftime,
            gmtime=time.gmtime,
        ),
    )
    monkeypatch.setattr(daemon.hypr, "connect_socket2", lambda *args: sock)
    monkeypatch.setattr(daemon.hypr, "make_hyprctl_json_reader", lambda *args: None)
    monkeypatch.setattr(daemon.hypr, "get_cursor_pos", lambda *args: None)
    monkeypatch.setattr(
        daemon.hypr,
        "get_monitors",
        lambda *args: [
            {
                "id": 0,
                "name": "fixture",
                **(
                    unavailable
                    if iteration == 1
                    else {"dpmsStatus": True, "disabled": False}
                ),
            }
        ],
    )
    monkeypatch.setattr(
        daemon.hypr,
        "get_active_window",
        lambda *args: {
            "monitor_id": 0,
            "class": "fixture",
            "title": "fixture",
            "workspace": "1",
            "geometry": {"x": 0, "y": 0, "width": 32, "height": 32},
        },
    )
    grabs = []

    def grab(*args):
        assert not (unavailable and iteration == 1), (
            "screencopy attempted on unavailable output"
        )
        grabs.append(args)
        return png.getvalue(), None

    writes = []

    def write(**kwargs):
        writes.append(kwargs)
        return None if len(writes) == 1 else tmp_path / "retained.webp"

    monkeypatch.setattr(daemon.capture, "run_grim", grab)
    monkeypatch.setattr(daemon.capture, "write_frame", write)
    args = daemon.build_arg_parser().parse_args(
        [
            "--capture-root",
            str(tmp_path),
            "--lane",
            "fixture",
            "--runtime-dir",
            str(tmp_path),
            "--instance-signature",
            "fixture",
            "--periodic-floor-seconds",
            "1",
        ]
    )
    assert daemon.run(args) == 1  # Controlled socket close ends the loop.
    assert sock.closed
    assert len(grabs) == 3
    assert len(writes) == 2  # Failed first write retried; successful frame deduped.
    assert writes[0]["webp_bytes"] == writes[1]["webp_bytes"]
    assert writes[0]["filename"] != writes[1]["filename"]
