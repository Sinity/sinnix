"""Prune inventory lifetime, without reading or removing headset media."""

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(
    os.environ.get(
        "QUEST_PRUNE_TEST_SCRIPT",
        Path(__file__).resolve().parents[3] / "scripts/sinnix-quest",
    )
)


def invocation(tmp_path, mode):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    archive = tmp_path / "archive"
    archive.mkdir()
    definition = (
        "media() {"
        + SCRIPT.read_text().split("\nmedia() {", 1)[1].split("\nsync()", 1)[0]
    )
    shell = (
        r"""
set -euo pipefail
resolve_target() { echo fixture; }
adb_shell_args() {
  touch "$READY"
  case "$MODE" in
    cancel) sleep 30 ;;
    fail) return 7 ;;
  esac
}
"""
        + definition
        + "\nmedia prune\n"
    )
    env = {
        "PATH": os.environ["PATH"],
        "TMPDIR": str(scratch),
        "MODE": mode,
        "ARCHIVE_DIR": str(archive),
        "READY": str(tmp_path / "ready"),
    }
    return shell, env, scratch


@pytest.mark.parametrize("mode", ["success", "fail"])
def test_prune_inventory_removed_on_completion(tmp_path, mode):
    shell, env, scratch = invocation(tmp_path, mode)
    result = subprocess.run(
        ["bash", "-c", shell], env=env, capture_output=True, text=True, timeout=5
    )
    assert result.returncode == (0 if mode == "success" else 1), result.stderr
    assert not list(scratch.iterdir())


def test_prune_inventory_removed_on_cancel(tmp_path):
    shell, env, scratch = invocation(tmp_path, "cancel")
    proc = subprocess.Popen(
        ["bash", "-c", shell],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 5
        while not (tmp_path / "ready").exists():
            assert proc.poll() is None
            assert time.monotonic() < deadline
            time.sleep(0.01)
        assert len(list(scratch.iterdir())) == 1
        os.killpg(proc.pid, signal.SIGTERM)
        proc.communicate(timeout=5)
        assert proc.returncode != 0
        assert not list(scratch.iterdir()), "cancelled prune left its inventory behind"
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate(timeout=5)
