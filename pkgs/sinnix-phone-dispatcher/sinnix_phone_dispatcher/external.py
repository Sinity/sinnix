"""Shelling out to the estate CLIs this service dispatches through.

Both `sinnix-steer` and `sinnix-score` are resolved off PATH rather than
imported: this package owns transport, they own their own schemas, and a
Python import coupling would pull the steering store's dependency tree
(claude-code, libnotify) into every process that imports this module. The
Nix package wires both onto the built wrapper's PATH explicitly (pkg.nix's
makeWrapperArgs), replacing the runtimeInputs the script frontmatter used to
declare (`@sinnix-steer @sinnix-score`) before this module had no wrapper of
its own to carry them.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import threading


def steer(*args: str) -> tuple[int, str]:
    """Run sinnix-steer. It owns the steering schema; this package owns transport."""
    exe = shutil.which("sinnix-steer")
    if exe is None:
        return 127, "sinnix-steer is not on PATH"
    proc = subprocess.run([exe, *args], capture_output=True, text=True, timeout=30)
    return proc.returncode, (proc.stdout or proc.stderr).strip()


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
        print(f"phone-dispatcher: score: sinnix-score run did not complete: {exc}", file=sys.stderr)
        return
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        print(f"phone-dispatcher: score: sinnix-score run exited {proc.returncode}: {detail}", file=sys.stderr)
    elif proc.stdout.strip():
        print(f"phone-dispatcher: score: {proc.stdout.strip()}", file=sys.stderr)


def trigger_score() -> None:
    """Score whatever just landed, without making the caller wait for it."""
    threading.Thread(target=_score_worker, daemon=True, name="phone-score").start()
