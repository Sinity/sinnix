"""The file plane: dispatching drained intents. A malformed intent file is
left in place (loudly, on stderr) rather than deleted, and a successfully
executed one is removed so a crash mid-sweep repeats rather than loses work.

Mutation that would fail this: deleting the intent file even when execute()
returns ok=False fails test_failed_intent_file_is_kept_not_deleted.
"""

from __future__ import annotations

import argparse
import json
import threading
from pathlib import Path

import sinnix_phone_dispatcher.dispatch as dispatch_mod
import sinnix_phone_dispatcher.execute as execute_mod
from test_server import _handler


def _args(outbox: Path) -> argparse.Namespace:
    return argparse.Namespace(outbox=str(outbox))


def test_executed_intent_file_is_removed(monkeypatch, tmp_path) -> None:
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "intent-1.json").write_text(
        json.dumps({"kind": "mark", "send_token": "tok-1"})
    )

    monkeypatch.setattr(
        dispatch_mod, "execute", lambda intent: {"ok": True, "kind": intent["kind"]}
    )

    dispatch_mod.cmd_dispatch(_args(outbox))

    assert not (outbox / "intent-1.json").exists()


def test_failed_intent_file_is_kept_not_deleted(monkeypatch, tmp_path) -> None:
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "intent-1.json").write_text(
        json.dumps({"kind": "job_answer", "send_token": "tok-1"})
    )

    monkeypatch.setattr(
        dispatch_mod, "execute", lambda intent: {"ok": False, "detail": "no answer"}
    )

    assert dispatch_mod.cmd_dispatch(_args(outbox)) == 1

    assert (outbox / "intent-1.json").exists()


def test_malformed_json_file_is_kept_not_deleted(tmp_path) -> None:
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "intent-1.json").write_text("{not json")

    dispatch_mod.cmd_dispatch(_args(outbox))

    assert (outbox / "intent-1.json").exists()


def test_missing_outbox_is_a_quiet_no_op(tmp_path) -> None:
    assert dispatch_mod.cmd_dispatch(_args(tmp_path / "does-not-exist")) == 0


def _resolve(token: str, item: str = "a") -> dict:
    return {
        "kind": "steering_resolve",
        "id": item,
        "outcome": "done",
        "send_token": token,
    }


def test_file_and_http_delivery_share_one_execution_slot(monkeypatch, tmp_path):
    """The file route holds the token while steer blocks; the HTTP route must
    wait and then answer the recorded outcome. Anti-vacuity: without the token
    lock both routes see no record and steer is called twice. This asserts one
    owned transition, not an exactly-once external effect."""
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    intent = _resolve("two-routes")
    path = outbox / "intent-1.json"
    path.write_text(json.dumps(intent))
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def steer(*args):
        calls.append(args)
        entered.set()
        assert release.wait(5)
        return 0, "ok"

    monkeypatch.setattr(execute_mod, "steer", steer)
    codes = []
    file_thread = threading.Thread(
        target=lambda: codes.append(dispatch_mod.cmd_dispatch(_args(outbox)))
    )
    file_thread.start()
    assert entered.wait(5)
    body = json.dumps(intent).encode()
    handler, sent = _handler("/v1/intent", body, str(len(body)))
    http_thread = threading.Thread(target=handler.do_POST)
    http_thread.start()
    http_thread.join(0.3)
    assert http_thread.is_alive(), "HTTP delivery did not wait for the slot"
    release.set()
    file_thread.join(5)
    http_thread.join(5)
    assert not file_thread.is_alive() and not http_thread.is_alive()
    assert len(calls) == 1
    assert codes == [0] and not path.exists()
    status, answer = sent[0]
    assert status == 200 and answer["duplicate"] is True and answer["ok"] is True


def test_file_route_keeps_conflicting_and_failed_intents(monkeypatch, tmp_path):
    """Anti-vacuity: deleting on `duplicate` or on any answer would remove a
    file whose request never completed."""
    results = iter([(0, "ok"), (2, "store busy"), (0, "ok")])
    monkeypatch.setattr(execute_mod, "steer", lambda *a: next(results))
    assert execute_mod.execute(_resolve("file-conflict"))["ok"] is True

    outbox = tmp_path / "outbox"
    outbox.mkdir()
    conflicting = outbox / "intent-1.json"
    conflicting.write_text(json.dumps(_resolve("file-conflict", item="b")))
    failing = outbox / "intent-2.json"
    failing.write_text(json.dumps(_resolve("file-failed")))

    assert dispatch_mod.cmd_dispatch(_args(outbox)) == 1
    assert conflicting.is_file() and failing.is_file()

    # A definitive failure is retried by the next sweep and then completes;
    # the conflict stays refused.
    assert dispatch_mod.cmd_dispatch(_args(outbox)) == 1
    assert conflicting.is_file() and not failing.exists()
