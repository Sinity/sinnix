from __future__ import annotations

from sinnix_capture_a11y.debounce import Debouncer


def test_first_call_for_a_key_is_always_allowed():
    d = Debouncer(min_interval=5.0, clock=lambda: 100.0)
    assert d.allow("a") is True


def test_calls_within_min_interval_are_suppressed():
    clock = {"t": 0.0}
    d = Debouncer(min_interval=1.0, clock=lambda: clock["t"])

    assert d.allow("a") is True
    clock["t"] = 0.5
    assert d.allow("a") is False


def test_calls_after_min_interval_are_allowed_again():
    clock = {"t": 0.0}
    d = Debouncer(min_interval=1.0, clock=lambda: clock["t"])

    assert d.allow("a") is True
    clock["t"] = 1.5
    assert d.allow("a") is True


def test_keys_are_independent():
    clock = {"t": 0.0}
    d = Debouncer(min_interval=1.0, clock=lambda: clock["t"])

    assert d.allow("a") is True
    assert d.allow("b") is True
