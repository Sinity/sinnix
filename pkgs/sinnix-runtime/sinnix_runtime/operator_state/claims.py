"""Advisory path claims: which agent session is working where, and on what.

A claim says "this session is editing under this path, for this purpose,
until then". Nothing is locked: a second session claiming an overlapping path
is told about the first and proceeds, and both appear as an overlap in
``sinnix state``. A claim lapses at its expiry without anyone releasing it.

The store is one JSON document, rewritten whole under a lock:

    {"schema": "sinnix-path-claims-v1",
     "claims": [{"id": "c-1a2b3c4d", "path": "/abs/path", "purpose": "...",
                 "harness": "claude", "session": "<session id>",
                 "claimed_at": "<UTC time>", "expires_at": "<UTC time>"}]}
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from sinnix_lib.atomic_json import modify_json, read_json

SCHEMA = "sinnix-path-claims-v1"
STORE = Path("/realm/state/hub/path-claims.json")
DEFAULT_DURATION = "4h"
MAX_DURATION_SECONDS = 7 * 86400
# The harness variables that name the calling agent session, as agentctl
# records them on a job.
SESSION_VARIABLES = (("claude", "CLAUDE_CODE_SESSION_ID"), ("codex", "CODEX_THREAD_ID"))
_DURATION = re.compile(r"(\d+(?:\.\d+)?)\s*([smhd])")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_duration(text: str) -> float:
    """Seconds in ``90m``, ``4h``, ``2d`` or ``1h30m``."""
    parts = _DURATION.findall(text.strip().lower())
    if not parts or "".join(f"{n}{u}" for n, u in parts) != re.sub(
        r"\s+", "", text.lower()
    ):
        raise ValueError(f"not a duration (use for example 90m, 4h, 2d): {text!r}")
    return sum(float(number) * _UNIT_SECONDS[unit] for number, unit in parts)


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def caller(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """The calling agent session, or the person at the terminal."""
    environ = os.environ if environ is None else environ
    for harness, variable in SESSION_VARIABLES:
        if session := environ.get(variable, "").strip():
            return {"harness": harness, "session": session[:128]}
    return {"harness": "person", "session": environ.get("USER") or str(os.getuid())}


def _live(document: Any, now: datetime) -> list[dict[str, Any]]:
    rows = document.get("claims") if isinstance(document, dict) else None
    live = []
    for row in rows if isinstance(rows, list) else []:
        try:
            if datetime.fromisoformat(row["expires_at"]) > now and row["path"]:
                live.append(row)
        except (KeyError, TypeError, ValueError):
            continue
    return live


def overlapping(first: str, second: str) -> bool:
    """One path is the other or lies inside it."""
    a, b = Path(first), Path(second)
    return a == b or a in b.parents or b in a.parents


def active(store: Path = STORE, now: datetime | None = None) -> list[dict[str, Any]]:
    """The claims that have not expired, oldest first."""
    now = now or datetime.now(timezone.utc)
    return sorted(_live(read_json(store, {}), now), key=lambda row: row["claimed_at"])


def overlaps(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each pair of claims by different sessions on overlapping paths."""
    pairs = []
    for index, first in enumerate(claims):
        for second in claims[index + 1 :]:
            if first["session"] != second["session"] and overlapping(
                first["path"], second["path"]
            ):
                pairs.append({"first": first, "second": second})
    return pairs


def claim(
    path: str | Path,
    purpose: str,
    *,
    who: Mapping[str, str],
    duration_seconds: float,
    store: Path = STORE,
    now: datetime | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Record a claim; return it with the other sessions' overlapping claims.

    A session's earlier claim on the same path is replaced.
    """
    now = now or datetime.now(timezone.utc)
    if not purpose.strip():
        raise ValueError("a claim says what it is for")
    if not 0 < duration_seconds <= MAX_DURATION_SECONDS:
        raise ValueError("a claim lasts between one second and seven days")
    row = {
        "id": "c-" + secrets.token_hex(4),
        "path": os.path.realpath(path),
        "purpose": " ".join(purpose.split())[:240],
        "harness": who["harness"],
        "session": who["session"],
        "claimed_at": iso(now),
        "expires_at": iso(now + timedelta(seconds=duration_seconds)),
    }
    with modify_json(store, {}, mode=0o600) as document:
        kept = [
            other
            for other in _live(document, now)
            if not (other["session"] == row["session"] and other["path"] == row["path"])
        ]
        document.clear()
        document.update({"schema": SCHEMA, "claims": [*kept, row]})
    others = [
        other
        for other in kept
        if other["session"] != row["session"]
        and overlapping(other["path"], row["path"])
    ]
    return row, others


def release(
    *,
    who: Mapping[str, str],
    path: str | Path | None = None,
    store: Path = STORE,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Drop this session's claim on ``path``, or all of its claims."""
    now = now or datetime.now(timezone.utc)
    target = os.path.realpath(path) if path is not None else None
    released: list[dict[str, Any]] = []
    with modify_json(store, {}, mode=0o600) as document:
        kept = []
        for row in _live(document, now):
            if row["session"] == who["session"] and target in (None, row["path"]):
                released.append(row)
            else:
                kept.append(row)
        document.clear()
        document.update({"schema": SCHEMA, "claims": kept})
    return released


def holder(row: Mapping[str, Any]) -> str:
    if row.get("harness") == "person":
        return str(row.get("session"))
    return f"{row.get('harness')} session {str(row.get('session'))[:8]}"


def claim_line(row: Mapping[str, Any]) -> str:
    return (
        f'{row["path"]}: {holder(row)}, for "{row["purpose"]}", '
        f"until {row['expires_at']}"
    )


def overlap_line(pair: Mapping[str, Any]) -> str:
    first, second = pair["first"], pair["second"]
    return (
        f'{first["path"]} ({holder(first)}, "{first["purpose"]}") overlaps '
        f'{second["path"]} ({holder(second)}, "{second["purpose"]}")'
    )


def _who(arguments: argparse.Namespace) -> dict[str, str]:
    who = caller()
    if arguments.session:
        who = {"harness": who["harness"], "session": arguments.session}
    return who


def main(argv: list[str] | None = None) -> int:
    """``sinnix claim``, ``sinnix claims`` and ``sinnix release``."""
    parser = argparse.ArgumentParser(
        prog="sinnix",
        description="Advisory path claims between agent sessions. Nothing is blocked.",
    )
    parser.add_argument("--store", type=Path, default=STORE, help=argparse.SUPPRESS)
    verbs = parser.add_subparsers(dest="verb", required=True)
    add = verbs.add_parser("claim", help="say this session works under a path")
    add.add_argument("path")
    add.add_argument("--for", dest="purpose", required=True, help="what the work is")
    add.add_argument(
        "--until",
        default=DEFAULT_DURATION,
        metavar="DURATION",
        help=f"how long the claim lasts, for example 90m or 2d (default {DEFAULT_DURATION})",
    )
    listing = verbs.add_parser("claims", help="every claim that has not expired")
    drop = verbs.add_parser("release", help="drop this session's claims")
    drop.add_argument("path", nargs="?", help="only the claim on this path")
    for verb in (add, listing, drop):
        verb.add_argument("--json", action="store_true")
    for verb in (add, drop):
        verb.add_argument(
            "--session", help="act as this session instead of the calling one"
        )
    arguments = parser.parse_args(argv)
    try:
        if arguments.verb == "claim":
            row, others = claim(
                arguments.path,
                arguments.purpose,
                who=_who(arguments),
                duration_seconds=parse_duration(arguments.until),
                store=arguments.store,
            )
            if arguments.json:
                print(json.dumps({"claim": row, "overlaps": others}, sort_keys=True))
            else:
                print(f"claimed {claim_line(row)}")
                for other in others:
                    print(f"overlaps {claim_line(other)}")
            return 0
        if arguments.verb == "release":
            released = release(
                who=_who(arguments), path=arguments.path, store=arguments.store
            )
            if arguments.json:
                print(json.dumps({"released": released}, sort_keys=True))
            else:
                for row in released:
                    print(f"released {row['path']}")
                if not released:
                    print("no claim of this session to release")
            return 0
    except ValueError as error:
        print(f"sinnix {arguments.verb}: {error}", file=sys.stderr)
        return 2
    rows = active(arguments.store)
    pairs = overlaps(rows)
    if arguments.json:
        print(json.dumps({"claims": rows, "overlaps": pairs}, sort_keys=True))
        return 0
    for row in rows:
        print(claim_line(row))
    for pair in pairs:
        print(f"overlap: {overlap_line(pair)}")
    if not rows:
        print("no claims")
    return 0
