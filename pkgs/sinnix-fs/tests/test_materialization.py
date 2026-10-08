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
    """A DuckDB failure occurs before either fixed reader-facing name moves.

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


@pytest.mark.parametrize("failure", ["ledger", "pointer"])
def test_failed_generation_preserves_one_reader_generation(tmp_path, monkeypatch, failure):
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
    if failure == "ledger":
        monkeypatch.setattr(fs, "ledger_run", lambda *args: 1)
    else:
        replace = fs.os.replace
        def fail_pointer(source, destination, **kwargs):
            if Path(destination) == index / "current":
                raise OSError("injected pointer publication failure")
            return replace(source, destination, **kwargs)
        monkeypatch.setattr(fs.os, "replace", fail_pointer)
    with pytest.raises((ValueError, OSError)):
        fs.publish_generation(index)
    assert fs.resolve_generation(index) == original
    assert fs.validate_generation(original)
    assert json.loads((index / "last-attempt.json").read_text())["status"] == "failed"


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
