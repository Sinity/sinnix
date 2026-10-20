import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from machine_telemetry import capacity, collector, segments


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "telemetry.sqlite"
    with collector.writer_guard(path):
        with closing(sqlite3.connect(path)) as connection:
            collector.init_db(connection)
    return path


def insert(database, monkeypatch, value=2**53 + 17):
    monkeypatch.setattr(
        capacity,
        "observe_capacity",
        lambda path: {
            "path": str(path),
            "status": "observed",
            "f_blocks": value,
            "f_bavail": value - 3,
            "f_bfree": value - 1,
            "f_frsize": 4096,
            "filesystem_uuid": "fixture-uuid",
            "mount_root": "/",
        },
    )
    with closing(sqlite3.connect(database)) as connection:
        capacity.insert_samples(
            connection,
            "2026-10-20T12:00:00+00:00",
            "fixture",
            "boot",
            volumes=[Path("/fixture")],
        )
        connection.commit()


def test_additive_schema_and_integer_precision(database, monkeypatch):
    insert(database, monkeypatch)
    with closing(sqlite3.connect(database)) as connection:
        collector.init_db(connection)
    result = capacity.read_history(database, "2026-10-01")
    assert result["rows"][0]["f_blocks"] == 2**53 + 17
    assert result["rows"][0]["f_bavail"] == 2**53 + 14


def seal(database, stamp="20261020T120000Z"):
    return segments.seal(
        database,
        collector.init_db,
        stamp=stamp,
        immutable=lambda _: None,
        holders=lambda _: [],
    )


def test_capacity_ids_continue_across_seal(database, monkeypatch):
    insert(database, monkeypatch)
    seal(database)
    insert(database, monkeypatch)
    rows = capacity.read_history(database, "2026-10-01")["rows"]
    assert [row["id"] for row in rows] == [1, 2]
    assert len({row["segment_id"] for row in rows}) == 2


def test_old_segment_without_capacity_is_explicit_absence(database, monkeypatch):
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("DROP TABLE filesystem_capacity_sample")
    manifest = seal(database)
    insert(database, monkeypatch)
    result = capacity.read_history(database, "2026-10-01")
    assert result["pre_feature_segments"] == [manifest["sealed"][0]["id"]]
    assert len(result["rows"]) == 1


@pytest.mark.parametrize(
    "damage", ["missing", "replaced", "sealing", "schema", "traversal"]
)
def test_reader_refuses_broken_owner_membership(database, monkeypatch, damage):
    insert(database, monkeypatch)
    manifest = seal(database)
    member = database.parent / manifest["sealed"][0]["file"]
    if damage == "missing":
        member.unlink()
    elif damage == "replaced":
        member.rename(member.with_suffix(".old"))
        member.write_bytes(b"wrong")
    elif damage == "sealing":
        manifest["state"] = "sealing"
        segments.manifest_path(database).write_text(json.dumps(manifest))
    elif damage == "traversal":
        manifest["sealed"][0]["file"] = "../outside.sqlite"
        segments.manifest_path(database).write_text(json.dumps(manifest))
    else:
        with closing(sqlite3.connect(database)) as connection:
            connection.execute(
                "ALTER TABLE filesystem_capacity_sample ADD COLUMN surprise TEXT"
            )
    before = set(database.parent.iterdir())
    with pytest.raises((OSError, ValueError, sqlite3.Error)):
        capacity.read_history(database, "2026-10-01")
    assert set(database.parent.iterdir()) == before


def test_probe_failure_preserves_unavailability(database, monkeypatch):
    def fail(path):
        raise PermissionError("fixture refusal")

    monkeypatch.setattr(capacity, "observe_capacity", fail)
    with closing(sqlite3.connect(database)) as connection:
        capacity.insert_samples(
            connection,
            "2026-10-20T12:00:00+00:00",
            "fixture",
            "boot",
            volumes=[Path("/fixture")],
        )
        connection.commit()
    row = capacity.read_history(database, "2026-10-01")["rows"][0]
    assert row["status"] == "unavailable" and row["f_bavail"] is None
    assert "fixture refusal" in row["reason"]


def test_missing_database_does_not_create_anything(tmp_path):
    with pytest.raises(FileNotFoundError):
        capacity.read_history(tmp_path / "absent.sqlite", "2026-10-01")
    assert list(tmp_path.iterdir()) == []


def test_manifest_change_during_read_is_refused(database, monkeypatch):
    manifest = seal(database)
    real_read = segments.read_manifest
    calls = []

    def changed(path):
        calls.append(path)
        return (
            real_read(path)
            if len(calls) == 1
            else {**manifest, "generation": "changed"}
        )

    monkeypatch.setattr(segments, "read_manifest", changed)
    with pytest.raises(ValueError, match="manifest changed"):
        capacity.read_history(database, "2026-10-01")


def test_active_missing_table_is_unavailable_not_old_coverage(database):
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("DROP TABLE filesystem_capacity_sample")
    with pytest.raises(ValueError, match="active telemetry"):
        capacity.read_history(database, "2026-10-01")
