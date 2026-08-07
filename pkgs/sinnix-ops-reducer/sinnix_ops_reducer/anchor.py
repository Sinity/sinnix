from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

ANCHOR_SCHEMA = "sinnix-session-anchor-v1"
ANCHOR_TTL = timedelta(hours=1)


def reduce_anchor_event(event: Mapping[str, Any], observed_at: datetime, *, previous: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    started = _parse(event.get("started_at"))
    resumed = _parse(event.get("resumed_at")) or observed_at
    if started is None or resumed - started < timedelta(minutes=30):
        return None
    interval_id = str(event.get("interval_id") or f"{started.isoformat()}:{resumed.isoformat()}")
    if previous and previous.get("interval_id") == interval_id:
        return dict(previous)
    observe = event.get("observe") if isinstance(event.get("observe"), Mapping) else {}
    return {
        "schema": ANCHOR_SCHEMA,
        "interval_id": interval_id,
        "started_at": started.isoformat().replace("+00:00", "Z"),
        "resumed_at": resumed.isoformat().replace("+00:00", "Z"),
        "expires_at": (resumed + ANCHOR_TTL).isoformat().replace("+00:00", "Z"),
        "brief": {
            "focused_project": observe.get("focused_project") or "unavailable",
            "recent_commits": _refs(observe.get("recent_commits"), "git:recent-commits"),
            "resumable_agents": _refs(observe.get("resumable_agents"), "polylogue:session-references"),
            "scratch_paths": _refs(observe.get("scratch_paths"), "scratch:references"),
        },
        "sources": {name: _availability(observe.get(key)) for name, key in (("activitywatch", "activitywatch"), ("polylogue", "polylogue"), ("git", "recent_commits"), ("scratch", "scratch_paths"))},
    }


def expire_anchor(anchor: Mapping[str, Any] | None, observed_at: datetime) -> None | dict[str, Any]:
    if not anchor:
        return None
    expires = _parse(anchor.get("expires_at"))
    return dict(anchor) if expires is None or observed_at < expires else None


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _refs(value: Any, fallback: str) -> list[str]:
    return [str(item) for item in value[:8]] if isinstance(value, list) else [fallback]


def _availability(value: Any) -> str:
    return "available" if value else "unavailable"
