"""Polylogue live-ingest attempt reader."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .sqlite_util import sqlite_columns, sqlite_rows, table_exists
from ..runtime_inventory import polylogue_archive

POLYLOGUE_TIERS = ("index.db", "source.db", "embeddings.db", "ops.db", "audit.db", "user.db")


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
    candidates = [os.environ.get("SINNIX_OBSERVE_POLYLOGUE_DB")]
    root = _archive_root()
    if root is not None:
        candidates.append(str(root / "index.db"))
    for candidate in candidates:
        if candidate and table_exists(Path(candidate), "live_ingest_attempt"):
            return Path(candidate)
    return Path(candidates[0]) if candidates[0] else None


def collect_polylogue_live_attempts(limit: int) -> dict[str, Any]:
    db = polylogue_db()
    source: dict[str, Any] = {
        "db": str(db) if db else None,
        "available": False,
        "rows": [],
        "archive": polylogue_tiers(),
    }
    if not db or not db.exists() or not table_exists(db, "live_ingest_attempt"):
        source["gaps"] = ["polylogue.live_attempts.unavailable"]
        return source
    cols = set(sqlite_columns(db, "live_ingest_attempt"))
    wanted = [
        "attempt_id",
        "started_at",
        "updated_at",
        "completed_at",
        "status",
        "phase",
        "queued_file_count",
        "needed_file_count",
        "succeeded_file_count",
        "failed_file_count",
        "input_bytes",
        "source_payload_read_bytes",
        "cursor_fingerprint_read_bytes",
        "parse_time_s",
        "convergence_time_s",
        "current_source",
        "current_path",
        "error",
        "rss_current_mb",
        "rss_peak_self_mb",
        "rss_peak_children_mb",
        "cgroup_path",
        "cgroup_memory_current_mb",
        "cgroup_memory_peak_mb",
        "cgroup_memory_swap_current_mb",
    ]
    selected = [col for col in wanted if col in cols]
    if not selected:
        source["gaps"] = ["polylogue.live_attempts.empty_schema"]
        return source
    rows = sqlite_rows(
        db,
        f"""
        select {", ".join(selected)}
        from live_ingest_attempt
        order by updated_at desc, started_at desc
        limit ?
        """,
        (limit,),
    )
    source["available"] = True
    source["rows"] = rows
    return source
