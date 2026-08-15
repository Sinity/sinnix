from __future__ import annotations

import numpy as np
import pytest
from PIL import Image
from sinnix_capture_screen.hashing import (
    CaptureAttemptGate,
    DailyThrottleGuard,
    PauseDetector,
    hamming_distance,
    is_degenerate_frame,
    is_near_duplicate,
    phash64,
    should_capture_periodic,
)


def test_capture_attempt_gate_coalesces_a_31_event_burst() -> None:
    gate = CaptureAttemptGate(min_interval_seconds=1.0)

    attempts = sum(gate.allow(100.0) for _ in range(31))

    assert attempts == 1


def test_capture_attempt_gate_backs_off_after_failure_then_recovers() -> None:
    gate = CaptureAttemptGate(min_interval_seconds=1.0, failure_backoff_seconds=30.0)
    assert gate.allow(100.0) is True
    gate.record_failure(100.0)

    assert gate.allow(101.0) is False
    assert gate.allow(129.999) is False
    assert gate.allow(130.0) is True


def test_capture_attempt_gate_resumes_at_normal_rate_after_success() -> None:
    gate = CaptureAttemptGate(min_interval_seconds=1.0)
    assert gate.allow(100.0) is True
    gate.record_success()

    assert gate.allow(100.999) is False
    assert gate.allow(101.0) is True


# ---------------------------------------------------------------------------
# phash64 / hamming_distance / is_near_duplicate
# ---------------------------------------------------------------------------


def _checkerboard(size: int = 32) -> np.ndarray:
    xs, ys = np.meshgrid(np.arange(size), np.arange(size))
    return ((xs // 4 + ys // 4) % 2 * 255).astype(np.float64)


def _gradient(size: int = 32) -> np.ndarray:
    return np.tile(np.linspace(0, 255, size), (size, 1))


def _smooth_ui_like(size: int = 32, seed: int = 7) -> np.ndarray:
    """A smooth, non-degenerate synthetic pattern standing in for a
    realistic mostly-static desktop frame (anti-aliased panels/gradients):
    a small random low-resolution grid, bilinearly upsampled. Unlike a
    clean analytic sinusoid (whose DCT has many exact-zero coefficients at
    this sample size -- a pathological case where the phash median itself
    sits at a tie and any perturbation flips many bits), the random
    low-res source gives generically non-zero, spread-out low-frequency
    DCT energy -- representative of real image content."""
    rng = np.random.default_rng(seed)
    small = rng.uniform(0, 255, size=(8, 8))
    im = Image.fromarray(small.astype(np.uint8), mode="L").resize(
        (size, size), Image.BILINEAR
    )
    return np.asarray(im, dtype=np.float64)


def test_phash64_is_deterministic() -> None:
    img = _checkerboard()
    assert phash64(img) == phash64(img.copy())


def test_phash64_returns_64_bit_value_for_8x8_hash_size() -> None:
    img = _checkerboard()
    h = phash64(img, hash_size=8)
    assert 0 <= h < (1 << 64)


def test_phash64_rejects_non_square_array() -> None:
    with pytest.raises(ValueError):
        phash64(np.zeros((32, 16)))


def test_phash64_distinguishes_very_different_images() -> None:
    checker = phash64(_checkerboard())
    gradient = phash64(_gradient())
    # Two structurally different images should not collide near-perfectly.
    assert hamming_distance(checker, gradient) > 4


def test_phash64_is_robust_to_tiny_pixel_noise() -> None:
    """The whole point of a perceptual hash over a cryptographic one: a
    near-identical frame (sub-pixel render noise between two consecutive
    captures of an otherwise-static window) hashes CLOSE, not essentially
    at random. A broken/non-perceptual hash (e.g. hashing raw pixel bytes)
    would show ~32/64 differing bits here (50%, i.e. uncorrelated) for any
    perturbation at all; this asserts far below that."""
    base = _smooth_ui_like()
    rng = np.random.default_rng(1234)
    noisy = np.clip(base + rng.normal(0, 2.0, base.shape), 0, 255)
    distance = hamming_distance(phash64(base), phash64(noisy))
    assert distance <= 6, (
        f"expected a small, correlated hash distance, got {distance}/64 bits"
    )


def test_hamming_distance_identical_is_zero() -> None:
    assert hamming_distance(0b1010, 0b1010) == 0


def test_hamming_distance_counts_differing_bits() -> None:
    assert hamming_distance(0b0000, 0b1111) == 4


def test_is_near_duplicate_true_for_first_ever_frame_is_false() -> None:
    # No previous hash for this window yet -> never a duplicate.
    assert is_near_duplicate(None, phash64(_checkerboard())) is False


def test_is_near_duplicate_true_for_identical_frame() -> None:
    h = phash64(_checkerboard())
    assert is_near_duplicate(h, h, threshold=4) is True


def test_is_near_duplicate_false_for_dissimilar_frame() -> None:
    checker = phash64(_checkerboard())
    gradient = phash64(_gradient())
    assert is_near_duplicate(checker, gradient, threshold=4) is False


def test_is_near_duplicate_threshold_is_inclusive_boundary() -> None:
    # Construct two hashes exactly `threshold` bits apart and confirm the
    # boundary is <=, not <.
    a = 0
    b = 0b1111  # 4 bits set
    assert hamming_distance(a, b) == 4
    assert is_near_duplicate(a, b, threshold=4) is True
    assert is_near_duplicate(a, b, threshold=3) is False


# ---------------------------------------------------------------------------
# is_degenerate_frame
# ---------------------------------------------------------------------------


def test_is_degenerate_frame_true_for_flat_black() -> None:
    assert is_degenerate_frame(np.zeros((32, 32))) is True


def test_is_degenerate_frame_true_for_flat_nonblack() -> None:
    assert is_degenerate_frame(np.full((32, 32), 128.0)) is True


def test_is_degenerate_frame_false_for_real_content() -> None:
    assert is_degenerate_frame(_checkerboard()) is False


def test_is_degenerate_frame_false_for_gradient() -> None:
    assert is_degenerate_frame(_gradient()) is False


# ---------------------------------------------------------------------------
# DailyThrottleGuard -- the runaway-bug backstop
# ---------------------------------------------------------------------------


def test_throttle_guard_allows_writes_under_ceiling() -> None:
    guard = DailyThrottleGuard(ceiling_bytes=1000, clock=lambda: 0.0)
    allowed, newly_tripped = guard.allow(400)
    assert (allowed, newly_tripped) == (True, False)
    allowed, newly_tripped = guard.allow(400)
    assert (allowed, newly_tripped) == (True, False)
    assert guard.state.bytes_written == 800


def test_throttle_guard_trips_exactly_once_when_ceiling_crossed() -> None:
    guard = DailyThrottleGuard(ceiling_bytes=1000, clock=lambda: 0.0)
    guard.allow(900)
    allowed, newly_tripped = guard.allow(200)  # would_be = 1100 > 1000
    assert (allowed, newly_tripped) == (False, True)
    # Second call after tripping: refused again, but NOT re-flagged as newly
    # tripped -- the "log loudly exactly once" contract.
    allowed, newly_tripped = guard.allow(1)
    assert (allowed, newly_tripped) == (False, False)


def test_throttle_guard_never_silently_allows_past_ceiling() -> None:
    guard = DailyThrottleGuard(ceiling_bytes=100, clock=lambda: 0.0)
    guard.allow(90)
    allowed, _ = guard.allow(50)
    assert allowed is False
    # A mutation that made `allow()` always return True (silently dropping
    # the ceiling entirely) would make this assertion fail.
    assert guard.state.bytes_written == 90


def test_throttle_guard_resets_on_new_utc_day() -> None:
    clock = {"t": 0.0}
    guard = DailyThrottleGuard(ceiling_bytes=100, clock=lambda: clock["t"])
    guard.allow(90)
    assert guard.state.bytes_written == 90
    clock["t"] += 86400  # next day
    allowed, newly_tripped = guard.allow(90)
    assert (allowed, newly_tripped) == (True, False)
    assert guard.state.bytes_written == 90  # not 180 -- the day rolled over


def test_throttle_guard_restores_persisted_state() -> None:
    from sinnix_capture_screen.hashing import ThrottleState

    state = ThrottleState(day="2026-08-12", bytes_written=999_999_000, tripped=False)
    guard = DailyThrottleGuard(
        ceiling_bytes=1_000_000_000, clock=lambda: 0.0, state=state
    )
    # Force the same day so the guard doesn't roll over the restored state.
    guard._roll_if_new_day = lambda: None  # type: ignore[method-assign]
    allowed, newly_tripped = guard.allow(2000)
    assert (allowed, newly_tripped) == (False, True)


# ---------------------------------------------------------------------------
# should_capture_periodic -- the 30s floor
# ---------------------------------------------------------------------------


def test_should_capture_periodic_true_on_first_ever_capture() -> None:
    assert should_capture_periodic(now=100.0, last_capture_ts=None) is True


def test_should_capture_periodic_false_before_floor_elapses() -> None:
    assert (
        should_capture_periodic(now=110.0, last_capture_ts=100.0, floor_seconds=30.0)
        is False
    )


def test_should_capture_periodic_true_once_floor_elapses() -> None:
    assert (
        should_capture_periodic(now=130.0, last_capture_ts=100.0, floor_seconds=30.0)
        is True
    )


def test_should_capture_periodic_boundary_is_inclusive() -> None:
    assert (
        should_capture_periodic(now=130.0, last_capture_ts=100.0, floor_seconds=30.0)
        is True
    )
    assert (
        should_capture_periodic(now=129.999, last_capture_ts=100.0, floor_seconds=30.0)
        is False
    )


# ---------------------------------------------------------------------------
# PauseDetector -- the idle-pause trigger heuristic
# ---------------------------------------------------------------------------


def test_pause_detector_does_not_fire_while_moving() -> None:
    pd = PauseDetector(idle_seconds=3.0)
    assert pd.sample(0.0, 0, 0) is False
    assert pd.sample(1.0, 5, 5) is False
    assert pd.sample(2.0, 10, 10) is False


def test_pause_detector_fires_once_after_idle_threshold() -> None:
    pd = PauseDetector(idle_seconds=3.0)
    pd.sample(0.0, 100, 100)  # first sample establishes position
    assert pd.sample(1.0, 100, 100) is False  # only 1s stationary
    assert pd.sample(2.9, 100, 100) is False  # just under threshold
    assert pd.sample(3.0, 100, 100) is True  # crosses threshold: fires


def test_pause_detector_does_not_refire_while_still_idle() -> None:
    pd = PauseDetector(idle_seconds=3.0)
    pd.sample(0.0, 100, 100)
    assert pd.sample(3.0, 100, 100) is True
    assert pd.sample(4.0, 100, 100) is False
    assert pd.sample(10.0, 100, 100) is False


def test_pause_detector_refires_after_movement_and_new_idle_period() -> None:
    pd = PauseDetector(idle_seconds=3.0)
    pd.sample(0.0, 100, 100)
    assert pd.sample(3.0, 100, 100) is True
    # cursor moves, resets the idle clock
    assert pd.sample(3.5, 200, 200) is False
    assert pd.sample(4.0, 200, 200) is False
    assert pd.sample(6.5, 200, 200) is True
