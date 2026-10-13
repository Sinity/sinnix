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
import os
import stat

import pytest
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


def test_noncanonical_days_are_refused_without_creating_files(isolated_state_dirs):
    for day in ("20260818\n", "２０２６０８１８"):
        assert uploads_mod.events_cursor(day)[0] == HTTPStatus.BAD_REQUEST
        assert uploads_mod.append_events(day, 0, b"fixture\n", None)[0] == HTTPStatus.BAD_REQUEST
    assert not isolated_state_dirs["events_dir"].exists()


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


def test_a_conflicting_overlap_is_refused_without_a_cursor(isolated_state_dirs):
    """Anti-vacuity: the old length-only check acknowledged this batch as a
    duplicate; a cursor in the refusal would make the phone skip past it."""
    original = b"abcdefgh"
    assert uploads_mod.append_events("20260818", 0, original, _sha(original))[0] == (
        HTTPStatus.OK
    )
    for offset, body in ((3, b"XYZ123"), (2, b"cX")):
        status, payload = uploads_mod.append_events(
            "20260818", offset, body, _sha(body)
        )
        assert status == HTTPStatus.CONFLICT and payload["ok"] is False
        assert "expected_offset" not in payload
    assert _day_file(isolated_state_dirs).read_bytes() == original


def test_short_pwrites_are_completed(isolated_state_dirs, monkeypatch):
    """Deterministic partial-write injection: every pwrite writes at most two
    bytes. Anti-vacuity: a single pwrite would land "ab" and still ack."""
    real = uploads_mod.os.pwrite
    calls = []

    def short(fd, data, offset):
        calls.append(offset)
        return real(fd, data[:2], offset)

    monkeypatch.setattr(uploads_mod.os, "pwrite", short)
    first = b"abc\n"
    uploads_mod.append_events("20260818", 0, first, _sha(first))
    body = b"abc\ndefg\n"  # overlaps the first batch, extends it
    status, payload = uploads_mod.append_events("20260818", 0, body, _sha(body))
    assert status == HTTPStatus.OK and payload["cursor"] == len(body)
    assert calls == [0, 2, 4, 6, 8]
    assert _day_file(isolated_state_dirs).read_bytes() == body


def test_a_pwrite_that_makes_no_progress_fails_visibly(
    isolated_state_dirs, monkeypatch
):
    monkeypatch.setattr(uploads_mod.os, "pwrite", lambda fd, data, offset: 0)
    body = b"abc\n"
    status, payload = uploads_mod.append_events("20260818", 0, body, _sha(body))
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR and payload["ok"] is False


@pytest.mark.parametrize("kind", ["fifo", "directory", "symlink", "dangling_symlink"])
def test_nonregular_day_is_not_empty_or_acknowledged(isolated_state_dirs, monkeypatch, kind):
    target = _day_file(isolated_state_dirs)
    target.parent.mkdir(parents=True)
    other = target.parent / "retained.jsonl"
    original = b"retained fixture\n"
    if kind == "fifo":
        os.mkfifo(target)
    elif kind == "directory":
        target.mkdir()
    else:
        if kind == "symlink":
            other.write_bytes(original)
        target.symlink_to(other)
    real_open = os.open

    def checked_open(path, flags, *args, **kwargs):
        if path == target:
            assert flags & os.O_NONBLOCK and flags & os.O_NOFOLLOW
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(uploads_mod.os, "open", checked_open)
    status, result = uploads_mod.events_cursor("20260818")
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR and result["ok"] is False
    assert "bytes" not in result
    body = b"new fixture\n"
    status, result = uploads_mod.append_events("20260818", 0, body, _sha(body))
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR and result["ok"] is False
    assert "cursor" not in result
    if kind == "symlink":
        assert other.read_bytes() == original
    if kind == "dangling_symlink":
        assert not other.exists()


def test_replacement_during_append_is_not_acknowledged(isolated_state_dirs, monkeypatch):
    target = _day_file(isolated_state_dirs)
    retired = target.with_suffix(".retained")
    real_write = os.pwrite
    replacement = b"replacement fixture\n"

    def replace_after_write(fd, data, offset):
        count = real_write(fd, data, offset)
        target.rename(retired)
        target.write_bytes(replacement)
        return count

    monkeypatch.setattr(uploads_mod.os, "pwrite", replace_after_write)
    body = b"new fixture\n"
    status, result = uploads_mod.append_events("20260818", 0, body, _sha(body))
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR and result["ok"] is False
    assert "cursor" not in result
    assert target.read_bytes() == replacement and retired.read_bytes() == body


def test_missing_day_gap_does_not_create_an_empty_file(isolated_state_dirs):
    body = b"new fixture\n"
    status, result = uploads_mod.append_events("20260818", 5, body, _sha(body))
    assert status == HTTPStatus.CONFLICT and result["expected_offset"] == 0
    assert not _day_file(isolated_state_dirs).exists()


def test_short_preads_are_completed(isolated_state_dirs, monkeypatch):
    real_read = os.pread
    monkeypatch.setattr(uploads_mod.os, "pread", lambda fd, size, offset: real_read(fd, min(size, 2), offset))
    body = b"new fixture\n"
    status, result = uploads_mod.append_events("20260818", 0, body, _sha(body))
    assert status == HTTPStatus.OK and result["cursor"] == len(body)
    assert _day_file(isolated_state_dirs).read_bytes() == body


def test_readonly_exact_replay_is_still_acknowledged(isolated_state_dirs):
    target = _day_file(isolated_state_dirs)
    target.parent.mkdir(parents=True)
    body = b"retained fixture\n"
    target.write_bytes(body)
    target.chmod(0o440)
    status, result = uploads_mod.append_events("20260818", 0, body, _sha(body))
    assert status == HTTPStatus.OK and result["duplicate"] is True
    assert target.read_bytes() == body and target.stat().st_mode & 0o777 == 0o440


def test_readonly_capture_does_not_acknowledge_missing_suffix(isolated_state_dirs):
    target = _day_file(isolated_state_dirs)
    target.parent.mkdir(parents=True)
    target.write_bytes(b"retained fixture\n")
    target.chmod(0o440)
    body = b"new fixture\n"
    status, result = uploads_mod.append_events("20260818", target.stat().st_size, body, _sha(body))
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR and result["ok"] is False
    assert target.read_bytes() == b"retained fixture\n"


def test_append_and_exact_replay_sync_file_and_directory(isolated_state_dirs, monkeypatch):
    real_sync = os.fsync
    synced = []

    def sync(fd):
        synced.append("directory" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file")
        real_sync(fd)

    monkeypatch.setattr(uploads_mod.os, "fsync", sync)
    body = b"retained fixture\n"
    assert uploads_mod.append_events("20260818", 0, body, _sha(body))[0] == HTTPStatus.OK
    assert synced[0] == "file" and synced[1:] and set(synced[1:]) == {"directory"}
    synced.clear()
    assert uploads_mod.append_events("20260818", 0, body, _sha(body))[1]["duplicate"] is True
    assert synced[0] == "file" and synced[1:] and set(synced[1:]) == {"directory"}


@pytest.mark.parametrize("fail_directory", [False, True])
def test_failed_sync_is_not_acknowledged_on_replay(isolated_state_dirs, monkeypatch, fail_directory):
    body = b"retained fixture\n"
    real_sync = os.fsync

    def fail(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode) is fail_directory:
            raise OSError("synthetic sync failure")
        real_sync(fd)

    monkeypatch.setattr(uploads_mod.os, "fsync", fail)
    for _ in range(2):
        status, result = uploads_mod.append_events("20260818", 0, body, _sha(body))
        assert status == HTTPStatus.INTERNAL_SERVER_ERROR and result["ok"] is False
        assert _day_file(isolated_state_dirs).read_bytes() == body
    monkeypatch.setattr(uploads_mod.os, "fsync", real_sync)
    assert uploads_mod.append_events("20260818", 0, body, _sha(body))[1]["duplicate"] is True


def test_changed_event_range_during_sync_is_not_acknowledged(isolated_state_dirs, monkeypatch):
    target = _day_file(isolated_state_dirs)
    real_sync = os.fsync
    replacement = b"replacement fixture\n"

    def change(fd):
        real_sync(fd)
        if stat.S_ISREG(os.fstat(fd).st_mode):
            target.write_bytes(replacement)

    monkeypatch.setattr(uploads_mod.os, "fsync", change)
    body = b"retained fixture\n"
    status, result = uploads_mod.append_events("20260818", 0, body, _sha(body))
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR and result["ok"] is False
    assert "cursor" not in result and target.read_bytes() == replacement


def test_append_syncs_new_directory_ancestors(isolated_state_dirs, monkeypatch):
    real_sync = os.fsync
    directories = set()

    def sync(fd):
        info = os.fstat(fd)
        if stat.S_ISDIR(info.st_mode):
            directories.add((info.st_dev, info.st_ino))
        real_sync(fd)

    monkeypatch.setattr(uploads_mod.os, "fsync", sync)
    body = b"retained fixture\n"
    assert uploads_mod.append_events("20260818", 0, body, _sha(body))[0] == HTTPStatus.OK
    for path in [_day_file(isolated_state_dirs).parent, _day_file(isolated_state_dirs).parent.parent]:
        info = path.stat()
        assert (info.st_dev, info.st_ino) in directories


def test_cursor_waits_for_pending_append_durability(isolated_state_dirs, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import contextmanager
    from threading import Event, get_ident

    syncing, release, querying = Event(), Event(), Event()
    writer_thread = []
    real_sync = uploads_mod._sync_capture_path
    real_lock = uploads_mod.flock

    def paused_sync(*args):
        if not syncing.is_set():
            writer_thread.append(get_ident())
            syncing.set()
            assert release.wait(5)
        return real_sync(*args)

    @contextmanager
    def observed_lock(*args, **kwargs):
        if syncing.is_set() and get_ident() != writer_thread[0]:
            querying.set()
        with real_lock(*args, **kwargs):
            yield

    monkeypatch.setattr(uploads_mod, "_sync_capture_path", paused_sync)
    monkeypatch.setattr(uploads_mod, "flock", observed_lock)
    body = b'{"kind":"neutral"}\n'
    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(uploads_mod.append_events, "20260818", 0, body, _sha(body))
        try:
            assert syncing.wait(2)
            reader = pool.submit(uploads_mod.events_cursor, "20260818")
            assert querying.wait(2), "cursor did not enter the shared lock"
            assert not reader.done(), "cursor acknowledged an unsynchronized write"
        finally:
            release.set()
        assert writer.result(timeout=2)[0] == HTTPStatus.OK
        status, payload = reader.result(timeout=2)
    assert status == HTTPStatus.OK and payload["bytes"] == len(body)


@pytest.mark.parametrize("error", [OSError, FileNotFoundError])
def test_cursor_sync_failure_does_not_acknowledge_bytes(isolated_state_dirs, monkeypatch, error):
    body = b'{"kind":"neutral"}\n'
    target = _day_file(isolated_state_dirs)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)

    def failure(*args):
        raise error("synthetic sync failure")

    monkeypatch.setattr(uploads_mod, "_sync_capture_path", failure)
    status, payload = uploads_mod.events_cursor("20260818")
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert payload["ok"] is False and "bytes" not in payload
    assert target.read_bytes() == body
