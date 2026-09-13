"""Verify one immutable snapshot against one Borg archive; no deletion here.

Canonical coverage excludes only explicitly declared noncanonical roots. Borg
patterns and cache markers control creation, but do not prove missing data safe.
The caller holds the Borg lock and rechecks identity before deleting a snapshot.
"""

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath


def run(*args):
    return subprocess.check_output(args, text=True)


def identity(source):
    output = run("btrfs", "subvolume", "show", str(source))
    uuid = re.search(r"^\s*UUID:\s*([0-9a-f-]{36})\s*$", output, re.M)
    if (
        not uuid
        or run("btrfs", "property", "get", "-ts", str(source), "ro").strip()
        != "ro=true"
    ):
        raise ValueError(f"snapshot is not an identified read-only subvolume: {source}")
    return uuid[1]


def archive_identity(archive, snapshot_uuid):
    archives = json.loads(run("borg", "info", "--json", "::" + archive))["archives"]
    if (
        len(archives) != 1
        or archives[0]["comment"] != "sinnix-snapshot-v1:" + snapshot_uuid
    ):
        raise ValueError(f"archive does not bind this snapshot UUID: {archive}")
    archive_id = archives[0]["id"]
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


def decode_borg_bytes(value):
    # Borg's debug JSON encodes bytes as DEL followed by hexadecimal.
    if not isinstance(value, str):
        raise ValueError("unrecognized Borg byte encoding")
    return (
        bytes.fromhex(value[1:]) if value.startswith("\x7f") else value.encode("utf-8")
    )


def verify(source, archive, noncanonical):
    source = Path(source)
    expected = {}
    ignored = set(noncanonical)
    omitted_roots = []
    nested_stubs = []
    if any(
        p.startswith("/")
        or ".." in PurePosixPath(p).parts
        or any(c in p for c in "*?[")
        for p in ignored
    ):
        raise ValueError("noncanonical roots must be explicit relative paths")

    def walk(path, relative):
        if relative in ignored:
            omitted_roots.append(relative)
            return
        st = path.lstat()
        expected[relative] = st
        if stat.S_ISDIR(st.st_mode):
            # Btrfs snapshotting replaces a nested subvolume with inode 2.
            # Its absent live bytes are outside this snapshot's proof.
            if relative != "." and st.st_ino == 2:
                nested_stubs.append(relative)
            for child in sorted(path.iterdir()):
                walk(child, str(PurePosixPath(relative) / child.name))

    walk(source, ".")
    seen = set()
    for item in command_items(
        ["borg", "debug", "dump-archive", "::" + archive, "/dev/stdout"],
        lambda stream: JsonStream(stream).items(),
    ):
        path = item["path"]
        if path not in expected:
            # Noncanonical material may be over-preserved by Borg.
            if path in ignored or any(path.startswith(p + "/") for p in ignored):
                continue
            raise ValueError(f"unexpected archive path: {path!r}")
        if path in seen:
            raise ValueError(f"duplicate archive path: {path!r}")
        seen.add(path)
        st = expected[path]
        for key, actual in (
            ("mode", st.st_mode),
            ("uid", st.st_uid),
            ("gid", st.st_gid),
            ("mtime", st.st_mtime_ns),
        ):
            if item.get(key) != actual:
                raise ValueError(f"archive {key} mismatch: {path!r}")
        actual_xattrs = {
            os.fsencode(key): os.getxattr(source / path, key, follow_symlinks=False)
            for key in os.listxattr(source / path, follow_symlinks=False)
        }
        archived_xattrs = {
            decode_borg_bytes(k): decode_borg_bytes(v)
            for k, v in item.get("xattrs", {}).items()
        }
        if actual_xattrs != archived_xattrs:
            raise ValueError(f"archive extended metadata mismatch: {path!r}")
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
        elif not stat.S_ISDIR(st.st_mode):
            raise ValueError(f"unsupported canonical file type: {path!r}")
    missing = expected.keys() - seen
    if missing:
        raise ValueError(
            f"canonical content missing from archive: {min(missing)!r} ({len(missing)} entries)"
        )

    hashed = set()
    hardlinks = {}
    digest = hashlib.sha256()
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
        path = item["path"]
        if path not in expected or not stat.S_ISREG(expected[path].st_mode):
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
        "nested_subvolume_stubs": nested_stubs,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    ident = sub.add_parser("identity")
    ident.add_argument("source")
    check = sub.add_parser("verify")
    check.add_argument("source")
    check.add_argument("archive")
    check.add_argument("uuid")
    check.add_argument("policy")
    args = parser.parse_args()
    if args.command == "identity":
        print(identity(args.source))
    else:
        archive_id = archive_identity(args.archive, args.uuid)
        result = verify(
            args.source, args.archive, json.loads(Path(args.policy).read_text())
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
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Snapshot retained: {error}", file=sys.stderr)
        sys.exit(1)
