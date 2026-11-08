"""Sinex runs come from devkit's run history store."""

import sqlite3

from sinnix_runtime.observe.sources import xtask


def make_runs(path):
    with sqlite3.connect(path) as conn:
        conn.execute(
            """create table runs (id integer primary key, project text, checkout text,
            command text, args text, pid integer, agentctl_job text, started_ms integer,
            duration_ms integer, status text, failure text)"""
        )
        conn.execute(
            "insert into runs values (1,'sinex','/repo','check','',10,'job-1',1777809600000,25000,'passed',null)"
        )
        conn.execute(
            "insert into runs values (2,'polylogue','/repo','check','',11,null,1777809600000,1000,'failed','x')"
        )


def test_default_store_is_devkit_history(tmp_path, monkeypatch):
    monkeypatch.delenv("SINNIX_OBSERVE_SINEX_DB", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert xtask.sinex_history_db() == tmp_path / "devkit/history.db"


def test_only_sinex_runs_are_read(tmp_path, monkeypatch):
    path = tmp_path / "history.db"
    make_runs(path)
    monkeypatch.setenv("SINNIX_OBSERVE_SINEX_DB", str(path))
    result = xtask.collect_sinex_xtask(5)
    assert result["available"] is True
    assert [row["id"] for row in result["rows"]] == [1]
    row = result["rows"][0]
    assert row["started_at"] == "2026-05-03T12:00:00Z"
    assert row["finished_at"] == "2026-05-03T12:00:25Z"
    assert row["duration_secs"] == 25.0
    assert row["agentctl_job"] == "job-1"


def test_invalid_schema_is_unavailable(tmp_path, monkeypatch):
    path = tmp_path / "history.db"
    with sqlite3.connect(path) as conn:
        conn.execute("create table runs(unrelated text)")
    monkeypatch.setenv("SINNIX_OBSERVE_SINEX_DB", str(path))
    result = xtask.collect_sinex_xtask(5)
    assert result["available"] is False
    assert result["gaps"] == ["sinex.xtask_history.invalid_schema"]
