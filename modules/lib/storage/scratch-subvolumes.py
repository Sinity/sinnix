"""Boot-only, reflink-only conversion of classified scratch directories."""

import array
import ctypes
import datetime
import fcntl
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path


def run(*args):
    result = subprocess.run(args, text=True, capture_output=True)
    if result.returncode:
        print(result.stderr, file=sys.stderr, flush=True)
        result.check_returncode()
    return result.stdout


def subvolume(path):
    return (
        subprocess.run(
            ["btrfs", "subvolume", "show", str(path)], capture_output=True
        ).returncode
        == 0
    )


def children(path):
    """Find immediate nested subvolumes, without following links or crossing them."""
    result = []
    for root, dirs, _ in os.walk(path, followlinks=False):
        for name in dirs[:]:
            child = Path(root) / name
            if (
                not child.is_symlink()
                and child.stat().st_ino == 256
                and subvolume(child)
            ):
                result.append(child)
                dirs.remove(name)
    return result


def prepare_flags(source, destination):
    """Reflinks require matching No_COW flags, including old files in +C dirs."""
    source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    target_fd = os.open(destination, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        source_flags = array.array("I", [0])
        target_flags = array.array("I", [0])
        fcntl.ioctl(source_fd, 0x80086601, source_flags, True)  # FS_IOC_GETFLAGS
        fcntl.ioctl(target_fd, 0x80086601, target_flags, True)
        target_flags[0] = (target_flags[0] & ~0x800000) | (source_flags[0] & 0x800000)
        fcntl.ioctl(target_fd, 0x40086602, target_flags)  # FS_IOC_SETFLAGS, FS_NOCOW_FL
    finally:
        os.close(source_fd)
        os.close(target_fd)
    if source.is_dir():
        for entry in source.iterdir():
            mode = entry.lstat().st_mode
            target = destination / entry.name
            if stat.S_ISDIR(mode):
                if entry.stat().st_ino == 256 and subvolume(entry):
                    continue
                target.mkdir()
                prepare_flags(entry, target)
            elif stat.S_ISREG(mode):
                target.touch()
                prepare_flags(entry, target)


def snapshot_children(source, destination):
    for child in children(source):
        target = destination / child.relative_to(source)
        # cp -x leaves an empty mountpoint, or omits it altogether.
        if target.exists():
            target.rmdir()
        run("btrfs", "subvolume", "snapshot", str(child), str(target))
        snapshot_children(child, target)
        if (
            run("btrfs", "property", "get", "-ts", str(child), "ro").strip()
            == "ro=true"
        ):
            run("btrfs", "property", "set", "-ts", str(target), "ro", "true")
        shutil.copystat(child.parent, target.parent)
    shutil.copystat(source, destination)


def remove_tree(path):
    is_subvolume = subvolume(path)
    if is_subvolume:
        run("btrfs", "property", "set", "-ts", str(path), "ro", "false")
    for child in children(path):
        remove_tree(child)
    if is_subvolume:
        run("btrfs", "subvolume", "delete", str(path))
    else:
        shutil.rmtree(path)


def exchange(left, right):
    # RENAME_EXCHANGE keeps the public path present, including across a crash.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.renameat2(-100, os.fsencode(left), -100, os.fsencode(right), 2):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def migrate(path):
    if path.is_symlink() or path.resolve() != path:
        raise RuntimeError(f"symlink in target path: {path}")
    if not path.exists():
        print(f"{path}: absent; left to its owner", flush=True)
        return
    if subvolume(path):
        print(f"{path}: already a subvolume", flush=True)
        return
    if not path.is_dir():
        raise RuntimeError(f"not a directory: {path}")
    # Bind mounts pin old inodes even when their mountpoint is elsewhere.
    # All relevant mounts must be ordered after this service.
    mounts = [
        line.split() for line in Path("/proc/self/mountinfo").read_text().splitlines()
    ]

    def unescape(value):
        import re

        return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), value)

    owners = [
        fields
        for fields in mounts
        if path == Path(unescape(fields[4]))
        or Path(unescape(fields[4])) in path.parents
    ]
    owner = max(owners, key=lambda fields: len(fields[4]))
    fs_path = Path(unescape(owner[3])) / path.relative_to(unescape(owner[4]))
    for fields in mounts:
        target, source = Path(unescape(fields[4])), Path(unescape(fields[3]))
        if (
            target == path
            or path in target.parents
            or (
                fields[2] == owner[2]
                and (source == fs_path or fs_path in source.parents)
            )
        ):
            raise RuntimeError(f"active mount uses {path}: {fields[4]}")
    staging = Path(str(path) + ".subvol-new")
    if (
        staging.exists()
        or staging.is_symlink()
        or list(path.parent.glob(path.name + ".pre-subvol-*"))
    ):
        raise RuntimeError(
            f"retained migration artifacts for {path}; reconcile before retry"
        )
    old = Path(
        str(path)
        + datetime.datetime.now(datetime.timezone.utc).strftime(
            ".pre-subvol-%Y%m%dT%H%M%S.%fZ"
        )
    )
    print(f"{path}: preparing reflink subvolume", flush=True)
    run("btrfs", "subvolume", "create", str(staging))
    committed = False
    try:
        prepare_flags(path, staging)
        run(
            "cp",
            "-a",
            "--one-file-system",
            "--reflink=always",
            str(path) + "/.",
            str(staging),
        )
        snapshot_children(path, staging)
        # Flush preparation before the single atomic namespace change.
        run("sync", "-f", str(staging))
        exchange(path, staging)
        committed = True
        staging.rename(old)
        run("sync", "-f", str(path.parent))
    except BaseException:
        # Before exchange the original has never been changed. After exchange
        # the complete replacement is authoritative; retain artifacts on error.
        if not committed:
            remove_tree(staging)
        raise
    print(f"{path}: installed; removing {old}", flush=True)
    remove_tree(old)
    print(f"{path}: complete", flush=True)


def main():
    paths = sys.argv[1:]
    if paths and paths[0] == "--boot-only":
        paths.pop(0)
        state = run(
            "systemctl", "show", "basic.target", "--property=ActiveState", "--value"
        ).strip()
        if state != "inactive":
            print("migration requires early boot, before basic.target", flush=True)
            return 1
    failures = 0
    for value in paths:
        try:
            migrate(Path(value))
        except Exception as error:
            failures += 1
            detail = (
                error.stderr if isinstance(error, subprocess.CalledProcessError) else ""
            )
            print(f"{value}: FAILED: {error} {detail}", file=sys.stderr, flush=True)
    return bool(failures)


if __name__ == "__main__":
    sys.exit(main())
