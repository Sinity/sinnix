"""Read-only sqlite helpers shared by xtask + polylogue source modules.

These read LIVE databases -- sinex's xtask history (2 GB) and polylogue's
index (40 GB) -- so copying is not on the table and `immutable=1` is wrong: it
promises SQLite the file cannot change, which on a live database buys stale or
incoherent reads. `mode=ro` is correct: SQLite falls back to read-only WAL
access when it cannot write the -shm sidecar.

What was NOT fine is below: every failure was swallowed into an empty result,
so a query that could not run rendered as a source with nothing in it. An
empty panel and a broken panel are the same picture, which is sinnix's
most-repeated failure shape. Errors are recorded and surfaced now, and the
callers still get their empty value so one unreadable database cannot take the
whole observation down.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from typing import Any

# Per thread: the hub server collects reports in-process from its refresh
# worker and from page requests at once, and each report publishes only the
# failures of its own collection.
_STATE = threading.local()


def _errors() -> list[dict[str, str]]:
    if not hasattr(_STATE, "errors"):
        _STATE.errors = []
    return _STATE.errors


def sqlite_errors() -> list[dict[str, str]]:
    """Failures recorded since the last clear, for the caller to publish."""
    return list(_errors())


def clear_sqlite_errors() -> None:
    _errors().clear()


def _record(db: Path, operation: str, exc: Exception) -> None:
    _errors().append(
        {
            "db": str(db),
            "operation": operation,
            "error": f"{type(exc).__name__}: {exc}",
        }
    )


def sqlite_columns(db: Path, table: str) -> set[str]:
    try:
        with closing(
            sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
        ) as conn:
            return {row[1] for row in conn.execute(f"pragma table_info({table})")}
    except (sqlite3.Error, OSError) as exc:
        _record(db, f"table_info({table})", exc)
        return set()


def sqlite_rows(
    db: Path, sql: str, params: tuple[Any, ...] = ()
) -> list[dict[str, Any]]:
    try:
        with closing(
            sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
        ) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(sql, params)]
    except (sqlite3.Error, OSError) as exc:
        _record(db, sql.split()[0].lower() if sql.split() else "query", exc)
        return []


def table_exists(db: Path, table: str) -> bool:
    try:
        db.stat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        _record(db, "stat", exc)
        return False
    rows = sqlite_rows(
        db,
        "select count(*) as n from sqlite_master where type='table' and name=?",
        (table,),
    )
    return bool(rows and rows[0].get("n") == 1)
