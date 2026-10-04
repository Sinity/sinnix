#!/usr/bin/env python3
"""Synchronize append-only hook journals into a stable reflink cache tree."""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

FICLONE = 0x40049409
MAX_SEAL_ATTEMPTS = 5


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW


def _open_directory_path(path: Path) -> int:
    current = os.open("/", _directory_flags())
    try:
        for component in path.absolute().parts[1:]:
            next_fd = os.open(component, _directory_flags(), dir_fd=current)
            os.close(current)
            current = next_fd
        return current
    except BaseException:
        os.close(current)
        raise


def _file_record(info: os.stat_result) -> dict[str, object]:
    return {
        "kind": "file",
        "dev": info.st_dev,
        "ino": info.st_ino,
        "size": info.st_size,
        "mtime_ns": info.st_mtime_ns,
        "ctime_ns": info.st_ctime_ns,
        "mode": stat.S_IMODE(info.st_mode),
    }


def _manifest(root: Path) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    root_fd = _open_directory_path(root)

    def visit(directory_fd: int, prefix: str = "") -> None:
        for name in sorted(os.listdir(directory_fd)):
            info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            relative = f"{prefix}/{name}" if prefix else name
            if stat.S_ISDIR(info.st_mode):
                child_fd = os.open(name, _directory_flags(), dir_fd=directory_fd)
                try:
                    child = os.fstat(child_fd)
                    if (child.st_dev, child.st_ino) != (info.st_dev, info.st_ino):
                        raise OSError(
                            f"hook directory changed during inventory: {relative}"
                        )
                    result[relative] = {
                        "kind": "directory",
                        "dev": info.st_dev,
                        "ino": info.st_ino,
                        "mode": stat.S_IMODE(info.st_mode),
                        "uid": info.st_uid,
                        "gid": info.st_gid,
                        "mtime_ns": info.st_mtime_ns,
                    }
                    visit(child_fd, relative)
                finally:
                    os.close(child_fd)
            elif stat.S_ISREG(info.st_mode):
                result[relative] = _file_record(info)
            elif stat.S_ISLNK(info.st_mode):
                result[relative] = {
                    "kind": "symlink",
                    "target": os.readlink(name, dir_fd=directory_fd),
                    "uid": info.st_uid,
                    "gid": info.st_gid,
                    "mtime_ns": info.st_mtime_ns,
                }
            else:
                raise OSError(f"unsupported hook-tree entry type: {relative}")

    try:
        visit(root_fd)
    finally:
        os.close(root_fd)
    return result


def _remove_node(path: Path) -> None:
    info = path.lstat()
    if stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode):
        shutil.rmtree(path)
    else:
        path.unlink()


def _ensure_parent_directories(root: Path, parent: Path) -> None:
    current = root
    for component in parent.relative_to(root).parts:
        current = current / component
        try:
            info = current.lstat()
        except FileNotFoundError:
            current.mkdir()
            continue
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            _remove_node(current)
            current.mkdir()


def _open_source_file(root: Path, relative: str) -> int:
    directory_fd = _open_directory_path(root)
    try:
        components = Path(relative).parts
        for component in components[:-1]:
            next_fd = os.open(component, _directory_flags(), dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        return os.open(
            components[-1],
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=directory_fd,
        )
    finally:
        os.close(directory_fd)


def _clone_file(
    source: Path,
    relative: str,
    destination: Path,
    expected: dict[str, object],
) -> None:
    source_fd = _open_source_file(source, relative)
    temporary = destination.with_name(f".{destination.name}.seal-tmp")
    temporary.unlink(missing_ok=True)
    try:
        before = os.fstat(source_fd)
        if not stat.S_ISREG(before.st_mode):
            raise OSError(f"source stopped being a regular file: {relative}")
        before_signature = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        if before_signature != tuple(
            expected[key] for key in ("dev", "ino", "size", "mtime_ns", "ctime_ns")
        ):
            raise OSError(f"source changed before reflink: {relative}")
        output_fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
            int(expected["mode"]),
        )
        try:
            fcntl.ioctl(output_fd, FICLONE, source_fd)
            os.fchown(output_fd, before.st_uid, before.st_gid)
            os.fchmod(output_fd, int(expected["mode"]))
            os.utime(output_fd, ns=(before.st_atime_ns, before.st_mtime_ns))
            os.fsync(output_fd)
        finally:
            os.close(output_fd)
        after = os.fstat(source_fd)
        after_signature = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if before_signature != after_signature:
            raise OSError(f"source changed during reflink: {relative}")
        if temporary.stat().st_size != before.st_size:
            raise OSError(f"reflink size mismatch: {relative}")
        os.replace(temporary, destination)
    finally:
        os.close(source_fd)
        temporary.unlink(missing_ok=True)


def _sync_once(
    source: Path, destination: Path, old_manifest: dict[str, dict[str, object]]
) -> dict[str, dict[str, object]]:
    source_manifest = _manifest(source)
    for relative, record in sorted(source_manifest.items()):
        dst = destination / relative
        _ensure_parent_directories(destination, dst.parent)
        if record["kind"] == "directory":
            if dst.is_symlink() or (dst.exists() and not dst.is_dir()):
                _remove_node(dst)
            dst.mkdir(parents=True, exist_ok=True)
        elif record["kind"] == "file":
            unchanged = (
                old_manifest.get(relative) == record
                and dst.is_file()
                and not dst.is_symlink()
                and dst.stat().st_size == record["size"]
                and dst.stat().st_mtime_ns == record["mtime_ns"]
            )
            if not unchanged:
                if dst.exists() and dst.is_dir() and not dst.is_symlink():
                    _remove_node(dst)
                _clone_file(source, relative, dst, record)
                # Reuse verified clones if another file changes during this pass.
                # The durable manifest is still published only after a stable pass.
                old_manifest[relative] = record
        else:
            unchanged = (
                old_manifest.get(relative) == record
                and dst.is_symlink()
                and os.readlink(dst) == record["target"]
            )
            if not unchanged:
                if dst.exists() and dst.is_dir() and not dst.is_symlink():
                    _remove_node(dst)
                temporary = dst.with_name(f".{dst.name}.seal-tmp")
                temporary.unlink(missing_ok=True)
                os.symlink(str(record["target"]), temporary)
                os.chown(
                    temporary,
                    int(record["uid"]),
                    int(record["gid"]),
                    follow_symlinks=False,
                )
                os.utime(
                    temporary,
                    ns=(int(record["mtime_ns"]), int(record["mtime_ns"])),
                    follow_symlinks=False,
                )
                os.replace(temporary, dst)

    if _manifest(source) != source_manifest:
        raise OSError("hook tree changed during seal pass")
    staged_paths = _manifest(destination)
    for relative in sorted(
        staged_paths.keys() - source_manifest.keys(),
        key=lambda value: value.count("/"),
        reverse=True,
    ):
        stale = destination / relative
        if stale.is_dir() and not stale.is_symlink():
            shutil.rmtree(stale)
        else:
            stale.unlink(missing_ok=True)
    for relative, record in sorted(
        source_manifest.items(), key=lambda item: item[0].count("/"), reverse=True
    ):
        if record["kind"] == "directory":
            directory = destination / relative
            os.chown(
                directory, int(record["uid"]), int(record["gid"]), follow_symlinks=False
            )
            os.chmod(directory, int(record["mode"]))
            os.utime(directory, ns=(int(record["mtime_ns"]), int(record["mtime_ns"])))
    return source_manifest


def _write_manifest(path: Path, manifest: dict[str, dict[str, object]]) -> None:
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(manifest, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} SOURCE_HOOKS DESTINATION_HOOKS", file=sys.stderr)
        return 64
    source, destination = map(Path, sys.argv[1:])
    manifest_path = destination.with_name(destination.name + ".manifest.json")
    lock_path = destination.with_name(destination.name + ".lock")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink():
            raise OSError(f"hook cache root must not be a symlink: {destination}")
        with lock_path.open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            destination.mkdir(parents=True, exist_ok=True)
            # The state root is the mount authority. If it is unavailable,
            # fail closed; a missing hooks directory inside an available root
            # means an empty fresh state and must clear this cache.
            parent_fd = _open_directory_path(source.parent)
            try:
                try:
                    source_info = os.stat(
                        source.name, dir_fd=parent_fd, follow_symlinks=False
                    )
                except FileNotFoundError:
                    source_info = None
            finally:
                os.close(parent_fd)
            if source_info is not None and stat.S_ISLNK(source_info.st_mode):
                raise OSError(f"hook source must not be a symlink: {source}")
            if source_info is not None and not stat.S_ISDIR(source_info.st_mode):
                raise OSError(f"hook source is not a directory: {source}")
            source_absent = source_info is None
            try:
                old_manifest = json.loads(manifest_path.read_text())
            except FileNotFoundError:
                old_manifest = {}
            for attempt in range(MAX_SEAL_ATTEMPTS):
                try:
                    if source_absent:
                        manifest = {}
                        for relative in sorted(
                            _manifest(destination),
                            key=lambda value: value.count("/"),
                            reverse=True,
                        ):
                            stale = destination / relative
                            if stale.is_dir() and not stale.is_symlink():
                                shutil.rmtree(stale)
                            else:
                                stale.unlink(missing_ok=True)
                    else:
                        manifest = _sync_once(source, destination, old_manifest)
                    if source_absent:
                        try:
                            source.lstat()
                        except FileNotFoundError:
                            current = {}
                        else:
                            current = _manifest(source)
                    else:
                        current = _manifest(source)
                    if current == manifest:
                        _write_manifest(manifest_path, manifest)
                        print(
                            f"sealed Polylogue hook tree on attempt {attempt + 1}: {source} -> {destination}"
                        )
                        return 0
                except OSError:
                    if attempt + 1 == MAX_SEAL_ATTEMPTS:
                        raise
            raise OSError(f"hook tree kept changing after {MAX_SEAL_ATTEMPTS} attempts")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"could not seal Polylogue hook tree: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
