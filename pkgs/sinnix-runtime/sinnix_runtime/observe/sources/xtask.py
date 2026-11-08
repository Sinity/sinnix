"""Sinex check and test history, read from devkit's run history store."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .sqlite_util import sqlite_columns, sqlite_errors, sqlite_rows, table_exists


def sinex_history_db() -> Path | None:
    override = os.environ.get("SINNIX_OBSERVE_SINEX_DB")
    if override:
        return Path(override)
    state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return state / "devkit/history.db"


def collect_sinex_xtask(limit: int) -> dict[str, Any]:
    """Recent Sinex xtask runs. Devkit records no per-run resource samples."""
    db = sinex_history_db()
    source: dict[str, Any] = {
        "db": str(db) if db else None,
        "available": False,
        "rows": [],
    }
    if not db or not db.exists() or not table_exists(db, "runs"):
        source["gaps"] = ["sinex.xtask_history.unavailable"]
        return source
    if not {"id", "project", "command", "started_ms", "status"}.issubset(
        sqlite_columns(db, "runs")
    ):
        source["gaps"] = ["sinex.xtask_history.invalid_schema"]
        return source
    prior_errors = len(sqlite_errors())
    rows = sqlite_rows(
        db,
        """
        select id, command, args, checkout as cwd, pid, agentctl_job, status, failure,
               strftime('%Y-%m-%dT%H:%M:%SZ', started_ms / 1000, 'unixepoch') as started_at,
               case when duration_ms is null then null else
                 strftime('%Y-%m-%dT%H:%M:%SZ', (started_ms + duration_ms) / 1000, 'unixepoch')
               end as finished_at,
               duration_ms / 1000.0 as duration_secs
        from runs
        where project = 'sinex'
        order by started_ms desc
        limit ?
        """,
        (limit,),
    )
    if len(sqlite_errors()) != prior_errors:
        source["gaps"] = ["sinex.xtask_history.query_failed"]
        return source
    source["available"] = True
    source["rows"] = rows
    return source


def infer_sinex_resource_class(row: dict[str, Any]) -> str | None:
    if str(row.get("command") or "") in {
        "check",
        "compile",
        "test",
        "warm",
        "coverage",
    }:
        return "developer-build"
    return None
