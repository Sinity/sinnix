from __future__ import annotations

import json
from typing import Any

from .capabilities import Capability, Principal
from .config import GatewayConfig


class CapabilityIndexError(ValueError):
    pass


class CapabilityIndexService:
    def __init__(self, config: GatewayConfig, principal: Principal):
        self.config = config
        self.principal = principal

    def _load(self) -> dict[str, Any] | None:
        try:
            raw = json.loads(self.config.capability_index.read_text())
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError):
            raise CapabilityIndexError("capability index is malformed") from None
        if (
            not isinstance(raw, dict)
            or raw.get("schema") != "sinnix-capability-index-v1"
            or not isinstance(raw.get("rows"), list)
            or any(not isinstance(row, dict) for row in raw["rows"])
        ):
            raise CapabilityIndexError("capability index is malformed")
        return raw

    @staticmethod
    def _page_value(value: Any, max_bytes: int) -> dict[str, Any] | None:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        if len(encoded) > max_bytes:
            return None
        return value

    @staticmethod
    def _limit(value: int) -> int:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 1 <= value <= 500
        ):
            raise CapabilityIndexError("limit must be 1-500")
        return value

    @staticmethod
    def _cursor(value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise CapabilityIndexError("cursor must be a non-negative integer")
        return value

    @staticmethod
    def _query(value: str) -> list[str]:
        if not isinstance(value, str) or len(value) > 1_024:
            raise CapabilityIndexError("query must be a string up to 1024 characters")
        return value.casefold().split()

    @staticmethod
    def _source(index: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema": index["schema"],
            "host": index.get("host"),
            "revision": index.get("revision"),
        }

    @staticmethod
    def _matches(
        row: dict[str, Any],
        terms: list[str],
        kind: str | None,
        enabled: bool | None,
    ) -> bool:
        if kind is not None and row.get("kind") != kind:
            return False
        if enabled is not None and row.get("enabled") is not enabled:
            return False
        searchable = " ".join(
            str(row.get(field, ""))
            for field in ("kind", "name", "description", "invoke", "owner", "docs")
        ).casefold()
        return all(term in searchable for term in terms)

    def search(
        self,
        query: str = "",
        kind: str | None = None,
        enabled: bool | None = None,
        cursor: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        self.principal.require(Capability.CAPABILITY_READ)
        terms = self._query(query)
        if kind is not None and (not isinstance(kind, str) or not kind):
            raise CapabilityIndexError("kind must be a non-empty string")
        if enabled is not None and not isinstance(enabled, bool):
            raise CapabilityIndexError("enabled must be a boolean")
        cursor = self._cursor(cursor)
        limit = self._limit(limit)
        index = self._load()
        if index is None:
            return {
                "available": False,
                "reason": "capability index is unavailable",
            }
        rows = [
            row for row in index["rows"] if self._matches(row, terms, kind, enabled)
        ]
        if cursor >= len(rows) and cursor != 0:
            raise CapabilityIndexError("cursor is beyond matching capability rows")
        selected = rows[cursor : cursor + limit]
        while selected or not rows:
            next_cursor = cursor + len(selected)
            response = {
                "available": True,
                "source": self._source(index),
                "query": query,
                "kind": kind,
                "enabled": enabled,
                "total": len(rows),
                "cursor": cursor,
                "next_cursor": next_cursor if next_cursor < len(rows) else None,
                "rows": selected,
            }
            bounded = self._page_value(response, self.config.max_result_bytes)
            if bounded is not None:
                return bounded
            if not selected:
                break
            selected.pop()
        return {
            "available": False,
            "reason": "one capability row exceeded response bound",
            "source": self._source(index),
        }

    def describe(self, name: str, kind: str | None = None) -> dict[str, Any]:
        self.principal.require(Capability.CAPABILITY_READ)
        if not isinstance(name, str) or not name or len(name) > 1_024:
            raise CapabilityIndexError(
                "name must be a non-empty string up to 1024 characters"
            )
        if kind is not None and (not isinstance(kind, str) or not kind):
            raise CapabilityIndexError("kind must be a non-empty string")
        index = self._load()
        if index is None:
            return {
                "available": False,
                "reason": "capability index is unavailable",
            }
        rows = [
            row
            for row in index["rows"]
            if row.get("name") == name and (kind is None or row.get("kind") == kind)
        ]
        if not rows:
            return {
                "available": False,
                "reason": "capability not found",
                "source": self._source(index),
                "name": name,
                "kind": kind,
            }
        response = {
            "available": True,
            "source": self._source(index),
            "name": name,
            "kind": kind,
            "ambiguous": len(rows) > 1,
            "rows": rows,
        }
        bounded = self._page_value(response, self.config.max_result_bytes)
        if bounded is None:
            return {
                "available": False,
                "reason": "capability description exceeded response bound",
                "source": self._source(index),
            }
        return bounded
