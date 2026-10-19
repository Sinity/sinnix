"""Installer log lifetime ends with the invocation, including cancellation."""

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(
    os.environ.get(
        "PHONE_INSTALL_TEST_SCRIPT",
        Path(__file__).resolve().parents[3] / "scripts/sinnix-phone",
    )
)


def installer(tmp_path, mode):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    body = (
        SCRIPT.read_text()
        .split("\napp-install)\n", 1)[1]
        .split("\n  ;;\napp-start)", 1)[0]
    )
    # The post-install recorder restart is independently covered. No device
    # command or Nix build is executed by this scratch-lifetime fixture.
    body = body.replace('"$0" app-start', ":")
    shell = (
        r"""
set -euo pipefail
ADB_RESOLVED=fixture
adb_any() { echo fixture; }
require_unlocked_phone() { :; }
ensure_app_grants() { :; }
ensure_device_capture_settings() { :; }
adb_shell_args() { :; }
ssh_phone() { :; }
nix() {
  touch "$READY"
  case "$MODE" in
    cancel) sleep 30 ;;
    fail) echo fixture-failure; return 7 ;;
    success) echo Success ;;
  esac
}
"""
        + body
    )
    env = {
        "PATH": os.environ["PATH"],
        "TMPDIR": str(scratch),
        "MODE": mode,
        "READY": str(tmp_path / "ready"),
    }
    return shell, env, scratch


@pytest.mark.parametrize("mode", ["success", "fail"])
def test_install_log_removed_on_completion(tmp_path, mode):
    shell, env, scratch = installer(tmp_path, mode)
    result = subprocess.run(
        ["bash", "-c", shell], env=env, capture_output=True, text=True, timeout=5
    )
    assert result.returncode == (0 if mode == "success" else 1), result.stderr
    assert not list(scratch.iterdir())


def test_install_log_removed_on_cancel(tmp_path):
    shell, env, scratch = installer(tmp_path, "cancel")
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
        assert not list(scratch.iterdir()), "cancelled install left its log behind"
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate(timeout=5)
