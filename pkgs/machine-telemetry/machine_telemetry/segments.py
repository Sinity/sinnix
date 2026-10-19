"""Telemetry SQLite segments: one active file and sealed, immutable ones.

`telemetry.sqlite.segments.json` beside the database lists them; Lynchpin
reads that file. The collector writes only the active file.

* `seal` closes the active file, makes it immutable under a dated name, and
  starts a new active file that continues the row-id sequences.
* `verify` checks each sealed file's SQLite structure once. A sealed file
  cannot change, so its result stays valid.
* `archive` compresses each sealed file once into the backup directory.
* `check` holds the collector's shared lock, proving no seal is in progress.

Sealing stops at a visible error rather than guessing: while the manifest
says "sealing" the collector refuses to start, and rerunning `seal` finishes
the recorded step.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sqlite3
import stat
import subprocess
import time
from contextlib import closing
from pathlib import Path
from typing import Callable

from sinnix_lib.atomic import atomic_publish

SCHEMA = "sinnix-machine-sqlite-segments-v1"
FS_IOC_GETFLAGS = 0x80086601
FS_IMMUTABLE_FL = 0x10


def manifest_path(database: Path) -> Path:
    return database.with_name(database.name + ".segments.json")


def lock_path(database: Path) -> Path:
    return database.with_name(database.name + ".segments.lock")


def identity(path: Path) -> dict[str, int]:
    value = path.lstat()
    if not stat.S_ISREG(value.st_mode):
        raise RuntimeError(f"not a regular SQLite file: {path}")
    return {
        "inode": value.st_ino,
        "size": value.st_size,
        "mtime_ns": value.st_mtime_ns,
        "ctime_ns": value.st_ctime_ns,
    }


def _sync(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish(path: Path, value: dict) -> None:
    atomic_publish(
        path, json.dumps(value, sort_keys=True).encode(), fsync=True, mode=0o600
    )
    owner = path.parent.stat()
    if os.geteuid() == 0:
        os.chown(path, owner.st_uid, owner.st_gid)
    _sync(path.parent)


def _match_owner(path: Path, reference: Path) -> None:
    owner = reference.stat()
    os.chmod(path, stat.S_IMODE(owner.st_mode))
    if os.geteuid() == 0:
        os.chown(path, owner.st_uid, owner.st_gid)


def make_immutable(path: Path) -> None:
    subprocess.run(["chattr", "+i", str(path)], check=True, timeout=10)
    import array

    flags = array.array("L", [0])
    with path.open("rb") as stream:
        fcntl.ioctl(stream, FS_IOC_GETFLAGS, flags, True)
    if not flags[0] & FS_IMMUTABLE_FL:
        raise RuntimeError(f"{path.name} was not made immutable")


def open_holders(path: Path) -> list[int]:
    """PIDs with `path` open; sealing needs the collector stopped."""
    target = path.stat()
    holders = []
    for process in Path("/proc").iterdir():
        if not process.name.isdigit() or int(process.name) == os.getpid():
            continue
        try:
            descriptors = list((process / "fd").iterdir())
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        for descriptor in descriptors:
            try:
                value = descriptor.stat()
            except (FileNotFoundError, ProcessLookupError):
                continue
            if (value.st_dev, value.st_ino) == (target.st_dev, target.st_ino):
                holders.append(int(process.name))
                break
    return holders


def read_manifest(database: Path) -> dict | None:
    path = manifest_path(database)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise RuntimeError("unsupported telemetry segment manifest")
    return payload


def _exclusive(database: Path):
    descriptor = os.open(
        lock_path(database), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600
    )
    held = os.fdopen(descriptor, "r+b")
    if not stat.S_ISREG(os.fstat(held.fileno()).st_mode):
        held.close()
        raise RuntimeError("telemetry segment lock is not a regular file")
    try:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as err:
        held.close()
        raise RuntimeError(
            "telemetry segments are locked by a running collector or seal"
        ) from err
    return held


def _prepare_next(
    database: Path, staging: Path, initialize: Callable[[sqlite3.Connection], None]
) -> None:
    """Checkpoint the active file and create its successor beside it."""
    with closing(
        sqlite3.connect(f"{database.as_uri()}?mode=rw", uri=True, timeout=5)
    ) as old:
        if old.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0]:
            raise RuntimeError("telemetry checkpoint is busy")
        if old.execute("PRAGMA journal_mode=DELETE").fetchone()[0] != "delete":
            raise RuntimeError("could not close the active file's WAL")
        sequence = old.execute("SELECT name, seq FROM sqlite_sequence").fetchall()
        columns = [row[1] for row in old.execute("PRAGMA table_info(source_status)")]
        statuses = old.execute("SELECT * FROM source_status ORDER BY source").fetchall()
    with closing(sqlite3.connect(staging, timeout=5)) as new:
        initialize(new)
        new.execute("PRAGMA synchronous=FULL")
        new.execute("BEGIN IMMEDIATE")
        # Row ids continue across segments, so a row keeps one identity.
        new.execute("DELETE FROM sqlite_sequence")
        new.executemany(
            "INSERT INTO sqlite_sequence(name, seq) VALUES (?, ?)", sequence
        )
        new.execute("DELETE FROM source_status")
        if statuses:
            fields = ",".join('"' + name.replace('"', '""') + '"' for name in columns)
            marks = ",".join("?" for _ in columns)
            new.executemany(
                f"INSERT INTO source_status({fields}) VALUES ({marks})", statuses
            )
        new.commit()
        if new.execute("PRAGMA journal_mode=DELETE").fetchone()[0] != "delete":
            raise RuntimeError("new active file kept a journal")
    with staging.open("rb") as stream:
        os.fsync(stream.fileno())
    _match_owner(staging, database)


def seal(
    database: Path,
    initialize: Callable[[sqlite3.Connection], None],
    *,
    stamp: str | None = None,
    immutable: Callable[[Path], None] = make_immutable,
    holders: Callable[[Path], list[int]] = open_holders,
) -> dict:
    """Seal the active file and start a new one; resume an interrupted seal."""
    database = database.absolute()
    directory = database.parent
    staging = database.with_name(database.name + ".next")
    with _exclusive(database):
        manifest = read_manifest(database) or {
            "schema": SCHEMA,
            "state": "ready",
            "generation": "unsegmented",
            "sealed": [],
            "current": {
                "id": "active-unsegmented",
                "file": database.name,
                "identity": identity(database),
            },
        }
        if manifest.get("state") == "sealing":
            pending = manifest["pending"]
        elif manifest.get("state") == "ready":
            if staging.exists():
                raise RuntimeError(
                    f"{staging.name} exists without a recorded seal; inspect it"
                )
            busy = holders(database)
            if busy:
                raise RuntimeError(
                    f"the active telemetry file is open by {busy}; stop the collector"
                )
            stamp = stamp or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            pending = {"stamp": stamp, "file": f"{database.stem}.{stamp}.sqlite"}
            if (directory / pending["file"]).exists():
                raise RuntimeError(f"{pending['file']} already exists")
            _prepare_next(database, staging, initialize)
            manifest.update(state="sealing", pending=pending)
            _publish(manifest_path(database), manifest)
        else:
            raise RuntimeError(
                f"unknown segment manifest state {manifest.get('state')!r}"
            )

        sealed = directory / pending["file"]
        if not sealed.exists():
            os.rename(database, sealed)
            _sync(directory)
        immutable(sealed)
        if not database.exists():
            os.rename(staging, database)
            _sync(directory)
        stamp = pending["stamp"]
        manifest["sealed"] = [
            *manifest.get("sealed", []),
            {
                "id": f"segment-{stamp}",
                "file": sealed.name,
                "identity": identity(sealed),
            },
        ]
        manifest["current"] = {
            "id": f"active-{stamp}",
            "file": database.name,
            "identity": identity(database),
        }
        manifest["generation"] = f"sealed-{stamp}"
        manifest["state"] = "ready"
        manifest.pop("pending", None)
        _publish(manifest_path(database), manifest)
        return manifest


def _record_path(records: Path, file: str, kind: str) -> Path:
    return records / f"{file}.{kind}.json"


def _done(record: Path, entry: dict) -> bool:
    if not record.exists():
        return False
    value = json.loads(record.read_text(encoding="utf-8"))
    return value.get("identity") == entry["identity"] and value.get("ok") is True


def _sealed_entries(database: Path) -> list[dict]:
    manifest = read_manifest(database)
    if manifest is None or manifest.get("state") != "ready":
        return []
    for entry in manifest["sealed"]:
        if identity(database.parent / entry["file"]) != entry["identity"]:
            raise RuntimeError(f"sealed file {entry['file']} changed after sealing")
    return manifest["sealed"]


def verify(
    database: Path, records: Path, run: Callable[[list[str]], None] | None = None
) -> list[str]:
    """Check each sealed file's structure once; return the files checked now."""
    run = run or (lambda argv: subprocess.run(argv, check=True))
    records.mkdir(mode=0o700, parents=True, exist_ok=True)
    checked = []
    for entry in _sealed_entries(database):
        record = _record_path(records, entry["file"], "verified")
        if _done(record, entry):
            continue
        source = database.parent / entry["file"]
        run(
            ["sinnix-sqlite-backup", "--immutable-source", "--verify-only", str(source)]
        )
        _publish(
            record,
            {
                "file": entry["file"],
                "identity": entry["identity"],
                "ok": True,
                "check": "structural",
                "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        )
        checked.append(entry["file"])
    return checked


def archive(
    database: Path, output: Path, run: Callable[[list[str]], None] | None = None
) -> list[str]:
    """Compress each sealed file once into `output`; return the files archived now."""
    run = run or (lambda argv: subprocess.run(argv, check=True))
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    archived = []
    for entry in _sealed_entries(database):
        record = _record_path(output, entry["file"], "archived")
        if _done(record, entry):
            continue
        # The first cutover archived the legacy file as legacy-<inode>.sqlite.zst
        # with its own receipt; adopt it rather than compress 70 GB again.
        earlier = output / f"legacy-{entry['identity']['inode']}.sqlite.zst.json"
        if earlier.exists():
            previous = json.loads(earlier.read_text(encoding="utf-8"))
            if (
                previous.get("state") == "ready"
                and previous.get("source_identity") == entry["identity"]
            ):
                _publish(
                    record,
                    {
                        "file": entry["file"],
                        "identity": entry["identity"],
                        "ok": True,
                        "artifact": Path(previous["artifact"]).name,
                        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    },
                )
                continue
        artifact = output / f"{entry['file']}.zst"
        run(
            [
                "sinnix-sqlite-backup",
                "--immutable-source",
                "--check-mode",
                "header",
                str(database.parent / entry["file"]),
                str(artifact),
            ]
        )
        _match_owner(artifact, output)
        _publish(
            record,
            {
                "file": entry["file"],
                "identity": entry["identity"],
                "ok": True,
                "artifact": artifact.name,
                "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        )
        archived.append(entry["file"])
    return archived


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=("check", "seal", "verify", "archive"))
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument(
        "--records", type=Path, help="where verify keeps its per-file results"
    )
    parser.add_argument(
        "--output", type=Path, help="where archive writes compressed copies"
    )
    args = parser.parse_args()
    from .collector import init_db, writer_guard

    if args.command == "check":
        with writer_guard(args.db):
            return 0
    if args.command == "seal":
        print(json.dumps(seal(args.db, init_db), sort_keys=True))
    elif args.command == "verify":
        if args.records is None:
            parser.error("verify needs --records")
        print(json.dumps(verify(args.db.absolute(), args.records)))
    else:
        if args.output is None:
            parser.error("archive needs --output")
        print(json.dumps(archive(args.db.absolute(), args.output)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
