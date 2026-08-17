"""Bounded correlation view for the shared agent gateway substrate."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .orphans import classify_jobs


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


def _json_lines(
    path: Path, *, bound: int = 1_048_576, limit: int = 100
) -> list[dict[str, Any]]:
    try:
        if path.is_symlink() or path.stat().st_size > bound:
            return []
        with path.open("rb") as handle:
            data = handle.read(bound + 1)
        if len(data) > bound:
            return []
        rows = []
        for raw in data.decode(errors="replace").splitlines()[-limit:]:
            value = json.loads(raw)
            if isinstance(value, dict):
                rows.append(value)
        return rows
    except (OSError, json.JSONDecodeError):
        return []


def _journal_rows(limit: int) -> tuple[list[dict[str, Any]], str | None]:
    fixture = os.environ.get("SINNIX_AGENT_JOURNAL_FILE")
    if fixture:
        return _json_lines(Path(fixture), limit=limit), None
    try:
        result = subprocess.run(
            [
                "journalctl",
                "-t",
                "sinnix-agent-job",
                "-o",
                "json",
                "--output-fields=SINNIX_JOB_ID,SINNIX_JOB_LIFECYCLE,SINNIX_SCOPE_UNIT,SINNIX_CGROUP",
                "-n",
                str(limit),
                "--no-pager",
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], type(exc).__name__
    if result.returncode != 0 or len(result.stdout) > 1_048_576:
        return [], "journal_unavailable" if result.returncode else "journal_bound"
    rows = []
    try:
        for raw in result.stdout.decode(errors="replace").splitlines():
            value = json.loads(raw)
            if isinstance(value, dict):
                rows.append(value)
    except json.JSONDecodeError:
        return [], "journal_malformed"
    return rows, None


def _polylogue_sessions(
    job_ids: list[str],
) -> tuple[dict[str, dict[str, Any]], str | None]:
    db = Path(
        os.environ.get(
            "SINNIX_POLYLOGUE_INDEX_DB", "/realm/data/ai/polylogue/index.db"
        )
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
            term = '"' + job_id.replace('"', '""') + '"'
            row = connection.execute(
                "select session_id from messages_fts where messages_fts match ? limit 1",
                (term,),
            ).fetchone()
            if row:
                found[job_id] = {
                    "session_id": row[0],
                    "source": "polylogue:index.db/messages_fts",
                }
        connection.close()
    except sqlite3.Error as exc:
        return found, type(exc).__name__
    return found, None


def _quota_view(quota: dict[str, Any] | None) -> dict[str, Any]:
    if not quota:
        return {
            "provenance": "inferred",
            "freshness": None,
            "values": {},
            "reason": "no provider observation",
        }
    observed_at = quota.get("observed_at")
    try:
        observed = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
        if observed.tzinfo is None:
            raise ValueError
    except (TypeError, ValueError):
        return {
            "provenance": "inferred",
            "freshness": observed_at,
            "values": quota,
            "reason": "provider observation has no valid timestamp",
        }
    max_age = max(1, int(os.environ.get("SINNIX_AGENT_QUOTA_MAX_AGE_SECONDS", "900")))
    age = (
        datetime.now(timezone.utc) - observed.astimezone(timezone.utc)
    ).total_seconds()
    if age < 0 or age > max_age:
        return {
            "provenance": "inferred",
            "freshness": observed_at,
            "values": quota,
            "reason": "provider observation is stale",
            "age_seconds": max(0, int(age)),
        }
    return {
        "provenance": "observed",
        "freshness": observed_at,
        "values": quota,
        "age_seconds": int(age),
    }


def collect_agent_gateway(
    limit: int = 20, below: dict[str, Any] | None = None
) -> dict[str, Any]:
    root = Path(
        os.environ.get(
            "SINNIX_AGENT_GATEWAY_STATE_DIR",
            str(Path.home() / ".local/state/sinnix/agent-gateway"),
        )
    )
    job_root = Path(os.environ.get("SINNIX_AGENT_JOB_STATE_DIR", str(root / "jobs")))
    jobs: list[dict[str, Any]] = []
    malformed: list[str] = []
    try:
        paths = sorted(
            job_root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
        )[: max(1, min(limit, 100))]
    except OSError:
        paths = []
    for path in paths:
        row = _json(path)
        if (
            row
            and row.get("schema_version") in {2, 3}
            and isinstance(row.get("job_id"), str)
        ):
            jobs.append(row)
        else:
            malformed.append(path.name)
    audit: list[dict[str, Any]] = []
    audit_error = None
    db = root / "audit/events.sqlite3"
    try:
        connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=0.25)
        connection.execute("pragma query_only=on")
        rows = connection.execute(
            "select sequence,event_id,occurred_at,profile,operation,outcome,payload_json from events order by sequence desc limit ?",
            (max(1, min(limit, 100)),),
        ).fetchall()
        connection.close()
        audit = [
            {
                "sequence": r[0],
                "event_id": r[1],
                "occurred_at": r[2],
                "profile": r[3],
                "operation": r[4],
                "outcome": r[5],
                "payload": json.loads(r[6]),
            }
            for r in rows
        ]
    except (OSError, sqlite3.Error, json.JSONDecodeError) as exc:
        audit_error = type(exc).__name__
    journal, journal_error = _journal_rows(max(20, min(limit * 10, 200)))
    journal_by_job: dict[str, list[dict[str, Any]]] = {}
    for row in journal:
        job_id = row.get("SINNIX_JOB_ID") or row.get("job_id")
        if job_id:
            journal_by_job.setdefault(str(job_id), []).append(row)
    history, polylogue_error = _polylogue_sessions([str(row["job_id"]) for row in jobs])
    audit_by_job: dict[str, list[str]] = {}
    for row in audit:
        payload = row.get("payload") or {}
        job_id = payload.get("correlation_id") or payload.get("job_id")
        if job_id:
            audit_by_job.setdefault(str(job_id), []).append(str(row["event_id"]))
    correlations = [
        {
            "job_id": row["job_id"],
            "scope_unit": row.get("launcher", {}).get("scope_unit"),
            "cgroup": row.get("launcher", {}).get("cgroup"),
            "delegation": row.get("delegation", {}),
            "identity": row.get("identity", {}),
            "actual_agent": row.get("actual_agent"),
            "completion": row.get("completion"),
            "lifecycle_events": _json_lines(
                job_root / f"{row['job_id']}.events.jsonl", limit=200
            ),
            "audit_event_ids": audit_by_job.get(row["job_id"], []),
            "journal": journal_by_job.get(row["job_id"], []),
            "polylogue": history.get(row["job_id"]),
            "complete": bool(
                audit_by_job.get(row["job_id"])
                and journal_by_job.get(row["job_id"])
                and history.get(row["job_id"])
            ),
        }
        for row in jobs
    ]
    quota_file = Path(
        os.environ.get("SINNIX_AGENT_QUOTA_FILE", str(root / "quota.json"))
    )
    quota = _json(quota_file)
    orphaned_jobs = classify_jobs(jobs, below)
    return {
        "schema": "sinnix-observe-agent-gateway-v1",
        "available": root.exists(),
        "jobs": jobs,
        "malformed_records": malformed,
        "audit": audit,
        "audit_error": audit_error,
        "journal_error": journal_error,
        "polylogue_error": polylogue_error,
        "correlations": correlations,
        "orphaned_jobs": orphaned_jobs,
        "quota": _quota_view(quota),
    }
