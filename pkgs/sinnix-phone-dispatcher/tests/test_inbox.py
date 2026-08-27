"""The downward direction the phone now fetches instead of prime pushing:
listing with hashes, name validation, and what a confirmation consumes.

Mutations that would fail these:

* deleting a confirmed entry without comparing the sha256 to the file still
  present fails test_confirming_a_stale_sha_does_not_delete;
* treating decks (or the generated state files) as one-shots fails
  test_confirming_a_deck_keeps_it -- the shelf would lose an instrument the
  moment the phone read it;
* accepting a name outside the three known subdirectories fails
  test_traversal_names_are_refused.
"""

from __future__ import annotations

import hashlib
import json
from http import HTTPStatus

import pytest
import sinnix_phone_dispatcher.inbox as inbox_mod


@pytest.fixture(autouse=True)
def stub_generated(monkeypatch):
    """The two generated entries are built from live host state (the ops
    reducer's socket); this suite is about the inbox mechanics, so they are
    replaced by builders with no dependencies."""
    monkeypatch.setattr(
        inbox_mod,
        "GENERATED",
        {
            "glance.json": lambda: {"attention": []},
            "steering.json": lambda: {"ready": []},
        },
    )


def _write(isolated_state_dirs, sub: str, name: str, text: str) -> None:
    d = isolated_state_dirs["inbox_dir"] / sub
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(text, encoding="utf-8")


def test_listing_carries_a_sha_the_bytes_match(isolated_state_dirs) -> None:
    _write(isolated_state_dirs, "receipts", "r1.json", '{"title":"Scored"}\n')

    _, payload = inbox_mod.list_inbox()
    entry = next(f for f in payload["files"] if f["name"] == "receipts/r1.json")

    status, body = inbox_mod.read_inbox("receipts/r1.json")
    assert status == HTTPStatus.OK
    assert hashlib.sha256(body).hexdigest() == entry["sha256"]
    assert entry["one_shot"] is True


def test_generated_state_is_served_without_a_file(isolated_state_dirs) -> None:
    _, payload = inbox_mod.list_inbox()
    names = [f["name"] for f in payload["files"]]
    assert "glance.json" in names and "steering.json" in names

    status, body = inbox_mod.read_inbox("glance.json")
    assert status == HTTPStatus.OK
    assert json.loads(body) == {"attention": []}
    assert not (isolated_state_dirs["inbox_dir"] / "glance.json").exists()


def test_generated_hash_ignores_request_time(monkeypatch, isolated_state_dirs) -> None:
    calls = iter(["2026-08-27T10:00:00Z", "2026-08-27T10:01:00Z"])
    monkeypatch.setattr(
        inbox_mod,
        "GENERATED",
        {"glance.json": lambda: {"generated_at": next(calls), "attention": []}},
    )

    _, first = inbox_mod.list_inbox()
    _, second = inbox_mod.list_inbox()

    assert first["files"][0]["sha256"] == second["files"][0]["sha256"]


def test_a_half_written_receipt_is_not_offered(isolated_state_dirs) -> None:
    _write(isolated_state_dirs, "receipts", "r1.json.part", '{"title":"hal')

    _, payload = inbox_mod.list_inbox()

    assert [f for f in payload["files"] if f["name"].startswith("receipts/")] == []


def test_confirming_a_receipt_deletes_it(isolated_state_dirs) -> None:
    text = '{"title":"Scored"}\n'
    _write(isolated_state_dirs, "receipts", "r1.json", text)
    digest = hashlib.sha256(text.encode()).hexdigest()

    status, payload = inbox_mod.confirm_inbox("receipts/r1.json", digest)

    assert status == HTTPStatus.OK
    assert payload["deleted"] is True
    assert not (isolated_state_dirs["receipts_dir"] / "r1.json").exists()


def test_reconfirming_a_gone_receipt_is_a_success(isolated_state_dirs) -> None:
    status, payload = inbox_mod.confirm_inbox("receipts/gone.json", "0" * 64)

    assert status == HTTPStatus.OK
    assert payload["already_gone"] is True


def test_confirming_a_stale_sha_does_not_delete(isolated_state_dirs) -> None:
    _write(isolated_state_dirs, "receipts", "r1.json", '{"title":"Scored"}\n')

    status, payload = inbox_mod.confirm_inbox("receipts/r1.json", "0" * 64)

    assert status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert payload["ok"] is False
    assert (isolated_state_dirs["receipts_dir"] / "r1.json").is_file()


def test_confirming_a_deck_keeps_it(isolated_state_dirs) -> None:
    text = '{"engine":"reaction"}\n'
    _write(isolated_state_dirs, "decks", "pvt.json", text)

    status, payload = inbox_mod.confirm_inbox(
        "decks/pvt.json", hashlib.sha256(text.encode()).hexdigest()
    )

    assert status == HTTPStatus.OK
    assert payload["retained"] is True
    assert (isolated_state_dirs["decks_dir"] / "pvt.json").is_file()


@pytest.mark.parametrize(
    "name",
    [
        "../../etc/passwd",
        "receipts/../../escape",
        "tokens/abcd",
        "receipts/",
        "receipts/.hidden",
    ],
)
def test_traversal_names_are_refused(name) -> None:
    assert inbox_mod.read_inbox(name)[0] == HTTPStatus.BAD_REQUEST
    assert inbox_mod.confirm_inbox(name, "0" * 64)[0] == HTTPStatus.BAD_REQUEST


def test_a_missing_entry_is_a_404(isolated_state_dirs) -> None:
    status, payload = inbox_mod.read_inbox("notify/nothing.json")
    assert status == HTTPStatus.NOT_FOUND
    assert payload["ok"] is False
