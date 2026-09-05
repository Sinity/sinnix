from __future__ import annotations

import os
import shutil
import signal
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / "scripts" / "sinnix-sqlite-backup"


def read_receipt(stdout: str) -> dict[str, str]:
    """Parse the one line a run publishes for the journal to hold."""
    lines = [
        line
        for line in stdout.splitlines()
        if line.startswith("sqlite-backup receipt:")
    ]
    assert len(lines) == 1, stdout
    fields = lines[0].removeprefix("sqlite-backup receipt:").split()
    return dict(field.split("=", 1) for field in fields)


def seed_large_database(path: Path) -> None:
    """A snapshot over FULL_INTEGRITY_PAGE_LIMIT, so it takes the quick_check
    route the live 38 GB database takes. One blob's overflow chain reaches the
    page count cheaply; walking it costs almost nothing."""
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA page_size=512")
        connection.execute("VACUUM")
        connection.execute("CREATE TABLE samples (value BLOB NOT NULL)")
        connection.execute("INSERT INTO samples VALUES (zeroblob(52000000))")
        assert connection.execute("PRAGMA page_count").fetchone()[0] > 100_000


@pytest.fixture(scope="module")
def slow_walk_database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A snapshot whose quick_check spends ~0.2s scanning, an order longer than
    CHECK_POLL_SECONDS, so a deadline or a signal lands inside the walk rather
    than after it. The scan's cost tracks cells rather than pages, which is why
    this is a million narrow rows and not the cheap overflow chain above. Built
    once and only ever opened read-only."""
    path = tmp_path_factory.mktemp("slow-walk") / "telemetry.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA page_size=512")
        connection.execute("VACUUM")
        connection.execute(
            "CREATE TABLE samples (id INTEGER PRIMARY KEY, unit TEXT, value TEXT)"
        )
        connection.executemany(
            "INSERT INTO samples(unit, value) VALUES (?, ?)",
            (
                (f"unit-{index % 97}", f"value-{index}-{'payload' * 6}")
                for index in range(1_000_000)
            ),
        )
        connection.execute("CREATE INDEX samples_unit ON samples(unit, id)")
        assert connection.execute("PRAGMA page_count").fetchone()[0] > 100_000
    return path


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
    receipt = read_receipt(result.stdout)
    assert receipt["check"] == "integrity_check"
    assert receipt["verdict"] == "ok"
    assert receipt["archive_check"] == "zstd-t:ok"
    assert receipt["archive"] == str(output)
    assert int(receipt["archive_bytes"]) == output.stat().st_size
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
    """A corrupt page must stop publication, not merely be noted.

    Mutation: replacing quick_check with schema_version accepts the corrupt
    overflow page, because page one, which stores the schema, is intact.
    """
    source = tmp_path / "telemetry.sqlite"
    seed_large_database(source)
    output = tmp_path / "out.zst"

    # Page three is part of the BLOB's overflow chain. Point it at itself while
    # preserving the schema page, so schema_version succeeds but quick_check
    # reports the malformed chain.
    with source.open("r+b") as database:
        database.seek(2 * 512)
        database.write((3).to_bytes(4, byteorder="big"))

    result = subprocess.run(
        [str(SCRIPT), "--immutable-source", str(source), str(output)],
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode != 0
    assert "quick_check(1) failed" in result.stderr
    assert not output.exists()
    assert not list(tmp_path.glob("*.tmp*"))


def test_integrity_walk_stops_when_it_outlasts_its_budget(
    tmp_path: Path, slow_walk_database: Path
) -> None:
    """The walk is bounded, and exhausting the bound publishes nothing.

    This also pins the mechanism: dropping either the watchdog's deadline arm
    or its connection.interrupt() call lets the walk run to completion and
    publish, because a progress handler cannot end a scan in flight.
    """
    source = slow_walk_database
    output = tmp_path / "out.zst"

    result = subprocess.run(
        [
            str(SCRIPT),
            "--immutable-source",
            "--check-budget-seconds",
            "0.01",
            str(source),
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 1
    assert "exceeded its integrity budget" in result.stderr
    assert not output.exists()
    assert not list(tmp_path.glob("*.tmp*"))


def test_run_answers_sigterm_once_the_walk_has_started(
    tmp_path: Path, slow_walk_database: Path
) -> None:
    """Signalling after the walk announces itself must end the run cleanly.

    Waiting for that line is what makes this deterministic: it is printed after
    the signal handlers are installed, so the run cancels rather than dying on
    the default SIGTERM disposition.
    """
    source = slow_walk_database
    output = tmp_path / "out.zst"

    process = subprocess.Popen(
        [str(SCRIPT), "--immutable-source", str(source), str(output)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout
    assert "quick_check(1)" in process.stdout.readline()
    process.send_signal(signal.SIGTERM)
    _, errors = process.communicate(timeout=30)

    assert process.returncode == 143, errors
    assert "cancelled" in errors
    assert not output.exists()
    assert not list(tmp_path.glob("*.tmp*"))


def test_cancellation_during_compression_leaves_no_partial_artifact(
    tmp_path: Path,
) -> None:
    """Mutation: dropping cleanup() from the cancellation path leaves the
    half-written .zst.tmp the stub created."""
    source = tmp_path / "telemetry.sqlite"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE samples (value TEXT NOT NULL)")
    output = tmp_path / "out.zst"
    partial = tmp_path / "out.zst.tmp"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    zstd = fake_bin / "zstd"
    # exec so the sleeping compressor is the direct child holding the pipes,
    # as the real zstd is; otherwise an orphan outlives the cancelled run and
    # the test waits on it rather than on the run.
    zstd.write_text(f"#!/bin/sh\nprintf 'partial' > {partial}\nexec sleep 60\n")
    zstd.chmod(0o755)

    process = subprocess.Popen(
        [str(SCRIPT), "--immutable-source", str(source), str(output)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"},
    )
    deadline = time.time() + 15
    while not partial.exists() and time.time() < deadline:
        time.sleep(0.02)
    assert partial.exists(), "compression stub never started"
    process.send_signal(signal.SIGTERM)
    _, errors = process.communicate(timeout=15)

    assert process.returncode == 143, errors
    assert not output.exists()
    assert not list(tmp_path.glob("*.tmp*"))


def test_publication_requires_the_archive_to_decompress(tmp_path: Path) -> None:
    """zstd exiting zero is not proof the artifact restores.

    The stub compresses for real and then flips a byte, so only an explicit
    test of the frame catches it. Mutation: dropping the `zstd -t` call
    publishes the corrupted archive.
    """
    source = tmp_path / "telemetry.sqlite"
    seed_database(source)
    with sqlite3.connect(source) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    Path(f"{source}-wal").unlink(missing_ok=True)
    output = tmp_path / "out.zst"
    real_zstd = shutil.which("zstd")
    assert real_zstd
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    zstd = fake_bin / "zstd"
    zstd.write_text(
        "#!/bin/sh\n"
        f'if [ "$1" = "-t" ]; then exec {real_zstd} "$@"; fi\n'
        f'{real_zstd} "$@" || exit $?\n'
        'out=""; prev=""\n'
        'for arg in "$@"; do\n'
        '  if [ "$prev" = "-o" ]; then out="$arg"; fi\n'
        '  prev="$arg"\n'
        "done\n"
        "printf '\\377' | dd of=\"$out\" bs=1 "
        'seek="$(( $(stat -c %s "$out") / 2 ))" conv=notrunc status=none\n'
    )
    zstd.chmod(0o755)

    result = subprocess.run(
        [str(SCRIPT), "--immutable-source", str(source), str(output)],
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"},
        timeout=60,
    )

    assert result.returncode != 0
    assert not output.exists()
    assert not list(tmp_path.glob("*.tmp*"))


def test_large_snapshot_receipt_records_the_quick_check_verdict(tmp_path: Path) -> None:
    """One live run must be readable back from the journal.

    Mutation: dropping the receipt line, or recording a check the run did not
    perform, fails this.
    """
    source = tmp_path / "telemetry.sqlite"
    seed_large_database(source)
    output = tmp_path / "out.zst"

    result = subprocess.run(
        [str(SCRIPT), "--immutable-source", str(source), str(output)],
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    receipt = read_receipt(result.stdout)
    assert receipt["check"] == "quick_check(1)"
    assert receipt["verdict"] == "ok"
    assert receipt["archive_check"] == "zstd-t:ok"
    assert receipt["source"] == str(source)
    assert int(receipt["source_bytes"]) == source.stat().st_size
    assert int(receipt["archive_bytes"]) == output.stat().st_size
    assert float(receipt["check_seconds"]) >= 0
    assert float(receipt["compress_seconds"]) >= 0


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
