"""Failure preservation for the filesystem index's derived artifacts."""

from __future__ import annotations

from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).parents[3] / "scripts" / "sinnix-fs"


def load_script():
    return SourceFileLoader("sinnix_fs", str(SCRIPT)).load_module()


def test_failed_materialization_keeps_the_previous_complete_pair(tmp_path, monkeypatch):
    """A DuckDB failure preserves both existing artifacts inside staging.

    Mutation: restore either old ``db.unlink()`` or direct final-Parquet COPY
    and the corresponding old artifact disappears or is overwritten before
    this assertion.
    """
    fs = load_script()
    db = tmp_path / "inventory.duckdb"
    parquet = tmp_path / "nodes.parquet"
    db.write_text("old database")
    parquet.write_text("old parquet")
    observed = []

    def fail(staged_db, _sql, _name):
        observed.append((staged_db, db.read_text(), parquet.read_text()))
        return SimpleNamespace(returncode=1, stdout="", stderr="forced failure")

    monkeypatch.setattr(fs, "run_duckdb_file", fail)
    with pytest.raises(SystemExit, match="duckdb failed"):
        fs.materialize_pair(db, parquet, lambda _path: "SELECT 1", "inventory")

    assert observed[0][0].parent != tmp_path
    assert observed[0][1:] == ("old database", "old parquet")
    assert db.read_text() == "old database"
    assert parquet.read_text() == "old parquet"
    assert list(tmp_path.iterdir()) == [db, parquet]


def test_validated_staged_pair_replaces_both_public_artifacts(tmp_path, monkeypatch):
    fs = load_script()
    db = tmp_path / "content.duckdb"
    parquet = tmp_path / "files.parquet"
    db.write_text("old database")
    parquet.write_text("old parquet")

    def build(staged_db, sql, _name):
        staged_db.write_text("new database")
        staged_parquet = Path(sql.removeprefix("COPY "))
        staged_parquet.write_text("new parquet")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def query(_db, _sql):
        return SimpleNamespace(returncode=0, stdout="1\n", stderr="")

    monkeypatch.setattr(fs, "run_duckdb_file", build)
    monkeypatch.setattr(fs, "duckdb_query", query)
    fs.materialize_pair(db, parquet, lambda path: f"COPY {path}", "files")

    assert db.read_text() == "new database"
    assert parquet.read_text() == "new parquet"
    assert list(tmp_path.iterdir()) == [db, parquet]


def test_ledger_view_normalizes_role_without_changing_raw_evidence(tmp_path):
    import json
    fs = load_script()
    fs.run_duckdb_file(tmp_path / "inventory.duckdb", "CREATE TABLE nodes(path VARCHAR); INSERT INTO nodes VALUES ('/sample');", "fixture")
    fs.run_duckdb_file(tmp_path / "content.duckdb", "CREATE TABLE files(schema VARCHAR, path VARCHAR, bytes BIGINT, sha256 VARCHAR, error VARCHAR);", "fixture")
    source = tmp_path / "judgments.jsonl"
    source.write_text(json.dumps({"target": "prefix:/sample", "field": "role", "value": "capture", "method": "operator", "evidence": "synthetic", "ts": "2026-01-01T00:00:00Z"}) + "\n")
    assert fs.ledger_run(tmp_path) == 0
    result = fs.duckdb_query(tmp_path / "inventory.duckdb", "SELECT value FROM resolved_judgments; SELECT value FROM judgments;")
    assert result.returncode == 0, result.stderr
    assert '"source"' in result.stdout
    assert '"capture"' in result.stdout


def test_coverage_counts_locations_once_and_preserves_content_identity(tmp_path):
    import json
    fs = load_script()
    db = tmp_path / "inventory.duckdb"
    fs.run_duckdb_file(db, "CREATE TABLE nodes(path VARCHAR); INSERT INTO nodes VALUES ('/scope'), ('/scope/boundary'), ('/scope/file');", "fixture")
    fs.run_duckdb_file(tmp_path / "content.duckdb", "CREATE TABLE files(schema VARCHAR, path VARCHAR, bytes BIGINT, sha256 VARCHAR, fingerprint_kind VARCHAR, error VARCHAR); INSERT INTO files VALUES ('sinnix-fs-content-v2', '/scope/boundary', NULL, NULL, NULL, NULL), ('sinnix-fs-content-v2', '/scope/file', 4, repeat('a', 64), 'sha256-full', NULL);", "fixture")
    (tmp_path / "judgments.jsonl").write_text(json.dumps({
        "target": "sha256:" + "a" * 64, "field": "subject", "value": "exact",
        "method": "operator", "evidence": "synthetic", "ts": "2026-01-01T00:00:00Z",
    }) + "\n")
    assert fs.ledger_run(tmp_path) == 0
    result = fs.duckdb_query(db, "SELECT count(*) FROM all_paths; SELECT sum(paths) FROM coverage; SELECT value FROM inherited_judgments WHERE path='/scope/file'; SELECT count(*) FROM files;")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["3", "3", '"exact"', "2"]
    fs.run_duckdb_file(tmp_path / "content.duckdb", "INSERT INTO files VALUES ('sinnix-fs-content-v2', '/scope/file', 4, repeat('b', 64), 'sha256-full', NULL);", "fixture")
    assert fs.ledger_run(tmp_path) == 0
    result = fs.duckdb_query(db, "SELECT count(*) FROM all_paths; SELECT sum(paths) FROM coverage; SELECT count(*) FROM inherited_judgments; SELECT count(*) FROM files;")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["3", "3", "0", "3"]


@pytest.mark.parametrize("failure", ["ledger", "pointer", "schema", "malformed", "memory", "disk", "interrupted"])
def test_failed_generation_preserves_one_reader_generation(tmp_path, monkeypatch, capsys, failure):
    import json
    fs = load_script()
    root = tmp_path / "input"
    root.mkdir()
    (root / "note.md").write_text("# Synthetic note")
    index = tmp_path / "index'quoted"
    index.mkdir()
    (index / "judgments.jsonl").write_text(json.dumps({"target": "prefix:" + str(root), "field": "topic", "value": "fixture", "method": "operator", "evidence": "synthetic", "ts": "2026-01-01T00:00:00Z"}) + "\n")
    assert fs.publish_generation(index, roots=[str(root)]) == 0
    original = fs.resolve_generation(index)
    assert fs.validate_generation(original)
    capsys.readouterr()
    with monkeypatch.context() as faults:
        if failure == "ledger":
            faults.setattr(fs, "ledger_run", lambda *args: 1)
        elif failure == "pointer":
            replace = fs.os.replace
            def fail_pointer(source, destination, **kwargs):
                if Path(destination) == index / "current":
                    raise OSError("injected pointer publication failure")
                return replace(source, destination, **kwargs)
            faults.setattr(fs.os, "replace", fail_pointer)
        elif failure == "malformed":
            with (index / "judgments.jsonl").open("a") as handle:
                handle.write("{broken JSON\n")
        else:
            errors = {"schema": ValueError("injected schema failure"),
                      "memory": MemoryError("injected memory exhaustion"),
                      "disk": OSError(28, "injected disk exhaustion"),
                      "interrupted": KeyboardInterrupt()}
            def fail(*args):
                raise errors[failure]
            faults.setattr(fs, "validate_generation" if failure == "schema" else "ledger_run", fail)
        with pytest.raises((ValueError, OSError, MemoryError, KeyboardInterrupt)):
            fs.publish_generation(index)
    assert fs.resolve_generation(index) == original
    assert fs.validate_generation(original)
    assert json.loads((index / "last-attempt.json").read_text())["status"] == "failed"
    capsys.readouterr()
    assert fs.cmd_status(SimpleNamespace(index_dir=index)) == (1 if failure == "malformed" else 0)
    status = json.loads(capsys.readouterr().out)
    assert status["valid"] is True
    assert status["publication_in_progress"] is False
    if failure == "malformed":
        assert status["classifications_stale"] is True and status["current_ledger_error"]


def test_status_exposes_interrupted_and_active_candidates(tmp_path, monkeypatch, capsys):
    import json
    import fcntl
    fs = load_script()
    index = tmp_path / "index"
    candidate = index / "generations/.building-interrupted"
    candidate.mkdir(parents=True)
    assert fs.cmd_status(SimpleNamespace(index_dir=index)) == 1
    status = json.loads(capsys.readouterr().out)
    assert status["unpublished_candidates"] == [str(candidate)]
    assert status["publication_in_progress"] is False
    with (index / "publication.lock").open("w") as writer:
        fcntl.flock(writer, fcntl.LOCK_EX)
        assert fs.cmd_status(SimpleNamespace(index_dir=index)) == 1
        assert json.loads(capsys.readouterr().out)["publication_in_progress"] is True


def test_sql_and_direct_resolution_share_time_ambiguity_unknown_and_invalid(tmp_path):
    import json
    from sinnix_lib.judgments import read_judgments, resolve_judgments
    fs = load_script()
    fs.run_duckdb_file(tmp_path / "inventory.duckdb", "CREATE TABLE nodes(path VARCHAR); INSERT INTO nodes VALUES ('/scope'), ('/scope/child'), ('/scope/unknown');", "fixture")
    fs.run_duckdb_file(tmp_path / "content.duckdb", "CREATE TABLE files(schema VARCHAR, path VARCHAR, bytes BIGINT, sha256 VARCHAR, error VARCHAR);", "fixture")
    def row(path, value, ts, observation="known"):
        return dict(target="prefix:" + path, field="topic", value=value, ts=ts, observation=observation, method="operator", evidence="synthetic")
    records = [row('/scope', 'earlier', '2026-01-01T12:00:00+02:00'), row('/scope', 'later', '2026-01-01T11:00:00Z'),
               row('/scope/child', 'one', '2026-01-01T11:00:00Z'), row('/scope/child', 'two', '2026-01-01T12:00:00+01:00'),
               row('/scope/unknown', None, '2026-01-01T11:00:00Z', 'unknown'), row('/scope', 'invalid', '2027-01-01')]
    ledger_path = tmp_path / "judgments.jsonl"
    ledger_path.write_text(''.join(json.dumps(r) + "\n" for r in records))
    ledger = read_judgments(ledger_path)
    assert len(ledger['issues']) == 1
    assert fs.ledger_run(tmp_path) == 0
    import subprocess
    result = subprocess.run(['duckdb', str(tmp_path / 'inventory.duckdb'), '-json', '-c', 'SELECT path,value,observation FROM inherited_judgments ORDER BY path'], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    for row in json.loads(result.stdout):
        direct = resolve_judgments(ledger, row['path'])['topic']
        assert row['observation'] == direct['status']
        assert row['value'] == direct.get('value')


def test_public_query_cannot_write_outside_its_read_only_database(tmp_path):
    import json
    import hashlib
    fs = load_script()
    index = tmp_path / "index"
    generation = index / "generations/synthetic"
    generation.mkdir(parents=True)
    (generation / "manifest.json").write_text(json.dumps({
        "schema": "sinnix.fs-generation.v1", "generation": "synthetic",
    }))
    (index / "current").symlink_to("generations/synthetic", target_is_directory=True)
    db = generation / "inventory.duckdb"
    build = fs.run_duckdb_file(db, "CREATE TABLE protected AS SELECT 1 AS value", "fixture")
    assert build.returncode == 0, build.stderr
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    args = SimpleNamespace(index_dir=index, database="inventory.duckdb", sql="SELECT * FROM protected")
    assert fs.cmd_query(args) == 0
    external = tmp_path / "external.csv"
    copy = f"COPY (SELECT * FROM protected) TO {fs.sql_string(external)}"
    for sql in (copy, "SET enable_external_access=true; " + copy, "INSERT INTO protected VALUES (2)"):
        args.sql = sql
        assert fs.cmd_query(args) != 0
        assert not external.exists()
        assert hashlib.sha256(db.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("omission", ["none", "denied", "boundary", "alias"])
def test_generation_and_status_include_content_failures(tmp_path, monkeypatch, capsys, omission):
    import json
    fs = load_script()
    root = tmp_path / "input"
    root.mkdir()
    source = root / "note.md"
    source.write_text("Synthetic content")
    if omission == "alias":
        (root / "alias.md").symlink_to(source)
    index = tmp_path / "index"
    index.mkdir()
    (index / "judgments.jsonl").write_text("")
    if omission == "denied":
        source.chmod(0)
    if omission == "boundary":
        monkeypatch.setattr(fs, "CONTENT_COLLECTION_BOUNDARIES", {str(root): "synthetic native owner"})
    try:
        assert fs.publish_generation(index, roots=[str(root)]) == 0
        generation = fs.resolve_generation(index)
        observed = fs.duckdb_query(generation / "content.duckdb", "SELECT count(*) FROM files WHERE error IS NOT NULL")
        assert observed.returncode == 0 and int(observed.stdout.strip()) == int(omission in {"denied", "alias"})
        manifest = json.loads((generation / "manifest.json").read_text())
        coverage = manifest["coverage"]
        assert coverage["directory_errors"] == coverage["pruned_directories"] == 0
        assert coverage["incomplete"] is (omission != "none")
        assert coverage["content_errors"] == int(omission == "denied")
        assert coverage["content_aliases_not_traversed"] == int(omission == "alias")
        assert coverage["content_boundaries"] == int(omission == "boundary")
        if omission == "boundary":
            assert manifest["scan"]["content_collection_boundaries"] == {str(root): "synthetic native owner"}
        capsys.readouterr()
        assert fs.cmd_status(SimpleNamespace(index_dir=index)) == 0
        status = json.loads(capsys.readouterr().out)
        assert status["valid"] is True and status["coverage"] == coverage
    finally:
        source.chmod(0o600)


def test_legacy_content_without_boundary_records_reports_unknown_coverage(tmp_path):
    fs = load_script()
    assert fs.run_duckdb_file(tmp_path / "inventory.duckdb",
        "CREATE TABLE nodes(error VARCHAR, prune_reason VARCHAR)", "fixture").returncode == 0
    assert fs.run_duckdb_file(tmp_path / "content.duckdb",
        "CREATE TABLE files(error VARCHAR)", "fixture").returncode == 0
    coverage = fs.generation_coverage(tmp_path)
    assert coverage["incomplete"] is True
    assert coverage["content_errors"] == 0
    assert coverage["content_boundaries"] is None


@pytest.mark.parametrize("manifest", [
    [],
    {"schema": "sinnix.fs-generation.v1", "generation": "synthetic"},
    {"schema": "sinnix.fs-generation.v1", "generation": "synthetic",
     "scan": [], "invalid_definitions": [], "ledger_sha256": "a" * 64},
    {"schema": "sinnix.fs-generation.v1", "generation": "synthetic",
     "scan": {}, "invalid_definitions": {}, "ledger_sha256": "a" * 64},
    {"schema": "sinnix.fs-generation.v1", "generation": "synthetic",
     "scan": {}, "invalid_definitions": [], "ledger_sha256": "sampled"},
])
def test_status_reports_invalid_manifest_without_probing_databases(tmp_path, monkeypatch, capsys, manifest):
    import json

    fs = load_script()
    index = tmp_path / "index"
    generation = index / "generations/synthetic"
    generation.mkdir(parents=True)
    source = generation / "manifest.json"
    source.write_text(json.dumps(manifest))
    before = source.read_bytes()
    (index / "current").symlink_to("generations/synthetic", target_is_directory=True)
    def unexpected_validation(*args):
        raise AssertionError("invalid metadata must be rejected before database validation")
    monkeypatch.setattr(fs, "validate_generation", unexpected_validation)
    assert fs.cmd_status(SimpleNamespace(index_dir=index)) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["valid"] is False
    assert "invalid generation" in report["reason"]
    assert source.read_bytes() == before


@pytest.mark.parametrize("valid_generation", [False, True])
def test_status_reports_unreadable_publication_lock(tmp_path, monkeypatch, capsys, valid_generation):
    """A wrong-type lock must not erase the generation diagnosis."""
    import json
    fs = load_script()
    (tmp_path / "publication.lock").mkdir()
    if valid_generation:
        generation = tmp_path / "generation"
        generation.mkdir()
        (generation / "manifest.json").write_text(json.dumps({
            "scan": {}, "invalid_definitions": [], "ledger_sha256": "a" * 64,
        }))
        monkeypatch.setattr(fs, "resolve_generation", lambda _index: generation)
        monkeypatch.setattr(fs, "validate_generation", lambda _generation: {})
        monkeypatch.setattr(fs, "generation_coverage", lambda _generation: {})
        monkeypatch.setattr(fs, "read_judgments", lambda _path: {"sha256": "a" * 64})
    assert fs.cmd_status(SimpleNamespace(index_dir=tmp_path)) == 1
    status = json.loads(capsys.readouterr().out)
    assert status["publication_in_progress"] is None
    assert status["publication_state_error"]
    assert status["valid"] is valid_generation
    if valid_generation:
        assert status["classifications_stale"] is False
    else:
        assert "no published generation" in status["reason"]


@pytest.mark.parametrize("failure", ["missing", "receipt-directory", "receipt-denied", "receipt-malformed", "candidates-denied", "candidates-file"])
def test_status_preserves_unknown_publication_observations(tmp_path, monkeypatch, capsys, failure):
    import json
    fs = load_script()
    generation = tmp_path / "selected"
    generation.mkdir()
    manifest = generation / "manifest.json"
    manifest.write_text(json.dumps({"scan": {}, "invalid_definitions": [], "ledger_sha256": "a" * 64}))
    before = manifest.read_bytes()
    monkeypatch.setattr(fs, "resolve_generation", lambda _index: generation)
    monkeypatch.setattr(fs, "validate_generation", lambda _generation: {})
    monkeypatch.setattr(fs, "generation_coverage", lambda _generation: {})
    monkeypatch.setattr(fs, "read_judgments", lambda _path: {"sha256": "a" * 64})
    receipt = tmp_path / "last-attempt.json"
    candidates = tmp_path / "generations"
    if failure == "receipt-directory":
        receipt.mkdir()
    elif failure in ("receipt-denied", "receipt-malformed"):
        receipt.write_text("not-json")
        if failure == "receipt-denied":
            original = fs.os.open
            def open_file(path, *args, **kwargs):
                if Path(path) == receipt:
                    raise PermissionError("synthetic receipt denied")
                return original(path, *args, **kwargs)
            monkeypatch.setattr(fs.os, "open", open_file)
    elif failure == "candidates-denied":
        candidates.mkdir()
        (candidates / ".building-retained").mkdir()
        original = fs.os.scandir
        def scandir(path):
            if Path(path) == candidates:
                raise PermissionError("synthetic candidate inventory denied")
            return original(path)
        monkeypatch.setattr(fs.os, "scandir", scandir)
    elif failure == "candidates-file":
        candidates.write_text("retained wrong-type source")
    assert fs.cmd_status(SimpleNamespace(index_dir=tmp_path)) == (0 if failure == "missing" else 1)
    status = json.loads(capsys.readouterr().out)
    assert status["valid"] is True and status["classifications_stale"] is False
    if failure.startswith("receipt-"):
        assert status["last_attempt_error"]
        if failure == "receipt-denied":
            assert "synthetic receipt denied" in status["last_attempt_error"]
    elif failure.startswith("candidates-"):
        assert status["unpublished_candidates"] is None and status["candidate_inventory_error"]
    else:
        assert status["unpublished_candidates"] == []
    assert manifest.read_bytes() == before


@pytest.mark.parametrize("special", ["receipt", "lock", "manifest"])
def test_status_refuses_fifo_metadata_without_waiting(tmp_path, special):
    import json
    import os
    import subprocess
    import sys

    generation = tmp_path / "generations/selected"
    generation.mkdir(parents=True)
    (tmp_path / "current").symlink_to("generations/selected")
    manifest = generation / "manifest.json"
    paths = {"receipt": tmp_path / "last-attempt.json", "lock": tmp_path / "publication.lock", "manifest": manifest}
    manifest.write_text(json.dumps({"schema": "sinnix.fs-generation.v1", "generation": "selected", "scan": {}, "invalid_definitions": [], "ledger_sha256": "a" * 64}))
    if special == "manifest":
        manifest.unlink()
    os.mkfifo(paths[special])
    # Only database validation is synthetic. The metadata paths, reader and
    # FIFO are real; the child deadline makes a blocking open a test failure.
    code = r'''
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace
import sys
fs = SourceFileLoader("fs_fifo_probe", sys.argv[1]).load_module()
fs.validate_generation = lambda _path: {}
fs.generation_coverage = lambda _path: {}
fs.read_judgments = lambda _path: {"sha256": "a" * 64}
raise SystemExit(fs.cmd_status(SimpleNamespace(index_dir=Path(sys.argv[2]))))
'''
    result = subprocess.run([sys.executable, "-c", code, str(SCRIPT), str(tmp_path)], capture_output=True, text=True, timeout=3)
    assert result.returncode == 1, result.stderr
    report = json.loads(result.stdout)
    error = {"receipt": "last_attempt_error", "lock": "publication_state_error", "manifest": "reason"}[special]
    assert "regular file" in report[error]
    assert report["valid"] is (special != "manifest")
    assert paths[special].is_fifo()


@pytest.mark.parametrize("receipt", [
    None, [], "published", 1, {},
    {"status": "unknown", "generation": "selected"},
    {"status": "published"},
    {"status": "published", "generation": []},
    {"status": "published", "generation": "  "},
    {"status": "failed", "candidate": "retained"},
    {"status": "failed", "candidate": [], "reason": "interrupted"},
    {"status": "failed", "candidate": "retained", "reason": None},
])
def test_status_rejects_invalid_receipt_shape_without_invalidating_generation(
    tmp_path, monkeypatch, capsys, receipt
):
    import json
    fs = load_script()
    generation = tmp_path / "selected"
    generation.mkdir()
    (generation / "manifest.json").write_text(json.dumps({
        "scan": {}, "invalid_definitions": [], "ledger_sha256": "a" * 64,
    }))
    monkeypatch.setattr(fs, "resolve_generation", lambda _index: generation)
    monkeypatch.setattr(fs, "validate_generation", lambda _generation: {})
    monkeypatch.setattr(fs, "generation_coverage", lambda _generation: {})
    monkeypatch.setattr(fs, "read_judgments", lambda _path: {"sha256": "a" * 64})
    source = tmp_path / "last-attempt.json"
    source.write_text(json.dumps(receipt))
    before = source.read_bytes()
    assert fs.cmd_status(SimpleNamespace(index_dir=tmp_path)) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["valid"] is True and report["classifications_stale"] is False
    assert "invalid publication receipt" in report["last_attempt_error"]
    assert "last_attempt" not in report
    assert source.read_bytes() == before


@pytest.mark.parametrize("failure", ["denied", "io", "file", "directory"])
def test_generation_pointer_errors_are_not_reported_as_absent(tmp_path, monkeypatch, failure):
    fs = load_script()
    pointer = tmp_path / "current"
    if failure in ("denied", "io"):
        original = fs.Path.lstat
        error = PermissionError("synthetic pointer denied") if failure == "denied" else OSError("synthetic pointer IO failure")
        def lstat(path, *args, **kwargs):
            if path == pointer:
                raise error
            return original(path, *args, **kwargs)
        monkeypatch.setattr(fs.Path, "lstat", lstat)
        with pytest.raises(type(error), match="synthetic pointer"):
            fs.resolve_generation(tmp_path)
    else:
        if failure == "file":
            pointer.write_text("retained wrong-type pointer")
        else:
            pointer.mkdir()
        with pytest.raises(ValueError, match="not a symbolic link"):
            fs.resolve_generation(tmp_path)
        assert pointer.exists()
