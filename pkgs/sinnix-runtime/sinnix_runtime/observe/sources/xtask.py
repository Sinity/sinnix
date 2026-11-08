"""Sinex check and test history, read from devkit's run history store."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

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
               boot_id, process_start,
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
    source["rows"] = [resolve_running(row) for row in rows]
    return source


def _current_boot_id() -> str | None:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return None


def _process_start(pid: int) -> int | None:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except (OSError, IndexError):
        return None
    try:
        return int(fields[19])  # field 22 (starttime), counted after the comm
    except (IndexError, ValueError):
        return None


def _agentctl_timed_out(job: str) -> bool:
    try:
        result = subprocess.run(
            ["agentctl", "job", "get", "--json", "--job-id", job, "0"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    try:
        job_state = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False
    return isinstance(job_state, dict) and (
        job_state.get("phase") == "timeout" or job_state.get("exit_code") == 124
    )


def resolve_running(
    row: dict[str, Any],
    *,
    boot_id: Callable[[], str | None] = _current_boot_id,
    process_start: Callable[[int], int | None] = _process_start,
    timed_out: Callable[[str], bool] = _agentctl_timed_out,
) -> dict[str, Any]:
    """A `running` row whose process no longer exists (another boot, or the
    pid now belongs to a different process) was interrupted -- the rule the
    devkit schema states. It reads `timeout` when AgentCTL recorded a timeout
    for its job, so a check killed at its limit does not show as running."""
    if row.get("status") != "running":
        return row
    pid = row.get("pid")
    alive = (
        row.get("boot_id") == boot_id()
        and isinstance(pid, int)
        and process_start(pid) == row.get("process_start")
    )
    if alive:
        return row
    job = row.get("agentctl_job")
    status = "timeout" if job and timed_out(str(job)) else "interrupted"
    return {**row, "status": status}


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
