"""Intent execution: send_token idempotency and the score-on-arrival trigger
guard (only voice_note/trace intents score; every other recorded kind must
not).

Mutations that would fail these: removing the `seen_token` check at the top
of execute() (so a re-drained intent runs its side effect twice) fails
test_second_execution_with_same_token_is_a_noop_duplicate; moving
trigger_score() outside the `if kind in ("voice_note", "trace")` guard (so
every recorded kind scores) fails
test_only_voice_note_and_trace_trigger_scoring.
"""

from __future__ import annotations

import sinnix_phone_dispatcher.execute as execute_mod


def test_second_execution_with_same_token_is_a_noop_duplicate(monkeypatch) -> None:
    calls = []

    def fake_steer(*args):
        calls.append(args)
        return 0, "ok"

    monkeypatch.setattr(execute_mod, "steer", fake_steer)

    intent = {"kind": "steering_resolve", "id": "item-1", "outcome": "done", "send_token": "tok-abc"}
    first = execute_mod.execute(dict(intent))
    second = execute_mod.execute(dict(intent))

    assert first.get("duplicate") is not True
    assert second == {"ok": True, "duplicate": True, "kind": "steering_resolve"}
    # The steer subprocess ran exactly once: the duplicate branch returns
    # before the kind dispatch, so a re-drained intent never re-executes the
    # outward action.
    assert len(calls) == 1


def test_a_different_token_still_executes(monkeypatch) -> None:
    monkeypatch.setattr(execute_mod, "steer", lambda *a: (0, "ok"))

    a = execute_mod.execute({"kind": "steering_resolve", "id": "x", "outcome": "done", "send_token": "tok-a"})
    b = execute_mod.execute({"kind": "steering_resolve", "id": "x", "outcome": "done", "send_token": "tok-b"})

    assert a.get("duplicate") is not True
    assert b.get("duplicate") is not True


def test_only_voice_note_and_trace_trigger_scoring(monkeypatch) -> None:
    triggered = []
    monkeypatch.setattr(execute_mod, "trigger_score", lambda: triggered.append(True))

    for kind in ("mark", "ema_answer", "voice_note", "trace"):
        execute_mod.execute({"kind": kind, "send_token": f"tok-{kind}"})

    assert len(triggered) == 2


def test_shared_text_emits_no_receipt(monkeypatch) -> None:
    emitted = []
    monkeypatch.setattr(execute_mod, "emit_receipt", lambda *a, **kw: emitted.append(a))

    result = execute_mod.execute({"kind": "shared_text", "text": "hello", "send_token": "tok-share"})

    assert result["ok"] is True
    assert emitted == []
