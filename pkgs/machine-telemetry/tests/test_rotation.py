"""Tiny native SQLite crash controls. Production snapshots are never opened."""

from contextlib import closing
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest


def load(name):
    path = Path(__file__).parents[1] / "machine_telemetry" / (name + ".py")
    spec = importlib.util.spec_from_file_location("fixture_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compressed_fixture(candidate):
    subprocess.run(
        ["zstd", "-q", "-o", str(candidate)],
        input=b"synthetic compressed fixture",
        check=True,
    )


@pytest.fixture
def source(tmp_path):
    collector, rotation = load("collector"), load("rotation")
    database = tmp_path / "telemetry.sqlite"
    with closing(sqlite3.connect(database)) as conn:
        collector.init_db(conn)
        conn.execute(
            "INSERT INTO gpu_sample(id,observed_at,host) VALUES (7,'2026-01-02T12:00:00Z','fixture')"
        )
        conn.execute(
            "INSERT INTO gpu_sample(id,observed_at,host) VALUES (1000,'2026-01-02T13:00:00Z','fixture')"
        )
        conn.execute("DELETE FROM gpu_sample WHERE id=1000")
        conn.execute(
            "INSERT INTO source_status VALUES ('journal.cursor','2026-01-02T12:00:00Z','ok',NULL,'{\"cursor\":\"fixture-cursor\"}')"
        )
        conn.commit()
    snapshot = tmp_path / "preimage"
    snapshot.mkdir()
    shutil.copy2(database, snapshot / database.name)
    kwargs = dict(
        initialize=collector.init_db,
        preimage_check=lambda *args: None,
        retained_check=lambda *args: None,
        seal_member=lambda path: None,
        check_holders=lambda *args: [],
    )
    return collector, rotation, database, snapshot, kwargs


@pytest.mark.parametrize(
    "phase",
    [
        None,
        "prepared",
        "new_ready",
        "legacy_rename",
        "legacy_named",
        "current_rename",
        "current_named",
        "ready_manifest",
        "published",
    ],
)
def test_cutover_recovers_every_publication_boundary_and_preserves_ids(source, phase):
    collector, rotation, database, snapshot, kwargs = source
    original = (snapshot / database.name).read_bytes()

    def crash(where):
        if where == phase:
            raise RuntimeError("synthetic crash")

    if phase is not None:
        with pytest.raises(RuntimeError, match="synthetic crash"):
            rotation.rotate(database, snapshot, fault=crash, **kwargs)
        control = database.with_name(database.name + ".segments.json")
        if control.exists() and json.loads(control.read_text())["state"] == "preparing":
            with pytest.raises(RuntimeError, match="incomplete"):
                with collector.writer_guard(database):
                    pytest.fail("writer entered an incomplete cutover")
    manifest = rotation.rotate(database, snapshot, **kwargs)
    legacy = database.parent / manifest["sealed"][0]["file"]
    with closing(sqlite3.connect(f"{legacy.as_uri()}?mode=ro", uri=True)) as conn:
        assert conn.execute("SELECT id,observed_at FROM gpu_sample").fetchall() == [
            (7, "2026-01-02T12:00:00Z")
        ]
    with collector.writer_guard(database):
        with closing(sqlite3.connect(database)) as conn:
            assert conn.execute("SELECT COUNT(*) FROM gpu_sample").fetchone() == (0,)
            assert conn.execute(
                "SELECT payload_json FROM source_status WHERE source='journal.cursor'"
            ).fetchone() == ('{"cursor":"fixture-cursor"}',)
            # A late observation keeps a new capture identity above the deleted
            # high-water mark, rather than colliding with retained history.
            conn.execute(
                "INSERT INTO gpu_sample(observed_at,host) VALUES ('2026-01-01T12:00:00Z','fixture')"
            )
            assert conn.execute("SELECT id FROM gpu_sample").fetchone() == (1001,)
            conn.rollback()
    assert (snapshot / database.name).read_bytes() == original
    assert manifest["origin"]["inode"] == legacy.stat().st_ino
    assert rotation.rotate(database, snapshot, **kwargs) == manifest


def test_foreign_holder_and_unowned_destinations_refuse_before_mutation(source):
    _, rotation, database, snapshot, kwargs = source
    original = database.read_bytes()
    kwargs["check_holders"] = lambda *args: [123]
    with pytest.raises(RuntimeError, match="descriptors remain"):
        rotation.rotate(database, snapshot, **kwargs)
    assert database.read_bytes() == original
    assert not database.with_name(database.name + ".segments.json").exists()
    kwargs["check_holders"] = lambda *args: []
    destination = database.with_name(database.stem + ".legacy.sqlite")
    destination.write_bytes(b"unrelated retained object")
    with pytest.raises(RuntimeError, match="unowned"):
        rotation.rotate(database, snapshot, **kwargs)
    assert destination.read_bytes() == b"unrelated retained object"


def test_committed_wal_survives_unclean_writer_exit_and_cutover(source):
    _, rotation, database, snapshot, kwargs = source
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import os,sqlite3,sys
c=sqlite3.connect(sys.argv[1])
c.execute('PRAGMA journal_mode=WAL')
c.execute("INSERT INTO gpu_sample(id,observed_at,host) VALUES (1002,'2026-01-02T14:00:00Z','fixture')")
c.commit()
os._exit(0)
""",
            str(database),
        ],
        check=True,
        timeout=10,
    )
    assert database.with_name(database.name + "-wal").stat().st_size > 0
    shutil.copy2(database, snapshot / database.name)
    shutil.copy2(
        database.with_name(database.name + "-wal"), snapshot / (database.name + "-wal")
    )
    manifest = rotation.rotate(database, snapshot, **kwargs)
    legacy = database.parent / manifest["sealed"][0]["file"]
    assert not legacy.with_name(legacy.name + "-wal").exists()
    with closing(sqlite3.connect(legacy)) as conn:
        assert conn.execute("SELECT id FROM gpu_sample ORDER BY id").fetchall() == [
            (7,),
            (1002,),
        ]
        assert conn.execute("PRAGMA journal_mode").fetchone() == ("delete",)
    with closing(sqlite3.connect(database)) as conn:
        assert conn.execute(
            "SELECT seq FROM sqlite_sequence WHERE name='gpu_sample'"
        ).fetchone() == (1002,)


def test_preimage_requires_native_readonly_and_matching_observations(
    source, monkeypatch
):
    _, rotation, database, snapshot, _ = source
    monkeypatch.setattr(
        rotation.subprocess,
        "run",
        lambda *a, **k: type("Result", (), {"stdout": "ro=false\n"})(),
    )
    with pytest.raises(RuntimeError, match="read-only"):
        rotation.validate_preimage(database, snapshot)
    monkeypatch.setattr(
        rotation.subprocess,
        "run",
        lambda *a, **k: type("Result", (), {"stdout": "ro=true\n"})(),
    )
    # A plain copy has a different inode. Do not accept it as native snapshot
    # provenance merely because the bytes currently happen to match.
    with pytest.raises(RuntimeError, match="does not match"):
        rotation.validate_preimage(database, snapshot)


def test_legacy_archive_is_once_only_and_detects_changed_artifacts(source, tmp_path):
    _, rotation, database, snapshot, kwargs = source
    rotation.rotate(database, snapshot, **kwargs)
    calls = []

    def acquire(raw, candidate):
        calls.append(raw)
        compressed_fixture(candidate)

    output = tmp_path / "archives"
    first = rotation.archive_legacy(database, output, backup=acquire)
    assert first["state"] == "ready"
    assert first["structural_check"] == "pending"
    assert len(calls) == 1
    assert (
        rotation.archive_legacy(
            database,
            output,
            backup=lambda *args: pytest.fail("unchanged legacy was recompressed"),
        )
        == first
    )
    Path(first["artifact"]).write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="artifact changed"):
        rotation.archive_legacy(database, output, backup=acquire)
    assert len(calls) == 1


@pytest.mark.parametrize("boundary", ["acquiring", "prepared", "rename"])
def test_legacy_archive_recovers_without_recompressing(
    source, tmp_path, monkeypatch, boundary
):
    _, rotation, database, snapshot, kwargs = source
    rotation.rotate(database, snapshot, **kwargs)
    original_publish, original_rename = rotation._publish, rotation.os.rename
    calls = []

    def acquire(raw, candidate):
        calls.append(raw)
        compressed_fixture(candidate)
        if boundary == "acquiring":
            raise RuntimeError("synthetic crash after helper publication")

    def publish(path, value):
        original_publish(path, value)
        if boundary == "prepared" and value.get("state") == "prepared":
            raise RuntimeError("synthetic crash after prepared receipt")

    def rename(left, right):
        original_rename(left, right)
        if boundary == "rename":
            raise RuntimeError("synthetic crash after rename")

    monkeypatch.setattr(rotation, "_publish", publish)
    monkeypatch.setattr(rotation.os, "rename", rename)
    output = tmp_path / "archives"
    with pytest.raises(RuntimeError, match="synthetic crash"):
        rotation.archive_legacy(database, output, backup=acquire)
    monkeypatch.setattr(rotation, "_publish", original_publish)
    monkeypatch.setattr(rotation.os, "rename", original_rename)
    result = rotation.archive_legacy(
        database,
        output,
        backup=lambda *args: pytest.fail("completed acquisition was repeated"),
    )
    assert result["state"] == "ready"
    assert len(calls) == 1


def test_legacy_archive_uses_the_existing_real_backup_helper(source, tmp_path):
    _, rotation, database, snapshot, kwargs = source
    rotation.rotate(database, snapshot, **kwargs)
    helper = Path(
        os.environ.get(
            "SINNIX_SQLITE_BACKUP",
            Path(__file__).parents[3] / "scripts" / "sinnix-sqlite-backup",
        )
    )

    def acquire(raw, candidate):
        subprocess.run(
            [
                str(helper),
                "--immutable-source",
                "--check-mode",
                "header",
                str(raw),
                str(candidate),
            ],
            check=True,
            timeout=30,
        )

    result = rotation.archive_legacy(database, tmp_path / "archives", backup=acquire)
    subprocess.run(
        ["zstd", "-t", result["artifact"]], check=True, capture_output=True, timeout=10
    )
    assert result["state"] == "ready"
    assert result["structural_check"] == "pending"


def test_recovery_never_resets_rows_written_after_ready_publication(source):
    _, rotation, database, snapshot, kwargs = source

    def crash(phase):
        if phase == "ready_manifest":
            raise RuntimeError("synthetic crash")

    with pytest.raises(RuntimeError, match="synthetic"):
        rotation.rotate(database, snapshot, fault=crash, **kwargs)
    with closing(sqlite3.connect(database)) as conn:
        conn.execute(
            "INSERT INTO gpu_sample(observed_at,host) VALUES ('2026-01-03T00:00:00Z','fixture')"
        )
        conn.commit()
    rotation.rotate(database, snapshot, **kwargs)
    with closing(sqlite3.connect(database)) as conn:
        assert conn.execute("SELECT id FROM gpu_sample").fetchall() == [(1001,)]
        assert conn.execute(
            "SELECT seq FROM sqlite_sequence WHERE name='gpu_sample'"
        ).fetchone() == (1001,)


def test_interrupted_candidate_with_bad_frame_is_not_adopted(source, tmp_path):
    _, rotation, database, snapshot, kwargs = source
    rotation.rotate(database, snapshot, **kwargs)
    output = tmp_path / "archives"

    def crash(raw, candidate):
        candidate.write_bytes(b"invalid frame")
        raise RuntimeError("synthetic crash")

    with pytest.raises(RuntimeError, match="synthetic"):
        rotation.archive_legacy(database, output, backup=crash)
    with pytest.raises(subprocess.CalledProcessError):
        rotation.archive_legacy(
            database,
            output,
            backup=lambda *args: pytest.fail("must preserve the suspect candidate"),
        )
    assert not list(output.glob("*.sqlite.zst"))
    assert len(list(output.glob(".*.candidate"))) == 1


def test_recovery_refuses_changed_retained_preimage_before_mutating_source(source):
    _, rotation, database, snapshot, kwargs = source

    def crash(phase):
        if phase == "prepared":
            raise RuntimeError("synthetic crash")

    with pytest.raises(RuntimeError, match="synthetic"):
        rotation.rotate(database, snapshot, fault=crash, **kwargs)
    original = database.read_bytes()
    (snapshot / database.name).write_bytes(b"changed preimage")
    with pytest.raises(RuntimeError, match="preimage changed"):
        rotation.rotate(database, snapshot, **kwargs)
    assert database.read_bytes() == original
    assert not database.with_name(database.name + ".segments.json").exists()
