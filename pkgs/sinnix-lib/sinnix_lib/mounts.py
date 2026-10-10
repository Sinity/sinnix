"""Read the caller's mount table without probing external payload trees."""

from collections.abc import Iterable
from pathlib import Path
import re


_OCTAL_ESCAPE = re.compile(r"\\([0-7]{3})")


def read_mountpoints() -> frozenset[Path]:
    """Decode payload mount paths; automount placeholders do not prove availability."""
    points = set()
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
        points.add(point)
    if not points:
        raise ValueError("mountinfo contains no mountpoints")
    return frozenset(points)


def has_mounted_ancestor(path: Path, boundary: Path, mountpoints: Iterable[Path]) -> bool:
    """A mount inside the declared boundary must cover this exact path."""
    return any(
        point.is_relative_to(boundary) and path.is_relative_to(point)
        for point in mountpoints
    )
