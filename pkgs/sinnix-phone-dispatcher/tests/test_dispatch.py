"""The file plane: dispatching drained intents. A malformed intent file is
left in place (loudly, on stderr) rather than deleted, and a successfully
executed one is removed so a crash mid-sweep repeats rather than loses work.

Mutation that would fail this: deleting the intent file even when execute()
returns ok=False fails test_failed_intent_file_is_kept_not_deleted.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import sinnix_phone_dispatcher.dispatch as dispatch_mod


def _args(outbox: Path) -> argparse.Namespace:
    return argparse.Namespace(outbox=str(outbox))


def test_executed_intent_file_is_removed(monkeypatch, tmp_path) -> None:
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "intent-1.json").write_text(json.dumps({"kind": "mark", "send_token": "tok-1"}))

    monkeypatch.setattr(dispatch_mod, "execute", lambda intent: {"ok": True, "kind": intent["kind"]})

    dispatch_mod.cmd_dispatch(_args(outbox))

    assert not (outbox / "intent-1.json").exists()


def test_failed_intent_file_is_kept_not_deleted(monkeypatch, tmp_path) -> None:
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "intent-1.json").write_text(json.dumps({"kind": "job_answer", "send_token": "tok-1"}))

    monkeypatch.setattr(dispatch_mod, "execute", lambda intent: {"ok": False, "detail": "no answer"})

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


def test_push_writes_glance_and_steering_json(monkeypatch, isolated_state_dirs) -> None:
    monkeypatch.setattr(dispatch_mod, "build_glance", lambda: {"verdict": "quiet"})
    monkeypatch.setattr(dispatch_mod, "build_steering", lambda: {"menu": []})

    dispatch_mod.cmd_push(argparse.Namespace())

    inbox = isolated_state_dirs["inbox_dir"]
    assert json.loads((inbox / "glance.json").read_text()) == {"verdict": "quiet"}
    assert json.loads((inbox / "steering.json").read_text()) == {"menu": []}
