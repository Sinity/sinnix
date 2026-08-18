"""The phone inbox contract: how prime leaves a message for the app.

Two producers write this directory -- the dispatcher
(``pkgs/sinnix-phone-dispatcher``) and the scorer (``scripts/sinnix-score``,
which posts a receipt back for every trace it scores) -- and the Android app
is the only reader. The schema string, the file naming and the
write-then-rename convention therefore live here once instead of in two
copies kept identical by review; a drifted copy would be invisible on prime
and show up as a message the phone silently ignores.

It cannot live in the dispatcher, its natural home: the dispatcher already
depends on the sinnix-score *binary* (pkg.nix puts it on the console script's
PATH), so an import in the other direction would close a package cycle.

The directory is a caller argument rather than a module constant because both
producers resolve their own state root (and the dispatcher's tests
monkeypatch theirs). Bytes stay plain ``json.dumps`` -- not
``sinnix_lib.atomic_json``'s sorted/compact shape -- because the app parses
these files as already written.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path
from typing import Any

from .ledger import utc_ts

SCHEMA = "sinnix.phone.receipt/1"


def message_name() -> str:
    """A stamped, collision-free file name: sortable by hand, unique by uuid."""
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:8]}.json"


def write_message(directory: Path | str, payload: dict[str, Any]) -> Path:
    """Land *payload* in *directory* as a complete file or not at all.

    The reader (drain or app) polls this directory, so a partially written
    file must never carry the final name -- hence ``.part`` plus a rename,
    which the inbox reader also knows to skip.
    """
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    name = message_name()
    tmp = d / (name + ".part")
    tmp.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    target = d / name
    tmp.rename(target)
    return target


def emit_receipt(
    directory: Path | str,
    kind: str,
    title: str,
    body: str,
    send_token: str | None,
    route: str | None = None,
) -> Path:
    """Answer something the phone asked for: an executed intent, a scored trace."""
    return write_message(
        directory,
        {
            "schema": SCHEMA,
            "kind": kind,
            "title": title,
            "body": body,
            "send_token": send_token,
            "route": route,
            "at": utc_ts(),
        },
    )


def emit_notify(
    directory: Path | str,
    title: str,
    body: str,
    route: str | None = None,
) -> Path:
    """Interrupt the operator through the phone, unprompted by any intent."""
    return write_message(
        directory,
        {
            "schema": SCHEMA,
            "title": title,
            "body": body,
            "route": route,
            "at": utc_ts(),
        },
    )
