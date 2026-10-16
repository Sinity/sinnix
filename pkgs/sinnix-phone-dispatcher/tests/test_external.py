"""Scoring triggers share a bounded worker without losing arrivals."""
import threading

import pytest
from sinnix_phone_dispatcher import external


def test_score_burst_has_one_worker_and_a_followup_pass(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    threads = []
    passes = []
    original_thread = threading.Thread

    def make_thread(*args, **kwargs):
        thread = original_thread(*args, **kwargs)
        threads.append(thread)
        return thread

    def score():
        passes.append(True)
        if len(passes) == 1:
            started.set()
            assert release.wait(3)

    monkeypatch.setattr(external.threading, "Thread", make_thread)
    monkeypatch.setattr(external, "_score_worker", score)
    try:
        external.trigger_score()
        assert started.wait(3)
        for _ in range(20):
            external.trigger_score()
        assert len(threads) == 1
    finally:
        release.set()
        for thread in threads:
            thread.join(3)
            assert not thread.is_alive()
    assert len(passes) == 2

    # Once idle, a later arrival still starts its own pass.
    external.trigger_score()
    threads[-1].join(3)
    assert not threads[-1].is_alive()
    assert len(passes) == 3


def test_score_worker_failure_does_not_strand_later_arrivals(monkeypatch):
    threads = []
    passes = []
    original_thread = threading.Thread

    def make_thread(*args, **kwargs):
        thread = original_thread(*args, **kwargs)
        threads.append(thread)
        return thread

    def score():
        passes.append(True)
        if len(passes) == 1:
            raise RuntimeError("synthetic scoring failure")

    monkeypatch.setattr(external.threading, "Thread", make_thread)
    monkeypatch.setattr(external, "_score_worker", score)
    for _ in range(2):
        external.trigger_score()
        threads[-1].join(3)
        assert not threads[-1].is_alive()
    assert len(passes) == 2


def test_score_thread_start_failure_does_not_strand_later_arrivals(monkeypatch):
    original_thread = threading.Thread
    passes = []
    threads = []

    class FailedThread:
        def start(self):
            raise RuntimeError("synthetic start failure")

    monkeypatch.setattr(external.threading, "Thread", lambda **kwargs: FailedThread())
    with pytest.raises(RuntimeError, match="synthetic start failure"):
        external.trigger_score()

    def make_thread(*args, **kwargs):
        thread = original_thread(*args, **kwargs)
        threads.append(thread)
        return thread

    monkeypatch.setattr(external.threading, "Thread", make_thread)
    monkeypatch.setattr(external, "_score_worker", lambda: passes.append(True))
    external.trigger_score()
    threads[-1].join(3)
    assert not threads[-1].is_alive()
    assert passes == [True]
