"""Executing one intent, from either plane: the send_token ledger, the intent
kind dispatch, and the two side-channel deliveries (job answers, shared text)
an intent's execution can land.

Every answer carries `ok` and a typed `outcome`, and both planes read them the
same way: only `ok` (a completed effect, first time or repeated) lets the
sender forget its copy. The HTTP routes answer 200 for every outcome, because
the phone app's outbox treats a non-2xx as "prime is unreachable" and would
re-post a refused intent at the head of its queue forever; an `ok:false` body
is what lets it set the intent aside instead."""

from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sinnix_lib.atomic import atomic_publish
from sinnix_lib.ledger import utc_ts

from .external import steer, trigger_score
from .state import LAKE_ROOT, TOKEN_RE, TOKENS_DIR, emit_receipt, ensure_dirs

# Outcomes a token record can hold. `failed` is the only non-success a retry
# may execute again: the effect definitively did not happen. `in_flight` on
# disk, found by a caller that now holds the token's lock, means the process
# that wrote it died mid-effect, which is `indeterminate` by another name.
# `partial` is a batch where some actions landed and some did not; repeating
# it would repeat the ones that landed.
COMPLETED = "completed"
FAILED = "failed"
IN_FLIGHT = "in_flight"
INDETERMINATE = "indeterminate"
PARTIAL = "partial"
# Answer-only outcomes, never recorded: the token is not this request's to use.
CONFLICT = "conflict"
REFUSED = "refused"

# The steering ritual's forecast when the phone sends none (absent or null).
# An explicit 0 is a forecast, not an absence, and is passed through as 0.
DEFAULT_PROBABILITY = 0.5


def _answer(kind: str, outcome: str, detail: str) -> dict:
    return {"ok": False, "outcome": outcome, "kind": kind, "detail": detail}


def _record(token: str, digest: str, outcome: str, result: dict | None = None) -> None:
    atomic_publish(
        TOKENS_DIR / token,
        (
            json.dumps(
                {"at": utc_ts(), "digest": digest, "outcome": outcome, "result": result}
            )
            + "\n"
        ).encode(),
        fsync=True,
        mode=0o600,
    )


@contextmanager
def _token_lock(token: str) -> Iterator[None]:
    """Hold the token's execution slot across processes.

    The server and the `dispatch` verb are separate processes that can both
    hold the same intent (posted live, and queued as a file), so an in-process
    lock is not enough. The lock file name starts with `.`, which no accepted
    token can, so a lock and a record never share a name.
    """
    ensure_dirs()
    fd = os.open(TOKENS_DIR / f".{token}.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _content_digest(intent: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            intent, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def execute(intent: dict) -> dict:
    """Run one intent. Returns what the phone should be told.

    A send_token binds one request's content to one execution slot. A repeat
    of completed content returns the recorded answer, marked `duplicate`,
    without acting again; a repeat of failed content runs again; a repeat of
    an indeterminate or partial effect is refused rather than guessed at; and
    the same token on different content is refused as a conflict.

    An intent without a token (the live /job-answer route sends none) runs
    without the ledger. A token that is present but malformed is refused: it
    would otherwise run unprotected while the sender believes it is keyed.
    """
    kind = str(intent.get("kind") or "")
    token = intent.get("send_token")
    if token is None or token == "":
        return _finish(_perform(intent, kind, ""), kind)
    if not isinstance(token, str) or not TOKEN_RE.fullmatch(token) or token[0] == ".":
        return _answer(kind, REFUSED, "invalid send_token")
    try:
        digest = _content_digest(intent)
    except (TypeError, ValueError):
        return _answer(kind, REFUSED, "intent content is not canonical JSON")

    with _token_lock(token):
        path = TOKENS_DIR / token
        if path.exists():
            try:
                prior = json.loads(path.read_text(encoding="utf-8"))
                prior_digest = prior["digest"]
                prior_outcome = prior["outcome"]
            except (OSError, ValueError, KeyError, TypeError):
                # Includes the one-line records written before tokens were
                # bound to content: what ran under them cannot be matched.
                return _answer(kind, INDETERMINATE, "token record is unreadable")
            if prior_digest != digest:
                return _answer(kind, CONFLICT, "send_token belongs to other content")
            if prior_outcome == COMPLETED:
                return {**prior["result"], "duplicate": True}
            if prior_outcome == PARTIAL:
                # The recorded answer again, but never marked `duplicate`:
                # the phone forgets anything so marked, and this is not done.
                return prior["result"]
            if prior_outcome != FAILED:
                return _answer(kind, INDETERMINATE, "a prior attempt may have acted")
        _record(token, digest, IN_FLIGHT)
        try:
            result = _finish(_perform(intent, kind, token), kind)
        except Exception as exc:  # noqa: BLE001 - the effect may already have run
            _record(token, digest, INDETERMINATE)
            return _answer(kind, INDETERMINATE, f"execution was interrupted: {exc}")
        _record(token, digest, result["outcome"], result)
        return result


def _finish(result: dict, kind: str) -> dict:
    result["kind"] = kind
    result.setdefault("outcome", COMPLETED if result.get("ok") else FAILED)
    return result


def _probability(row: dict) -> str | None:
    """The forecast to pass on, or None when the row's value is not one."""
    value = row.get("probability")
    if value is None:
        return str(DEFAULT_PROBABILITY)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not 0 <= value <= 1:
        return None
    return str(value)


def _perform(intent: dict, kind: str, token: str) -> dict:
    result: dict[str, Any]
    if kind == "ready_send":
        # The ready queue's SEND is a request, never a send. Prime performs the
        # outward action; the phone only ever asked for it.
        item = str(intent.get("id") or "")
        code, out = steer("intent", "done", item) if item else (2, "no id")
        result = {"ok": code == 0, "detail": out}
        emit_receipt(
            "ready_send",
            "Sent" if code == 0 else "Could not send",
            out or item,
            token,
            "ready",
        )
    elif kind == "steering_ritual":
        intentions = intent.get("intentions")
        if intentions is None:
            intentions = []
        if not isinstance(intentions, list):
            return {"ok": False, "detail": "intentions must be a list"}
        added = 0
        detail = []
        for row in intentions:
            if not isinstance(row, dict):
                detail.append("an intention is not an object")
                continue
            forecast = _probability(row)
            if forecast is None:
                detail.append(f"invalid probability {row.get('probability')!r}")
                continue
            code, out = steer(
                "intent",
                "add",
                str(row.get("id") or row.get("title") or "intention"),
                "--forecast",
                forecast,
            )
            if code == 0:
                added += 1
            else:
                detail.append(out)
        total = len(intentions)
        result = {
            "ok": added == total,
            "added": added,
            "total": total,
            "detail": detail,
        }
        if added and added < total:
            result["outcome"] = PARTIAL
        emit_receipt(
            "steering_ritual",
            "Intentions recorded"
            if added == total
            else "Intentions incomplete"
            if added
            else "Intentions not recorded",
            f"{added} of {total} committed for today",
            token,
            "home",
        )
    elif kind == "steering_resolve":
        item = str(intent.get("id") or "")
        outcome = str(intent.get("outcome") or "")
        verb = {"done": "done", "missed": "miss", "partly": "done"}.get(outcome)
        if verb and item:
            code, out = steer("intent", verb, item)
        else:
            code, out = 2, f"unknown outcome {outcome!r}"
        result = {"ok": code == 0, "detail": out}
        emit_receipt(
            "steering_resolve",
            "Resolved" if code == 0 else "Could not resolve",
            f"{item}: {outcome}",
            token,
            "home",
        )
    elif kind == "job_answer":
        result = deliver_job_answer(intent)
        emit_receipt(
            "job_answer",
            "Answer delivered" if result.get("ok") else "Answer not delivered",
            str(result.get("detail") or ""),
            token,
            # A navigation target in the app, not a name for anything here:
            # the string is matched against the phone's own screen routes.
            # Renamed on both sides at once (the app's Destination.PRIME and
            # its Prime tab), because one side alone sends a tapped
            # notification to a route the app does not have. An in-flight
            # receipt carrying the older value is harmless -- the app matches
            # the route against its known destinations and opens home when it
            # does not recognise one.
            "prime",
        )
    elif kind in ("shared_text", "shared_file"):
        result = land_shared(intent)
        # No receipt: sharing is fire-and-forget by design, and a notification
        # per shared link would make the verb cost more than it saves.
    elif kind in ("ema_answer", "mark", "voice_note", "trace"):
        # These are records, not requests. They reach the lake through the
        # events plane and the blob drain; there is nothing for prime to do
        # except acknowledge that they arrived.
        result = {"ok": True, "recorded": kind}
        if kind in ("voice_note", "trace"):
            # The intent's arrival is the signal that a trace or a voice note
            # landed in the outbox: this JSON is the acknowledgement, and the
            # blob itself came in beside it. Scored on arrival rather than on
            # a schedule -- `sinnix-score run` re-scans the whole outbox and
            # dedups against its own ledger, so triggering it here costs a
            # no-op sweep when there is nothing new and saves the wait when
            # there is.
            trigger_score()
    else:
        result = {"ok": False, "detail": f"unknown intent kind {kind!r}"}

    return result


def deliver_job_answer(intent: dict) -> dict:
    """Hand an operator's answer to a waiting agent job.

    Written into the gateway's own answer directory rather than posted at the
    agent: the job may have moved, restarted, or be between polls, and a file
    it picks up when it next looks is the only delivery that survives all of
    those.
    """
    job_id = str(intent.get("job_id") or "")
    answer = str(intent.get("answer") or "")
    if not job_id or not answer:
        return {"ok": False, "detail": "job_answer needs job_id and answer"}
    if Path(job_id).name != job_id or job_id in {".", ".."}:
        return {"ok": False, "detail": "job_answer needs a safe job_id"}
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    answers = Path(
        os.environ.get("SINNIX_AGENT_ANSWER_DIR", f"{runtime}/sinnix/agent-answers")
    )
    try:
        answers.mkdir(parents=True, exist_ok=True)
        target = answers / f"{job_id}.json"
        atomic_publish(
            target,
            (
                json.dumps({"job_id": job_id, "answer": answer, "at": utc_ts()}) + "\n"
            ).encode(),
            fsync=True,
            mode=0o600,
        )
        return {"ok": True, "detail": f"answer left for {job_id}"}
    except OSError as exc:
        return {"ok": False, "detail": f"could not write answer: {exc}"}


def land_shared(intent: dict) -> dict:
    """Put shared text where the lake keeps it.

    Files shared from the phone come through the blob drain as real files; only
    the text form needs a home written here, and a dated JSONL is the same
    shape every other capture lane uses.
    """
    day = dt.datetime.now(dt.timezone.utc).date().isoformat()
    target = LAKE_ROOT / "shared" / f"{day}.jsonl"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(intent) + "\n")
        return {"ok": True, "detail": str(target)}
    except OSError as exc:
        return {"ok": False, "detail": str(exc)}
