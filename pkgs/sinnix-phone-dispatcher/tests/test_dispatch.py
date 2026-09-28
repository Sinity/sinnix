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

    dispatch_mod.cmd_dispatch(_args(outbox))

    assert (outbox / "intent-1.json").exists()


def test_malformed_json_file_is_kept_not_deleted(tmp_path) -> None:
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "intent-1.json").write_text("{not json")

    dispatch_mod.cmd_dispatch(_args(outbox))

    assert (outbox / "intent-1.json").exists()


def test_missing_outbox_is_a_quiet_no_op(tmp_path) -> None:
    assert dispatch_mod.cmd_dispatch(_args(tmp_path / "does-not-exist")) == 0


def test_file_and_http_share_one_token_transition(monkeypatch, tmp_path):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    intent = {
        "kind": "steering_resolve",
        "id": "a",
        "outcome": "done",
        "send_token": "two-routes",
    }
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
    file_thread = threading.Thread(
        target=dispatch_mod.cmd_dispatch, args=(_args(outbox),)
    )
    file_thread.start()
    assert entered.wait(5)
    body = json.dumps(intent).encode()
    handler, sent = _handler("/v1/intent", body, str(len(body)))
    http_thread = threading.Thread(target=handler.do_POST)
    http_thread.start()
    release.set()
    file_thread.join(5)
    http_thread.join(5)
    assert not file_thread.is_alive() and not http_thread.is_alive()
    assert len(calls) == 1
    assert sent[0][1]["duplicate"] is True
    assert not path.exists()


def test_file_route_keeps_conflicting_content(monkeypatch, tmp_path):
    monkeypatch.setattr(execute_mod, "steer", lambda *args: (0, "ok"))
    first = {
        "kind": "steering_resolve",
        "id": "a",
        "outcome": "done",
        "send_token": "file-conflict",
    }
    assert execute_mod.execute(first)["ok"] is True
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    path = outbox / "intent-1.json"
    path.write_text(json.dumps({**first, "id": "b"}))
    assert dispatch_mod.cmd_dispatch(_args(outbox)) == 1
    assert path.is_file()
