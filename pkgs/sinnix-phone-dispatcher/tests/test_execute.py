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

import json

import sinnix_phone_dispatcher.execute as execute_mod


def test_second_execution_with_same_token_is_a_noop_duplicate(monkeypatch) -> None:
    calls = []

    def fake_steer(*args):
        calls.append(args)
        return 0, "ok"

    monkeypatch.setattr(execute_mod, "steer", fake_steer)

    intent = {
        "kind": "steering_resolve",
        "id": "item-1",
        "outcome": "done",
        "send_token": "tok-abc",
    }
    first = execute_mod.execute(dict(intent))
    second = execute_mod.execute(dict(intent))

    assert first.get("duplicate") is not True
    assert second == {**first, "duplicate": True}
    # The steer subprocess ran exactly once: the duplicate branch returns
    # before the kind dispatch, so a re-drained intent never re-executes the
    # outward action.
    assert len(calls) == 1


def test_a_different_token_still_executes(monkeypatch) -> None:
    monkeypatch.setattr(execute_mod, "steer", lambda *a: (0, "ok"))

    a = execute_mod.execute(
        {
            "kind": "steering_resolve",
            "id": "x",
            "outcome": "done",
            "send_token": "tok-a",
        }
    )
    b = execute_mod.execute(
        {
            "kind": "steering_resolve",
            "id": "x",
            "outcome": "done",
            "send_token": "tok-b",
        }
    )

    assert a.get("duplicate") is not True
    assert b.get("duplicate") is not True


def test_only_voice_note_and_trace_trigger_scoring(monkeypatch) -> None:
    triggered = []
    monkeypatch.setattr(execute_mod, "trigger_score", lambda: triggered.append(True))

    for kind in ("mark", "ema_answer", "voice_note", "trace"):
        execute_mod.execute({"kind": kind, "send_token": f"tok-{kind}"})

    assert len(triggered) == 2


def test_steering_resolve_leaves_a_real_receipt_on_disk(
    monkeypatch, isolated_state_dirs
) -> None:
    """No emit_receipt monkeypatch here: execute() must run the actual
    state.py -> sinnix_lib.phone_inbox write and land a real file, not just
    call something named emit_receipt."""
    monkeypatch.setattr(execute_mod, "steer", lambda *a: (0, "ok"))

    execute_mod.execute(
        {
            "kind": "steering_resolve",
            "id": "item-1",
            "outcome": "done",
            "send_token": "tok-disk",
        }
    )

    receipts = list(isolated_state_dirs["receipts_dir"].iterdir())
    assert len(receipts) == 1
    payload = json.loads(receipts[0].read_text())
    assert payload["kind"] == "steering_resolve"
    assert payload["title"] == "Resolved"
    assert payload["body"] == "item-1: done"
    assert payload["send_token"] == "tok-disk"
    assert payload["route"] == "home"


def test_shared_text_emits_no_receipt(monkeypatch) -> None:
    emitted = []
    monkeypatch.setattr(execute_mod, "emit_receipt", lambda *a, **kw: emitted.append(a))

    result = execute_mod.execute(
        {"kind": "shared_text", "text": "hello", "send_token": "tok-share"}
    )

    assert result["ok"] is True
    assert emitted == []


def test_job_answer_is_private_and_rejects_path_traversal(
    monkeypatch, tmp_path
) -> None:
    answers = tmp_path / "answers"
    monkeypatch.setenv("SINNIX_AGENT_ANSWER_DIR", str(answers))

    result = execute_mod.deliver_job_answer({"job_id": "42", "answer": "yes"})
    target = answers / "42.json"
    assert result["ok"] is True
    assert json.loads(target.read_text())["answer"] == "yes"
    assert target.stat().st_mode & 0o777 == 0o600
    assert list(answers.glob("*.part")) == []
    assert (
        execute_mod.deliver_job_answer({"job_id": "../escape", "answer": "no"})["ok"]
        is False
    )
    assert not (tmp_path / "escape.json").exists()


def test_token_conflict_and_failed_retry(monkeypatch):
    calls = []

    def steer(*args):
        calls.append(args)
        return (2, "failed") if len(calls) == 1 else (0, "done")

    monkeypatch.setattr(execute_mod, "steer", steer)
    intent = {
        "kind": "steering_resolve",
        "id": "a",
        "outcome": "done",
        "send_token": "retry",
    }
    assert execute_mod.execute(intent)["outcome"] == "failed"
    assert execute_mod.execute({**intent, "id": "b"})["outcome"] == "conflict"
    assert execute_mod.execute(intent)["outcome"] == "completed"
    assert len(calls) == 2


def test_indeterminate_effect_is_not_replayed(monkeypatch):
    calls = []

    def uncertain(*args):
        calls.append(args)
        raise RuntimeError("connection lost")

    monkeypatch.setattr(execute_mod, "steer", uncertain)
    intent = {"kind": "ready_send", "id": "a", "send_token": "uncertain"}
    assert execute_mod.execute(intent)["outcome"] == "indeterminate"
    assert execute_mod.execute(intent)["outcome"] == "indeterminate"
    assert len(calls) == 1


def test_ritual_zero_default_and_partial_failure(monkeypatch):
    forecasts = []

    def steer(*args):
        forecasts.append(args[-1])
        return (0, "ok") if len(forecasts) == 1 else (2, "rejected")

    monkeypatch.setattr(execute_mod, "steer", steer)
    intent = {
        "kind": "steering_ritual",
        "send_token": "ritual",
        "intentions": [{"id": "a", "probability": 0}, {"id": "b"}],
    }
    result = execute_mod.execute(intent)
    assert forecasts == ["0", "0.5"]
    assert result["ok"] is False and result["added"] == 1
    assert result["outcome"] == "indeterminate"
    assert execute_mod.execute(intent)["outcome"] == "indeterminate"
    assert len(forecasts) == 2


def test_ritual_all_failed_is_retryable(monkeypatch):
    calls = []
    monkeypatch.setattr(
        execute_mod, "steer", lambda *args: calls.append(args) or (2, "rejected")
    )
    intent = {
        "kind": "steering_ritual",
        "send_token": "all-failed",
        "intentions": [{"id": "a"}],
    }
    first = execute_mod.execute(intent)
    second = execute_mod.execute(intent)
    assert first["ok"] is False and first["outcome"] == "failed"
    assert second["ok"] is False and second["outcome"] == "failed"
    assert len(calls) == 2
