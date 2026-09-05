"""Case-insensitive term search over catalog-like rows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def search_rows(
    rows: Iterable[Mapping[str, Any]], text: str | None, fields: Iterable[str]
) -> list[Mapping[str, Any]]:
    """Rows whose joined ``fields`` contain every whitespace-separated term of ``text``."""
    terms = (text or "").casefold().split()
    names = tuple(fields)
    if not terms:
        return list(rows)
    selected = []
    for row in rows:
        haystack = " ".join(
            " ".join(map(str, value))
            if isinstance(value, (list, tuple))
            else str(value)
            for value in (row.get(name, "") for name in names)
            if value is not None
        ).casefold()
        if all(term in haystack for term in terms):
            selected.append(row)
    return selected
