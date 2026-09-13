"""The phone inbox contract, shared by the dispatcher and the scorer."""

import json

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
