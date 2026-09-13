"""Immutable exact-byte payload storage; observations own separate metadata."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from sinnix_lib.atomic import atomic_publish


def retain(root: Path, payload: bytes, *, link: Path | None = None) -> Path:
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = root / hashlib.sha256(payload).hexdigest()
    atomic_publish(path, payload, fsync=True, exclusive=True)
    if link is not None:
        os.link(path, link)
        descriptor = os.open(link.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    return path
