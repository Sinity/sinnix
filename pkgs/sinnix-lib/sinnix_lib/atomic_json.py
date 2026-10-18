"""Atomic JSON state files.

Replaces the hand-rolled ``jq > tmp && mv`` / ``json.load → mutate →
json.dump`` sequences that seventeen scripts each carried their own copy
of. The JSON shape is sorted keys and compact separators; the publish
itself is ``atomic.atomic_publish``. ``modify_json`` serializes concurrent
writers with an flock on a sidecar lock file, so read-modify-write is safe
across processes.
"""

from __future__ import annotations

import errno
import json
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .atomic import atomic_publish
from .lock import flock


def read_json(path: Path | str, default: Any = None) -> Any:
    """Parsed content of *path*, or *default* when absent or unparseable.

    Unparseable-as-default is deliberate: state files are regenerable caches
    of their own history, and a torn write from a crashed producer should
    heal on the next cycle rather than wedge every future run.
    Other filesystem errors propagate: an unavailable file is not an empty
    cache, and a modifier must not replace state it could not read.
    """
    p = Path(path)
    fd: int | None = None
    try:
        # Inspect the opened object. Nonblocking open prevents a FIFO from
        # hanging before its type can be rejected; regular-file reads are
        # unaffected. Following a symlink to a regular state file is valid.
        fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK)
        kind = os.fstat(fd).st_mode
        if stat.S_ISDIR(kind):
            raise IsADirectoryError(errno.EISDIR, "JSON state is a directory", p)
        if not stat.S_ISREG(kind):
            raise OSError(errno.EINVAL, "JSON state must be a regular file", p)
        stream = os.fdopen(fd, encoding="utf-8")
        fd = None
        with stream:
            return json.load(stream)
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return default
    finally:
        if fd is not None:
            os.close(fd)


def write_json_atomic(
    path: Path | str,
    data: Any,
    *,
    mode: int = 0o644,
    fsync: bool = False,
) -> None:
    """Publish *data* as one compact JSON document, creating parents.

    ``fsync=True`` syncs the file and the directory it is published into, so
    the published name resolves after a crash and not merely the bytes behind
    it.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n"
    atomic_publish(p, body.encode("utf-8"), fsync=fsync, mode=mode)


@contextmanager
def modify_json(
    path: Path | str,
    default: Any = None,
    *,
    mode: int = 0o644,
) -> Iterator[Any]:
    """Locked read-modify-write: yields the parsed document (or *default*),
    writes it back atomically on clean exit. The value yielded is written;
    mutate it in place. An exception inside the block writes nothing.

    Durability: atomic only. Missing or malformed cache content can heal from
    ``default``; filesystem failures propagate without entering the block or
    publishing. A caller requiring crash durability publishes it itself.
    """
    p = Path(path)
    with flock(p.with_name(p.name + ".lock")):
        doc = read_json(p, default)
        yield doc
        write_json_atomic(p, doc, mode=mode)
