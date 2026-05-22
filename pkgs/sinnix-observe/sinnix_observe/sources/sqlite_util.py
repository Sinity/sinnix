"""Read-only sqlite helpers shared by xtask + polylogue source modules."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def sqlite_columns(db: Path, table: str) -> set[str]:
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            return {row[1] for row in conn.execute(f"pragma table_info({table})")}
    except sqlite3.Error:
        return set()


def sqlite_rows(
    db: Path, sql: str, params: tuple[Any, ...] = ()
) -> list[dict[str, Any]]:
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(sql, params)]
    except sqlite3.Error:
        return []


def table_exists(db: Path, table: str) -> bool:
    if not db.exists():
        return False
    rows = sqlite_rows(
        db,
        "select count(*) as n from sqlite_master where type='table' and name=?",
        (table,),
    )
    return bool(rows and rows[0].get("n") == 1)
