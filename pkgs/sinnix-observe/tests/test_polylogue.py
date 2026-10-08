"""Current archive OPS schema and explicit source overrides."""
import json
import sqlite3

from sinnix_observe.sources import polylogue


def make_ops(path):
    with sqlite3.connect(path) as conn:
        conn.execute("""create table ingest_attempts (
            attempt_id text primary key, source_path text, origin text,
            status text, phase text, started_at_ms integer,
            heartbeat_at_ms integer, finished_at_ms integer,
            parsed_raw_count integer, materialized_count integer,
            error_message text)""")


def test_current_ops_tier_and_empty_source(tmp_path, monkeypatch):
    root = tmp_path / "archive"
    root.mkdir()
    make_ops(root / "ops.db")
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps({"polylogue": {"archiveRoot": str(root)}}))
    monkeypatch.setenv("SINNIX_RUNTIME_INVENTORY_FILE", str(inventory))
    monkeypatch.delenv("SINNIX_OBSERVE_POLYLOGUE_DB", raising=False)
    result = polylogue.collect_polylogue_live_attempts(5)
    assert result["available"] is True
    assert result["rows"] == []
    assert result["db"] == str(root / "ops.db")


def test_attempt_projection_preserves_counts_and_order(tmp_path, monkeypatch):
    path = tmp_path / "ops#literal?name.db"
    make_ops(path)
    with sqlite3.connect(path) as conn:
        conn.executemany("insert into ingest_attempts values(?,?,?,?,?,?,?,?,?,?,?)", [
            ("first", "/fixture/one", "codex", "succeeded", "done", 1000, None, 3000, 7, 2, None),
            ("second", "/fixture/two", "claude", "running", "parse", 2000, 4000, None, 3, 0, None),
        ])
    monkeypatch.setenv("SINNIX_OBSERVE_POLYLOGUE_DB", str(path))
    rows = polylogue.collect_polylogue_live_attempts(2)["rows"]
    assert [row["attempt_id"] for row in rows] == ["second", "first"]
    assert rows[0]["started_at"] == "1970-01-01T00:00:02+00:00"
    assert rows[0]["updated_at"] == "1970-01-01T00:00:04+00:00"
    assert rows[0]["completed_at"] is None
    assert rows[1]["parsed_raw_count"] == 7
    assert rows[1]["materialized_count"] == 2
    assert "succeeded_file_count" not in rows[1]
    assert "source_payload_read_bytes" not in rows[1]


def test_explicit_unavailable_source_does_not_fall_back(tmp_path, monkeypatch):
    monkeypatch.setenv("SINNIX_OBSERVE_POLYLOGUE_DB", str(tmp_path / "missing.db"))
    result = polylogue.collect_polylogue_live_attempts(5)
    assert result["available"] is False
    assert result["db"] == str(tmp_path / "missing.db")
    assert result["gaps"] == ["polylogue.live_attempts.unavailable"]


def test_obsolete_schema_is_unavailable(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute("create table live_ingest_attempt(attempt_id text)")
    monkeypatch.setenv("SINNIX_OBSERVE_POLYLOGUE_DB", str(path))
    assert polylogue.collect_polylogue_live_attempts(5)["available"] is False
