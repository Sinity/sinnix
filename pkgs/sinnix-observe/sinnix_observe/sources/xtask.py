"""Sinex xtask invocation-history reader."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..util import float_or_zero
from .sqlite_util import sqlite_columns, sqlite_rows, table_exists


def sinex_history_db() -> Path | None:
    override = os.environ.get("SINNIX_OBSERVE_SINEX_DB")
    if override:
        return Path(override)
    sinex_root = Path(os.environ.get("SINEX_ROOT", "/realm/project/sinex"))
    candidates = [
        sinex_root / ".sinex/state/xtask-history.db",
        Path("/realm/project/sinex/.sinex/state/xtask-history.db"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def collect_sinex_xtask(limit: int) -> dict[str, Any]:
    db = sinex_history_db()
    source: dict[str, Any] = {
        "db": str(db) if db else None,
        "available": False,
        "rows": [],
    }
    if not db or not db.exists() or not table_exists(db, "invocations"):
        source["gaps"] = ["sinex.xtask_history.unavailable"]
        return source
    cols = sqlite_columns(db, "invocations")
    wanted = [
        "id",
        "command",
        "subcommand",
        "profile",
        "args_json",
        "started_at",
        "finished_at",
        "duration_secs",
        "status",
        "exit_code",
        "cwd",
        "pid",
        "scope_key",
        "launch_mode",
        "is_background",
        "process_cpu_usage_avg",
        "process_memory_usage_max_mb",
        "process_count_max",
        "resource_sample_count",
        "shared_nix_build_slice_cpu_usage_avg",
        "shared_nix_build_slice_memory_usage_max_mb",
        "shared_background_slice_cpu_usage_avg",
        "shared_background_slice_memory_usage_max_mb",
    ]
    selected = [col for col in wanted if col in cols]
    rows = sqlite_rows(
        db,
        f"""
        select {", ".join(selected)}
        from invocations
        order by started_at desc
        limit ?
        """,
        (limit,),
    )
    source["available"] = True
    source["rows"] = rows
    return source


def infer_sinex_resource_class(row: dict[str, Any]) -> str:
    command = str(row.get("command") or "")
    bg_mb = float_or_zero(row.get("shared_background_slice_memory_usage_max_mb"))
    nix_mb = float_or_zero(row.get("shared_nix_build_slice_memory_usage_max_mb"))
    if command in {"build", "check", "test", "doc"} or nix_mb > 0:
        return "developer-build"
    if row.get("is_background") or row.get("launch_mode") == "background" or bg_mb > 0:
        return "background-maintenance"
    return "unknown"
