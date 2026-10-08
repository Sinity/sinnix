"""Explicit Sinex source roots and honest unavailable observations."""
import sqlite3
from pathlib import Path

from sinnix_observe.sources import xtask


def test_missing_explicit_root_cannot_select_another_checkout(tmp_path, monkeypatch):
    fallback = tmp_path / "fallback.db"
    fallback.touch()
    root = tmp_path / "selected-checkout"
    monkeypatch.delenv("SINNIX_OBSERVE_SINEX_DB", raising=False)
    monkeypatch.setenv("SINEX_ROOT", str(root))
    monkeypatch.setattr(xtask, "Path", lambda value: fallback if value == "/realm/project/sinex/repo/.sinex/state/xtask-history.db" else Path(value))
    assert xtask.sinex_history_db() == root / ".sinex/state/xtask-history.db"


def test_invalid_schema_is_unavailable(tmp_path, monkeypatch):
    path = tmp_path / "history.db"
    with sqlite3.connect(path) as conn:
        conn.execute("create table invocations(unrelated text)")
    monkeypatch.setenv("SINNIX_OBSERVE_SINEX_DB", str(path))
    result = xtask.collect_sinex_xtask(5)
    assert result["available"] is False
    assert result["gaps"] == ["sinex.xtask_history.invalid_schema"]


def test_current_empty_source_is_available(tmp_path, monkeypatch):
    path = tmp_path / "history.db"
    with sqlite3.connect(path) as conn:
        conn.execute("create table invocations(id integer, command text, started_at text, status text)")
    monkeypatch.setenv("SINNIX_OBSERVE_SINEX_DB", str(path))
    result = xtask.collect_sinex_xtask(5)
    assert result["available"] is True
    assert result["rows"] == []
