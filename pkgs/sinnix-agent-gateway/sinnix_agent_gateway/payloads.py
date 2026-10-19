"""Immutable exact-byte payload storage; observations own separate metadata."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterator

from sinnix_lib.atomic import atomic_publish_at


def canonical_chunks(payload: Any, *, default=None) -> Iterator[bytes]:
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), default=default)
    for fragment in encoder.iterencode(payload):
        # The encoder may materialize one string; avoid another complete byte copy.
        for start in range(0, len(fragment), 65_536):
            yield fragment[start : start + 65_536].encode()


def canonical_size(payload: Any, *, default=None) -> int:
    # Validate the whole input, including invalid tails after oversized prefixes.
    return sum(map(len, canonical_chunks(payload, default=default)))


def retain_json(root: Path, payload: Any, *, link: Path | None = None) -> Path:
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with tempfile.TemporaryFile(dir=root) as staged:
            digest = hashlib.sha256()
            for chunk in canonical_chunks(payload):
                staged.write(chunk)
                digest.update(chunk)
            staged.flush()
            staged.seek(0)
            name = digest.hexdigest()
            atomic_publish_at(directory, name, staged, fsync=True, exclusive=True)
        path = root / name
        if link is not None:
            os.link(path, link)
            descriptor = os.open(link.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        return path
    finally:
        os.close(directory)
