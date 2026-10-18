from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable


def product_source(
    path: Path, *, max_age_seconds: float = 86400.0
) -> Callable[[], dict[str, Any]]:
    def collect() -> dict[str, Any]:
        started = time.monotonic()
        stat = path.stat()
        if time.time() - stat.st_mtime > max_age_seconds:
            raise RuntimeError("ambient product is stale")
        value = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(value, dict)
            or value.get("schema") != "lynchpin-ambient-intelligence-v1"
        ):
            raise ValueError("ambient product schema is unsupported")
        if time.monotonic() - started > 1.0:
            raise TimeoutError("ambient product read exceeded 1 second")
        return value

    return collect
