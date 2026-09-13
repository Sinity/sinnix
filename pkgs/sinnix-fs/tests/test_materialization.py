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
