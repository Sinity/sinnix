"""Atomic JSON state files.

Replaces the hand-rolled ``jq > tmp && mv`` / ``json.load → mutate →
json.dump`` sequences that seventeen scripts each carried their own copy
of. The JSON shape is sorted keys and compact separators; the publish
itself is ``atomic.atomic_publish``. ``modify_json`` serializes concurrent
writers with an flock on a sidecar lock file, so read-modify-write is safe
across processes.
"""

from __future__ import annotations

import json
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
    """
    p = Path(path)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


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

    Durability: atomic only. A document this helper heals from ``default``
    when it is unreadable is one whose loss to a crash is survivable; a
    caller that needs otherwise publishes it itself.
    """
    p = Path(path)
    with flock(p.with_name(p.name + ".lock")):
        doc = read_json(p, default)
        yield doc
        write_json_atomic(p, doc, mode=mode)
