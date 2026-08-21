from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from .capabilities import Capability, Principal
from .sessions import SessionError, SessionLogService


class TimelineError(ValueError):
    pass


_RAW_PROVIDERS = ("claude-code", "codex")
_UNAVAILABLE_SOURCES = {
    "polylogue": "upstream is intentionally unavailable on this host",
    "sinex": "upstream is intentionally unavailable on this host",
    "lynchpin": "no gateway semantic adapter is registered yet",
}
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

    @staticmethod
    def _providers(providers: list[str] | None) -> list[str]:
        known = {*_RAW_PROVIDERS, *_UNAVAILABLE_SOURCES}
        if providers is None:
            return [*_RAW_PROVIDERS, *_UNAVAILABLE_SOURCES]
        if (
            not isinstance(providers, list)
            or not providers
            or any(not isinstance(provider, str) for provider in providers)
        ):
            raise TimelineError("providers must be a non-empty list of source names")
        unknown = sorted(set(providers) - known)
        if unknown:
            raise TimelineError(f"unknown timeline source(s): {unknown}")
        return list(dict.fromkeys(providers))

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
        if query is not None and (not isinstance(query, str) or not query or len(query) > 1_000):
            raise TimelineError("query must contain 1-1000 characters")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise TimelineError("limit must be 1-500")
        requested = self._providers(providers)
        raw_requested = [provider for provider in requested if provider in _RAW_PROVIDERS]
        per_source_limit = max(1, -(-limit // max(1, len(raw_requested))))
        sources = []
        entries = []
        for provider in requested:
            if provider in _UNAVAILABLE_SOURCES:
                sources.append(
                    {
                        "source": provider,
                        "authority": "upstream",
                        "availability": "unavailable",
                        "reason": _UNAVAILABLE_SOURCES[provider],
                    }
                )
                continue
            source = next(
                candidate
                for candidate in self.sessions.sources
                if candidate.provider == provider
            )
            if not source.root.is_dir():
                sources.append(
                    {
                        "source": provider,
                        "authority": "authoritative-local-session-jsonl",
                        "availability": "unavailable",
                        "reason": "session source directory is unavailable",
                    }
                )
                continue
            try:
                result = self.sessions.timeline(
                    provider, start_ns, end_ns, query, per_source_limit
                )
            except SessionError as exc:
                raise TimelineError(str(exc)) from exc
            sources.append(
                {
                    "source": provider,
                    "authority": "authoritative-local-session-jsonl",
                    "availability": "available",
                    "coverage": {
                        "scanned_bytes": result["scanned_bytes"],
                        "truncated": result["truncated"],
                    },
                }
            )
            entries.extend(
                {
                    "source": provider,
                    "authority": "authoritative-local-session-jsonl",
                    "object_reference": entry.pop("reference"),
                    **entry,
                }
                for entry in result["entries"]
            )
        entries.sort(key=lambda entry: entry["mtime_ns"], reverse=True)
        entry_limit_truncated = len(entries) > limit
        entries = entries[:limit]
        truncated = entry_limit_truncated or any(
            source.get("coverage", {}).get("truncated") is True for source in sources
        )
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
            encoded = json.dumps(response, sort_keys=True, separators=(",", ":")).encode()
            if len(encoded) <= self.sessions.config.max_result_bytes:
                return response
            if not entries:
                return {
                    "available": False,
                    "reason": "timeline response metadata exceeded response bound",
                }
            entries.pop()
            truncated = True
