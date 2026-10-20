"""Pure decision logic for capture-screen: attempt rate limiting, p-hash
dedup, degenerate-frame detection, the daily-volume throttle guard, and the
idle-pause trigger.

Every function/class here is pixel-array or plain-value in, plain-value out
-- no subprocess calls, no filesystem, no Wayland/Hyprland IO -- so the
pytest suite exercises this file directly without a live desktop session.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

import numpy as np


@dataclass
class CaptureAttemptGate:
    """Bound expensive screencopy attempts during event bursts and failures."""

    min_interval_seconds: float = 1.0
    failure_backoff_seconds: float = 30.0
    _last_attempt_ts: float | None = None
    _blocked_until_ts: float = 0.0

    def allow(self, now: float) -> bool:
        if now < self._blocked_until_ts:
            return False
        if (
            self._last_attempt_ts is not None
            and now - self._last_attempt_ts < self.min_interval_seconds
        ):
            return False
        self._last_attempt_ts = now
        return True

    def record_failure(self, now: float) -> None:
        self._blocked_until_ts = max(
            self._blocked_until_ts, now + self.failure_backoff_seconds
        )

    def record_success(self) -> None:
        self._blocked_until_ts = 0.0


# ---------------------------------------------------------------------------
# Perceptual hash (DCT-based pHash, the same construction as the widely-used
# `imagehash.phash`: resize to hash_size*high_freq_factor, DCT-II, keep the
# top-left hash_size x hash_size low-frequency block, threshold against the
# block's median (excluding the DC term) -> hash_size**2 bits). Implemented
# directly on numpy (matrix-multiply DCT-II) instead of pulling in scipy or
# the `imagehash` package, since neither is otherwise needed by this lane.
# ---------------------------------------------------------------------------


def _dct_basis(n: int) -> np.ndarray:
    """Orthonormal n x n DCT-II basis matrix."""
    k = np.arange(n).reshape(-1, 1)
    m = np.arange(n).reshape(1, -1)
    basis = np.cos(np.pi / n * (m + 0.5) * k)
    basis[0, :] *= 1.0 / np.sqrt(2.0)
    return basis * np.sqrt(2.0 / n)


def dct2(a: np.ndarray) -> np.ndarray:
    """2D DCT-II via separable matrix multiplication (rows then columns)."""
    rows, cols = a.shape
    row_basis = _dct_basis(rows)
    col_basis = _dct_basis(cols)
    return row_basis @ a @ col_basis.T


def phash64(gray: np.ndarray, hash_size: int = 8) -> int:
    """Compute a `hash_size**2`-bit perceptual hash from a square grayscale
    array (caller resizes to `hash_size * high_freq_factor` -- see
    `image_to_phash_array` in capture.py for the PIL-facing glue that
    produces this array from a real frame)."""
    if gray.ndim != 2 or gray.shape[0] != gray.shape[1]:
        raise ValueError(f"phash64 expects a square 2D array, got shape {gray.shape}")
    dct = dct2(gray.astype(np.float64))
    low = dct[:hash_size, :hash_size]
    flat = low.flatten()
    median = np.median(flat[1:])  # exclude the DC coefficient from the median
    bits = flat > median
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def hamming_distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def is_near_duplicate(
    prev_hash: int | None, new_hash: int, *, threshold: int = 4
) -> bool:
    """True when `new_hash` is within `threshold` Hamming bits of
    `prev_hash` for the SAME window -- the per-window dedup gate.
    `prev_hash is None` (first frame ever seen for this window) is never a
    duplicate."""
    if prev_hash is None:
        return False
    return hamming_distance(prev_hash, new_hash) <= threshold


def is_degenerate_frame(gray: np.ndarray, *, stddev_threshold: float = 1.0) -> bool:
    """Reject nearly constant grayscale frames before publication.

    The threshold is measured on 0-255 values; compositor screencopy failures
    can yield solid black or other single-color frames.
    """
    return float(np.std(gray)) < stddev_threshold


# Crossing the byte ceiling blocks writes until UTC day rollover. The caller
# logs the transition once and persists state across daemon restarts.


@dataclass
class ThrottleState:
    day: str
    bytes_written: int = 0
    tripped: bool = False


@dataclass
class DailyThrottleGuard:
    ceiling_bytes: int
    clock: Callable[[], float] = time.time
    state: ThrottleState = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.state is None:
            self.state = ThrottleState(day=self._today())

    def _today(self) -> str:
        return time.strftime("%Y-%m-%d", time.gmtime(self.clock()))

    def _roll_if_new_day(self) -> None:
        today = self._today()
        if today != self.state.day:
            self.state = ThrottleState(day=today)

    def blocked(self) -> bool:
        """Avoid frame acquisition work while today's write budget is exhausted."""
        self._roll_if_new_day()
        return self.state.tripped

    def allow(self, nbytes: int) -> tuple[bool, bool]:
        """Attempt to account for `nbytes` more written today.

        Returns `(allowed, newly_tripped)`:
          - `allowed=True`  -- under the ceiling, `nbytes` has been counted.
          - `allowed=False, newly_tripped=True`  -- this call is the one
            that crossed the ceiling; the caller should log loudly exactly
            once (this is the "never silently drop" contract).
          - `allowed=False, newly_tripped=False`  -- already tripped today;
            the caller should skip writing without re-logging.
        """
        self._roll_if_new_day()
        if self.state.tripped:
            return False, False
        would_be = self.state.bytes_written + nbytes
        if would_be > self.ceiling_bytes:
            self.state.tripped = True
            return False, True
        self.state.bytes_written = would_be
        return True, False


# ---------------------------------------------------------------------------
# 30-second periodic floor: long stretches with no window/workspace change
# still get sampled.
# ---------------------------------------------------------------------------


def should_capture_periodic(
    now: float, last_capture_ts: float | None, *, floor_seconds: float = 30.0
) -> bool:
    if last_capture_ts is None:
        return True
    return (now - last_capture_ts) >= floor_seconds


class PauseDetector:
    """Fires exactly once per idle period, at the moment `idle_seconds`
    have elapsed since the cursor was last seen moving -- not on every
    still sample thereafter, and not again until the cursor moves and goes
    still again."""

    def __init__(self, idle_seconds: float = 3.0) -> None:
        self.idle_seconds = idle_seconds
        self._last_pos: tuple[int, int] | None = None
        self._last_moved_ts: float | None = None
        self._fired_for_current_idle = False

    def sample(self, ts: float, x: int, y: int) -> bool:
        pos = (x, y)
        if pos != self._last_pos:
            self._last_pos = pos
            self._last_moved_ts = ts
            self._fired_for_current_idle = False
            return False
        if self._last_moved_ts is None:
            self._last_moved_ts = ts
            return False
        idle_for = ts - self._last_moved_ts
        if idle_for >= self.idle_seconds and not self._fired_for_current_idle:
            self._fired_for_current_idle = True
            return True
        return False
