"""Atomic JSON state files.

Replaces the hand-rolled ``jq > tmp && mv`` / ``json.load → mutate →
json.dump`` sequences that seventeen scripts each carried their own copy
of. The write is crash-safe (tmp in the same directory, ``os.replace``),
and ``modify_json`` serializes concurrent writers with an flock on a
sidecar lock file, so read-modify-write is safe across processes.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .lock import flock


def read_json(path: Path | str, default: Any = None) -> Any:
    """Parsed content of *path*, or *default* when absent or unparseable.

    Unparseable-as-default is deliberate: state files are regenerable caches
    of their own history, and a torn write from a crashed producer should
    heal on the next cycle rather than wedge every future run.
    """
    p = Path(path)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json_atomic(path: Path | str, data: Any, *, mode: int = 0o644) -> None:
    """Write *data* as JSON to *path* via tmp-in-same-dir + os.replace."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=p.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, sort_keys=True, separators=(",", ":"))
            fh.write("\n")
        os.chmod(tmp, mode)
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


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
    """
    p = Path(path)
    with flock(p.with_name(p.name + ".lock")):
        doc = read_json(p, default)
        yield doc
        write_json_atomic(p, doc, mode=mode)
