"""Digest-guarded capture index repair, preserving every original line."""

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
from tempfile import TemporaryDirectory

from sinnix_lib.layout import capture_lane_path
from sinnix_lib.lock import flock

from .query import _valid_timestamp


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode))


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _digest_regular(path):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("index evidence is not a regular file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        os.fsync(fd)
        return digest
    finally:
        os.close(fd)


def _verified_entry(directory, lane, evidence):
    """Project a reviewed original record, never metadata supplied on trust."""
    if (not isinstance(evidence, dict) or type(evidence.get("seq")) is not int
            or evidence["seq"] < 1 or not _valid_timestamp(evidence.get("ts"))):
        raise ValueError("invalid restoration metadata")
    filename = evidence.get("file")
    offset = evidence.get("offset")
    if (not isinstance(filename, str) or Path(filename).name != filename
            or not Path(filename).match(f"{lane}-[0-9]*.jsonl")
            or type(offset) is not int or offset < 0):
        raise ValueError("invalid restoration source location")
    path = directory / filename
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("restoration source is not a regular file")
        if offset and os.pread(fd, 1, offset - 1) != b"\n":
            raise ValueError("restoration offset is not a record boundary")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            stream.seek(offset)
            line = stream.readline()
        if (not line.endswith(b"\n")
                or hashlib.sha256(line).hexdigest() != evidence.get("sha256")):
            raise ValueError("restoration source record changed")
        row = json.loads(line)
        if (not isinstance(row, dict) or type(row.get("seq")) is not int
                or row["seq"] < 1 or not _valid_timestamp(row.get("ts"))
                or (row["seq"], row["ts"]) != (evidence.get("seq"), evidence.get("ts"))):
            raise ValueError("restoration source metadata differs from review")
        current = path.lstat()
        if (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError("restoration source entrance changed")
        return {"seq": row["seq"], "ts": row["ts"], "file": filename}
    finally:
        os.close(fd)


def repair_index(capture_root, lane, *, expected_sha256, expected_size, restore_entries=()):
    """Repair reviewed metadata under the producer lock; never renumber/drop.

    This maintenance operation holds the lane's writer lock through publication.
    Callers must admit its work from the explicitly reviewed index size. Scratch
    memory stays bounded with a disk-backed sorter. It does not certify that the
    index covers every payload, or repair ambiguous duplicate sequence IDs.
    Restorations require exact record boundaries and full source-record hashes.
    """
    if (not isinstance(expected_sha256, str) or len(expected_sha256) != 64
            or any(c not in "0123456789abcdef" for c in expected_sha256)):
        raise ValueError("expected SHA-256 must be a full lowercase digest")
    if type(expected_size) is not int or expected_size < 0:
        raise ValueError("expected index size must be a nonnegative integer")
    directory = capture_lane_path(capture_root, lane)
    index = directory / f"{lane}-index.jsonl"
    # Refuse absent inputs before flock could create a new lane/lock entrance.
    if not stat.S_ISREG(index.lstat().st_mode):
        raise ValueError("index repair requires a regular physical index")
    with flock(directory / f"{lane}.seq.lock"):
        observed = index.lstat()
        if not stat.S_ISREG(observed.st_mode) or observed.st_size != expected_size:
            raise ValueError("index changed since review")
        if observed.st_uid != os.geteuid():
            raise ValueError("index repair must run as its owner")
        with TemporaryDirectory(prefix=".index-order-", dir=directory) as scratch:
            with closing(sqlite3.connect(Path(scratch) / "sort.sqlite")) as db:
                db.execute("PRAGMA cache_size = -1024")
                db.execute("PRAGMA synchronous = OFF")
                # Length + decimal digits order arbitrary positive integers
                # exactly, without SQLite's signed-int64 conversion limit.
                db.execute("CREATE TABLE rows (digits INTEGER, seq TEXT, line BLOB, PRIMARY KEY(digits,seq)) WITHOUT ROWID")
                digest = hashlib.sha256()
                previous = 0
                ordered = True
                count = 0
                fd = os.open(index, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
                try:
                    if _identity(os.fstat(fd)) != _identity(observed):
                        raise ValueError("index changed since review")
                    with os.fdopen(fd, "rb", closefd=False) as stream:
                        for line in stream:
                            if not line.endswith(b"\n"):
                                raise ValueError("index has an incomplete final record")
                            row = json.loads(line)
                            if (not isinstance(row, dict) or type(row.get("seq")) is not int
                                    or row["seq"] < 1 or not _valid_timestamp(row.get("ts"))):
                                raise ValueError("index has malformed timestamp/sequence fields")
                            seq = row["seq"]
                            ordered = ordered and seq > previous
                            previous = seq
                            key = str(seq)
                            try:
                                db.execute("INSERT INTO rows VALUES (?, ?, ?)", (len(key), key, line))
                            except sqlite3.IntegrityError as exc:
                                raise ValueError("duplicate sequence requires payload reconciliation") from exc
                            digest.update(line)
                            count += 1
                    if _identity(os.fstat(fd)) != _identity(observed):
                        raise ValueError("index changed during review")
                finally:
                    os.close(fd)
                if digest.hexdigest() != expected_sha256 or _identity(index.lstat()) != _identity(observed):
                    raise ValueError("index changed since review")
                restored = 0
                for evidence in restore_entries:
                    row = _verified_entry(directory, lane, evidence)
                    seq = row["seq"]
                    key = str(seq)
                    line = (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode()
                    try:
                        db.execute("INSERT INTO rows VALUES (?, ?, ?)", (len(key), key, line))
                    except sqlite3.IntegrityError as exc:
                        raise ValueError("restored sequence is already indexed; reconciliation required") from exc
                    restored += 1
                if ordered and not restored:
                    return {"changed": False, "records": count, "sha256": expected_sha256}
                pending = Path(scratch) / "index.jsonl"
                new_digest = hashlib.sha256()
                with pending.open("xb") as stream:
                    for (line,) in db.execute("SELECT line FROM rows ORDER BY digits, seq"):
                        stream.write(line)
                        new_digest.update(line)
                    current = os.fstat(stream.fileno())
                    if (current.st_uid, current.st_gid) != (observed.st_uid, observed.st_gid):
                        os.fchown(stream.fileno(), observed.st_uid, observed.st_gid)
                    os.fchmod(stream.fileno(), stat.S_IMODE(observed.st_mode))
                    stream.flush()
                    os.fsync(stream.fileno())
                backups = directory / ".index-repairs"
                backups.mkdir(mode=0o700, exist_ok=True)
                if not stat.S_ISDIR(backups.lstat().st_mode):
                    raise ValueError("index preimage entrance must be a physical directory")
                backup = backups / f"{expected_sha256}.jsonl"
                try:
                    os.link(index, backup, follow_symlinks=False)
                except FileExistsError:
                    pass
                if _digest_regular(backup) != expected_sha256:
                    raise ValueError("retained index preimage verification failed")
                _sync_directory(backups)
                _sync_directory(directory)
                if _identity(index.lstat()) != _identity(observed):
                    raise ValueError("index changed before publication")
                os.replace(pending, index)
                _sync_directory(directory)
                if _digest_regular(index) != new_digest.hexdigest():
                    raise ValueError("published index verification failed; preimage retained")
                return {"changed": True, "records": count + restored, "restored_records": restored, "sha256": new_digest.hexdigest(),
                        "previous_sha256": expected_sha256, "backup": str(backup)}
