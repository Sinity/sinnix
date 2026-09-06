from __future__ import annotations

from typing import Any

from .capabilities import Capability, Principal
from .sessions import SessionError, SessionLogService
from .sources import (
    LOCAL_AUTHORITY,
    any_source_truncated,
    fetch_each_source,
    resolve_providers,
)


class MemoryError(ValueError):
    pass


class MemoryService:
    def __init__(self, principal: Principal, sessions: SessionLogService):
        self.principal = principal
        self.sessions = sessions

    @staticmethod
    def _query(value: Any) -> str:
        if not isinstance(value, str) or not value or len(value) > 1_000:
            raise MemoryError("query must contain 1-1000 characters")
        return value

    def search(
        self, query: str, providers: list[str] | None = None, limit: int = 100
    ) -> dict[str, Any]:
        self.principal.require(Capability.SESSION_READ)
        query = self._query(query)
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 500
        ):
            raise MemoryError("limit must be 1-500")
        requested = resolve_providers(providers, error=MemoryError, noun="memory")
        sources, fetched = fetch_each_source(
            self.sessions,
            requested,
            limit,
            lambda provider, per_source_limit: self.sessions.search(
                provider, query, per_source_limit
            ),
        )
        matches = [
            {
                "source": provider,
                "authority": LOCAL_AUTHORITY,
                "object_reference": row["reference"],
                "line": row["line"],
                "text": row["text"],
            }
            for provider, result in fetched
            for row in result["matches"]
        ]
        return {
            "query": query,
            "sources": sources,
            "matches": matches[:limit],
            "truncated": len(matches) > limit or any_source_truncated(sources),
        }

    def get(
        self, reference: str, offset: int = 0, max_bytes: int = 64_000
    ) -> dict[str, Any]:
        self.principal.require(Capability.SESSION_READ)
        if not isinstance(reference, str) or not reference or len(reference) > 8_192:
            raise MemoryError("reference must be a bounded non-empty string")
        try:
            result = self.sessions.read(reference, offset, max_bytes)
        except SessionError as exc:
            raise MemoryError(str(exc)) from exc
        return {
            "source": result["provider"],
            "authority": LOCAL_AUTHORITY,
            "availability": "available",
            "object_reference": result["reference"],
            "offset": result["offset"],
            "bytes": result["bytes"],
            "truncated": result["truncated"],
            "content": result["content"],
        }
