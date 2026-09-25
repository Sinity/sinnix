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

import argparse
from collections import Counter
from datetime import datetime
from fnmatch import fnmatchcase
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath


SNAPSHOT_NAME = re.compile(r"^[^.]+\.(\d{8}T\d{6}[+-]\d{4})$")


def snapshot_epoch(name):
    match = SNAPSHOT_NAME.fullmatch(name)
    if not match:
        raise ValueError(f"invalid snapshot timestamp: {name}")
    return int(datetime.strptime(match[1], "%Y%m%dT%H%M%S%z").timestamp())


def read_marker_fields(marker):
    try:
        return dict(line.split("=", 1) for line in Path(marker).read_text().splitlines())
    except FileNotFoundError:
        return None


def read_latest_epoch(marker):
    fields = read_marker_fields(marker)
    return snapshot_epoch(fields["snapshot"]) if fields is not None else None


def marker_order(fields):
    if fields is None or ("generation" not in fields and "subvolume_id" not in fields):
        return None
    try:
        order = int(fields["generation"]), int(fields["subvolume_id"])
    except (KeyError, ValueError) as error:
        raise ValueError("invalid verified cutoff creation generation") from error
    if min(order) <= 0:
        raise ValueError("invalid verified cutoff creation generation")
    return order


def snapshot_names(directory, glob):
    if not Path(directory).is_dir():
        raise ValueError(f"snapshot directory unavailable: {directory}")
    return sorted(
        (path.name for path in Path(directory).glob(glob) if path.is_dir() and not path.is_symlink()),
        key=snapshot_epoch,
    )


def choose_snapshot(directory, glob, latest_marker):
    names = snapshot_names(directory, glob)
    if not names:
        return None
    records = [(name, snapshot_details(Path(directory) / name)) for name in names]
    newest, details = max(records, key=lambda row: row[1][1:])
    fields = read_marker_fields(latest_marker)
    cutoff = marker_order(fields)
    if cutoff is None or details[1:] > cutoff:
        return newest
    if details[1] == cutoff[0] and details[0] != json.loads(fields["coverage"])["snapshot_uuid"]:
        raise ValueError("another snapshot shares the verified creation generation")
    return None


def within_fresh_window(now):
    return now.hour in (0, 6, 12, 18) and 5 <= now.minute <= 25


def verified_prune_plan(directory, glob, marker, prefix, replacement_suffix):
    fields = read_marker_fields(marker)
    if fields is None:
        raise ValueError("no verified archive cutoff")
    snapshot = fields["snapshot"]
    archive = fields["archive"]
    proof = json.loads(fields["coverage"])
    if not fnmatchcase(snapshot, glob):
        raise ValueError("verified cutoff names another snapshot volume")
    snapshot_epoch(snapshot)
    cutoff = marker_order(fields)
    # Old markers were written before creation generations were recorded.
    # Archive a fresh generation-bound cutoff before deleting any backlog.
    if cutoff is None:
        return []
    expected_archive = f"{prefix}-{snapshot}"
    if archive not in (expected_archive, expected_archive + replacement_suffix):
        raise ValueError("verified cutoff names another archive")
    uuid = proof["snapshot_uuid"]
    if proof["archive"] != archive or archive_identity(archive, uuid) != proof["archive_id"]:
        raise ValueError("verified cutoff archive identity changed")
    records = [(name, snapshot_details(Path(directory) / name)) for name in snapshot_names(directory, glob)]
    selected = next((details for name, details in records if name == snapshot), None)
    if selected is not None and selected != (uuid, *cutoff):
        raise ValueError("verified cutoff snapshot identity changed")
    return [
        (name, *details)
        for name, details in sorted(records, key=lambda row: row[1][1:])
        if details[1] < cutoff[0]
    ]


def run(*args):
    return subprocess.check_output(args, text=True)


def snapshot_details(source):
    output = run("btrfs", "subvolume", "show", str(source))
    uuid = re.search(r"^\s*UUID:\s*([0-9a-f-]{36})\s*$", output, re.M)
    generation = re.search(r"^\s*Gen at creation:\s*(\d+)\s*$", output, re.M)
    subvolume_id = re.search(r"^\s*Subvolume ID:\s*(\d+)\s*$", output, re.M)
    if (
        not uuid
        or not generation
        or not subvolume_id
        or run("btrfs", "property", "get", "-ts", str(source), "ro").strip()
        != "ro=true"
    ):
        raise ValueError(f"snapshot is not an identified read-only subvolume: {source}")
    return uuid[1], int(generation[1]), int(subvolume_id[1])


def identity(source):
    return snapshot_details(source)[0]


def archive_identity(archive, snapshot_uuid):
    archives = json.loads(
        run("borg", "list", "--json", "--format", "{comment}")
    )["archives"]
    matches = [
        entry for entry in archives
        if entry.get("archive", entry.get("name")) == archive
    ]
    if (
        len(matches) != 1
        or matches[0].get("comment") != "sinnix-snapshot-v1:" + snapshot_uuid
    ):
        raise ValueError(f"archive does not bind this snapshot UUID: {archive}")
    archive_id = matches[0]["id"]
    if not re.fullmatch(r"[0-9a-f]{64}", archive_id):
        raise ValueError("invalid archive ID")
    return archive_id


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


def command_items(command, parser):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, text=True)
    try:
        yield from parser(process.stdout)
        if process.wait() != 0:
            raise ValueError(f"archive read failed: {command[1]}")
    finally:
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
# This proves an ACL is present on both sides, not that its entries are
# identical: Borg stores ACLs as libacl's rendered text, and reproducing that
# rendering from the raw xattr would couple this check to libacl's and Borg's
# formatting. Permission drift that reaches the mode bits (an ACL's mask is
# the group mode) is still caught by the mode comparison above.
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


def archived_acl_markers(item):
    """The ACL markers an archived item implies, spelled as listxattr does."""
    return {name for name, field in ACL_XATTR_FIELDS.items() if item.get(field)}


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


def verify(source, archive, noncanonical, chrome_extension_caches=False):
    source = Path(source)
    expected = {}
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
        expected[relative] = st
        if stat.S_ISDIR(st.st_mode):
            # Btrfs snapshotting replaces a nested subvolume with inode 2.
            # Its absent live bytes are outside this snapshot's proof.
            if relative != "." and st.st_ino == 2:
                nested_stubs.append(relative)
            for child in sorted(path.iterdir()):
                walk(child, str(PurePosixPath(relative) / child.name))

    walk(source, ".")
    nested_stub_paths = frozenset(nested_stubs)
    seen = set()
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
        if path not in expected:
            # Noncanonical material may be over-preserved by Borg.
            if any(
                path == p or path.startswith(p + "/") for p in omitted_roots
            ):
                continue
            raise ValueError(f"unexpected archive path: {path!r}")
        if path in seen:
            raise ValueError(f"duplicate archive path: {path!r}")
        seen.add(path)
        st = expected[path]
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
        if actual_acls != archived_acl_markers(item):
            raise ValueError(f"archive ACL mismatch: {path!r}")
        if stat.S_ISLNK(st.st_mode):
            if item.get("source") != os.readlink(source / path):
                raise ValueError(f"archive symlink mismatch: {path!r}")
        elif stat.S_ISREG(st.st_mode):
            if "source" in item:
                target = item["source"]
                if target not in expected or (st.st_ino, st.st_dev) != (
                    expected[target].st_ino,
                    expected[target].st_dev,
                ):
                    raise ValueError(f"archive hardlink mismatch: {path!r}")
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
    missing = expected.keys() - seen
    if missing:
        groups = Counter("/".join(path.split("/", 2)[:2]) for path in missing)
        largest = sorted(groups.items(), key=lambda group: (-group[1], group[0]))[:8]
        summary = ", ".join(f"{root}={count}" for root, count in largest)
        raise ValueError(
            f"canonical content missing from archive: {min(missing)!r} "
            f"({len(missing)} entries; largest roots: {summary})"
        )

    hashed = set()
    hardlinks = {}
    digest = hashlib.sha256()
    # Only names that Borg cannot spell need the fallback, so the index stays
    # empty on an ordinary tree and an exact match always wins.
    lossy_index = {}
    for candidate in expected:
        rendered = lossy_borg_path(candidate)
        if rendered != candidate:
            lossy_index.setdefault(rendered, []).append(candidate)
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
        if path not in expected:
            candidates = lossy_index.get(path, ())
            if len(candidates) > 1:
                raise ValueError(
                    f"ambiguous archive path: {path!r} matches "
                    + ", ".join(repr(c) for c in sorted(candidates))
                )
            if not candidates:
                continue
            path = candidates[0]
        if not stat.S_ISREG(expected[path].st_mode):
            continue
        if not item["healthy"]:
            raise ValueError(f"damaged archive file: {path!r}")
        if item.get("source"):
            hardlinks[path] = item["source"]
            continue
        with (source / path).open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        if checksum != item["sha256"] or item["size"] != expected[path].st_size:
            raise ValueError(f"archive content mismatch: {path!r}")
        hashed.add(path)
        digest.update(json.dumps([path, checksum], ensure_ascii=True).encode())
    for path, target in hardlinks.items():
        if target not in hashed:
            raise ValueError(f"unverified hardlink data: {path!r}")
        hashed.add(path)
    if hashed != {p for p, st in expected.items() if stat.S_ISREG(st.st_mode)}:
        raise ValueError("incomplete archive data verification")
    return {
        "canonical_entries": len(expected),
        "content_sha256": digest.hexdigest(),
        "noncanonical_roots": omitted_roots,
        "unarchivable_entries": unarchivable,
        "nested_subvolume_stubs": nested_stubs,
    }


def decode_policy(policy):
    if isinstance(policy, list):
        return policy, False
    if isinstance(policy, dict):
        return policy["noncanonical"], policy.get("chrome_extension_caches", False)
    raise ValueError("invalid coverage policy")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    ident = sub.add_parser("identity")
    ident.add_argument("source")
    details = sub.add_parser("details")
    details.add_argument("source")
    check = sub.add_parser("verify")
    check.add_argument("source")
    check.add_argument("archive")
    check.add_argument("uuid")
    check.add_argument("policy")
    select = sub.add_parser("select")
    select.add_argument("directory")
    select.add_argument("glob")
    select.add_argument("latest_marker")
    prune = sub.add_parser("prune-plan")
    prune.add_argument("directory")
    prune.add_argument("glob")
    prune.add_argument("marker")
    prune.add_argument("prefix")
    prune.add_argument("replacement_suffix")
    sub.add_parser("fresh-window")
    freshness = sub.add_parser("freshness")
    freshness.add_argument("latest_marker")
    freshness.add_argument("freshness_budget", type=int)
    newer = sub.add_parser("newer")
    newer.add_argument("latest_marker")
    newer.add_argument("snapshot")
    args = parser.parse_args()
    if args.command == "identity":
        print(identity(args.source))
    elif args.command == "details":
        print("\t".join(map(str, snapshot_details(args.source))))
    elif args.command == "select":
        selected = choose_snapshot(
            args.directory, args.glob, args.latest_marker,
        )
        if selected:
            print(selected)
    elif args.command == "prune-plan":
        for name, uuid, generation, subvolume_id in verified_prune_plan(
            args.directory, args.glob, args.marker, args.prefix, args.replacement_suffix,
        ):
            print(f"{name}\t{uuid}\t{generation}\t{subvolume_id}")
    elif args.command == "fresh-window":
        if not within_fresh_window(datetime.now()):
            return 1
    elif args.command == "freshness":
        epoch = read_latest_epoch(args.latest_marker)
        if epoch is None:
            raise ValueError("no archived snapshot freshness marker")
        age = int(datetime.now().timestamp()) - epoch
        print(f"latest_archived_epoch={epoch} age_seconds={age}")
        if age > args.freshness_budget:
            raise ValueError(f"latest archived snapshot is {age}s old")
    elif args.command == "newer":
        latest = read_latest_epoch(args.latest_marker)
        if latest is not None and snapshot_epoch(args.snapshot) <= latest:
            return 1
    else:
        archive_id = archive_identity(args.archive, args.uuid)
        noncanonical, chrome_extension_caches = decode_policy(
            json.loads(Path(args.policy).read_text())
        )
        result = verify(
            args.source,
            args.archive,
            noncanonical,
            chrome_extension_caches,
        )
        if archive_identity(args.archive, args.uuid) != archive_id:
            raise ValueError("archive changed during verification")
        print(
            json.dumps(
                result
                | {
                    "snapshot_uuid": args.uuid,
                    "archive_id": archive_id,
                    "archive": args.archive,
                }
            )
        )


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Snapshot retained: {error}", file=sys.stderr)
        sys.exit(1)
