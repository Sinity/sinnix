"""Reports preserve literal paths and never reuse someone else's staging file."""
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys

import pytest

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


@pytest.mark.parametrize("failure", ["denied-root", "denied-parent", "denied-child", "missing", "wrong-type"])
def test_unavailable_scan_preserves_previous_report(tmp_path, failure):
    parent = tmp_path / "source-parent"
    parent.mkdir()
    source = parent / "source"
    source.mkdir()
    (source / "MEMORY.md").write_text("2000-01-01 neutral fixture\n")
    blocked = None
    if failure == "denied-root":
        blocked = source
    elif failure == "denied-parent":
        blocked = parent
    elif failure == "denied-child":
        blocked = source / "blocked"
        blocked.mkdir()
        (blocked / "MEMORY.md").write_text("neutral child\n")
    elif failure == "missing":
        source = parent / "absent"
    else:
        source = parent / "ordinary-file"
        source.touch()
    output = tmp_path / "reports" / "audit.jsonl"
    output.parent.mkdir()
    output.write_bytes(b"previous verified report\n")
    before = (output.read_bytes(), output.stat().st_ino, output.stat().st_mtime_ns)
    if blocked:
        blocked.chmod(0)
    try:
        result = subprocess.run(["bash", str(SCRIPT), "--root", str(source), "--output", str(output)],
                                capture_output=True, text=True)
    finally:
        if blocked:
            blocked.chmod(0o700)
    assert result.returncode != 0, "unavailable scan was published as complete"
    assert (output.read_bytes(), output.stat().st_ino, output.stat().st_mtime_ns) == before
    assert not list(output.parent.glob(".memory-audit.*"))


def test_explicit_directory_root_link_is_scanned(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "MEMORY.md").write_text("2000-01-01 neutral fixture\n")
    link = tmp_path / "requested-root"
    link.symlink_to(source, target_is_directory=True)
    output = tmp_path / "audit.jsonl"
    result = subprocess.run(["bash", str(SCRIPT), "--root", str(link), "--output", str(output)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert any(json.loads(line)["kind"] == "stale_date" for line in output.read_text().splitlines())


def test_accessible_empty_scan_can_publish_empty_report(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "audit.jsonl"
    result = subprocess.run(["bash", str(SCRIPT), "--root", str(source), "--output", str(output)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert output.read_bytes() == b""


def test_same_second_default_reports_have_distinct_names(tmp_path):
    binary = tmp_path / "bin"
    binary.mkdir()
    date = binary / "date"
    date.write_text(f"#!{sys.executable}\n" + """
import os, sys
if sys.argv[1:] == ['-u', '+%Y%m%dT%H%M%SZ']:
    print('20260101T000000Z')
else:
    os.execv(os.environ['REAL_DATE'], [os.environ['REAL_DATE'], *sys.argv[1:]])
""")
    date.chmod(0o755)
    source = tmp_path / "source"
    source.mkdir()
    reports = tmp_path / "reports"
    env = {"PATH": f"{binary}:{os.environ['PATH']}", "HOME": str(tmp_path),
           "REAL_DATE": shutil.which("date"), "SINNIX_MEMORY_AUDIT_DIR": str(reports)}
    paths = []
    for _ in range(2):
        result = subprocess.run(["bash", str(SCRIPT), "--root", str(source)],
                                env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        paths.append(Path(result.stdout.strip()))
    assert len(set(paths)) == 2
    assert all(p.is_file() and p.stat().st_mode & 0o777 == 0o600 for p in paths)


def test_directory_output_is_refused_without_publishing_inside_it(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "existing-directory"
    output.mkdir()
    sentinel = output / "retained"
    sentinel.write_bytes(b"neutral retained evidence")
    result = subprocess.run(["bash", str(SCRIPT), "--root", str(source), "--output", str(output)],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert list(output.iterdir()) == [sentinel]
    assert sentinel.read_bytes() == b"neutral retained evidence"
    assert not list(tmp_path.glob(".memory-audit.*"))
