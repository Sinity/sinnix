"""Bounded observation of canonical Sinnixd attested-agent records."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any


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
    db = Path(
        os.environ.get("SINNIX_POLYLOGUE_INDEX_DB", "/realm/data/ai/polylogue/index.db")
    )
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
    """Read daemon-owned job records. `below` remains a caller-compatible input."""

    _ = below
    root = Path(
        os.environ.get("SINNIXD_STATE_DIR", str(Path.home() / ".local/state/sinnixd"))
    )
    records_root = root / "jobs"
    malformed: list[str] = []
    jobs: list[dict[str, Any]] = []
    try:
        paths = sorted(
            records_root.glob("*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[: max(1, min(limit, 100))]
    except OSError:
        paths = []
    for path in paths:
        row = _json(path)
        if row is None or not _is_canonical_job_record(row):
            malformed.append(path.name)
            continue
        job = _public_agent_record(row)
        if job is not None:
            jobs.append(job)
    history, polylogue_error = _polylogue_sessions([str(job["job_id"]) for job in jobs])
    correlations = []
    for job in jobs:
        state = job["state"]
        systemd = state.get("systemd") if isinstance(state.get("systemd"), dict) else {}
        correlations.append(
            {
                "job_id": job["job_id"],
                "unit": job["unit"],
                "cgroup": systemd.get("ControlGroup"),
                "terminal": bool(state.get("terminal")),
                "polylogue": history.get(job["job_id"]),
            }
        )
    return {
        "schema": "sinnix-observe-agentctl-v1",
        "available": records_root.exists(),
        "jobs": jobs,
        "malformed_records": malformed,
        "correlations": correlations,
        "polylogue_error": polylogue_error,
    }
