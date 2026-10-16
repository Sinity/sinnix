"""Authored ledger inputs are files, never unbounded streams."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest

from sinnix_lib.judgments import read_judgments


def test_fifo_ledger_is_refused_without_waiting_for_a_writer(tmp_path):
    path = tmp_path / "judgments.jsonl"
    os.mkfifo(path)
    code = '''
from pathlib import Path
from sinnix_lib.judgments import read_judgments
import sys
try:
    read_judgments(Path(sys.argv[1]))
except ValueError as exc:
    assert "regular file" in str(exc)
else:
    raise AssertionError("FIFO ledger accepted")
'''
    result = subprocess.run([sys.executable, "-c", code, str(path)], capture_output=True, text=True, timeout=3)
    assert result.returncode == 0, result.stderr
    assert path.is_fifo()


def test_directory_ledger_is_refused(tmp_path):
    with pytest.raises(IsADirectoryError):
        read_judgments(tmp_path)


def test_regular_symlink_preserves_exact_ledger_digest(tmp_path):
    raw = b'\n{"target":"prefix:/synthetic","field":"topic","value":"fixture","method":"operator","evidence":"neutral","ts":"2026-01-01T00:00:00Z"}\n'
    source = tmp_path / "authored.jsonl"
    source.write_bytes(raw)
    link = tmp_path / "judgments.jsonl"
    link.symlink_to(source.name)
    result = read_judgments(link)
    assert result["sha256"] == hashlib.sha256(raw).hexdigest()
    assert len(result["valid"]) == 1
    assert source.read_bytes() == raw and link.is_symlink()


def test_missing_ledger_remains_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_judgments(tmp_path / "absent.jsonl")
