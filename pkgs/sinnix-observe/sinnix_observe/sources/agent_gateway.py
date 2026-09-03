"""Bounded observation of canonical Sinnixd attested-agent records."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any

from ..runtime_inventory import polylogue_archive


def _json(path: Path, bound: int = 262_144) -> dict[str, Any] | None:
    try:
        if path.is_symlink() or path.stat().st_size > bound:
            return None
        with path.open("rb") as handle:
            data = handle.read(bound + 1)
        if len(data) > bound:
            return None
        value = json.loads(data)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _polylogue_sessions(
    job_ids: list[str],
) -> tuple[dict[str, dict[str, Any]], str | None]:
    configured = polylogue_archive().get("archiveRoot")
    default = str(Path(configured) / "index.db") if isinstance(configured, str) else ""
    db = Path(os.environ.get("SINNIX_POLYLOGUE_INDEX_DB", default))
    if not db.is_file():
        return {}, "polylogue_archive_unavailable"
    found: dict[str, dict[str, Any]] = {}
    started = time.monotonic()
    try:
        connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=0.25)
        connection.execute("pragma query_only=on")
        connection.set_progress_handler(
            lambda: 1 if time.monotonic() - started > 0.5 else 0, 1000
        )
        for job_id in job_ids:
            row = connection.execute(
                "select session_id from messages_fts where messages_fts match ? limit 1",
                ('"' + job_id.replace('"', '""') + '"',),
            ).fetchone()
            if row:
                found[job_id] = {
                    "session_id": row[0],
                    "source": "polylogue:index.db/messages_fts",
                }
        connection.close()
    except sqlite3.Error:
        return found, "polylogue_index_unreadable"
    return found, None


def _public_agent_record(value: dict[str, Any]) -> dict[str, Any] | None:
    spec = value.get("spec")
    state = value.get("state")
    if (
        value.get("schema_version") not in {2, 3, 4}
        or not isinstance(value.get("job_id"), str)
        or not isinstance(value.get("unit"), str)
        or not isinstance(spec, dict)
        or spec.get("kind") != "attested-agent"
        or not isinstance(state, dict)
    ):
        return None
    contract = spec.get("contract") if isinstance(spec.get("contract"), dict) else {}
    checkout = spec.get("checkout") if isinstance(spec.get("checkout"), dict) else {}
    return {
        "job_id": value["job_id"],
        "unit": value["unit"],
        "kind": spec["kind"],
        "project_id": spec.get("project_id"),
        "created_at": value.get("created_at"),
        "timeout_seconds": spec.get("timeout_seconds"),
        "checkout": checkout,
        "contract": contract,
        "backend": contract.get("backend"),
        "model": contract.get("model"),
        "effort": contract.get("effort"),
        "state": state,
    }


def _is_canonical_job_record(value: dict[str, Any]) -> bool:
    return (
        value.get("schema_version") in {2, 3, 4}
        and isinstance(value.get("job_id"), str)
        and isinstance(value.get("unit"), str)
        and isinstance(value.get("spec"), dict)
        and isinstance(value.get("state"), dict)
    )


def collect_agent_gateway(
    limit: int = 20, below: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Read the canonical job plane through agentctl."""

    _ = below
    try:
        command = os.environ.get("SINNIX_AGENTCTL_COMMAND", "agentctl")
        result = subprocess.run(
            [command, "--json", "job", "list"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        value = json.loads(result.stdout)
        rows = value if isinstance(value, list) else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        rows = []
    jobs = [
        row
        for row in rows[: max(1, min(limit, 100))]
        if isinstance(row, dict) and row.get("kind") == "attested-agent"
    ]
    history, polylogue_error = _polylogue_sessions([str(job["job_id"]) for job in jobs])
    correlations = []
    for job in jobs:
        state = job
        correlations.append(
            {
                "job_id": job["job_id"],
                "unit": job.get("label"),
                "cgroup": job.get("cgroup"),
                "terminal": bool(state.get("terminal")),
                "polylogue": history.get(job["job_id"]),
            }
        )
    return {
        "schema": "sinnix-observe-agentctl-v1",
        "available": bool(jobs),
        "jobs": jobs,
        "malformed_records": [],
        "correlations": correlations,
        "polylogue_error": polylogue_error,
    }
