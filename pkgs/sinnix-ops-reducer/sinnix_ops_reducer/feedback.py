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
  * no read endpoint on the spool itself -- agents read the annotation spool
    from the filesystem. Serving arbitrary posted payloads back would turn a
    write-only sink into an exfiltration surface for the personal analysis
    those annotations describe;
  * permissive CORS -- reports are also opened straight off disk as file://
    (Origin: null), and the handback must work there too.

What is new is the trigger. An elicit comparison session posts one record per
judgment, and those records used to sit in the spool until a 120s timer drained
them. Arrival is the event, so arrival is what runs the drain -- coalesced,
because a session is a burst of posts and refitting a Bradley-Terry model once
per tap would be absurd.

Also new: a narrow, bounded READ for elicit's own fitted model
(`resolve_elicit_model`), which is a different thing from the spool's "no
read endpoint" decision above and does not revisit it. The spool refusal is
about serving back *arbitrary posted payloads* -- the personal-analysis
annotations an operator writes about a report, which the operator never
asked to see echoed over the network. An elicit domain's `model.json` is
not that: it is a derived Bradley-Terry fit over items the operator
themselves defined (`sinnix elicit init`), on this same host, and the
in-session "learning so far" preview a comparison page wants to show is
just that fit read back mid-session rather than after the next full page
load. Bounded the same way the rest of the hub is bounded: domain names are
validated against a fixed charset, and the resolved path must stay under
the configured preferences root -- never an arbitrary filesystem read.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

SCHEMA = "sinnix-hub-feedback-v1"
ELICIT_SCHEMA = "sinnix-elicit-v1"
MAX_BODY = 1 << 20  # 1 MiB: a generous annotated report, not a file upload

# Mirrors sinnix-elicit's own BASE_DIR default (scripts/sinnix-elicit); a
# domain writes its model at <root>/<domain>/model.json.
ELICIT_MODEL_DIR_DEFAULT = Path("/realm/state/elicit")
ELICIT_DOMAIN_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def resolve_elicit_model(base_dir: Path, domain: str) -> Path | None:
    """The `model.json` path for *domain* under *base_dir*, or None if the
    domain name is not a plain identifier or the resolved path would not
    stay under the configured root (defence in depth alongside the charset
    check -- a domain of "." or ".." never matches the regex, but a
    resolved-path check costs nothing and does not rely on the regex being
    the only guard). Existence is the caller's problem, not this
    function's: a missing model.json (no `rank` run yet) is a normal state,
    not a rejected request."""
    if not ELICIT_DOMAIN_RE.match(domain):
        return None
    root = base_dir.resolve()
    candidate = (base_dir / domain / "model.json").resolve()
    if candidate != root and root not in candidate.parents:
        return None
    return candidate


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
