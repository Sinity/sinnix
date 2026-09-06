from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from .capabilities import Capability, Principal
from .sessions import SessionError, SessionLogService
from .sources import (
    LOCAL_AUTHORITY,
    any_source_truncated,
    fetch_each_source,
    resolve_providers,
)


class TimelineError(ValueError):
    pass


_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


class TimelineService:
    def __init__(self, principal: Principal, sessions: SessionLogService):
        self.principal = principal
        self.sessions = sessions

    @staticmethod
    def _timestamp(value: str | None, name: str) -> int | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value or len(value) > 64:
            raise TimelineError(f"{name} must be an RFC 3339 timestamp")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise TimelineError(f"{name} must be an RFC 3339 timestamp") from exc
        if parsed.tzinfo is None:
            raise TimelineError(f"{name} must include a timezone")
        delta = parsed.astimezone(UTC) - _EPOCH
        return (
            delta.days * 86_400_000_000_000
            + delta.seconds * 1_000_000_000
            + delta.microseconds * 1_000
        )

    def query(
        self,
        start: str | None = None,
        end: str | None = None,
        query: str | None = None,
        providers: list[str] | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        self.principal.require(Capability.SESSION_READ)
        start_ns = self._timestamp(start, "start")
        end_ns = self._timestamp(end, "end")
        if start_ns is not None and end_ns is not None and start_ns > end_ns:
            raise TimelineError("start must not be after end")
        if query is not None and (
            not isinstance(query, str) or not query or len(query) > 1_000
        ):
            raise TimelineError("query must contain 1-1000 characters")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 500
        ):
            raise TimelineError("limit must be 1-500")
        requested = resolve_providers(providers, error=TimelineError, noun="timeline")

        def fetch(provider: str, per_source_limit: int) -> dict[str, Any]:
            try:
                return self.sessions.timeline(
                    provider, start_ns, end_ns, query, per_source_limit
                )
            except SessionError as exc:
                raise TimelineError(str(exc)) from exc

        sources, fetched = fetch_each_source(self.sessions, requested, limit, fetch)
        entries = [
            {
                "source": provider,
                "authority": LOCAL_AUTHORITY,
                "object_reference": entry.pop("reference"),
                **entry,
            }
            for provider, result in fetched
            for entry in result["entries"]
        ]
        entries.sort(key=lambda entry: entry["mtime_ns"], reverse=True)
        entry_limit_truncated = len(entries) > limit
        entries = entries[:limit]
        truncated = entry_limit_truncated or any_source_truncated(sources)
        while True:
            response = {
                "time_basis": "session-file-mtime",
                "start": start,
                "end": end,
                "query": query,
                "sources": sources,
                "entries": entries,
                "truncated": truncated,
            }
            encoded = json.dumps(
                response, sort_keys=True, separators=(",", ":")
            ).encode()
            if len(encoded) <= self.sessions.config.max_result_bytes:
                return response
            if not entries:
                return {
                    "available": False,
                    "reason": "timeline response metadata exceeded response bound",
                }
            entries.pop()
            truncated = True
