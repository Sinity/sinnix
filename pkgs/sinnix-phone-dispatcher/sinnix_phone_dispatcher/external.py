"""Shelling out to the sinnix CLIs this service dispatches through.

`sinnix-score` is resolved off PATH rather than imported: this package owns
transport, the scorer owns its own schema. The Nix package puts it on the
built wrapper's PATH explicitly (pkg.nix's makeWrapperArgs).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import threading


def _score_worker() -> None:
    """Run `sinnix-score run` in the background and put its outcome in the journal.

    Fire-and-forget on purpose: the intent that triggered this already
    returned its own receipt, and scoring is a separate promise (the receipt
    a hold-still instrument tells the operator will "come back later"). A
    failure here must not fail the intent, and it does not need to be
    retried explicitly -- `sinnix-score run` re-scans the whole outbox and
    dedups against its own ledger, so the very next trace to arrive re-tries
    anything this pass dropped.
    """
    exe = shutil.which("sinnix-score")
    if exe is None:
        print("phone-dispatcher: score: sinnix-score is not on PATH", file=sys.stderr)
        return
    try:
        proc = subprocess.run([exe, "run"], capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(
            f"phone-dispatcher: score: sinnix-score run did not complete: {exc}",
            file=sys.stderr,
        )
        return
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        print(
            f"phone-dispatcher: score: sinnix-score run exited {proc.returncode}: {detail}",
            file=sys.stderr,
        )
    elif proc.stdout.strip():
        print(f"phone-dispatcher: score: {proc.stdout.strip()}", file=sys.stderr)


_score_lock = threading.Lock()
_score_running = False
_score_pending = False


def _score_loop() -> None:
    global _score_running, _score_pending
    while True:
        with _score_lock:
            if not _score_pending:
                _score_running = False
                return
            _score_pending = False
        try:
            _score_worker()
        except Exception as exc:  # noqa: BLE001 - advisory; retain future triggers
            print(f"phone-dispatcher: score: scoring pass failed: {exc}", file=sys.stderr)


def trigger_score() -> None:
    """Request scoring without spawning a process for every arrival.

    A pass re-scans the durable outbox, so arrivals can share one pending
    follow-up pass. Changing pending/running under one lock prevents losing
    a trigger as the worker becomes idle. No intent or trace is discarded.
    """
    global _score_running, _score_pending
    with _score_lock:
        _score_pending = True
        if _score_running:
            return
        _score_running = True
        try:
            threading.Thread(target=_score_loop, daemon=True, name="phone-score").start()
        except BaseException:
            _score_running = False
            raise
