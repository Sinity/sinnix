"""The hub's annotation spool, and the ranking drain it triggers.

Ported from an earlier standalone feedback daemon. The spool file format is
the contract -- agents read `<spool>/<UTC-date>.jsonl` directly, and the
generated reports and `sinnix rank session` pages POST to `/feedback` -- so the envelope,
its key order, its spacing and its fsync-per-line are reproduced exactly rather
than re-expressed through a shared ledger helper with compact separators.

Deliberately minimal, and each omission is a decision carried over intact:
  * no database -- a JSONL file per UTC day is grep-able, tail-able, and
    survives every failure mode a database introduces;
  * no auth of its own -- the tailnet is the security boundary, same as the
    rest of the hub, and the hub server's socket is the operator's;
  * no read endpoint on the spool itself -- agents read the annotation spool
    from the filesystem. Serving arbitrary posted payloads back would turn a
    write-only sink into an exfiltration surface for the personal analysis
    those annotations describe;
  * permissive CORS -- reports are also opened straight off disk as file://
    (Origin: null), and the handback must work there too.

What is new is the trigger. A ranking session page posts one record per
judgment, and those records used to sit in the spool until a 120s timer drained
them. Arrival is the event, so arrival is what runs the drain -- coalesced,
because a session is a burst of posts and draining once per tap would be
absurd.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from sinnix_lib.ledger import append_jsonl

SCHEMA = "sinnix-hub-feedback-v1"
# Stamped by `sinnix rank session` pages on each judgment they post.
RANK_SCHEMA = "sinnix-rank-v1"
MAX_BODY = 1 << 20  # 1 MiB: a generous annotated report, not a file upload


def parse_command_argv(raw: str) -> list[str]:
    """Decode the explicitly serialized command contract for a drain."""
    try:
        command = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("command must be a JSON argv array") from error
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(argument, str) and argument for argument in command)
    ):
        raise ValueError("command must be a nonempty JSON argv array of strings")
    return command


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
            print(f"sinnix-hub-server: feedback drain failed: {error}", file=sys.stderr)
            return False
        if result.returncode != 0:
            print(
                "sinnix-hub-server: feedback drain exited "
                f"{result.returncode}: {result.stderr.strip()[:400]}",
                file=sys.stderr,
            )
            return False
        return True


class FeedbackSpool:
    def __init__(
        self, directory: Path, rank_ingest: CoalescingTrigger | None = None
    ) -> None:
        self.directory = Path(directory)
        self.rank_ingest = rank_ingest
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
            target = self.directory / f"{received:%Y-%m-%d}.jsonl"
            # The spool is read directly by agents, so preserve its readable
            # spacing while sharing the durable append contract.
            append_jsonl(
                target, envelope, mode=0o644, fsync=True, separators=(", ", ": ")
            )
        if self.rank_ingest is not None and is_rank_judgment(payload):
            self.rank_ingest.trigger()
        return {
            "status": "spooled",
            "sequence": envelope["sequence"],
            "file": str(target),
        }


def is_rank_judgment(payload: Any) -> bool:
    return isinstance(payload, dict) and payload.get("schema") == RANK_SCHEMA
