"""Intent execution: send_token idempotency and the score-on-arrival trigger
guard (only voice_note/trace intents score; every other recorded kind must
not).

Mutations that would fail these: removing the token-record check at the top
of execute() (so a re-drained intent runs its side effect twice) fails
test_second_execution_with_same_token_is_a_noop_duplicate; moving
trigger_score() outside the `if kind in ("voice_note", "trace")` guard (so
every recorded kind scores) fails
test_only_voice_note_and_trace_trigger_scoring.
"""

from __future__ import annotations

import json

import pytest
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


def _resolve(token: str, item: str = "a") -> dict:
    return {
        "kind": "steering_resolve",
        "id": item,
        "outcome": "done",
        "send_token": token,
    }


def test_token_is_bound_to_content_and_a_failure_stays_retryable(monkeypatch):
    """Anti-vacuity: the conflicting call must not reach steer (calls stays 2),
    and the failed-then-retried token must reach it again (not return the
    recorded failure)."""
    calls = []

    def steer(*args):
        calls.append(args)
        return (2, "store busy") if len(calls) == 1 else (0, "done")

    monkeypatch.setattr(execute_mod, "steer", steer)
    intent = _resolve("retry")

    failed = execute_mod.execute(intent)
    assert failed["ok"] is False and failed["outcome"] == "failed"
    conflict = execute_mod.execute(_resolve("retry", item="b"))
    assert conflict["ok"] is False and conflict["outcome"] == "conflict"
    retried = execute_mod.execute(intent)
    assert retried["ok"] is True and retried["outcome"] == "completed"
    repeat = execute_mod.execute(intent)
    assert repeat["duplicate"] is True and repeat["ok"] is True
    assert len(calls) == 2


def test_an_interrupted_effect_is_not_replayed(monkeypatch):
    """Anti-vacuity: a second call that re-ran steer would make calls == 2."""
    calls = []

    def uncertain(*args):
        calls.append(args)
        raise TimeoutError("steer did not answer")

    monkeypatch.setattr(execute_mod, "steer", uncertain)
    intent = {"kind": "ready_send", "id": "a", "send_token": "uncertain"}
    first = execute_mod.execute(intent)
    second = execute_mod.execute(intent)
    assert first["outcome"] == second["outcome"] == "indeterminate"
    assert first["ok"] is second["ok"] is False
    assert second.get("duplicate") is not True
    assert len(calls) == 1


def test_an_in_flight_record_left_by_a_dead_process_is_indeterminate(
    monkeypatch, isolated_state_dirs
):
    """Anti-vacuity: steer is never called, so a replay of the stale slot fails."""
    monkeypatch.setattr(
        execute_mod, "steer", lambda *a: pytest.fail("replayed an in-flight effect")
    )
    intent = _resolve("crashed")
    isolated_state_dirs["tokens_dir"].mkdir(parents=True)
    execute_mod._record("crashed", execute_mod._content_digest(intent), "in_flight")
    assert execute_mod.execute(intent)["outcome"] == "indeterminate"


def test_a_legacy_token_record_is_not_guessed_at(monkeypatch, isolated_state_dirs):
    monkeypatch.setattr(
        execute_mod, "steer", lambda *a: pytest.fail("acted on an unmatched token")
    )
    isolated_state_dirs["tokens_dir"].mkdir(parents=True)
    (isolated_state_dirs["tokens_dir"] / "old").write_text("2026-09-01T00:00:00Z ok\n")
    result = execute_mod.execute(_resolve("old"))
    assert result["ok"] is False and result["outcome"] == "indeterminate"


def test_a_malformed_token_is_refused_and_no_token_runs_unkeyed(
    monkeypatch, tmp_path, isolated_state_dirs
):
    """The live /job-answer route sends no token; it must still deliver."""
    monkeypatch.setattr(
        execute_mod, "steer", lambda *a: pytest.fail("ran under a refused token")
    )
    for bad in ("..", ".hidden", "a/b", 7):
        refused = execute_mod.execute(_resolve(bad))
        assert refused["ok"] is False and refused["outcome"] == "refused"

    monkeypatch.setenv("SINNIX_AGENT_ANSWER_DIR", str(tmp_path / "answers"))
    answered = execute_mod.execute({"kind": "job_answer", "job_id": "7", "answer": "y"})
    assert answered["ok"] is True and answered["outcome"] == "completed"
    assert (tmp_path / "answers" / "7.json").is_file()
    assert not isolated_state_dirs["tokens_dir"].exists() or not any(
        p for p in isolated_state_dirs["tokens_dir"].iterdir() if p.name[0] != "."
    )


def test_ritual_forecasts_keep_zero_and_default_only_the_absent(monkeypatch):
    """Anti-vacuity: `probability or 0.5` turns the explicit 0 into "0.5"."""
    forecasts = []
    monkeypatch.setattr(
        execute_mod, "steer", lambda *a: forecasts.append(a[-1]) or (0, "ok")
    )
    result = execute_mod.execute(
        {
            "kind": "steering_ritual",
            "send_token": "forecasts",
            "intentions": [
                {"id": "a", "probability": 0},
                {"id": "b"},
                {"id": "c", "probability": None},
                {"id": "d", "probability": 0.9},
            ],
        }
    )
    assert forecasts == ["0", "0.5", "0.5", "0.9"]
    assert result["ok"] is True and result["outcome"] == "completed"
    assert result["added"] == result["total"] == 4


def test_a_partial_ritual_is_not_success_and_not_replayed(
    monkeypatch, isolated_state_dirs
):
    """Anti-vacuity: a replay would append to forecasts; a success receipt or
    a `duplicate` marker would let the phone forget an unfinished request."""
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
    assert result["ok"] is False and result["outcome"] == "partial"
    assert (result["added"], result["total"]) == (1, 2)
    again = execute_mod.execute(intent)
    assert again["ok"] is False and again["outcome"] == "partial"
    assert again.get("duplicate") is not True
    assert len(forecasts) == 2
    (receipt,) = [
        json.loads(p.read_text()) for p in isolated_state_dirs["receipts_dir"].iterdir()
    ]
    assert receipt["title"] == "Intentions incomplete"
    assert receipt["body"] == "1 of 2 committed for today"


def test_an_all_failed_ritual_is_a_retryable_failure(monkeypatch, isolated_state_dirs):
    calls = []
    monkeypatch.setattr(
        execute_mod, "steer", lambda *a: calls.append(a) or (2, "rejected")
    )
    intent = {
        "kind": "steering_ritual",
        "send_token": "all-failed",
        "intentions": [{"id": "a"}, {"id": "b", "probability": 2}],
    }
    first = execute_mod.execute(intent)
    second = execute_mod.execute(intent)
    assert first["ok"] is False and first["outcome"] == "failed"
    assert second["ok"] is False and second["outcome"] == "failed"
    # The out-of-range forecast never reaches steer; the valid row is retried.
    assert len(calls) == 2
    titles = {
        json.loads(p.read_text())["title"]
        for p in isolated_state_dirs["receipts_dir"].iterdir()
    }
    assert titles == {"Intentions not recorded"}


@pytest.mark.parametrize("outcome", ["completed", "partial", "failed"])
@pytest.mark.parametrize(
    "result",
    [
        None,
        [],
        {},
        {"ok": True, "outcome": "wrong"},
        {"ok": False, "outcome": "completed", "kind": "steering_resolve"},
        {"ok": True, "outcome": "completed", "kind": "another_action"},
    ],
)
def test_malformed_terminal_token_is_indeterminate_and_never_replayed(
    monkeypatch, isolated_state_dirs, outcome, result
):
    intent = _resolve("malformed-terminal")
    monkeypatch.setattr(
        execute_mod,
        "steer",
        lambda *args: pytest.fail("replayed malformed terminal evidence"),
    )
    isolated_state_dirs["tokens_dir"].mkdir(parents=True)
    execute_mod._record(
        intent["send_token"], execute_mod._content_digest(intent), outcome, result
    )
    before = (isolated_state_dirs["tokens_dir"] / intent["send_token"]).read_bytes()
    answer = execute_mod.execute(intent)
    assert answer["ok"] is False and answer["outcome"] == "indeterminate"
    assert (
        isolated_state_dirs["tokens_dir"] / intent["send_token"]
    ).read_bytes() == before
