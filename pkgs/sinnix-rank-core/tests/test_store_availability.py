"""Unavailable authored ledgers cannot become an empty preference history."""

import json
import os
import subprocess
import sys

import pytest

from rank_core.store import Store, read_log


def read(kind, directory):
    return read_log(directory / "comparisons.jsonl") if kind == "comparisons" else Store(directory).load_items()


def filename(kind):
    return "comparisons.jsonl" if kind == "comparisons" else "items.jsonl"


@pytest.mark.parametrize("kind", ["comparisons", "items"])
def test_denied_ledger_does_not_become_empty(tmp_path, kind):
    if os.geteuid() == 0:
        pytest.skip("permission boundary requires an unprivileged reader")
    private = tmp_path / "private"
    private.mkdir()
    (private / filename(kind)).write_text('{"id":"retained"}\n')
    private.chmod(0)
    try:
        with pytest.raises(PermissionError):
            read(kind, private)
    finally:
        private.chmod(0o700)


@pytest.mark.parametrize("kind", ["comparisons", "items"])
def test_dangling_ledger_is_unavailable(tmp_path, kind):
    (tmp_path / filename(kind)).symlink_to(tmp_path / "missing-target")
    with pytest.raises(FileNotFoundError):
        read(kind, tmp_path)


@pytest.mark.parametrize("kind", ["comparisons", "items"])
def test_fifo_ledger_refuses_without_waiting(tmp_path, kind):
    path = tmp_path / filename(kind)
    os.mkfifo(path)
    program = """import sys
from pathlib import Path
from rank_core.store import Store, read_log
try:
    if sys.argv[2] == 'comparisons': read_log(Path(sys.argv[1]) / 'comparisons.jsonl')
    else: Store(sys.argv[1]).load_items()
except ValueError:
    raise SystemExit(0)
raise SystemExit(1)
"""
    result = subprocess.run(
        [sys.executable, "-c", program, str(tmp_path), kind],
        env={"PATH": "/nonexistent", "PYTHONPATH": os.pathsep.join(sys.path)},
        capture_output=True, text=True, timeout=2,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("kind", ["comparisons", "items"])
def test_json_unicode_line_separator_is_content(tmp_path, kind):
    text = "neutral\u2028value"
    record = {"id": "a", "label": text, "context": text}
    (tmp_path / filename(kind)).write_text(json.dumps(record, ensure_ascii=False) + "\n")
    result = read(kind, tmp_path)
    assert (result.live[0]["context"] if kind == "comparisons" else result["a"].label) == text


@pytest.mark.parametrize("kind", ["comparisons", "items"])
def test_missing_empty_and_regular_symlink_remain_supported(tmp_path, kind):
    def empty(result):
        return not result.live if kind == "comparisons" else not result
    assert empty(read(kind, tmp_path))
    target = tmp_path / "native.jsonl"
    target.write_text("")
    (tmp_path / filename(kind)).symlink_to(target)
    assert empty(read(kind, tmp_path))
    target.write_text('{"id":"a","label":"neutral"}\n')
    result = read(kind, tmp_path)
    assert len(result.live if kind == "comparisons" else result) == 1
