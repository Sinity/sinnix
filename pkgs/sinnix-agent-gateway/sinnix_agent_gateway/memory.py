from __future__ import annotations

from typing import Any

from .capabilities import Capability, Principal
from .sessions import SessionError, SessionLogService


class MemoryError(ValueError):
    pass


_RAW_PROVIDERS = ("claude-code", "codex")
_UNAVAILABLE_SOURCES = {
    "polylogue": "upstream is intentionally unavailable on this host",
    "sinex": "upstream is intentionally unavailable on this host",
    "lynchpin": "no gateway semantic adapter is registered yet",
}


class MemoryService:
    def __init__(self, principal: Principal, sessions: SessionLogService):
        self.principal = principal
        self.sessions = sessions

    @staticmethod
    def _query(value: Any) -> str:
        if not isinstance(value, str) or not value or len(value) > 1_000:
            raise MemoryError("query must contain 1-1000 characters")
        return value

    def _providers(self, providers: list[str] | None) -> list[str]:
        known = {*_RAW_PROVIDERS, *_UNAVAILABLE_SOURCES}
        if providers is None:
            return [*_RAW_PROVIDERS, *_UNAVAILABLE_SOURCES]
        if (
            not isinstance(providers, list)
            or not providers
            or any(not isinstance(provider, str) for provider in providers)
        ):
            raise MemoryError("providers must be a non-empty list of source names")
        unknown = sorted(set(providers) - known)
        if unknown:
            raise MemoryError(f"unknown memory source(s): {unknown}")
        return list(dict.fromkeys(providers))

    def search(
        self, query: str, providers: list[str] | None = None, limit: int = 100
    ) -> dict[str, Any]:
        self.principal.require(Capability.SESSION_READ)
        query = self._query(query)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise MemoryError("limit must be 1-500")
        requested = self._providers(providers)
        raw_requested = [provider for provider in requested if provider in _RAW_PROVIDERS]
        per_source_limit = max(1, -(-limit // max(1, len(raw_requested))))
        sources = []
        matches = []
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
            source = next(source for source in self.sessions.sources if source.provider == provider)
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
            result = self.sessions.search(provider, query, per_source_limit)
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
            matches.extend(
                {
                    "source": provider,
                    "authority": "authoritative-local-session-jsonl",
                    "object_reference": row["reference"],
                    "line": row["line"],
                    "text": row["text"],
                }
                for row in result["matches"]
            )
        return {
            "query": query,
            "sources": sources,
            "matches": matches[:limit],
            "truncated": len(matches) > limit or any(
                source.get("coverage", {}).get("truncated") is True for source in sources
            ),
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
            "authority": "authoritative-local-session-jsonl",
            "availability": "available",
            "object_reference": result["reference"],
            "offset": result["offset"],
            "bytes": result["bytes"],
            "truncated": result["truncated"],
            "content": result["content"],
        }
