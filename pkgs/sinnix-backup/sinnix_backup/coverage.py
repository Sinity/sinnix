"""Verify one immutable snapshot against one Borg archive; no deletion here.

Canonical coverage excludes only explicitly declared noncanonical roots. Borg
patterns and cache markers control creation, but do not prove missing data safe.
The caller holds the Borg lock and rechecks identity before deleting a snapshot.

Behaviours of Borg this file depends on, each established by running borg 1.4.5
rather than read from its docs, and each the cause of a lane that retained every
snapshot until it was handled (2026-09-14):

- A POSIX ACL is stored in an item's acl_access/acl_default, never in xattrs.
- A unix socket is skipped entirely; a FIFO is archived as a mode and nothing
  else; a device node adds rdev. Sockets therefore cannot be covered, the other
  two can.
- "debug dump-archive" encodes a non-UTF-8 path as DEL plus hex. "list
  --json-lines" cannot, because JSON is Unicode, and substitutes one "?" per
  undecodable byte; its bpath key is not emitted.
- An inode-2 stub stands in for a nested subvolume and its mtime tracks the live
  subvolume, so it never matches what was archived.

The rule that is deliberately NOT taken from Borg is exclusion. --exclude-caches
and --exclude-if-present decide what creation writes; they never decide what
coverage may waive, or a tag file dropped anywhere would authorize deleting the
only copy of whatever sits beside it. Only the declared noncanonical roots do
that (see modules/backup.nix).
"""

import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import struct
import subprocess
import tempfile
import threading
from contextvars import ContextVar
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

METADATA_CONTRACT = "posix-acl-numeric-entries-v1"


def policy_identity(policy, require_borg_excludes=False):
    """Bind a proof to the declaration and the metadata verification contract."""
    decode_policy(policy)
    if require_borg_excludes and (
        not isinstance(policy, dict) or "borg_excludes" not in policy
    ):
        raise ValueError("created proof requires declared Borg exclusions")
    return hashlib.sha256(
        json.dumps(
            {"policy": policy, "metadata_contract": METADATA_CONTRACT},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


class JsonStream:
    """Bound memory to one metadata item while consuming Borg's JSON dump."""

    def __init__(self, stream):
        self.stream, self.buffer, self.eof = stream, "", False

    def fill(self):
        data = self.stream.read(65536)
        self.buffer += data
        self.eof = not data

    def token(self, expected):
        while not self.buffer.strip() and not self.eof:
            self.fill()
        self.buffer = self.buffer.lstrip()
        if not self.buffer.startswith(expected):
            raise ValueError(f"invalid archive metadata: expected {expected!r}")
        self.buffer = self.buffer[len(expected) :]

    def peek(self):
        while not self.buffer.strip() and not self.eof:
            self.fill()
        return self.buffer.lstrip()[:1]

    def value(self):
        while True:
            self.buffer = self.buffer.lstrip()
            try:
                value, end = json.JSONDecoder().raw_decode(self.buffer)
                self.buffer = self.buffer[end:]
                return value
            except json.JSONDecodeError:
                if self.eof:
                    raise
                self.fill()

    def items(self):
        self.token("{")
        found = False
        while self.peek() != "}":
            key = self.value()
            self.token(":")
            if key == "_items":
                if found:
                    raise ValueError("duplicate archive item list")
                found = True
                self.token("[")
                while self.peek() != "]":
                    yield self.value()
                    if self.peek() != "]":
                        self.token(",")
                self.token("]")
            else:
                self.value()
            if self.peek() != "}":
                self.token(",")
        self.token("}")
        if not found or self.peek():
            raise ValueError("incomplete archive metadata")


ROUTINE_BORG_CHILD_SECONDS = 300


_COMMAND_TIMEOUT = ContextVar("borg_coverage_child_timeout", default=None)


def command_items(command, parser):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, text=True)
    expired = threading.Event()

    def expire():
        expired.set()
        process.kill()

    budget = _COMMAND_TIMEOUT.get()
    timer = threading.Timer(budget, expire) if budget is not None else None
    if timer is not None:
        timer.start()

    def finish():
        status = process.wait()
        if timer is not None:
            timer.cancel()
        if expired.is_set():
            raise ValueError(f"archive child exceeded {budget}s budget: {command[1]}")
        if status != 0:
            raise ValueError(f"archive read failed: {command[1]}")

    try:
        if tuple(command[1:3]) == ("debug", "dump-archive") or tuple(command[1:2]) == (
            "list",
        ):
            # Filesystem metadata validation can be much slower than reading
            # archive headers. Drain and reap Borg first so parser backpressure
            # cannot hold its repository lock for longer than needed. The private spool
            # is unlinked and bounded in memory, not an archive or a receipt.
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as spool:
                shutil.copyfileobj(process.stdout, spool, length=65536)
                finish()
                spool.seek(0)
                yield from parser(spool)
        else:
            yield from parser(process.stdout)
            finish()
    finally:
        if timer is not None:
            timer.cancel()
        process.stdout.close()
        if process.poll() is None:
            process.terminate()
        process.wait()


# Borg does not round-trip POSIX ACLs through xattrs. It reads
# system.posix_acl_access / system.posix_acl_default into an item's own
# acl_access / acl_default fields and emits no "xattrs" entry for them
# (verified against borg 1.4.5: an ACL'd directory dumps
# "acl_access": "user::rwx\nuser:sinity:rwx:1000\n..." and no xattrs key).
# Comparing raw listxattr output against the archived xattrs therefore
# mismatches forever on any path carrying an extended ACL, which is what
# stalled the /persist drain once ~/.config/chrome-ws acquired one. Compare
# ACLs through the fields Borg actually writes, and leave every other xattr
# an exact comparison.
#
# Compare numeric principals and permissions, not display names or rendering
# order. Borg appends the stored numeric UID/GID to each named entry.
ACL_XATTR_FIELDS = {
    b"system.posix_acl_access": "acl_access",
    b"system.posix_acl_default": "acl_default",
}


# Borg cannot archive a unix socket at all: archiver.py dispatches on file
# type and answers a socket with "# Ignore unix sockets; return" (verified
# against borg 1.4.5 -- a socket never appears in a created archive, while a
# FIFO in the same directory does). A socket carries no bytes, so requiring one
# to be covered waives no content; it only makes the lane unprovable for as
# long as any socket exists under the source. This is a property of the file
# type, not a marker a tool can drop into a directory, so unlike an inherited
# CACHEDIR.TAG it cannot be used to authorize deleting real content.
def is_unarchivable_type(mode):
    """File types Borg silently skips rather than archiving."""
    return stat.S_ISSOCK(mode)


# A nested subvolume is replaced by an inode-2 stub when its parent is
# snapshotted. The stub's mtime tracks the live subvolume rather than this
# snapshot's frozen state -- sampled three seconds apart it advances with the
# wall clock -- so it can never equal what Borg archived, and comparing it
# fails every verification forever. The stub's contents are already outside
# this snapshot's proof (see walk() below), so its mtime carries no coverage
# meaning either. Ownership and mode stay compared: those are stable.
METADATA_KEYS = ("mode", "uid", "gid", "mtime")


def metadata_keys_for(path, nested_stubs):
    """The metadata fields that must match the archive for one path."""
    if path in nested_stubs:
        return tuple(key for key in METADATA_KEYS if key != "mtime")
    return METADATA_KEYS


def partition_acl_xattrs(names):
    """Split raw listxattr names into ACL markers and ordinary xattr names."""
    markers = set()
    ordinary = []
    for name in names:
        encoded = os.fsencode(name)
        if encoded in ACL_XATTR_FIELDS:
            markers.add(encoded)
        else:
            ordinary.append(name)
    return markers, ordinary


def validate_acl_entries(entries):
    if not all((tag, None) in entries for tag in (1, 4, 32)):
        raise ValueError("ACL missing owner, group or other entry")
    if any(tag in (2, 8) for tag, _ in entries) and (16, None) not in entries:
        raise ValueError("ACL missing mask for named principals")
    return entries


def source_acl_entries(raw):
    """Linux POSIX ACL xattr v2: little-endian header and tag/perm/id entries."""
    if len(raw) < 4 or (len(raw) - 4) % 8 or struct.unpack_from("<I", raw)[0] != 2:
        raise ValueError("invalid POSIX ACL xattr")
    entries = {}
    for tag, perm, identity in struct.iter_unpack("<HHI", raw[4:]):
        if tag not in (1, 2, 4, 8, 16, 32) or perm > 7:
            raise ValueError("invalid POSIX ACL entry")
        named = tag in (2, 8)
        if named == (identity == 0xFFFFFFFF):
            raise ValueError("invalid POSIX ACL principal")
        key = (tag, identity if named else None)
        if key in entries:
            raise ValueError("duplicate POSIX ACL principal")
        entries[key] = perm
    return validate_acl_entries(entries)


def archived_acl_entries(text):
    if text is None or text == "" or text == b"":
        return {}
    if isinstance(text, str):
        text = decode_borg_bytes(text)
    if isinstance(text, bytes):
        text = text.decode("utf-8", "surrogateescape")
    if not isinstance(text, str):
        raise ValueError("invalid archived ACL text")
    tags = {"user": (1, 2), "group": (4, 8), "mask": (16, 16), "other": (32, 32)}
    entries = {}
    for line in text.split("\n"):
        if not line:
            continue
        fields = line.split(":")
        if len(fields) not in (3, 4) or fields[0] not in tags:
            raise ValueError("invalid archived ACL entry")
        kind, qualifier, permissions = fields[:3]
        # Borg removes getfacl's effective-permission comment but retains
        # its tab before the appended numeric principal ("rwx\t:1001").
        permissions = permissions.strip()
        if not re.fullmatch(r"[r-][w-][x-]", permissions):
            raise ValueError("invalid archived ACL permissions")
        named = bool(qualifier)
        if named:
            numeric = fields[3] if len(fields) == 4 else qualifier
            if kind not in ("user", "group") or not re.fullmatch(r"[0-9]+", numeric):
                raise ValueError("archived ACL has no numeric principal")
            identity = int(numeric)
            if identity >= 0xFFFFFFFF:
                raise ValueError("invalid archived ACL principal")
        else:
            if len(fields) != 3:
                raise ValueError("invalid archived ACL object entry")
            identity = None
        key = (tags[kind][int(named)], identity)
        if key in entries:
            raise ValueError("duplicate archived ACL principal")
        entries[key] = sum(
            bit for char, bit in zip(permissions, (4, 2, 1), strict=True) if char != "-"
        )
    return validate_acl_entries(entries)


def verify_acl_metadata(path, mode, names, item):
    for name, field in ACL_XATTR_FIELDS.items():
        archived = archived_acl_entries(item.get(field))
        if name in names:
            actual = source_acl_entries(os.getxattr(path, name, follow_symlinks=False))
        elif field == "acl_access" and archived:
            # A default-only directory causes Borg to emit its ordinary
            # access ACL too, although Linux stores that ACL in mode bits.
            actual = {
                (1, None): (mode >> 6) & 7,
                (4, None): (mode >> 3) & 7,
                (32, None): mode & 7,
            }
        else:
            actual = {}
        if actual != archived:
            raise ValueError(f"archive ACL mismatch: {path!r} ({field})")


def archive_path(item):
    """The archived path as os.fsdecode spells it.

    Borg's debug JSON cannot hold a non-UTF-8 name as text, so it encodes such
    a path as DEL followed by hex -- a Facebook export carrying a Latin-1 byte
    arrives as "\x7f6163...". Comparing that raw against a walk's
    fsdecode'd keys never matches, and the realm lane reported it as
    "unexpected archive path". Decoding to the same surrogate-escaped form the
    walk produces makes the two comparable; an ordinary ASCII path round-trips
    unchanged.
    """
    return os.fsdecode(decode_borg_bytes(item["path"]))


def lossy_borg_path(path):
    """Borg's own lossy rendering of a path, one "?" per undecodable byte.

    "borg list --json-lines" cannot carry a verbatim path: JSON strings must be
    valid Unicode, so Borg substitutes each surrogate with "?" and the listing
    alone cannot name a file whose bytes are not UTF-8. Reproducing the same
    substitution lets such a listing be matched back to the walk, and any
    ambiguity it creates is refused rather than guessed (see verify).
    """
    return "".join(
        "?" if "\ud800" <= character <= "\udfff" else character for character in path
    )


def decode_borg_bytes(value):
    # Borg's debug JSON encodes bytes as DEL followed by hexadecimal.
    if not isinstance(value, str):
        raise ValueError("unrecognized Borg byte encoding")
    return (
        bytes.fromhex(value[1:]) if value.startswith("\x7f") else value.encode("utf-8")
    )


CHROME_EXTENSION_CACHE = re.compile(
    r"home/sinity/\.config/chrome-ws/Default/Storage/ext/([a-p]{32})/def/"
    r"(DawnGraphiteCache|DawnWebGPUCache|GPUCache|Shared Dictionary/cache)\Z"
)


class CoverageInventory:
    """Disposable disk index. Neither an archive nor a reusable coverage proof."""

    def __init__(self, filename):
        self.db = sqlite3.connect(filename)
        # Losing this scratch index fails verification; it cannot publish a
        # receipt. Avoid a second copy in the journal and bound SQLite's cache.
        self.db.executescript("""
            PRAGMA journal_mode=OFF;
            PRAGMA synchronous=OFF;
            PRAGMA cache_size=-8192;
            PRAGMA mmap_size=0;
            PRAGMA temp_store=FILE;
            CREATE TABLE entries (
                path BLOB PRIMARY KEY, metadata TEXT NOT NULL,
                root BLOB NOT NULL, regular INTEGER NOT NULL, size INTEGER NOT NULL,
                seen INTEGER NOT NULL DEFAULT 0,
                hashed INTEGER NOT NULL DEFAULT 0,
                lossy BLOB, hardlink BLOB, hardlink_order INTEGER
            ) WITHOUT ROWID;
            CREATE INDEX lossy_paths ON entries(lossy) WHERE lossy IS NOT NULL;
        """)
        self.writes = 0
        self.hardlink_order = 0

    def execute(self, sql, args=()):
        cursor = self.db.execute(sql, args)
        self.writes += 1
        if self.writes % 4096 == 0:
            self.db.commit()
        return cursor

    def add(self, path, st):
        fields = ("mode", "uid", "gid", "mtime_ns", "size", "ino", "dev", "rdev")
        # JSON preserves unsigned inode/device values and nanoseconds exactly.
        metadata = json.dumps({"st_" + k: getattr(st, "st_" + k) for k in fields})
        lossy = lossy_borg_path(path)
        self.execute(
            "INSERT INTO entries(path, metadata, root, regular, size, lossy) VALUES(?,?,?,?,?,?)",
            (
                os.fsencode(path),
                metadata,
                os.fsencode("/".join(path.split("/", 2)[:2])),
                int(stat.S_ISREG(st.st_mode)),
                st.st_size,
                os.fsencode(lossy) if lossy != path else None,
            ),
        )

    def get(self, path):
        row = self.db.execute(
            "SELECT metadata FROM entries WHERE path=?", (os.fsencode(path),)
        ).fetchone()
        return SimpleNamespace(**json.loads(row[0])) if row else None

    def mark_seen(self, path):
        changed = self.execute(
            "UPDATE entries SET seen=1 WHERE path=? AND seen=0", (os.fsencode(path),)
        ).rowcount
        if not changed:
            raise ValueError(f"duplicate archive path: {path!r}")

    def require_metadata(self):
        count = self.db.execute("SELECT count(*) FROM entries WHERE seen=0").fetchone()[
            0
        ]
        if not count:
            return
        first = min(
            os.fsdecode(row[0])
            for row in self.db.execute("SELECT path FROM entries WHERE seen=0")
        )
        largest = self.db.execute(
            "SELECT root,count(*) AS n FROM entries WHERE seen=0 "
            "GROUP BY root ORDER BY n DESC,root LIMIT 8"
        )
        summary = ", ".join(f"{os.fsdecode(root)}={n}" for root, n in largest)
        raise ValueError(
            f"canonical content missing from archive: {first!r} "
            f"({count} entries; largest roots: {summary})"
        )

    def resolve_lossy(self, path):
        cursor = self.db.execute(
            "SELECT path FROM entries WHERE lossy=?", (os.fsencode(path),)
        )
        candidates = [os.fsdecode(row[0]) for row in cursor.fetchmany(2)]
        if len(candidates) > 1:
            # The complete diagnostic is only allocated on a failing proof.
            candidates.extend(os.fsdecode(row[0]) for row in cursor)
            raise ValueError(
                f"ambiguous archive path: {path!r} matches "
                + ", ".join(repr(c) for c in sorted(candidates))
            )
        return candidates[0] if candidates else None

    def mark_hashed(self, path):
        self.execute("UPDATE entries SET hashed=1 WHERE path=?", (os.fsencode(path),))

    def defer_hardlink(self, path, target):
        # Preserve first appearance order, including duplicate list records.
        self.execute(
            "UPDATE entries SET hardlink=?,hardlink_order=coalesce(hardlink_order,?) "
            "WHERE path=?",
            (os.fsencode(target), self.hardlink_order, os.fsencode(path)),
        )
        self.hardlink_order += 1

    def require_data(self):
        for path, target in self.db.execute(
            "SELECT path,hardlink FROM entries WHERE hardlink IS NOT NULL "
            "ORDER BY hardlink_order"
        ):
            row = self.db.execute(
                "SELECT hashed FROM entries WHERE path=?", (target,)
            ).fetchone()
            if not row or not row[0]:
                raise ValueError(f"unverified hardlink data: {os.fsdecode(path)!r}")
            self.mark_hashed(os.fsdecode(path))
        if self.db.execute(
            "SELECT 1 FROM entries WHERE regular=1 AND hashed=0 LIMIT 1"
        ).fetchone():
            raise ValueError("incomplete archive data verification")

    def count(self):
        return self.db.execute("SELECT count(*) FROM entries").fetchone()[0]


def verify(source, archive, noncanonical, chrome_extension_caches=False, **options):
    token = _COMMAND_TIMEOUT.set(
        ROUTINE_BORG_CHILD_SECONDS
        if options.get("content_mode") in {"metadata", "sampled"}
        else None
    )
    try:
        return _verify_with_inventory(
            source, archive, noncanonical, chrome_extension_caches, **options
        )
    finally:
        _COMMAND_TIMEOUT.reset(token)


def _verify_with_inventory(
    source, archive, noncanonical, chrome_extension_caches, **options
):
    with tempfile.TemporaryDirectory(prefix="borg-coverage-") as scratch:
        inventory = CoverageInventory(Path(scratch) / "inventory.sqlite")
        try:
            return verify_inventory(
                source,
                archive,
                noncanonical,
                chrome_extension_caches,
                inventory,
                **options,
            )
        finally:
            inventory.db.close()


def verify_inventory(
    source,
    archive,
    noncanonical,
    chrome_extension_caches,
    expected,
    *,
    content_mode="full",
    sample_bytes=1073741824,
    sample_files=128,
    sample_after=None,
):
    if content_mode not in {"full", "metadata", "sampled"}:
        raise ValueError("unknown content verification mode")
    if sample_bytes <= 0 or not 1 <= sample_files <= 128:
        raise ValueError("sample needs positive byte budget and 1-128 files")
    source = Path(source)
    ignored = set(noncanonical)
    omitted_roots = []
    unarchivable = []
    nested_stubs = []
    if any(
        p.startswith("/")
        or ".." in PurePosixPath(p).parts
        or any(c in p for c in "*?[")
        for p in ignored
    ):
        raise ValueError("noncanonical roots must be explicit relative paths")

    def is_noncanonical_root(path, relative):
        return relative in ignored or (
            chrome_extension_caches
            and CHROME_EXTENSION_CACHE.fullmatch(relative)
            and stat.S_ISDIR(path.lstat().st_mode)
        )

    def walk(path, relative):
        if is_noncanonical_root(path, relative):
            omitted_roots.append(relative)
            return
        st = path.lstat()
        if is_unarchivable_type(st.st_mode):
            unarchivable.append(relative)
            return
        expected.add(relative, st)
        if stat.S_ISDIR(st.st_mode):
            # Btrfs snapshotting replaces a nested subvolume with inode 2.
            # Its absent live bytes are outside this snapshot's proof.
            if relative != "." and st.st_ino == 2:
                nested_stubs.append(relative)
            for child in sorted(path.iterdir()):
                walk(child, str(PurePosixPath(relative) / child.name))

    walk(source, ".")
    nested_stub_paths = frozenset(nested_stubs)
    for item in command_items(
        ["borg", "debug", "dump-archive", "::" + archive, "/dev/stdout"],
        lambda stream: JsonStream(stream).items(),
    ):
        # Borg's archive stream includes checkpoint parts, marked by the
        # structural `part` key. Its ordinary item iterator filters them;
        # debug dump-archive does not. A part is neither a source path nor
        # proof of the complete file, which must appear separately below.
        if "part" in item:
            continue
        path = archive_path(item)
        st = expected.get(path)
        if st is None:
            # Noncanonical material may be over-preserved by Borg.
            if any(path == p or path.startswith(p + "/") for p in omitted_roots):
                continue
            raise ValueError(f"unexpected archive path: {path!r}")
        expected.mark_seen(path)
        actual_metadata = {
            "mode": st.st_mode,
            "uid": st.st_uid,
            "gid": st.st_gid,
            "mtime": st.st_mtime_ns,
        }
        for key in metadata_keys_for(path, nested_stub_paths):
            if item.get(key) != actual_metadata[key]:
                raise ValueError(f"archive {key} mismatch: {path!r}")
        actual_acls, ordinary_names = partition_acl_xattrs(
            os.listxattr(source / path, follow_symlinks=False)
        )
        actual_xattrs = {
            os.fsencode(key): os.getxattr(source / path, key, follow_symlinks=False)
            for key in ordinary_names
        }
        archived_xattrs = {
            decode_borg_bytes(k): decode_borg_bytes(v)
            for k, v in item.get("xattrs", {}).items()
        }
        if actual_xattrs != archived_xattrs:
            raise ValueError(f"archive extended metadata mismatch: {path!r}")
        verify_acl_metadata(source / path, st.st_mode, actual_acls, item)
        if stat.S_ISLNK(st.st_mode):
            if item.get("source") != os.readlink(source / path):
                raise ValueError(f"archive symlink mismatch: {path!r}")
        elif stat.S_ISREG(st.st_mode):
            if "source" in item:
                target = item["source"]
                target_st = expected.get(target)
                if target_st is None or (st.st_ino, st.st_dev) != (
                    target_st.st_ino,
                    target_st.st_dev,
                ):
                    raise ValueError(f"archive hardlink mismatch: {path!r}")
                expected.defer_hardlink(path, target)
            elif item.get("size") != st.st_size:
                raise ValueError(f"archive size mismatch: {path!r}")
        elif stat.S_ISFIFO(st.st_mode):
            # Borg archives a FIFO as metadata alone -- verified against 1.4.5,
            # its item carries a mode and nothing else, no size and no chunks.
            # The mode/uid/gid/mtime comparison above is therefore the whole
            # proof, and rejecting the type instead made the realm lane
            # unprovable over one netdata timer FIFO.
            pass
        elif stat.S_ISCHR(st.st_mode) or stat.S_ISBLK(st.st_mode):
            # A device node's rdev is its entire content, and Borg records it.
            if item.get("rdev") != st.st_rdev:
                raise ValueError(f"archive device mismatch: {path!r}")
        elif not stat.S_ISDIR(st.st_mode):
            raise ValueError(f"unsupported canonical file type: {path!r}")
    expected.require_metadata()
    metadata_result = {
        "canonical_entries": expected.count(),
        "noncanonical_roots": omitted_roots,
        "unarchivable_entries": unarchivable,
        "nested_subvolume_stubs": nested_stubs,
    }
    if content_mode == "metadata":
        return metadata_result | {
            "content_verification": "not_performed",
            "source_hashed_bytes": 0,
            "archive_content_verified_bytes": 0,
        }
    if content_mode == "sampled":
        return metadata_result | verify_content_sample(
            source,
            archive,
            expected,
            byte_budget=sample_bytes,
            file_budget=sample_files,
            after=sample_after,
        )

    digest = hashlib.sha256()
    hashed_bytes = 0
    for item in command_items(
        [
            "borg",
            "list",
            "--json-lines",
            "--format",
            "{path}{sha256}{health}{size}",
            "::" + archive,
        ],
        lambda stream: (json.loads(line) for line in stream),
    ):
        path = archive_path(item)
        st = expected.get(path)
        if st is None:
            path = expected.resolve_lossy(path)
            if path is None:
                continue
            st = expected.get(path)
        if not stat.S_ISREG(st.st_mode):
            continue
        if not item["healthy"]:
            raise ValueError(f"damaged archive file: {path!r}")
        if item.get("source"):
            expected.defer_hardlink(path, item["source"])
            continue
        with (source / path).open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        if checksum != item["sha256"] or item["size"] != st.st_size:
            raise ValueError(f"archive content mismatch: {path!r}")
        expected.mark_hashed(path)
        hashed_bytes += st.st_size
        digest.update(json.dumps([path, checksum], ensure_ascii=True).encode())
    expected.require_data()
    return {
        "canonical_entries": expected.count(),
        "content_sha256": digest.hexdigest(),
        "source_hashed_bytes": hashed_bytes,
        "archive_content_verified_bytes": hashed_bytes,
        "noncanonical_roots": omitted_roots,
        "unarchivable_entries": unarchivable,
        "nested_subvolume_stubs": nested_stubs,
    }


def verify_content_sample(
    source, archive, inventory, *, byte_budget, file_budget, after=None
):
    """Compare a bounded subset; neither this digest nor its cursor is full proof."""
    selected = {}
    selected_bytes = 0
    argument_bytes = 0
    examined = 0
    skipped = 0
    skipped_reasons = {"unaddressable_name": 0, "empty": 0, "over_byte_budget": 0}
    cursor = None
    # Metadata eligibility excludes populations which a cursor can never hash.
    # Otherwise a run of oversized names, or a cursor at EOF, can wedge every
    # later retry once zero-content receipts correctly stop refreshing success.
    query = (
        "SELECT path FROM entries WHERE regular=1 AND hardlink IS NULL "
        "AND size>0 AND size<=? AND lossy IS NULL AND path>? ORDER BY path LIMIT ?"
    )

    def candidates(boundary):
        return inventory.db.execute(
            query,
            (byte_budget, os.fsencode(boundary) if boundary else b"", file_budget * 4),
        ).fetchall()

    rows = candidates(after)
    wrapped = bool(after and not rows)
    if wrapped:
        rows = candidates(None)
    excluded_count, excluded_bytes, unaddressable, empty = inventory.db.execute(
        "SELECT COALESCE(SUM(size>?),0), COALESCE(SUM(CASE WHEN size>? THEN size ELSE 0 END),0), "
        "COALESCE(SUM(lossy IS NOT NULL),0), COALESCE(SUM(size=0),0) FROM entries WHERE regular=1",
        (byte_budget, byte_budget),
    ).fetchone()
    for (raw_path,) in rows:
        examined += 1
        path = os.fsdecode(raw_path)
        previous_cursor = cursor
        cursor = path
        st = inventory.get(path)
        try:
            encoded = path.encode("utf-8")
        except UnicodeEncodeError:
            skipped += 1
            skipped_reasons["unaddressable_name"] += 1
            continue
        if st.st_size <= 0 or st.st_size > byte_budget:
            skipped += 1
            skipped_reasons["empty" if st.st_size <= 0 else "over_byte_budget"] += 1
            continue
        if (
            st.st_size > byte_budget - selected_bytes
            or argument_bytes + len(encoded) > 65536
        ):
            cursor = previous_cursor
            examined -= 1
            break
        selected[path] = st
        selected_bytes += st.st_size
        argument_bytes += len(encoded)
        if len(selected) == file_budget:
            break
    patterns = [part for path in selected for part in ("--pattern", "+ pf:" + path)]
    digest = hashlib.sha256()
    hashed_bytes = 0
    verified = set()
    objects = []
    if selected:
        for item in command_items(
            [
                "borg",
                "list",
                "--json-lines",
                "--format",
                "{path}{sha256}{health}{size}",
                *patterns,
                "--pattern",
                "- re:.*",
                "::" + archive,
            ],
            lambda stream: (json.loads(line) for line in stream),
        ):
            path = archive_path(item)
            if path not in selected or path in verified or item.get("source"):
                raise ValueError("unexpected or duplicate sampled archive member")
            st = selected[path]
            if not item.get("healthy") or item.get("size") != st.st_size:
                raise ValueError(f"damaged sampled archive member: {path!r}")
            with (source / path).open("rb") as stream:
                checksum = hashlib.file_digest(stream, "sha256").hexdigest()
            if checksum != item.get("sha256"):
                raise ValueError(f"sampled archive content mismatch: {path!r}")
            verified.add(path)
            objects.append({"path": path, "sha256": checksum, "size": st.st_size})
            hashed_bytes += st.st_size
            digest.update(json.dumps([path, checksum], ensure_ascii=True).encode())
        if verified != selected.keys():
            raise ValueError("incomplete sampled content verification")
    return {
        "content_verification": "bounded_sample" if verified else "not_performed",
        "content_coverage": "partial",
        "sample_content_sha256": digest.hexdigest(),
        "sampled_files": len(verified),
        "sample_examined_files": examined,
        "sample_skipped_files": skipped,
        "sample_skipped_by_reason": skipped_reasons,
        "sample_scope": "selected_acknowledged_snapshot",
        "sample_cursor_wrapped": wrapped,
        "sample_excluded_population": {
            "over_byte_budget_files": excluded_count,
            "over_byte_budget_bytes": excluded_bytes,
            "unaddressable_files": unaddressable,
            "empty_files": empty,
        },
        "sample_excludes": [
            "files_larger_than_byte_budget",
            "unaddressable_names",
            "other_retained_archives",
        ],
        "sample_start_after": after,
        "sample_next_after": cursor if examined else None,
        "sample_objects": objects,
        "sample_byte_budget": byte_budget,
        "sample_file_budget": file_budget,
        "source_hashed_bytes": hashed_bytes,
        "archive_content_verified_bytes": hashed_bytes,
    }


def decode_policy(policy):
    if isinstance(policy, list):
        return policy, False
    if isinstance(policy, dict):
        excludes = policy.get("borg_excludes", [])
        if not isinstance(excludes, list) or any(
            not isinstance(pattern, str) for pattern in excludes
        ):
            raise ValueError("invalid Borg exclusion policy")
        return policy["noncanonical"], policy.get("chrome_extension_caches", False)
    raise ValueError("invalid coverage policy")
