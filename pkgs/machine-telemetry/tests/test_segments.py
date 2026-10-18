from __future__ import annotations

from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(
        f"machine_telemetry.{name}", ROOT / "machine_telemetry" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


collector = _load("collector")
segments = _load("segments")


@pytest.fixture
def database(tmp_path: Path) -> Path:
    path = tmp_path / "telemetry.sqlite"
    with closing(sqlite3.connect(path)) as connection:
        collector.init_db(connection)
        connection.execute(
            "INSERT INTO metric_sample(observed_at, host, schema_version, interval_s)"
            " VALUES ('2026-10-18T00:00:00Z', 'host', 1, 10)"
        )
        connection.commit()
    return path


def seal(database: Path, stamp: str) -> dict:
    return segments.seal(
        database,
        collector.init_db,
        stamp=stamp,
        immutable=lambda path: None,
        holders=lambda path: [],
    )


def test_sealing_continues_row_ids_and_lists_both_files(database: Path) -> None:
    manifest = seal(database, "20261025T000000Z")
    sealed = database.parent / "telemetry.20261025T000000Z.sqlite"
    assert manifest["state"] == "ready"
    assert [entry["file"] for entry in manifest["sealed"]] == [sealed.name]
    assert manifest["sealed"][0]["identity"] == segments.identity(sealed)
    assert manifest["current"]["identity"]["inode"] == database.stat().st_ino
    with closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "INSERT INTO metric_sample(observed_at, host, schema_version, interval_s)"
            " VALUES ('2026-10-25T00:00:00Z', 'host', 1, 10)"
        )
        assert connection.execute("SELECT max(id) FROM metric_sample").fetchone() == (2,)
    assert json.loads(segments.manifest_path(database).read_text()) == manifest


def test_a_second_seal_appends(database: Path) -> None:
    seal(database, "20261025T000000Z")
    manifest = seal(database, "20261101T000000Z")
    assert [entry["file"] for entry in manifest["sealed"]] == [
        "telemetry.20261025T000000Z.sqlite",
        "telemetry.20261101T000000Z.sqlite",
    ]


def test_an_interrupted_seal_finishes_on_rerun(database: Path, monkeypatch) -> None:
    real_rename = segments.os.rename

    def crash_on_second(source, target):
        if str(source).endswith(".next"):
            raise OSError("power lost")
        real_rename(source, target)

    monkeypatch.setattr(segments.os, "rename", crash_on_second)
    with pytest.raises(OSError):
        seal(database, "20261025T000000Z")
    assert json.loads(segments.manifest_path(database).read_text())["state"] == "sealing"
    monkeypatch.setattr(segments.os, "rename", real_rename)
    manifest = seal(database, "ignored")
    assert manifest["state"] == "ready"
    assert manifest["sealed"][0]["file"] == "telemetry.20261025T000000Z.sqlite"
    assert database.exists()


def test_the_collector_refuses_to_start_mid_seal(database: Path, monkeypatch) -> None:
    monkeypatch.setattr(segments.os, "rename", lambda *_: (_ for _ in ()).throw(OSError("stop")))
    with pytest.raises(OSError):
        seal(database, "20261025T000000Z")
    with pytest.raises(RuntimeError, match="incomplete"):
        with collector.writer_guard(database):
            pass


def test_verify_and_archive_run_once_per_sealed_file(database: Path, tmp_path: Path) -> None:
    seal(database, "20261025T000000Z")
    calls: list[list[str]] = []

    def run(argv: list[str]) -> None:
        calls.append(argv)
        if "--check-mode" in argv:
            Path(argv[-1]).write_bytes(b"zstd")

    records, output = tmp_path / "verified", tmp_path / "archives"
    assert segments.verify(database, records, run) == ["telemetry.20261025T000000Z.sqlite"]
    assert segments.verify(database, records, run) == []
    assert segments.archive(database, output, run) == ["telemetry.20261025T000000Z.sqlite"]
    assert segments.archive(database, output, run) == []
    assert len(calls) == 2


def test_archive_adopts_the_first_cutovers_legacy_artifact(database: Path, tmp_path: Path) -> None:
    manifest = seal(database, "20261025T000000Z")
    entry = manifest["sealed"][0]
    output = tmp_path / "archives"
    output.mkdir()
    (output / f"legacy-{entry['identity']['inode']}.sqlite.zst.json").write_text(
        json.dumps(
            {
                "state": "ready",
                "source_identity": entry["identity"],
                "artifact": str(output / "legacy-1.sqlite.zst"),
            }
        )
    )
    assert segments.archive(database, output, lambda argv: pytest.fail("recompressed")) == []


def test_a_changed_sealed_file_is_refused(database: Path, tmp_path: Path) -> None:
    seal(database, "20261025T000000Z")
    sealed = database.parent / "telemetry.20261025T000000Z.sqlite"
    with sealed.open("ab") as stream:
        stream.write(b"x")
    with pytest.raises(RuntimeError, match="changed after sealing"):
        segments.verify(database, tmp_path / "verified", lambda argv: None)
