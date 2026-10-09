"""Bounded, private-free projection of Clodex's routed inference ledger."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

MAX_BYTES = 2 * 1024 * 1024
MAX_LINES = 4096


def clodex_usage(path: Path | None) -> tuple[dict[str, Any], dict[str, Any]]:
    source = "clodex-inference-accounting"
    if path is None:
        return {}, _health("disabled", source, "no accounting path configured")
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            start = max(0, handle.tell() - MAX_BYTES)
            handle.seek(max(0, start - 1))
            boundary = handle.read(1) if start else b"\n"
            data = handle.read(MAX_BYTES)
            if boundary != b"\n":
                # The tail starts inside a record, not at its beginning.
                data = data.partition(b"\n")[2]
    except OSError as error:
        return {}, _health("unavailable", source, str(error)[:240])
    total = {
        "requests": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
    }
    newest: str | None = None
    for line in data.decode("utf-8", errors="replace").splitlines()[-MAX_LINES:]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (
            not isinstance(row, dict)
            or row.get("event") != "response_usage"
            or row.get("route") != "translated"
        ):
            continue
        fields = (
            ("inputTokens", "input_tokens"),
            ("outputTokens", "output_tokens"),
            ("cacheReadInputTokens", "cache_read_tokens"),
            ("cacheCreationInputTokens", "cache_write_tokens"),
        )
        values = [row.get(source_key) for source_key, _ in fields]
        if not all(
            type(value) in (int, float)
            and value >= 0
            and (not isinstance(value, float) or math.isfinite(value))
            for value in values
        ):
            continue
        total["requests"] += 1
        for value, (_, target) in zip(values, fields, strict=True):
            total[target] += int(value)
        if isinstance(row.get("timestamp"), str):
            newest = row["timestamp"]
    if newest:
        total["last_recorded_at"] = newest
    return total, _health("healthy", "clodex-inference-accounting", None)


def _health(status: str, source: str, degradation: str | None) -> dict[str, Any]:
    return {
        "status": status,
        "source": source,
        "freshness": "current" if status == "healthy" else "unknown",
        "degradation": degradation,
    }
