"""Reports preserve literal paths and never reuse someone else's staging file."""
import json
import os
from pathlib import Path
import subprocess

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/sinnix-memory-audit"


def test_quoted_control_filename_produces_private_valid_json(tmp_path):
    source = tmp_path / 'memory"\\line\nfile.md'
    source.write_text("2000-01-01 neutral dated fixture\n")
    output = tmp_path / "reports" / "audit.jsonl"
    output.parent.mkdir()
    sentinel = Path(str(output) + ".tmp")
    sentinel.write_bytes(b"retained unrelated temporary data")
    result = subprocess.run(["bash", str(SCRIPT), "--root", str(tmp_path), "--output", str(output)],
                            env=os.environ.copy(), capture_output=True, text=True, umask=0)
    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert any(row["file"] == str(source) and row["kind"] == "stale_date" for row in rows)
    assert output.stat().st_mode & 0o777 == 0o600
    assert sentinel.read_bytes() == b"retained unrelated temporary data"
    assert not list(output.parent.glob(".memory-audit.*"))


def test_review_words_before_a_path_remain_visible(tmp_path):
    source = tmp_path / "MEMORY.md"
    source.write_text("obsolete entry /realm/synthetic-unavailable-memory-fixture\n")
    output = tmp_path / "audit.jsonl"
    result = subprocess.run(["bash", str(SCRIPT), "--root", str(tmp_path), "--output", str(output)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert any(row["kind"] == "review_required" for row in rows)
