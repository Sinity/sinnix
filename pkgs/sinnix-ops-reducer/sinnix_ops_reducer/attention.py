"""Normalize provider attention events into the reducer-owned queue."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

ACTIONABLE = {
    "approval": "waiting_approval",
    "user_wait": "waiting_user",
    "rate_limit": "rate_limited",
}
TERMINAL = {"completion", "failure"}


def _sort_key(event: dict[str, Any]) -> str:
    return str(event.get("at") or "")


def _event_id(job_id: str, event: dict[str, Any]) -> str:
    payload = event.get("payload")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    source = "|".join(
        [job_id, str(event.get("event") or ""), str(event.get("at") or ""), encoded]
    )
    return "attention-" + hashlib.sha256(source.encode()).hexdigest()[:24]


def _valid_time(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def normalize_attention(report: dict[str, Any]) -> dict[str, Any]:
    """Return redacted, deduplicated attention state from gateway correlations."""

    gateway = report.get("agent_gateway")
    correlations = gateway.get("correlations", []) if isinstance(gateway, dict) else []
    pending: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    for correlation in correlations:
        if not isinstance(correlation, dict):
            continue
        job_id = correlation.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            continue
        job = next(
            (
                item
                for item in gateway.get("jobs", [])
                if isinstance(item, dict) and item.get("job_id") == job_id
            ),
            {},
        )
        provider = job.get("backend") if isinstance(job, dict) else None
        job_correlation = job.get("correlation", {}) if isinstance(job, dict) else {}
        if not isinstance(job_correlation, dict):
            job_correlation = {}
        for event in sorted(correlation.get("lifecycle_events", []), key=_sort_key):
            if not isinstance(event, dict) or not _valid_time(event.get("at")):
                continue
            kind = event.get("event")
            if kind in TERMINAL:
                for key in [key for key, item in pending.items() if item["job_id"] == job_id]:
                    pending.pop(key, None)
                continue
            state = ACTIONABLE.get(kind)
            if state is None:
                continue
            event_id = _event_id(job_id, event)
            if event_id in seen:
                continue
            seen.add(event_id)
            pending[event_id] = {
                "event_id": event_id,
                "job_id": job_id,
                "provider": provider if isinstance(provider, str) else "unknown",
                "state": state,
                "occurred_at": event["at"],
                "summary": {
                    "waiting_approval": "approval required",
                    "waiting_user": "user response required",
                    "rate_limited": "provider rate limit",
                }[state],
                "target": {
                    key: job_correlation.get(key)
                    for key in ("kitty_socket", "kitty_window_id", "hyprland_address")
                    if job_correlation.get(key)
                },
            }
    items = sorted(pending.values(), key=lambda item: (item["occurred_at"], item["event_id"]))
    return {
        "schema": "sinnix-attention-v1",
        "pending": items,
        "pending_count": len(items),
        "oldest_event_id": items[0]["event_id"] if items else None,
    }
