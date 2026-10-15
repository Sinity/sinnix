"""Phone observation scratch is disposable on success, failure and SIGTERM."""

import json
import os
from pathlib import Path
import signal
import subprocess
import time

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/sinnix-phone"


def observation(tmp_path, command, mode):
    following = "app-install" if command == "app-status" else "app-grants"
    body = SCRIPT.read_text().split(f"\n{command})\n", 1)[1].split(f"\n  ;;\n{following})", 1)[0]
    body = body.replace("date -u +%s", "clock_now")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    status = {"updated_at": "1970-01-01T00:16:40Z", "recording": True,
              "chunk_dir_is_shared": True, "package": "example.capture", "app_version": 1,
              "current_chunk_elapsed_seconds": 0, "chunk_seconds_target": 300,
              "chunks_closed": 1, "failures": 0}
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path), "TMPDIR": str(scratch),
           "CLOCK": str(tmp_path / "clock"), "READY": str(tmp_path / "ready"),
           "STATUS_JSON": json.dumps(status), "MOCK_MODE": mode}
    shell = r'''
set -euo pipefail
APP_ID=example.capture
clock_now() {
  if [ -e "$CLOCK" ]; then echo 1001; else touch "$CLOCK"; echo 1000; fi
}
adb_any() {
  case "$*" in
    get-state) return 0 ;;
    "shell pm list packages "*) echo package:example.capture ;;
    "shell cat "*) printf '%s\n' "$STATUS_JSON" ;;
    "shell ls "*) echo ambient-19700101T001640.m4a ;;
    "pull "*) printf 'synthetic measurement audio' > "$3" ;;
    *) return 1 ;;
  esac
}
ffprobe() {
  touch "$READY"
  if [ "$MOCK_MODE" = wait ]; then sleep 30; fi
  [ "$MOCK_MODE" != fail ] || return 7
  echo 300
}
ffmpeg() {
  [ "$MOCK_MODE" != fail ] || return 7
  echo 'mean_volume: -12.0 dB' >&2
}
run_observation() {
''' + body + "\n}\nrun_observation 1\n"
    return shell, env, scratch


@pytest.mark.parametrize("command", ["app-status", "app-soak"])
@pytest.mark.parametrize("mode", ["fail", "success"])
def test_observation_removes_scratch_on_exit(tmp_path, command, mode):
    shell, env, scratch = observation(tmp_path, command, mode)
    result = subprocess.run(["bash", "-c", shell], env=env, capture_output=True, text=True, timeout=5)
    assert result.returncode == (7 if mode == "fail" else 0), result.stderr
    assert not list(scratch.iterdir()), "measurement scratch leaked"


@pytest.mark.parametrize("command", ["app-status", "app-soak"])
def test_observation_removes_scratch_on_sigterm(tmp_path, command):
    shell, env, scratch = observation(tmp_path, command, "wait")
    proc = subprocess.Popen(["bash", "-c", shell], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        deadline = time.monotonic() + 5
        while not (tmp_path / "ready").exists():
            assert proc.poll() is None, "measurement exited before readiness"
            assert time.monotonic() < deadline, "measurement never became ready"
            time.sleep(0.01)
        os.killpg(proc.pid, signal.SIGTERM)
        proc.communicate(timeout=5)
        assert proc.returncode != 0
        assert not list(scratch.iterdir()), "cancelled measurement scratch leaked"
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate(timeout=5)
