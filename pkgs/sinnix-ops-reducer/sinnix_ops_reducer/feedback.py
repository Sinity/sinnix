"""The hub's annotation spool, and the elicit drain it triggers.

Ported from an earlier standalone feedback daemon. The spool file format is
the contract -- agents read `<spool>/<UTC-date>.jsonl` directly, and the
generated reports and elicit sessions POST to `/feedback` -- so the envelope,
its key order, its spacing and its fsync-per-line are reproduced exactly rather
than re-expressed through a shared ledger helper with compact separators.

Deliberately minimal, and each omission is a decision carried over intact:
  * no database -- a JSONL file per UTC day is grep-able, tail-able, and
    survives every failure mode a database introduces;
  * no auth of its own -- the tailnet is the security boundary, same as the
    rest of the hub, and the reducer's socket is the operator's;
  * no read endpoint -- agents read the spool from the filesystem. Serving it
    back would turn a write-only sink into an exfiltration surface for the
    personal analysis those annotations describe;
  * permissive CORS -- reports are also opened straight off disk as file://
    (Origin: null), and the handback must work there too.

What is new is the trigger. An elicit comparison session posts one record per
judgment, and those records used to sit in the spool until a 120s timer drained
them. Arrival is the event, so arrival is what runs the drain -- coalesced,
because a session is a burst of posts and refitting a Bradley-Terry model once
per tap would be absurd.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

SCHEMA = "sinnix-hub-feedback-v1"
ELICIT_SCHEMA = "sinnix-elicit-v1"
MAX_BODY = 1 << 20  # 1 MiB: a generous annotated report, not a file upload


class CoalescingTrigger:
    """Run *command* once, shortly after the last trigger() in a burst.

    The delay is what makes a comparison session one drain instead of thirty.
    Failures are isolated from the caller entirely -- a feedback POST must be
    spooled and answered whether or not anything downstream of it works -- and
    are re-armed exactly once, so a drain that lost a race with itself still
    happens while a persistently broken one cannot spin.
    """

    def __init__(
        self, command: list[str], delay: float = 5.0, timeout: float = 300.0
    ) -> None:
        self.command = command
        self.delay = delay
        self.timeout = timeout
        self._lock = threading.Lock()
        self._pending = False
        self._thread: threading.Thread | None = None

    def trigger(self) -> None:
        with self._lock:
            self._pending = True
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def _loop(self) -> None:
        retried = False
        while True:
            threading.Event().wait(self.delay)
            with self._lock:
                if not self._pending:
                    self._thread = None
                    return
                self._pending = False
            if self._run() or retried:
                retried = False
                continue
            retried = True
            with self._lock:
                self._pending = True

    def _run(self) -> bool:
        try:
            result = subprocess.run(
                self.command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            print(
                f"sinnix-ops-reducer: feedback drain failed: {error}", file=sys.stderr
            )
            return False
        if result.returncode != 0:
            print(
                "sinnix-ops-reducer: feedback drain exited "
                f"{result.returncode}: {result.stderr.strip()[:400]}",
                file=sys.stderr,
            )
            return False
        return True


class FeedbackSpool:
    def __init__(
        self, directory: Path, elicit: CoalescingTrigger | None = None
    ) -> None:
        self.directory = Path(directory)
        self.elicit = elicit
        self.lock = threading.Lock()
        self.sequence = 0

    def append(
        self, payload: Any, page: str | None, agent: str | None
    ) -> dict[str, Any]:
        received = dt.datetime.now(dt.timezone.utc)
        with self.lock:
            self.sequence += 1
            envelope = {
                "schema": SCHEMA,
                "received_at": received.isoformat(timespec="seconds"),
                "sequence": self.sequence,
                "page": page,
                "user_agent": agent,
                "payload": payload,
            }
            self.directory.mkdir(parents=True, exist_ok=True)
            target = self.directory / f"{received:%Y-%m-%d}.jsonl"
            with target.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(envelope, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            # The retired daemon ran under UMask 0022 and the reducer runs
            # under 0077; the spool is read by whatever an agent happens to be
            # running as, so keep the mode the readers were written against.
            os.chmod(target, 0o644)
        if self.elicit is not None and is_elicit(payload):
            self.elicit.trigger()
        return {
            "status": "spooled",
            "sequence": envelope["sequence"],
            "file": str(target),
        }


def is_elicit(payload: Any) -> bool:
    return isinstance(payload, dict) and payload.get("schema") == ELICIT_SCHEMA
