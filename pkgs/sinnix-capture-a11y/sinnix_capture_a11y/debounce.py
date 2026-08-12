"""Per-key debounce/coalesce gate.

Bounds write-rate for high-frequency event streams (e.g. AT-SPI2
text-changed events firing on every keystroke across every focused text
widget) without dropping the *shape* of activity: callers still see one
record whenever at least ``min_interval`` seconds have elapsed since the
last accepted event for that key.
"""

from __future__ import annotations

import time
from typing import Callable


def _default_clock() -> float:
    return time.monotonic()


class Debouncer:
    def __init__(
        self, min_interval: float, clock: Callable[[], float] | None = None
    ) -> None:
        self._min_interval = min_interval
        self._clock = clock or _default_clock
        self._last_emit: dict[str, float] = {}

    def allow(self, key: str) -> bool:
        now = self._clock()
        last = self._last_emit.get(key)
        if last is not None and (now - last) < self._min_interval:
            return False
        self._last_emit[key] = now
        return True
