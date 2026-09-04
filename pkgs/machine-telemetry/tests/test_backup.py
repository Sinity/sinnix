from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / "scripts" / "sinnix-sqlite-backup"


def backup_module():
    loader = importlib.machinery.SourceFileLoader("sinnix_sqlite_backup", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seed_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            "CREATE TABLE samples (id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.executemany(
            "INSERT INTO samples(value) VALUES (?)",
            ((f"value-{index}",) for index in range(1000)),
        )


def test_backup_completes_against_active_writer_and_decompresses_cleanly(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.sqlite"
    output = tmp_path / "backup.sqlite.zst"
    seed_database(source)
    stop = threading.Event()

    def writer() -> None:
        while not stop.is_set():
            with sqlite3.connect(source, timeout=5) as connection:
                connection.execute("INSERT INTO samples(value) VALUES ('live')")
            time.sleep(0.002)

    thread = threading.Thread(target=writer)
    thread.start()
    try:
        result = subprocess.run(
            [str(SCRIPT), str(source), str(output)],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    finally:
        stop.set()
        thread.join(timeout=5)
    assert result.returncode == 0, result.stderr
    assert output.exists()
    restored = tmp_path / "restored.sqlite"
    subprocess.run(
        ["zstd", "-q", "-d", "-f", str(output), "-o", str(restored)], check=True
    )
    with sqlite3.connect(restored) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("SELECT count(*) FROM samples").fetchone()[0] >= 1000
    assert not list(tmp_path.glob("*.tmp*"))


def test_failed_backup_removes_all_temporary_sidecars(tmp_path: Path) -> None:
    source = tmp_path
    output = tmp_path / "backup.sqlite.zst"
    result = subprocess.run(
        [str(SCRIPT), str(source), str(output)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert not list(tmp_path.glob("*.tmp*"))


def test_backup_sweeps_orphaned_sidecar_from_a_prior_crashed_run(
    tmp_path: Path,
) -> None:
    # A run under a different (e.g. earlier timestamp-derived) name was
    # killed before its own `finally: cleanup()` ran, leaving a sidecar this
    # run's per-run cleanup() -- scoped to its own raw_path -- cannot see.
    source = tmp_path / "source.sqlite"
    output = tmp_path / "telemetry-later.sqlite.zst"
    seed_database(source)
    orphan = tmp_path / "telemetry-earlier.sqlite.tmp-journal"
    orphan.write_bytes(b"stale")
    old = time.time() - 7200
    os.utime(orphan, (old, old))

    result = subprocess.run(
        [str(SCRIPT), str(source), str(output)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert output.exists()
    assert not orphan.exists()


def test_backup_of_a_parked_walless_database_succeeds(tmp_path: Path) -> None:
    """A cleanly-checkpointed (parked) db has no -wal sidecar; that is the
    clean state, not an error. Mutation: reverting the exists() check to the
    old try/except-FileNotFoundError shape fails this (cp exits 1 ->
    CalledProcessError, which that handler never caught)."""
    source = tmp_path / "parked.sqlite"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE t (x INTEGER)")
        connection.execute("INSERT INTO t VALUES (1)")
    assert not Path(f"{source}-wal").exists()
    output = tmp_path / "parked.sqlite.zst"
    result = subprocess.run(
        [str(SCRIPT), str(source), str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert output.exists() and output.stat().st_size > 0


def test_immutable_snapshot_source_is_compressed_without_copy(tmp_path: Path) -> None:
    source = tmp_path / "snapshot" / "telemetry.sqlite"
    source.parent.mkdir()
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE t (x INTEGER)")
        connection.execute("INSERT INTO t VALUES (1)")
    output = tmp_path / "snapshot.sqlite.zst"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    cp = fake_bin / "cp"
    cp.write_text("#!/bin/sh\nexit 99\n")
    cp.chmod(0o755)
    result = subprocess.run(
        [str(SCRIPT), "--immutable-source", str(source), str(output)],
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"},
    )
    assert result.returncode == 0, result.stderr
    assert output.exists()
    assert "SQLite quick_check(1): ok" in result.stdout
    assert "SQLite compression: ok" in result.stdout
    assert not list(tmp_path.glob("*.tmp*"))


def test_immutable_snapshot_source_rejects_wal_sidecar(tmp_path: Path) -> None:
    source = tmp_path / "telemetry.sqlite"
    seed_database(source)
    with sqlite3.connect(source) as connection:
        connection.execute("INSERT INTO samples(value) VALUES ('uncheckpointed')")
    assert Path(f"{source}-wal").exists()
    result = subprocess.run(
        [str(SCRIPT), "--immutable-source", str(source), str(tmp_path / "out.zst")],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "must not have a WAL" in result.stderr


def test_immutable_snapshot_source_accepts_empty_wal_sidecar(tmp_path: Path) -> None:
    source = tmp_path / "telemetry.sqlite"
    seed_database(source)
    Path(f"{source}-wal").write_bytes(b"")

    result = subprocess.run(
        [str(SCRIPT), "--immutable-source", str(source), str(tmp_path / "out.zst")],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_immutable_large_snapshot_rejects_corruption(tmp_path: Path) -> None:
    """A large snapshot must run quick_check, not only read schema_version.

    Mutation: replacing quick_check with schema_version makes this accept the
    corrupt overflow page because page one, which stores the schema, is intact.
    """
    source = tmp_path / "telemetry.sqlite"
    with sqlite3.connect(source) as connection:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA page_size=512")
        connection.execute("VACUUM")
        connection.execute("CREATE TABLE samples (value BLOB NOT NULL)")
        connection.execute("INSERT INTO samples VALUES (zeroblob(52000000))")
        assert connection.execute("PRAGMA page_count").fetchone()[0] > 100_000

    # Page three is part of the BLOB's overflow chain. Point it at itself while
    # preserving the schema page, so schema_version succeeds but quick_check
    # reports the malformed chain.
    with source.open("r+b") as database:
        database.seek(2 * 512)
        database.write((3).to_bytes(4, byteorder="big"))

    result = subprocess.run(
        [str(SCRIPT), "--immutable-source", str(source), str(tmp_path / "out.zst")],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode != 0
    assert "quick_check failed" in result.stderr


def test_quick_check_honors_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cancellation must interrupt quick_check instead of waiting for its scan.

    Mutation: removing the progress handler leaves the synthetic query running
    and fails this test.
    """
    backup = backup_module()

    class Connection:
        progress_handler = None

        def set_progress_handler(self, handler, _operations):
            self.progress_handler = handler

        def execute(self, statement):
            assert statement == "PRAGMA quick_check(1)"
            backup.request_cancel(0, None)
            assert self.progress_handler and self.progress_handler()
            raise sqlite3.OperationalError("interrupted")

    monkeypatch.setattr(backup, "cancel_requested", False)
    with pytest.raises(backup.BackupCancelled):
        backup.require_quick_check(Connection())


def test_immutable_snapshot_does_not_publish_when_compression_fails(
    tmp_path: Path,
) -> None:
    source = tmp_path / "telemetry.sqlite"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE samples (value TEXT NOT NULL)")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    zstd = fake_bin / "zstd"
    zstd.write_text("#!/bin/sh\nexit 99\n")
    zstd.chmod(0o755)
    output = tmp_path / "out.zst"

    result = subprocess.run(
        [str(SCRIPT), "--immutable-source", str(source), str(output)],
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"},
    )

    assert result.returncode != 0
    assert not output.exists()
