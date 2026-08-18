from __future__ import annotations

import os
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

SCRIPT = Path(__file__).parents[3] / "scripts" / "sinnix-sqlite-backup"


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
