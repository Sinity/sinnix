"""Executing one intent, from either plane: the send_token dedup, the intent
kind dispatch, and the two side-channel deliveries (job answers, shared text)
an intent's execution can land."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

from sinnix_lib.ledger import utc_ts

from .external import steer, trigger_score
from .state import LAKE_ROOT, TOKEN_RE, TOKENS_DIR, emit_receipt, ensure_dirs


def seen_token(token: str) -> bool:
    if not token or not TOKEN_RE.match(token):
        return False
    return (TOKENS_DIR / token).exists()


def mark_token(token: str, result: str) -> None:
    if not token or not TOKEN_RE.match(token):
        return
    ensure_dirs()
    (TOKENS_DIR / token).write_text(f"{utc_ts()} {result}\n", encoding="utf-8")


def execute(intent: dict) -> dict:
    """Run one intent. Returns what the phone should be told.

    Every branch ends in a receipt, including the duplicate branch. A phone
    that sent something live and then had it re-drained must not be left
    wondering which delivery counted — it counted once, and it hears about it
    once either way.
    """
    kind = str(intent.get("kind") or "")
    token = str(intent.get("send_token") or "")

    if token and seen_token(token):
        return {"ok": True, "duplicate": True, "kind": kind}

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
        intentions = intent.get("intentions") or []
        added = 0
        detail = []
        for row in intentions if isinstance(intentions, list) else []:
            if not isinstance(row, dict):
                continue
            code, out = steer(
                "intent",
                "add",
                str(row.get("id") or row.get("title") or "intention"),
                "--forecast",
                str(row.get("probability") or 0.5),
            )
            if code == 0:
                added += 1
            else:
                detail.append(out)
        result = {"ok": True, "added": added, "detail": detail}
        emit_receipt(
            "steering_ritual",
            "Intentions recorded",
            f"{added} committed for today",
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
            "steering_resolve", "Resolved", f"{item}: {outcome}", token, "home"
        )
    elif kind == "job_answer":
        result = deliver_job_answer(intent)
        emit_receipt(
            "job_answer",
            "Answer delivered" if result.get("ok") else "Answer queued",
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

    mark_token(token, "ok" if result.get("ok") else "failed")
    result["kind"] = kind
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
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    answers = Path(
        os.environ.get("SINNIX_AGENT_ANSWER_DIR", f"{runtime}/sinnix/agent-answers")
    )
    try:
        answers.mkdir(parents=True, exist_ok=True)
        target = answers / f"{job_id}.json"
        tmp = target.with_suffix(".json.part")
        tmp.write_text(
            json.dumps({"job_id": job_id, "answer": answer, "at": utc_ts()}) + "\n",
            encoding="utf-8",
        )
        tmp.rename(target)
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
