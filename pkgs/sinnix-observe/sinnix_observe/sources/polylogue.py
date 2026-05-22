"""Polylogue live-ingest attempt reader."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .sqlite_util import sqlite_columns, sqlite_rows, table_exists


def polylogue_db() -> Path | None:
    candidates = [
        os.environ.get("SINNIX_OBSERVE_POLYLOGUE_DB"),
        os.environ.get("POLYLOGUE_DB_PATH"),
        str(Path.home() / ".local/share/polylogue/polylogue.db"),
        str(Path.home() / ".local/share/polylogue/archive.db"),
        str(Path.home() / ".local/share/polylogue/polylogue.sqlite"),
        str(
            Path(os.environ.get("POLYLOGUE_ROOT", "/realm/project/polylogue"))
            / ".local/browser-capture/xdg-data/polylogue/polylogue.db"
        ),
    ]
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
