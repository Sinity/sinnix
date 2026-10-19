"""The phone inbox contract, shared by the dispatcher and the scorer."""

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sinnix_lib import phone_inbox


def test_receipt_payload_shape(tmp_path):
    path = phone_inbox.emit_receipt(
        tmp_path, "score", "Pulse", "62 bpm", "tok-1", route="score/pulse"
    )
    payload = json.loads(path.read_text())
    assert payload == {
        "schema": "sinnix.phone.receipt/1",
        "kind": "score",
        "title": "Pulse",
        "body": "62 bpm",
        "send_token": "tok-1",
        "route": "score/pulse",
        "at": payload["at"],
    }
    assert path.parent == tmp_path


def test_notify_payload_has_no_intent_fields(tmp_path):
    path = phone_inbox.emit_notify(tmp_path, "Backup", "Done", route="ops")
    assert set(json.loads(path.read_text())) == {
        "schema",
        "title",
        "body",
        "route",
        "at",
    }


def test_message_is_private_and_leaves_no_temporary(tmp_path):
    path = phone_inbox.emit_receipt(tmp_path, "k", "t", "b", None)

    assert path.stat().st_mode & 0o777 == 0o600
    assert [p.name for p in tmp_path.iterdir()] == [path.name]


def test_names_are_unique_within_a_second(tmp_path):
    a = phone_inbox.emit_receipt(tmp_path, "k", "t", "b", None)
    b = phone_inbox.emit_receipt(tmp_path, "k", "t", "b", None)
    assert a != b
    assert len(list(tmp_path.iterdir())) == 2


def test_new_message_directory_is_private_under_permissive_umask(tmp_path):
    previous = os.umask(0o022)
    try:
        path = phone_inbox.emit_notify(tmp_path / "new-inbox", "Fixture", "Unchanged")
    finally:
        os.umask(previous)
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text())["body"] == "Unchanged"


def test_collision_retries_without_overwriting_message(tmp_path, monkeypatch):
    retained = tmp_path / "collision.json"
    retained.write_bytes(b"previous message")
    names = iter(["collision.json", "fresh.json"])
    monkeypatch.setattr(phone_inbox, "message_name", lambda: next(names))
    payload = {"fixture": "new message"}
    result = phone_inbox.write_message(tmp_path, payload)
    assert retained.read_bytes() == b"previous message"
    assert result.name == "fresh.json" and json.loads(result.read_text()) == payload
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "collision.json",
        "fresh.json",
    ]


def test_exhausted_names_preserve_existing_message(tmp_path, monkeypatch):
    retained = tmp_path / "collision.json"
    retained.write_bytes(b"previous message")
    monkeypatch.setattr(phone_inbox, "message_name", lambda: "collision.json")
    with pytest.raises(FileExistsError, match="unique phone inbox message"):
        phone_inbox.write_message(tmp_path, {"fixture": "new message"})
    assert retained.read_bytes() == b"previous message"
    assert list(tmp_path.iterdir()) == [retained]


def test_concurrent_same_name_messages_both_survive(tmp_path, monkeypatch):
    barrier = threading.Barrier(2)
    local = threading.local()

    def name():
        if not getattr(local, "attempted", False):
            local.attempted = True
            barrier.wait(timeout=5)
            return "same-name.json"
        return "retry-" + threading.current_thread().name + ".json"

    monkeypatch.setattr(phone_inbox, "message_name", name)
    with ThreadPoolExecutor(max_workers=2) as workers:
        paths = list(
            workers.map(
                lambda n: phone_inbox.write_message(tmp_path, {"fixture": n}), [1, 2]
            )
        )
    assert paths[0] != paths[1]
    assert sorted(json.loads(p.read_text())["fixture"] for p in paths) == [1, 2]
    assert len(list(tmp_path.iterdir())) == 2
