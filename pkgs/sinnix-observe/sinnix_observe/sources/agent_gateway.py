"""Bounded correlation view for the shared agent gateway substrate."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any


def _json(path: Path, bound: int = 262_144) -> dict[str, Any] | None:
    try:
        if path.is_symlink() or path.stat().st_size > bound:
            return None
        value = json.loads(path.read_bytes()[: bound + 1])
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def collect_agent_gateway(limit: int = 20) -> dict[str, Any]:
    root = Path(os.environ.get("SINNIX_AGENT_GATEWAY_STATE_DIR", str(Path.home() / ".local/state/sinnix/agent-gateway")))
    job_root = Path(os.environ.get("SINNIX_AGENT_JOB_STATE_DIR", str(root / "jobs")))
    lease_root = Path(os.environ.get("SINNIX_HEAVY_LEASE_STATE_DIR", str(Path.home() / ".local/state/sinnix/heavy-lease")))
    history_path = Path(os.environ.get("SINNIX_AGENT_HISTORY_FILE", str(root / "history-correlation.jsonl")))
    jobs: list[dict[str, Any]] = []
    malformed: list[str] = []
    try:
        paths = sorted(job_root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[: max(1, min(limit, 100))]
    except OSError:
        paths = []
    for path in paths:
        row = _json(path)
        if row and row.get("schema_version") == 2 and isinstance(row.get("job_id"), str):
            jobs.append(row)
        else:
            malformed.append(path.name)
    audit: list[dict[str, Any]] = []
    audit_error = None
    db = root / "audit/events.sqlite3"
    try:
        connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=0.25)
        connection.execute("pragma query_only=on")
        rows = connection.execute("select sequence,event_id,occurred_at,profile,operation,outcome,payload_json from events order by sequence desc limit ?", (max(1, min(limit, 100)),)).fetchall()
        connection.close()
        audit = [{"sequence": r[0], "event_id": r[1], "occurred_at": r[2], "profile": r[3], "operation": r[4], "outcome": r[5], "payload": json.loads(r[6])} for r in rows]
    except (OSError, sqlite3.Error, json.JSONDecodeError) as exc:
        audit_error = type(exc).__name__
    history: dict[str, dict[str, Any]] = {}
    try:
        if not history_path.is_symlink() and history_path.stat().st_size <= 1_048_576:
            for raw in history_path.read_text().splitlines()[-100:]:
                row = json.loads(raw)
                if isinstance(row, dict) and row.get("job_id"):
                    history[str(row["job_id"])] = row
    except (OSError, json.JSONDecodeError):
        pass
    audit_by_job: dict[str, list[str]] = {}
    for row in audit:
        payload = row.get("payload") or {}
        job_id = payload.get("correlation_id") or payload.get("job_id")
        if job_id:
            audit_by_job.setdefault(str(job_id), []).append(str(row["event_id"]))
    correlations = [{"job_id": row["job_id"], "scope_unit": row.get("launcher", {}).get("scope_unit"), "cgroup": row.get("launcher", {}).get("cgroup"), "audit_event_ids": audit_by_job.get(row["job_id"], []), "history": history.get(row["job_id"]), "complete": bool(audit_by_job.get(row["job_id"]) and history.get(row["job_id"]))} for row in jobs]
    quota_file = Path(os.environ.get("SINNIX_AGENT_QUOTA_FILE", str(root / "quota.json")))
    quota = _json(quota_file)
    quota_view = {"provenance": "observed", "freshness": quota.get("observed_at"), "values": quota} if quota else {"provenance": "inferred", "freshness": None, "values": {}, "reason": "no provider observation"}
    return {"schema": "sinnix-observe-agent-gateway-v1", "available": root.exists(), "jobs": jobs, "malformed_records": malformed, "audit": audit, "audit_error": audit_error, "lease": _json(lease_root / "owner.json"), "correlations": correlations, "quota": quota_view}
