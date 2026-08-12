from __future__ import annotations

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
