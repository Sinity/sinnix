"""The app's event log arriving as byte ranges: positional writes, a retry
that changes nothing, and a gap that is refused rather than padded.

Mutations that would fail these:

* appending at the END of the day file instead of pwrite-ing at the offset the
  batch declares fails test_partially_overlapping_batch_lands_only_the_new_tail
  (the overlap is duplicated instead of rewritten in place) -- verified by
  mutation; a fully replayed batch is caught one step earlier, by the
  offset-behind-cursor branch, which is what
  test_replayed_batch_leaves_the_file_identical pins;
* accepting an offset beyond prime's cursor fails
  test_a_gap_is_refused_with_primes_cursor (the file gets a NUL-padded hole);
* verifying the sha256 after the write instead of before fails
  test_sha_mismatch_writes_nothing.
"""

from __future__ import annotations

import hashlib
from http import HTTPStatus

import sinnix_phone_dispatcher.uploads as uploads_mod


def _sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _day_file(isolated_state_dirs):
    return isolated_state_dirs["events_dir"] / "events-20260818.jsonl"


def test_first_batch_creates_the_day_file(isolated_state_dirs) -> None:
    body = b'{"kind":"mark"}\n'

    status, payload = uploads_mod.append_events("20260818", 0, body, _sha(body))

    assert status == HTTPStatus.OK
    assert payload["duplicate"] is False
    assert payload["cursor"] == len(body)
    assert _day_file(isolated_state_dirs).read_bytes() == body


def test_consecutive_batches_extend_the_same_file(isolated_state_dirs) -> None:
    first = b'{"kind":"mark"}\n'
    second = b'{"kind":"chunk_closed"}\n'
    uploads_mod.append_events("20260818", 0, first, _sha(first))

    status, payload = uploads_mod.append_events(
        "20260818", len(first), second, _sha(second)
    )

    assert status == HTTPStatus.OK
    assert payload["cursor"] == len(first) + len(second)
    assert _day_file(isolated_state_dirs).read_bytes() == first + second


def test_replayed_batch_leaves_the_file_identical(isolated_state_dirs) -> None:
    """A lost acknowledgement makes the phone re-send; that must be free."""
    first = b'{"kind":"mark"}\n'
    second = b'{"kind":"chunk_closed"}\n'
    uploads_mod.append_events("20260818", 0, first, _sha(first))
    uploads_mod.append_events("20260818", len(first), second, _sha(second))
    before = _day_file(isolated_state_dirs).read_bytes()

    status, payload = uploads_mod.append_events(
        "20260818", len(first), second, _sha(second)
    )

    assert status == HTTPStatus.OK
    assert payload["duplicate"] is True
    assert _day_file(isolated_state_dirs).read_bytes() == before


def test_partially_overlapping_batch_lands_only_the_new_tail(
    isolated_state_dirs,
) -> None:
    """The phone rewound further than it needed to. The overlap is rewritten
    with identical bytes and only the remainder extends the file."""
    first = b'{"kind":"mark"}\n'
    uploads_mod.append_events("20260818", 0, first, _sha(first))
    overlapping = first + b'{"kind":"power"}\n'

    status, payload = uploads_mod.append_events(
        "20260818", 0, overlapping, _sha(overlapping)
    )

    assert status == HTTPStatus.OK
    assert payload["duplicate"] is False
    assert _day_file(isolated_state_dirs).read_bytes() == overlapping


def test_a_gap_is_refused_with_primes_cursor(isolated_state_dirs) -> None:
    first = b'{"kind":"mark"}\n'
    uploads_mod.append_events("20260818", 0, first, _sha(first))
    ahead = b'{"kind":"much_later"}\n'

    status, payload = uploads_mod.append_events("20260818", 4096, ahead, _sha(ahead))

    assert status == HTTPStatus.CONFLICT
    assert payload["expected_offset"] == len(first)
    assert _day_file(isolated_state_dirs).read_bytes() == first


def test_sha_mismatch_writes_nothing(isolated_state_dirs) -> None:
    status, payload = uploads_mod.append_events(
        "20260818", 0, b'{"kind":"mark"}\n', "0" * 64
    )

    assert status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert payload["ok"] is False
    assert not _day_file(isolated_state_dirs).exists()


def test_a_day_that_is_not_a_date_is_refused(isolated_state_dirs) -> None:
    status, payload = uploads_mod.append_events("../escape", 0, b"x", None)

    assert status == HTTPStatus.BAD_REQUEST
    assert payload["ok"] is False
    assert not isolated_state_dirs["events_dir"].exists()


def test_cursor_reports_what_prime_holds(isolated_state_dirs) -> None:
    body = b'{"kind":"mark"}\n'
    assert uploads_mod.events_cursor("20260818")[1]["bytes"] == 0

    uploads_mod.append_events("20260818", 0, body, _sha(body))

    status, payload = uploads_mod.events_cursor("20260818")
    assert status == HTTPStatus.OK
    assert payload["bytes"] == len(body)


def test_cursor_rejects_a_malformed_day(isolated_state_dirs) -> None:
    status, payload = uploads_mod.events_cursor("2026-08-18")
    assert status == HTTPStatus.BAD_REQUEST
    assert payload["ok"] is False


def test_a_landed_batch_is_mirrored_with_only_its_new_bytes(
    isolated_state_dirs, monkeypatch
) -> None:
    """A batch that arrives is scanned for notification_posted lines, but only
    the part of it this write actually added -- an overlapping retry must not
    re-scan bytes that were already forwarded on the first landing."""
    mirrored = []
    monkeypatch.setattr(
        uploads_mod,
        "mirror_new_events",
        lambda day, new_bytes: mirrored.append((day, new_bytes)),
    )
    first = b'{"kind":"mark"}\n'
    uploads_mod.append_events("20260818", 0, first, _sha(first))
    overlapping = first + b'{"kind":"notification_posted","app":"x"}\n'

    uploads_mod.append_events("20260818", 0, overlapping, _sha(overlapping))

    assert mirrored[-1] == ("20260818", b'{"kind":"notification_posted","app":"x"}\n')


def test_a_pure_replay_mirrors_nothing(isolated_state_dirs, monkeypatch) -> None:
    mirrored = []
    monkeypatch.setattr(
        uploads_mod,
        "mirror_new_events",
        lambda day, new_bytes: mirrored.append((day, new_bytes)),
    )
    first = b'{"kind":"notification_posted","app":"x"}\n'
    uploads_mod.append_events("20260818", 0, first, _sha(first))
    mirrored.clear()

    uploads_mod.append_events("20260818", 0, first, _sha(first))

    assert mirrored == []


def test_a_mirroring_failure_does_not_fail_the_upload(
    isolated_state_dirs, monkeypatch
) -> None:
    def _boom(day, new_bytes):
        raise RuntimeError("notify-send is not installed")

    monkeypatch.setattr(uploads_mod, "mirror_new_events", _boom)
    body = b'{"kind":"notification_posted","app":"x"}\n'

    status, payload = uploads_mod.append_events("20260818", 0, body, _sha(body))

    assert status == HTTPStatus.OK
    assert payload["duplicate"] is False
    assert _day_file(isolated_state_dirs).read_bytes() == body
