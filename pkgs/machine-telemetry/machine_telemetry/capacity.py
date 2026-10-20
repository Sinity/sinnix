"""Exact filesystem observations and read-only access through the segment owner."""

from __future__ import annotations

import fcntl
import json
import os
import sqlite3
import stat
from contextlib import closing
from pathlib import Path

from sinnix_lib.mounts import observe_capacity

from . import segments

INTERVAL_SECONDS = 300
VOLUMES = (Path("/realm"), Path("/outer-realm"), Path("/neo-outer-realm"))
COLUMNS = (
    "observed_at",
    "host",
    "boot_id",
    "path",
    "status",
    "reason",
    "mount_id",
    "device",
    "mount_root",
    "filesystem_type",
    "source",
    "filesystem_uuid",
    "f_blocks",
    "f_bfree",
    "f_bavail",
    "f_frsize",
)


def init_db(connection: sqlite3.Connection) -> None:
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS filesystem_capacity_sample (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          observed_at TEXT NOT NULL, host TEXT NOT NULL, boot_id TEXT,
          path TEXT NOT NULL, status TEXT NOT NULL, reason TEXT,
          mount_id INTEGER, device INTEGER, mount_root TEXT, filesystem_type TEXT,
          source TEXT, filesystem_uuid TEXT,
          f_blocks INTEGER, f_bfree INTEGER, f_bavail INTEGER, f_frsize INTEGER
        );
        CREATE INDEX IF NOT EXISTS filesystem_capacity_observed
          ON filesystem_capacity_sample(observed_at);
    """)


def insert_samples(connection, observed_at, host, boot_id, *, volumes=VOLUMES):
    for path in volumes:
        try:
            row = observe_capacity(path)
        except (OSError, ValueError) as error:
            row = {"path": str(path), "status": "unavailable", "reason": str(error)}
        row.update(observed_at=observed_at, host=host, boot_id=boot_id)
        connection.execute(
            f"INSERT INTO filesystem_capacity_sample ({','.join(COLUMNS)})"
            f" VALUES ({','.join('?' for _ in COLUMNS)})",
            [row.get(column) for column in COLUMNS],
        )


def read_history(database: Path, since: str) -> dict:
    """Never initialize a file; refuse broken membership rather than partial history."""
    database = database.absolute()
    descriptor = os.open(segments.lock_path(database), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("telemetry segment lock is not a regular file")
        fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
        opened_lock = os.fstat(descriptor)
        entrance_lock = segments.lock_path(database).lstat()
        if (opened_lock.st_dev, opened_lock.st_ino) != (
            entrance_lock.st_dev,
            entrance_lock.st_ino,
        ):
            raise ValueError("telemetry segment lock changed while opening")
        manifest = segments.read_manifest(database)
        if manifest is None:
            entries = [{"id": "unsegmented", "file": database.name}]
        else:
            if manifest.get("state") != "ready":
                raise ValueError("telemetry segment cutover is incomplete")
            entries = [*manifest["sealed"], manifest["current"]]
            if manifest["current"]["file"] != database.name:
                raise ValueError("telemetry current entrance changed")
        rows, absent, names, ids = [], [], set(), set()
        for entry in entries:
            name, segment_id = entry["file"], entry["id"]
            if not isinstance(name, str) or Path(name).name != name or name in names:
                raise ValueError("invalid or duplicate telemetry member")
            if (
                name in {".", ".."}
                or not isinstance(segment_id, str)
                or segment_id in ids
            ):
                raise ValueError("invalid or duplicate telemetry segment identity")
            names.add(name)
            ids.add(segment_id)
            source = database.parent / name
            before = segments.identity(source)
            expected = entry.get("identity")
            if manifest is not None and not isinstance(expected, dict):
                raise ValueError("telemetry member lacks its declared identity")
            if expected is not None:
                matches = (
                    before == expected
                    if name != database.name
                    else (before["inode"] == expected["inode"])
                )
                if not matches:
                    raise ValueError(f"telemetry segment identity changed: {name}")
            with closing(
                sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True, timeout=5)
            ) as connection:
                connection.row_factory = sqlite3.Row
                columns = [
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(filesystem_capacity_sample)"
                    )
                ]
                if not columns:
                    if name == database.name:
                        raise ValueError("active telemetry has no capacity schema")
                    absent.append(segment_id)
                elif columns != ["id", *COLUMNS]:
                    raise ValueError(f"invalid capacity schema in {name}")
                else:
                    selected = connection.execute(
                        "SELECT * FROM filesystem_capacity_sample WHERE observed_at >= ?"
                        " ORDER BY observed_at, id LIMIT 100001",
                        (since,),
                    ).fetchall()
                    if len(selected) > 100000:
                        raise ValueError("capacity history exceeds the bounded reader")
                    rows.extend(
                        {**dict(row), "segment_id": segment_id} for row in selected
                    )
            after = segments.identity(source)
            if after["inode"] != before["inode"] or (
                name != database.name and before != after
            ):
                raise ValueError(f"telemetry member changed while reading: {name}")
        if segments.read_manifest(database) != manifest:
            raise ValueError("telemetry manifest changed while reading")
        return {
            "schema": "sinnix.capacity-history.v1",
            "status": "observed",
            "rows": sorted(rows, key=lambda row: (row["observed_at"], row["id"])),
            "pre_feature_segments": absent,
            "generation": manifest["generation"] if manifest else "unsegmented",
        }
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("invalid telemetry segment manifest") from error
    finally:
        os.close(descriptor)
