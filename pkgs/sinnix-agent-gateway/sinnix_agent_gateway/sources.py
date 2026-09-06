"""The source fan-out shared by the memory and timeline services.

Both walk the same requested-source list: an upstream this host does not serve
is reported unavailable with its standing reason, a session provider is fetched
through `SessionLogService`, and every source yields exactly one provenance
row. The per-source limit divides the caller's limit across the session
providers alone, so naming an unavailable upstream never shrinks what a live
provider may return.

Row mapping and error translation stay with the caller: memory rows and
timeline entries have different shapes, and each service raises its own error
class.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .sessions import SessionLogService

RAW_PROVIDERS = ("claude-code", "codex")
UNAVAILABLE_SOURCES = {
    "polylogue": "upstream is intentionally unavailable on this host",
    "sinex": "upstream is intentionally unavailable on this host",
    "lynchpin": "no gateway semantic adapter is registered yet",
}
LOCAL_AUTHORITY = "authoritative-local-session-jsonl"


def resolve_providers(
    providers: list[str] | None, *, error: type[Exception], noun: str
) -> list[str]:
    known = {*RAW_PROVIDERS, *UNAVAILABLE_SOURCES}
    if providers is None:
        return [*RAW_PROVIDERS, *UNAVAILABLE_SOURCES]
    if (
        not isinstance(providers, list)
        or not providers
        or any(not isinstance(provider, str) for provider in providers)
    ):
        raise error("providers must be a non-empty list of source names")
    unknown = sorted(set(providers) - known)
    if unknown:
        raise error(f"unknown {noun} source(s): {unknown}")
    return list(dict.fromkeys(providers))


def fetch_each_source(
    sessions: SessionLogService,
    providers: list[str],
    limit: int,
    fetch: Callable[[str, int], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[tuple[str, dict[str, Any]]]]:
    """Return one provenance row per requested source and the fetched payloads.

    `fetch(provider, per_source_limit)` is the session-service call the caller
    wants; its payload must carry `scanned_bytes` and `truncated`.
    """
    session_providers = [
        provider for provider in providers if provider in RAW_PROVIDERS
    ]
    per_source_limit = max(1, -(-limit // max(1, len(session_providers))))
    sources: list[dict[str, Any]] = []
    fetched: list[tuple[str, dict[str, Any]]] = []
    for provider in providers:
        if provider in UNAVAILABLE_SOURCES:
            sources.append(
                {
                    "source": provider,
                    "authority": "upstream",
                    "availability": "unavailable",
                    "reason": UNAVAILABLE_SOURCES[provider],
                }
            )
            continue
        source = next(
            candidate
            for candidate in sessions.sources
            if candidate.provider == provider
        )
        if not source.root.is_dir():
            sources.append(
                {
                    "source": provider,
                    "authority": LOCAL_AUTHORITY,
                    "availability": "unavailable",
                    "reason": "session source directory is unavailable",
                }
            )
            continue
        result = fetch(provider, per_source_limit)
        sources.append(
            {
                "source": provider,
                "authority": LOCAL_AUTHORITY,
                "availability": "available",
                "coverage": {
                    "scanned_bytes": result["scanned_bytes"],
                    "truncated": result["truncated"],
                },
            }
        )
        fetched.append((provider, result))
    return sources, fetched


def any_source_truncated(sources: list[dict[str, Any]]) -> bool:
    return any(
        source.get("coverage", {}).get("truncated") is True for source in sources
    )
