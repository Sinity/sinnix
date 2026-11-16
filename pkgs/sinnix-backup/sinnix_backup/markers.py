"""Marker files under the state directory: key=value text written atomically."""

from __future__ import annotations

import grp
import os
import tempfile
from pathlib import Path

# A daily marker is reused for 20 hours, so the boot catch-up after a night's
# calendar run does not repeat finished work, while each night stays due.
DAILY_MARKER_SECONDS = 72000


def read_marker(path: Path) -> dict[str, str] | None:
    """The key=value fields of a marker, or None when it does not exist."""
    try:
        text = Path(path).read_text()
    except FileNotFoundError:
        return None
    return dict(line.split("=", 1) for line in text.splitlines())


def publish_marker(path: Path, text: str, mode: int = 0o644) -> None:
    """Replace `path` with `text`: temporary file, fsync, rename, directory fsync.

    Only this file and its rename are flushed, not unrelated filesystem writes.
    """
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.tmp.", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(text)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def marker_text(fields: dict[str, object]) -> str:
    return "".join(f"{key}={value}\n" for key, value in fields.items())


def make_directory(path: Path, mode: int, group: str | None = None) -> None:
    """`install -d -m <mode> [-g <group>]`: create and set mode; root also sets the group.

    The state directory is root-owned and readable by the operator's group,
    so unprivileged health probes can read published markers.
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, mode)
    if group is not None and os.geteuid() == 0:
        os.chown(path, 0, grp.getgrnam(group).gr_gid)


def daily_marker_fresh(path: Path, policy: str, now: int) -> bool:
    """True when the marker names `policy` and its epoch is under 20 hours old."""
    try:
        fields = read_marker(path)
    except (OSError, ValueError, UnicodeDecodeError):
        return False
    if fields is None:
        return False
    epoch = fields.get("epoch", "")
    if not epoch.isascii() or not epoch.isdigit() or len(epoch) > 10:
        return False
    value = int(epoch)
    return (
        fields.get("policy_sha256") == policy
        and now >= value
        and now - value < DAILY_MARKER_SECONDS
    )
