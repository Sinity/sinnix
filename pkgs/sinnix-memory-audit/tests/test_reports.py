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


@pytest.mark.parametrize("state", ["denied", "wrong-parent", "missing", "present"])
def test_reference_lookup_preserves_unavailable_vs_missing(tmp_path, state):
    source = tmp_path / "source"
    source.mkdir()
    parent = tmp_path / "referenced"
    target = parent / "retained"
    if state == "wrong-parent":
        parent.write_bytes(b"unexpected parent object")
    else:
        parent.mkdir()
        if state != "missing":
            target.write_bytes(b"retained fixture payload")
    # /build is outside the audit's intentional path-prefix vocabulary.
    # This supported spelling resolves to the same fixture under either root.
    reference = "/tmp/.." + str(target)
    (source / "MEMORY.md").write_text(reference + "\n")
    output = tmp_path / "report.jsonl"
    if state == "denied":
        parent.chmod(0)
    try:
        result = subprocess.run(["bash", str(SCRIPT), "--root", str(source), "--output", str(output)], capture_output=True, text=True)
    finally:
        if state == "denied":
            parent.chmod(0o700)
    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    matched = [row for row in rows if row.get("value") == reference]
    if state == "present":
        assert not matched
    else:
        expected = "dead_path" if state == "missing" else "unavailable_path"
        assert len(matched) == 1 and matched[0]["kind"] == expected
        if state != "missing":
            assert matched[0]["reason"]
    if state in ("denied", "present"):
        assert target.read_bytes() == b"retained fixture payload"


def test_newline_filename_does_not_select_outside_memory(tmp_path):
    root = tmp_path / "scan"
    root.mkdir()
    outside = tmp_path / "outside" / "MEMORY.md"
    outside.parent.mkdir()
    outside.write_text("1999-02-02 obsolete outside fixture\n")
    (root / "MEMORY.md").write_text("neutral benign fixture\n")
    malicious = root / ("MEMORY.md\n" + str(outside))
    malicious.parent.mkdir(parents=True)
    malicious.write_text("2000-01-01 neutral in-scope fixture\n")
    output = tmp_path / "report.jsonl"
    result = subprocess.run(["bash", str(SCRIPT), "--root", str(root), "--output", str(output)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert any(row["file"] == str(malicious) for row in rows)
    assert not any(row["file"] == str(outside) for row in rows)
    assert not any(row.get("value") == "1999-02-02" for row in rows)



@pytest.mark.parametrize("bad_home", [False, True])
def test_reference_probe_ignores_project_python_environment(tmp_path, bad_home):
    source = tmp_path / "source"
    source.mkdir()
    (source / "MEMORY.md").write_text("/realm/synthetic-missing-memory-path-fixture\n")
    poison = tmp_path / "python-env"
    poison.mkdir()
    marker = tmp_path / "imported"
    (poison / "sitecustomize.py").write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('unexpected fixture import')\n")
    output = tmp_path / "report.jsonl"
    env = {**os.environ, "PYTHONPATH": str(poison)}
    if bad_home:
        env["PYTHONHOME"] = str(tmp_path / "missing-python-home")
    result = subprocess.run(["bash", str(SCRIPT), "--root", str(source), "--output", str(output)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert not marker.exists()
    assert any(json.loads(line)["kind"] == "dead_path" for line in output.read_text().splitlines())


def test_literal_filename_bytes_remain_readable_in_json_report(tmp_path):
    source = tmp_path / os.fsdecode(b"memory-\xff.md")
    source.write_text("2000-01-01 neutral fixture\n")
    output = tmp_path / "report.jsonl"
    result = subprocess.run(["bash", str(SCRIPT), "--root", str(tmp_path), "--output", str(output)], capture_output=True, text=True, errors="surrogateescape")
    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert any(os.fsencode(row["file"]) == os.fsencode(source) for row in rows)


@pytest.mark.parametrize("valid_prefix", [False, True])
def test_invalid_calendar_date_cannot_reuse_a_previous_epoch(tmp_path, valid_prefix):
    source = tmp_path / "MEMORY.md"
    content = ("2000-01-01 neutral dated fixture\n" if valid_prefix else "")
    source.write_text(content + "2026-02-30 invalid calendar fixture\n")
    output = tmp_path / "report.jsonl"
    result = subprocess.run(["bash", str(SCRIPT), "--root", str(tmp_path), "--output", str(output)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    stale = [row["value"] for row in rows if row["kind"] == "stale_date"]
    assert stale == (["2000-01-01"] if valid_prefix else [])
