"""The file plane: dispatching drained intents. A malformed intent file is
left in place (loudly, on stderr) rather than deleted, and a successfully
executed one is removed so a crash mid-sweep repeats rather than loses work.

Mutation that would fail this: deleting the intent file even when execute()
returns ok=False fails test_failed_intent_file_is_kept_not_deleted.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import threading
from pathlib import Path

import pytest
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
    return {"kind": "job_answer", "job_id": item, "answer": "yes", "send_token": token}


def test_file_and_http_delivery_share_one_execution_slot(monkeypatch, tmp_path):
    """The file route holds the token while the effect blocks; the HTTP route
    must wait and then answer the recorded outcome. Anti-vacuity: without the
    token lock both routes see no record and the effect runs twice. This asserts one
    owned transition, not an exactly-once external effect."""
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    intent = _resolve("two-routes")
    path = outbox / "intent-1.json"
    path.write_text(json.dumps(intent))
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def deliver(intent):
        calls.append(intent)
        entered.set()
        assert release.wait(5)
        return {"ok": True, "detail": "ok"}

    monkeypatch.setattr(execute_mod, "deliver_job_answer", deliver)
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
    results = iter(
        [
            {"ok": True, "detail": "ok"},
            {"ok": False, "detail": "answer directory busy"},
            {"ok": True, "detail": "ok"},
        ]
    )
    monkeypatch.setattr(execute_mod, "deliver_job_answer", lambda i: next(results))
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


@pytest.mark.parametrize(
    "payload", [b"\xff", b"[]", b"null", b"1", b'{"value":' + b"9" * 5000 + b"}"]
)
def test_unusable_intent_keeps_evidence_and_continues(monkeypatch, tmp_path, payload):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    bad = outbox / "intent-1.json"
    bad.write_bytes(payload)
    good = outbox / "intent-2.json"
    good.write_text('{"kind":"mark"}')
    calls = []
    monkeypatch.setattr(
        dispatch_mod, "execute", lambda intent: calls.append(intent) or {"ok": True}
    )
    assert dispatch_mod.cmd_dispatch(_args(outbox)) == 1
    assert bad.read_bytes() == payload
    assert not good.exists()
    assert calls == [{"kind": "mark"}]


def test_wrong_type_outbox_fails_visibly(tmp_path, capsys):
    outbox = tmp_path / "outbox"
    outbox.write_text("retained object")
    assert dispatch_mod.cmd_dispatch(_args(outbox)) == 1
    assert "unavailable" in capsys.readouterr().err
    assert outbox.read_text() == "retained object"


def test_unreadable_outbox_fails_visibly(monkeypatch, tmp_path, capsys):
    outbox = tmp_path / "outbox"
    outbox.mkdir()

    def denied(path):
        assert isinstance(path, int)
        raise PermissionError("synthetic access denied")

    monkeypatch.setattr(dispatch_mod.os, "scandir", denied)
    assert dispatch_mod.cmd_dispatch(_args(outbox)) == 1
    assert "unavailable" in capsys.readouterr().err


@pytest.mark.parametrize("kind", ["fifo", "directory", "symlink"])
def test_nonregular_intent_is_refused_without_blocking(monkeypatch, tmp_path, kind):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    bad = outbox / "intent-1.json"
    outside = tmp_path / "outside.json"
    outside.write_text('{"kind":"outside"}')
    if kind == "fifo":
        os.mkfifo(bad)
    elif kind == "directory":
        bad.mkdir()
    else:
        bad.symlink_to(outside)
    good = outbox / "intent-2.json"
    good.write_text('{"kind":"mark"}')
    calls = []
    monkeypatch.setattr(
        dispatch_mod, "execute", lambda intent: calls.append(intent) or {"ok": True}
    )

    def timeout(*_):
        raise RuntimeError("dispatch blocked opening a nonregular intent")

    previous = signal.signal(signal.SIGALRM, timeout)
    signal.alarm(2)
    try:
        assert dispatch_mod.cmd_dispatch(_args(outbox)) == 1
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)
    assert bad.lstat()
    assert outside.read_text() == '{"kind":"outside"}'
    assert not good.exists()
    assert calls == [{"kind": "mark"}]


def test_replacement_during_execution_is_preserved(monkeypatch, tmp_path):
    box = tmp_path / "outbox"
    box.mkdir()
    path = box / "intent-1.json"
    path.write_text('{"kind":"old"}')

    def execute(intent):
        assert intent == {"kind": "old"}
        replacement = box / "new"
        replacement.write_text('{"kind":"new"}')
        replacement.replace(path)
        return {"ok": True}

    monkeypatch.setattr(dispatch_mod, "execute", execute)
    assert dispatch_mod.cmd_dispatch(_args(box)) == 1
    assert path.read_text() == '{"kind":"new"}'


def test_replaced_outbox_cannot_redirect_consumption(monkeypatch, tmp_path):
    box = tmp_path / "outbox"
    box.mkdir()
    path = box / "intent-1.json"
    path.write_text('{"kind":"old"}')
    moved = tmp_path / "retained"

    def execute(intent):
        box.rename(moved)
        box.mkdir()
        (box / path.name).write_text('{"kind":"new"}')
        return {"ok": True}

    monkeypatch.setattr(dispatch_mod, "execute", execute)
    assert dispatch_mod.cmd_dispatch(_args(box)) == 0
    assert (box / path.name).read_text() == '{"kind":"new"}'
    assert not (moved / path.name).exists()


def test_replacement_during_consumption_is_retained(monkeypatch, tmp_path, capsys):
    box = tmp_path / "outbox"
    box.mkdir()
    path = box / "intent-1.json"
    path.write_text('{"kind":"old"}')
    original_rename = dispatch_mod.os.rename

    def race(source, destination, **kwargs):
        replacement = box / "replacement"
        replacement.write_text('{"kind":"new"}')
        replacement.replace(path)
        original_rename(source, destination, **kwargs)

    monkeypatch.setattr(dispatch_mod.os, "rename", race)
    monkeypatch.setattr(dispatch_mod, "execute", lambda intent: {"ok": True})
    assert dispatch_mod.cmd_dispatch(_args(box)) == 1
    assert path.read_text() == '{"kind":"new"}'
    assert "retained_at" in capsys.readouterr().err
    claims = list(box.glob(".confirmation-*.json"))
    assert len(claims) == 1 and claims[0].read_bytes() == path.read_bytes()


def test_dispatch_does_not_accept_utf16_as_utf8(monkeypatch, tmp_path):
    box = tmp_path / "outbox"
    box.mkdir()
    path = box / "intent-1.json"
    body = '{"kind":"mark"}'.encode("utf-16")
    path.write_bytes(body)
    monkeypatch.setattr(
        dispatch_mod, "execute", lambda intent: pytest.fail("non-UTF8 intent executed")
    )
    assert dispatch_mod.cmd_dispatch(_args(box)) == 1
    assert path.read_bytes() == body
