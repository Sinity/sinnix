"""Recoverable first telemetry cutover; no historical repartition or scan."""

from __future__ import annotations

import argparse
from contextlib import closing
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
from typing import Callable

from sinnix_lib.atomic import atomic_publish

SCHEMA = "sinnix-machine-sqlite-segments-v1"


def _publish(path: Path, value: dict) -> None:
    atomic_publish(
        path, json.dumps(value, sort_keys=True).encode(), fsync=True, mode=0o600
    )
    owner = path.parent.stat()
    if os.geteuid() == 0:
        os.chown(path, owner.st_uid, owner.st_gid)
    with path.open("rb") as stream:
        os.fsync(stream.fileno())
    _sync(path.parent)


def _identity(path: Path) -> dict[str, int]:
    value = path.lstat()
    if not stat.S_ISREG(value.st_mode):
        raise RuntimeError(f"not a regular SQLite member: {path}")
    return dict(
        inode=value.st_ino,
        size=value.st_size,
        mtime_ns=value.st_mtime_ns,
        ctime_ns=value.st_ctime_ns,
    )


def _sync(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def validate_preimage(database: Path, snapshot: Path) -> None:
    """Require the owner's read-only Btrfs package, including committed WAL."""
    result = subprocess.run(
        ["btrfs", "property", "get", "-ts", str(snapshot), "ro"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    if result.stdout.strip() != "ro=true":
        raise RuntimeError("cutover preimage is not a read-only Btrfs snapshot")
    for suffix in ("", "-wal"):
        live = database.with_name(database.name + suffix)
        retained = snapshot / live.name
        if live.exists():
            left, right = _identity(live), _identity(retained)
            # A native subvolume snapshot keeps inode, size and mtime. This is
            # snapshot provenance, not a substitute for structural integrity.
            if any(left[key] != right[key] for key in ("inode", "size", "mtime_ns")):
                raise RuntimeError(
                    "cutover preimage does not match the quiesced source"
                )
        elif retained.exists():
            raise RuntimeError("preimage contains an unexpected WAL member")


def seal(path: Path) -> None:
    subprocess.run(["chattr", "+i", str(path)], check=True, timeout=10)
    # Read the native inode flags rather than treating successful invocation
    # as proof that the immutable boundary is present.
    import array

    flags = array.array("L", [0])
    with path.open("rb") as stream:
        fcntl.ioctl(stream, 0x80086601, flags, True)  # FS_IOC_GETFLAGS
    if not flags[0] & 0x10:  # FS_IMMUTABLE_FL
        raise RuntimeError("legacy telemetry member was not made immutable")


def _holders(inode: int, device: int) -> list[int]:
    holders = []
    for process in Path("/proc").iterdir():
        if not process.name.isdigit() or int(process.name) == os.getpid():
            continue
        try:
            descriptors = list((process / "fd").iterdir())
        except (FileNotFoundError, ProcessLookupError):
            continue
        for descriptor in descriptors:
            try:
                value = descriptor.stat()
            except (FileNotFoundError, ProcessLookupError):
                continue
            if (value.st_dev, value.st_ino) == (device, inode):
                holders.append(int(process.name))
                break
    return holders


def rotate(
    database: Path,
    snapshot: Path,
    *,
    initialize: Callable[[sqlite3.Connection], None],
    preimage_check: Callable[[Path, Path], None] = validate_preimage,
    seal_member: Callable[[Path], None] = seal,
    check_holders: Callable[[int, int], list[int]] = _holders,
    fault: Callable[[str], None] = lambda phase: None,
) -> dict:
    """Finish or resume the first lossless cutover under exclusive ownership.

    The caller stops the systemd collector and retains a native preimage first.
    Every filesystem transition is recognizable by its recorded inode, even
    after termination between rename and journal publication. No existing
    payload is deleted or overwritten. Broader recurring rotation is separate.
    """
    database = database.absolute()
    snapshot = snapshot.absolute()
    control = database.with_name(database.name + ".segments.json")
    journal = database.with_name(database.name + ".rotation.json")
    lock = database.with_name(database.name + ".segments.lock")

    def require_closed() -> None:
        for suffix in ("", "-wal", "-shm"):
            member = database.with_name(database.name + suffix)
            try:
                _identity(member)
                value = member.stat()
            except FileNotFoundError:
                continue
            holders = check_holders(value.st_ino, value.st_dev)
            if holders:
                raise RuntimeError(
                    f"old telemetry descriptors remain open for {member.name}: {holders}"
                )

    descriptor = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "r+b") as held:
        if not stat.S_ISREG(os.fstat(held.fileno()).st_mode):
            raise RuntimeError("source lock must be a regular file")
        owner = database.parent.stat()
        if os.geteuid() == 0:
            os.fchown(held.fileno(), owner.st_uid, owner.st_gid)
        fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if journal.exists():
            state = json.loads(journal.read_text())
            if state.get("schema") != SCHEMA or state.get("database") != str(database):
                raise RuntimeError("unrecognized telemetry recovery journal")
            if state["snapshot"] != str(snapshot):
                raise RuntimeError("recovery requires the original retained preimage")
            if (
                state.get("phase")
                not in {
                    "prepared",
                    "new_ready",
                    "legacy_named",
                    "current_named",
                    "published",
                }
                or state.get("legacy") != database.stem + ".legacy.sqlite"
                or state.get("staging") != database.name + ".next"
                or not isinstance(state.get("original"), dict)
                or type(state["original"].get("inode")) is not int
                or (
                    state["phase"] != "prepared"
                    and type(state.get("new_inode")) is not int
                )
            ):
                raise RuntimeError("invalid telemetry recovery state")
        else:
            if control.exists():
                raise RuntimeError(
                    "first cutover refuses an existing source-set manifest"
                )
            original = _identity(database)
            value = database.stat()
            require_closed()
            preimage_check(database, snapshot)
            preimage_members = {}
            for suffix in ("", "-wal", "-shm"):
                member = database.with_name(database.name + suffix)
                if member.exists():
                    observation: dict[str, int | str] = dict(_identity(member))
                    if suffix == "-wal":
                        with member.open("rb") as stream:
                            observation["header_sha256"] = hashlib.sha256(
                                stream.read(32)
                            ).hexdigest()
                    preimage_members[member.name] = observation
            state = dict(
                schema=SCHEMA,
                database=str(database),
                snapshot=str(snapshot),
                phase="prepared",
                original=original,
                origin=dict(
                    path=str(database.resolve()),
                    device=value.st_dev,
                    inode=value.st_ino,
                ),
                preimage_members=preimage_members,
                legacy=database.stem + ".legacy.sqlite",
                staging=database.name + ".next",
            )
            for name in (state["legacy"], state["staging"]):
                if (database.parent / name).exists():
                    raise RuntimeError("unowned cutover destination already exists")
            _publish(journal, state)
            fault("prepared")

        def record(phase: str) -> None:
            state["phase"] = phase
            _publish(journal, state)
            fault(phase)

        legacy = database.parent / state["legacy"]
        staging = database.parent / state["staging"]
        if state["phase"] == "published":
            ready = json.loads(control.read_text())
            if (
                _identity(legacy) != ready["sealed"][0]["identity"]
                or _identity(database)["inode"] != ready["current"]["identity"]["inode"]
            ):
                raise RuntimeError("published telemetry members changed")
            return ready

        _publish(control, dict(schema=SCHEMA, state="preparing"))
        if state["phase"] == "prepared":
            if _identity(database)["inode"] != state["original"]["inode"]:
                raise RuntimeError("original current member changed before preparation")
            require_closed()
            with closing(
                sqlite3.connect(f"{database.as_uri()}?mode=rw", uri=True, timeout=5)
            ) as old:
                if old.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0]:
                    raise RuntimeError("telemetry checkpoint is busy")
                if old.execute("PRAGMA journal_mode=DELETE").fetchone()[0] != "delete":
                    raise RuntimeError("could not seal the old SQLite journal")
                sequence = old.execute(
                    "SELECT name,seq FROM sqlite_sequence"
                ).fetchall()
                columns = [
                    row[1] for row in old.execute("PRAGMA table_info(source_status)")
                ]
                statuses = old.execute(
                    "SELECT * FROM source_status ORDER BY source"
                ).fetchall()
            wal = database.with_name(database.name + "-wal")
            if wal.exists() and wal.stat().st_size:
                raise RuntimeError("telemetry WAL remained after checkpoint")
            # An interrupted initialization owns this exact staging basename;
            # preserve it for diagnosis and resume it transactionally, never
            # remove it or a sidecar in order to make a retry look clean.
            with closing(sqlite3.connect(staging, timeout=5)) as new:
                initialize(new)
                new.execute("PRAGMA synchronous=FULL")
                new.execute("BEGIN IMMEDIATE")
                new.execute("DELETE FROM sqlite_sequence")
                new.executemany(
                    "INSERT INTO sqlite_sequence(name,seq) VALUES (?,?)", sequence
                )
                new.execute("DELETE FROM source_status")
                if statuses:
                    fields = ",".join(
                        '"' + name.replace('"', '""') + '"' for name in columns
                    )
                    new.executemany(
                        f"INSERT INTO source_status({fields}) VALUES ({','.join('?' for _ in columns)})",
                        statuses,
                    )
                new.commit()
                if new.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0]:
                    raise RuntimeError("new telemetry checkpoint is busy")
                if new.execute("PRAGMA journal_mode=DELETE").fetchone()[0] != "delete":
                    raise RuntimeError("new telemetry staging journal remained active")
            with staging.open("rb") as stream:
                os.fsync(stream.fileno())
            owner = database.stat()
            os.chmod(staging, stat.S_IMODE(owner.st_mode))
            if os.geteuid() == 0:
                os.chown(staging, owner.st_uid, owner.st_gid)
            state["new_inode"] = _identity(staging)["inode"]
            state["sequence"] = {name: value for name, value in sequence}
            state["source_status_sha256"] = hashlib.sha256(
                json.dumps(
                    {"columns": columns, "rows": statuses}, sort_keys=True
                ).encode()
            ).hexdigest()
            _sync(database.parent)
            record("new_ready")

        if not legacy.exists():
            if _identity(database)["inode"] != state["original"]["inode"]:
                raise RuntimeError("cannot locate original telemetry member")
            os.rename(database, legacy)
            _sync(database.parent)
            fault("legacy_rename")
        if _identity(legacy)["inode"] != state["original"]["inode"]:
            raise RuntimeError(
                "legacy destination is not the original telemetry member"
            )
        seal_member(legacy)
        with legacy.open("rb") as stream:
            os.fsync(stream.fileno())
        record("legacy_named")
        if not database.exists():
            if _identity(staging)["inode"] != state["new_inode"]:
                raise RuntimeError("cannot identify the prepared new telemetry member")
            os.rename(staging, database)
            _sync(database.parent)
            fault("current_rename")
        if _identity(database)["inode"] != state["new_inode"]:
            raise RuntimeError(
                "current destination is not the prepared telemetry member"
            )
        record("current_named")
        ready = dict(
            schema=SCHEMA,
            state="ready",
            generation="initial-" + str(state["origin"]["inode"]),
            origin=state["origin"],
            sealed=[
                dict(id="legacy-initial", file=legacy.name, identity=_identity(legacy))
            ],
            current=dict(
                id="active-initial", file=database.name, identity=_identity(database)
            ),
        )
        _publish(control, ready)
        fault("ready_manifest")
        record("published")
        return ready


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--preimage", type=Path)
    parser.add_argument("--check-source", action="store_true")
    args = parser.parse_args()
    from .collector import init_db, writer_guard

    if args.check_source:
        with writer_guard(args.db):
            return 0
    if args.preimage is None:
        parser.error("rotation requires --preimage")
    result = rotate(args.db, args.preimage, initialize=init_db)
    print(json.dumps(result, sort_keys=True))
    return 0


def archive_legacy(
    database: Path, output: Path, *, backup: Callable[[Path, Path], None] | None = None
) -> dict:
    """Publish the immutable legacy member once through the existing helper.

    A receipt records acquisition before the helper starts. Its candidate is
    published by that helper only after compression/frame checks. Recovery can
    therefore finish the small receipt/rename transaction without recompressing
    unchanged history. Existing completed artifacts are observed, not rehashed
    on every daily backup; independent repository/media checks stay separate.
    """
    control = database.with_name(database.name + ".segments.json")
    if not control.exists():
        return {"state": "not_segmented"}
    manifest = json.loads(control.read_text())
    if manifest.get("schema") != SCHEMA or manifest.get("state") != "ready":
        raise RuntimeError("legacy backup requires a ready source set")
    if len(manifest.get("sealed", [])) != 1:
        raise RuntimeError("first legacy backup requires exactly one sealed member")
    entry = manifest["sealed"][0]
    if (
        entry.get("id") != "legacy-initial"
        or entry.get("file") != database.stem + ".legacy.sqlite"
    ):
        raise RuntimeError("unexpected legacy member identity")
    source = database.parent / entry["file"]
    identity = _identity(source)
    if identity != entry.get("identity"):
        raise RuntimeError("legacy source changed before backup")
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    artifact = output / f"legacy-{identity['inode']}.sqlite.zst"
    candidate = artifact.with_name("." + artifact.name + ".candidate")
    receipt = artifact.with_name(artifact.name + ".json")
    lock = artifact.with_name(artifact.name + ".lock")
    descriptor = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "r+b") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if receipt.exists():
            state = json.loads(receipt.read_text())
            if state.get("source_identity") != identity or state.get("source") != str(
                source
            ):
                raise RuntimeError("legacy backup receipt belongs to another source")
        else:
            if artifact.exists() or candidate.exists():
                raise RuntimeError("unowned legacy backup artifact already exists")
            state = dict(
                state="acquiring",
                source=str(source),
                source_identity=identity,
                artifact=str(artifact),
                source_check="header",
                structural_check="pending",
            )
            _publish(receipt, state)

        def observed(path: Path) -> dict:
            value = _identity(path)
            return {key: value[key] for key in ("inode", "size", "mtime_ns")}

        if state.get("state") == "ready":
            if _identity(artifact) != state.get("artifact_identity"):
                raise RuntimeError("completed legacy backup artifact changed")
            return state
        if state.get("state") not in {"acquiring", "prepared"}:
            raise RuntimeError("unrecognized legacy backup publication state")
        if state["state"] == "acquiring":
            if not candidate.exists():
                if backup is None:
                    subprocess.run(
                        [
                            "sinnix-sqlite-backup",
                            "--immutable-source",
                            "--check-mode",
                            "header",
                            str(source),
                            str(candidate),
                        ],
                        check=True,
                    )
                else:
                    backup(source, candidate)
            else:
                # The helper may have renamed its candidate just before an
                # interruption. Recheck that frame before adopting it; there
                # is not yet a durable artifact receipt for this branch.
                subprocess.run(["zstd", "-t", "-q", str(candidate)], check=True)
            if _identity(source) != identity:
                raise RuntimeError("legacy source changed during backup")
            before = observed(candidate)
            digest = hashlib.sha256()
            with candidate.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
                os.fsync(stream.fileno())
            if observed(candidate) != before:
                raise RuntimeError(
                    "legacy backup candidate changed during receipt construction"
                )
            state.update(
                state="prepared",
                artifact_identity=before,
                archive_sha256=digest.hexdigest(),
                frame_check="zstd-t:ok",
            )
            _publish(receipt, state)
        if artifact.exists():
            if observed(artifact) != state["artifact_identity"]:
                raise RuntimeError(
                    "legacy backup destination is not the prepared artifact"
                )
        else:
            if observed(candidate) != state["artifact_identity"]:
                raise RuntimeError(
                    "legacy backup candidate is not the prepared artifact"
                )
            os.rename(candidate, artifact)
            _sync(output)
        owner = output.stat()
        if os.geteuid() == 0:
            os.chown(artifact, owner.st_uid, owner.st_gid)
        with artifact.open("rb") as stream:
            os.fsync(stream.fileno())
        state["artifact_identity"] = _identity(artifact)
        state["state"] = "ready"
        _publish(receipt, state)
        return state


def archive_main() -> int:
    parser = argparse.ArgumentParser(
        description="Archive the sealed telemetry legacy member once"
    )
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            archive_legacy(args.db.absolute(), args.output.absolute()), sort_keys=True
        )
    )
    return 0
