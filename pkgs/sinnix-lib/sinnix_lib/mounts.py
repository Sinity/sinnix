"""Read the caller's mount table without probing external payload trees."""

import os
import re
import stat
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path

_OCTAL_ESCAPE = re.compile(r"\\([0-7]{3})")


@contextmanager
def pinned_mount(path: Path, mount_id: int):
    """Pin an already observed payload; refuse a replacement before probing."""
    descriptor = os.open(path, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        ids = [
            int(line.partition(":")[2].strip())
            for line in Path(f"/proc/self/fdinfo/{descriptor}").read_text().splitlines()
            if line.startswith("mnt_id:")
        ]
        if ids != [mount_id]:
            raise ValueError("payload mount changed during observation")
        yield descriptor
    finally:
        os.close(descriptor)


def observe_capacity(path: Path) -> dict:
    """Exact counters and observed UUID provenance, without activating autofs."""
    mounted = read_payload_mounts()
    if path not in mounted:
        return {"path": str(path), "status": "not_mounted"}
    with pinned_mount(path, mounted[path]) as descriptor:
        records = [
            line.split()
            for line in Path("/proc/self/mountinfo").read_text().splitlines()
        ]
        rows = [
            fields for fields in records if fields and fields[0] == str(mounted[path])
        ]
        if len(rows) != 1:
            raise ValueError("payload mount changed during observation")
        fields = rows[0]
        if len(fields) < 10 or "-" not in fields[6:]:
            raise ValueError("malformed mountinfo record")
        separator = fields.index("-", 6)
        if len(fields) < separator + 4:
            raise ValueError("malformed mountinfo record")

        def decode(value):
            return _OCTAL_ESCAPE.sub(lambda match: chr(int(match[1], 8)), value)

        source = Path(decode(fields[separator + 2]))
        uuids = []
        try:
            device = source.stat()
            if stat.S_ISBLK(device.st_mode):
                for candidate in Path("/dev/disk/by-uuid").iterdir():
                    try:
                        if candidate.stat().st_rdev == device.st_rdev:
                            uuids.append(candidate.name)
                    except FileNotFoundError:
                        continue
                if source.stat().st_rdev != device.st_rdev:
                    raise ValueError("mount source changed during observation")
        except (FileNotFoundError, PermissionError):
            pass
        info = os.fstatvfs(descriptor)
        return {
            "path": str(path),
            "status": "observed",
            "mount_id": mounted[path],
            "device": os.fstat(descriptor).st_dev,
            "mount_root": decode(fields[3]),
            "filesystem_type": fields[separator + 1],
            "source": str(source),
            "filesystem_uuid": uuids[0] if len(uuids) == 1 else None,
            "f_blocks": info.f_blocks,
            "f_bfree": info.f_bfree,
            "f_bavail": info.f_bavail,
            "f_frsize": info.f_frsize,
        }


def read_payload_mounts() -> dict[Path, int]:
    """Decode payload mount paths; automount placeholders do not prove availability."""
    points = {}
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        fields = line.split()
        if len(fields) < 10 or "-" not in fields[6:]:
            raise ValueError("malformed mountinfo record")
        separator = fields.index("-", 6)
        if len(fields) < separator + 4:
            raise ValueError("malformed mountinfo record")
        if fields[separator + 1] == "autofs":
            continue
        point = Path(_OCTAL_ESCAPE.sub(lambda match: chr(int(match[1], 8)), fields[4]))
        if not point.is_absolute():
            raise ValueError("mountinfo mountpoint must be absolute")
        try:
            mount_id = int(fields[0])
        except ValueError as error:
            raise ValueError("mountinfo mount identity must be an integer") from error
        if mount_id <= 0:
            raise ValueError("mountinfo mount identity must be positive")
        points[point] = mount_id
    if not points:
        raise ValueError("mountinfo contains no mountpoints")
    return points


def read_mountpoints() -> frozenset[Path]:
    """Payload mount paths, without probing the payload or an automount."""
    return frozenset(read_payload_mounts())


def has_mounted_ancestor(
    path: Path, boundary: Path, mountpoints: Iterable[Path]
) -> bool:
    """A mount inside the declared boundary must cover this exact path."""
    return any(
        point.is_relative_to(boundary) and path.is_relative_to(point)
        for point in mountpoints
    )
