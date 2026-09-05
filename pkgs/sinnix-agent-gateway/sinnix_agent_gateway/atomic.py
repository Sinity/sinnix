"""One publish for gateway state files.

Write to a private temporary in the destination's own directory, then
rename over the destination: a reader sees either the whole old file or the
whole new one, never a partial write, and a failed write leaves the old
content untouched. The temporary is removed on every path.

``fsync`` has no default. Each caller states whether its content must
survive a crash, because the answer differs per file and the five hand-
rolled copies this replaces silently disagreed about it. There is no
file-only sync level: fsyncing a file whose new directory entry is not
synced does not guarantee the published name is findable after a crash, so
it buys latency without buying the guarantee.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

MODE = 0o600


def atomic_publish(
    destination: Path,
    payload: bytes,
    *,
    fsync: bool,
    exclusive: bool = False,
) -> bool:
    """Publish *payload* at *destination* as one indivisible step.

    ``exclusive`` publishes by hard link instead of rename, so an existing
    destination is never replaced -- for content nobody may silently
    overwrite, such as a key other state is already derived from. Returns
    whether this call published; False means ``exclusive`` and the
    destination already existed.

    The temporary is created 0600 rather than chmod'd afterwards: a state
    file must never be briefly readable by anyone else, however narrow the
    window.
    """
    directory = destination.parent
    temporary = directory / f".{destination.name}.{uuid.uuid4().hex}.tmp"
    try:
        descriptor = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, MODE
        )
        with os.fdopen(descriptor, "wb") as handle:
            os.fchmod(handle.fileno(), MODE)
            handle.write(payload)
            handle.flush()
            if fsync:
                os.fsync(handle.fileno())
        if exclusive:
            try:
                os.link(temporary, destination)
            except FileExistsError:
                return False
        else:
            os.replace(temporary, destination)
        if fsync:
            directory_descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    finally:
        temporary.unlink(missing_ok=True)
    return True
