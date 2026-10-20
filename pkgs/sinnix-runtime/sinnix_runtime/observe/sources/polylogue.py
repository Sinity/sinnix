"""Polylogue live-ingest attempt reader."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..runtime_inventory import polylogue_archive
from .sqlite_util import sqlite_columns, sqlite_errors, sqlite_rows, table_exists

POLYLOGUE_TIERS = (
    "index.db",
    "source.db",
    "embeddings.db",
    "ops.db",
    "audit.db",
    "user.db",
)


def _archive_root() -> Path | None:
    configured = polylogue_archive().get("archiveRoot")
    return Path(configured) if isinstance(configured, str) and configured else None


def polylogue_tiers() -> dict[str, Any]:
    root = _archive_root()
    rows: list[dict[str, str]] = []
    if root is None:
        return {"root": None, "tiers": rows}
    for name in POLYLOGUE_TIERS:
        path = root / name
        try:
            if path.is_symlink():
                state = "compatibility" if path.exists() else "stale_compatibility"
            elif path.is_file():
                state = "active"
            elif path.exists():
                state = "inaccessible"
            else:
                state = "missing"
        except OSError:
            state = "inaccessible"
        rows.append({"name": name, "path": str(path), "state": state})
    return {"root": str(root), "tiers": rows}


def polylogue_db() -> Path | None:
    override = os.environ.get("SINNIX_OBSERVE_POLYLOGUE_DB")
    if override:
        return Path(override)
    root = _archive_root()
    return root / "ops.db" if root is not None else None


def collect_polylogue_live_attempts(limit: int) -> dict[str, Any]:
    db = polylogue_db()
    source: dict[str, Any] = {
        "db": str(db) if db else None,
        "available": False,
        "rows": [],
        "archive": polylogue_tiers(),
    }
    if not db or not table_exists(db, "ingest_attempts"):
        source["gaps"] = ["polylogue.live_attempts.unavailable"]
        return source
    required = {
        "attempt_id",
        "source_path",
        "origin",
        "status",
        "phase",
        "started_at_ms",
        "heartbeat_at_ms",
        "finished_at_ms",
        "parsed_raw_count",
        "materialized_count",
        "error_message",
    }
    if not required.issubset(sqlite_columns(db, "ingest_attempts")):
        source["gaps"] = ["polylogue.live_attempts.invalid_schema"]
        return source
    # The OPS tier owns this relation. Retain its fields and units; only the
    # common report timestamps and path/error names need a projection.
    prior_errors = len(sqlite_errors())
    rows = sqlite_rows(
        db,
        """
        select *, coalesce(heartbeat_at_ms, finished_at_ms, started_at_ms) as updated_at_ms
        from ingest_attempts
        order by coalesce(heartbeat_at_ms, finished_at_ms, started_at_ms) desc,
                 started_at_ms desc, attempt_id
        limit ?
        """,
        (limit,),
    )
    if len(sqlite_errors()) != prior_errors:
        source["gaps"] = ["polylogue.live_attempts.query_failed"]
        return source
    for row in rows:
        row.update(
            started_at=_timestamp(row["started_at_ms"]),
            updated_at=_timestamp(row["updated_at_ms"]),
            completed_at=_timestamp(row["finished_at_ms"]),
            current_source=row["origin"],
            current_path=row["source_path"],
            error=row["error_message"],
        )
    source["available"] = True
    source["rows"] = rows
    return source


def _timestamp(milliseconds: int | None) -> str | None:
    if milliseconds is None:
        return None
    return datetime.fromtimestamp(milliseconds / 1000, UTC).isoformat()
