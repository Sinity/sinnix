import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / "scripts/ytdlp-clip-watch"


def invoke(tmp_path, payload):
    calls = tmp_path / "calls.json"
    launcher = tmp_path / "setsid"
    launcher.write_text(
        f"#!{sys.executable}\nimport json,sys\nfrom pathlib import Path\nPath({str(calls)!r}).write_text(json.dumps(sys.argv[1:]))\n"
    )
    launcher.chmod(0o700)
    env = {
        **os.environ,
        "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
        "YTDLP_CLIP_DIR": str(tmp_path / "download"),
        "YTDLP_CLIP_LOG_DIR": str(tmp_path / "logs"),
    }
    process = subprocess.Popen(
        ["bash", str(SCRIPT), "--handle"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    completed = []

    def produce():
        try:
            for offset in range(0, len(payload), 65536):
                process.stdin.write(payload[offset : offset + 65536])
            process.stdin.close()
            completed.append(True)
        except BrokenPipeError:
            completed.append(False)

    writer = threading.Thread(target=produce)
    writer.start()
    process.wait(timeout=10)
    writer.join(timeout=2)
    assert completed == [True], "clipboard producer was not fully drained"
    return (
        process.returncode,
        process.stderr.read().decode(),
        json.loads(calls.read_text()) if calls.exists() else None,
    )


def test_single_url_is_passed_without_clipboard_reread(tmp_path):
    url = "https://example.invalid/watch?q=neutral"
    code, _, args = invoke(tmp_path, (url + "\n").encode())
    assert code == 0
    assert args[-2] == url
    assert (tmp_path / "logs").stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize(
    "payload",
    [
        b"https://example.invalid/" + b"x" * (8 * 1024 * 1024),
        b"https://example.invalid/one\nhttps://example.invalid/two",
    ],
    ids=["oversized", "multiline"],
)
def test_oversized_or_multiline_selection_is_refused_after_full_drain(
    tmp_path, payload
):
    code, error, args = invoke(tmp_path, payload)
    assert code == 2
    assert "clipboard" in error
    assert args is None
