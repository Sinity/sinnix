from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__import__("sinnix_fs.inventory", fromlist=["__file__"]).__file__)
CHILD = r"""
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace
import sys
fs = SourceFileLoader('fs_write_lock_probe', sys.argv[1]).load_module()
root = Path(sys.argv[2])
if len(sys.argv) > 4:
    original = fs.fcntl.flock
    def announced(*args):
        (root / 'ready').touch()
        return original(*args)
    fs.fcntl.flock = announced
if sys.argv[3] == 'publication':
    fs.publish_generation(root, roots=[])
else:
    fs.cmd_judgments(SimpleNamespace(action='import', index_dir=root, observations=root / 'incoming.jsonl'))
"""


def fixture(root):
    decision = {
        "target": "prefix:/fixture",
        "field": "topic",
        "value": "synthetic",
        "method": "operator",
        "ts": "2026-01-01T00:00:00Z",
        "evidence": "test",
    }
    (root / "incoming.jsonl").write_text(json.dumps(decision) + "\n")
    ledger = root / "judgments.jsonl"
    ledger.write_bytes(b"\n")
    (root / "current").symlink_to("generations/previous")
    return ledger


@pytest.mark.parametrize("lane", ["publication", "judgments"])
@pytest.mark.parametrize("kind", ["fifo", "directory"])
def test_special_write_locks_are_refused_without_mutation(tmp_path, lane, kind):
    ledger = fixture(tmp_path)
    lock = tmp_path / (
        "publication.lock" if lane == "publication" else "judgments.jsonl.lock"
    )
    if kind == "fifo":
        os.mkfifo(lock)
    else:
        lock.mkdir()
    result = subprocess.run(
        [sys.executable, "-c", CHILD, str(SCRIPT), str(tmp_path), lane],
        capture_output=True,
        text=True,
        timeout=3,
    )
    assert result.returncode != 0, result.stdout
    assert ledger.read_bytes() == b"\n"
    assert (tmp_path / "current").readlink() == Path("generations/previous")
    assert not (tmp_path / "last-attempt.json").exists()
    assert not list(tmp_path.glob("generations/.building-*"))


def test_regular_import_lock_still_serializes_writers(tmp_path):
    ledger = fixture(tmp_path)
    lock = tmp_path / "judgments.jsonl.lock"
    with lock.open("a+") as holder:
        fcntl.flock(holder, fcntl.LOCK_EX)
        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                CHILD,
                str(SCRIPT),
                str(tmp_path),
                "classify",
                "announce",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.monotonic() + 3
            while not (tmp_path / "ready").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert (tmp_path / "ready").exists()
            assert child.poll() is None
            assert ledger.read_bytes() == b"\n"
            fcntl.flock(holder, fcntl.LOCK_UN)
            stdout, stderr = child.communicate(timeout=3)
            assert child.returncode == 0, stderr
            assert json.loads(stdout)["added"] == 1
            assert b'"synthetic"' in ledger.read_bytes()
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate(timeout=3)
