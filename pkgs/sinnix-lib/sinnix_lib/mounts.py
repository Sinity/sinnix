"""Read the caller's mount table without probing external payload trees."""

import re
from collections.abc import Iterable
from pathlib import Path

_OCTAL_ESCAPE = re.compile(r"\\([0-7]{3})")


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
