"""Mirroring `notification_posted` lines from the events plane onto the
desktop, and NOT mirroring anything else.

Mutations that would fail this: forwarding on every kind rather than only
`notification_posted` fails test_other_kinds_are_not_forwarded; forwarding a
batch's full bytes instead of the caller-supplied new suffix would be a
caller bug, covered from the uploads.py side in test_events.py; failing to
buffer a line split across two calls fails
test_a_line_split_across_two_calls_is_still_forwarded_once; re-scanning the
buffered tail on the next call (instead of consuming it) fails
test_a_line_split_across_two_calls_is_still_forwarded_once by forwarding
twice.
"""

from __future__ import annotations

import sys
import tempfile

import pytest

import sinnix_phone_dispatcher.notifications as notifications_mod


_files = {}


def _reset():
    for stream in _files.values():
        stream.close()
    _files.clear()


@pytest.fixture(autouse=True)
def close_capture_files():
    yield
    _reset()


def _mirror(day, data):
    if day not in _files:
        _files[day] = tempfile.TemporaryFile()
    stream = _files[day]
    stream.seek(0, 2)
    start = stream.tell()
    stream.write(data)
    stream.flush()
    notifications_mod.mirror_new_events(stream.fileno(), start, start + len(data))


def test_undecodable_record_does_not_discard_later_notifications(monkeypatch):
    _reset()
    calls = []
    monkeypatch.setattr(
        notifications_mod, "notify_desktop", lambda *a, **kw: calls.append(a)
    )
    _mirror(
        "20260101",
        b'\xff\n{"kind":"notification_posted","title":"fixture","text":"retained"}\n',
    )
    assert calls == [("fixture", "retained")]


def test_integer_digit_limit_does_not_discard_later_notifications(monkeypatch):
    _reset()
    calls = []
    monkeypatch.setattr(
        notifications_mod, "notify_desktop", lambda *a, **kw: calls.append(a)
    )
    previous_limit = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(4300)
        _mirror(
            "20260101",
            b'{"value":' + b"9" * 4301 + b'}\n'
            b'{"kind":"notification_posted","title":"fixture","text":"retained"}\n',
        )
    finally:
        sys.set_int_max_str_digits(previous_limit)
    assert calls == [("fixture", "retained")]


def test_notification_posted_is_forwarded_to_the_desktop(monkeypatch) -> None:
    _reset()
    calls = []
    monkeypatch.setattr(
        notifications_mod,
        "notify_desktop",
        lambda title, body, **kw: calls.append((title, body, kw)),
    )

    _mirror(
        "20260818",
        b'{"kind":"notification_posted","app":"Signal","title":"Alice","text":"hi"}\n',
    )

    assert len(calls) == 1
    title, body, kw = calls[0]
    assert title == "Signal: Alice"
    assert body == "hi"
    assert kw.get("app_name") == "sinnix-phone"


def test_ongoing_notifications_are_not_forwarded(monkeypatch) -> None:
    """A foreground service's persistent status line (Termux's session
    notification, measured live: 230 of 240 posts on an ordinary day) is not
    a discrete event -- mirroring it would flood the desktop on every content
    tick."""
    _reset()
    calls = []
    monkeypatch.setattr(
        notifications_mod, "notify_desktop", lambda *a, **kw: calls.append(a)
    )

    _mirror(
        "20260818",
        b'{"kind":"notification_posted","app":"com.termux","title":"Termux",'
        b'"text":"1 session","ongoing":true}\n',
    )

    assert calls == []


def test_other_kinds_are_not_forwarded(monkeypatch) -> None:
    _reset()
    calls = []
    monkeypatch.setattr(
        notifications_mod, "notify_desktop", lambda *a, **kw: calls.append(a)
    )

    _mirror(
        "20260818",
        b'{"kind":"notification_removed","app":"Signal","title":"Alice"}\n'
        b'{"kind":"grant_transition","state":"connected"}\n'
        b'{"kind":"mark","word":"caffeine"}\n',
    )

    assert calls == []


def test_a_line_split_across_two_calls_is_still_forwarded_once(monkeypatch) -> None:
    _reset()
    calls = []
    monkeypatch.setattr(
        notifications_mod, "notify_desktop", lambda *a, **kw: calls.append(a)
    )
    line = b'{"kind":"notification_posted","app":"Mail","title":"New message","text":"x"}\n'
    first, second = line[:20], line[20:]

    _mirror("20260818", first)
    assert calls == []  # the line has not ended yet -- nothing to forward
    _mirror("20260818", second)

    assert len(calls) == 1


def test_malformed_json_is_dropped_not_raised(monkeypatch) -> None:
    _reset()
    calls = []
    monkeypatch.setattr(
        notifications_mod, "notify_desktop", lambda *a, **kw: calls.append(a)
    )

    _mirror("20260818", b"not json at all\n")

    assert calls == []


def test_empty_bytes_are_a_no_op(monkeypatch) -> None:
    _reset()
    calls = []
    monkeypatch.setattr(
        notifications_mod, "notify_desktop", lambda *a, **kw: calls.append(a)
    )

    _mirror("20260818", b"")

    assert calls == []


def test_tail_buffer_is_kept_per_day(monkeypatch) -> None:
    _reset()
    calls = []
    monkeypatch.setattr(
        notifications_mod, "notify_desktop", lambda *a, **kw: calls.append(a)
    )

    _mirror("20260818", b'{"kind":"notification_posted"')
    _mirror("20260819", b'{"kind":"mark"}\n')

    assert calls == []
    assert not hasattr(notifications_mod, "_tail_by_day")
    _mirror("20260818", b',"title":"completed"}\n')
    assert calls == [("completed", "")]


def test_large_unfinished_record_does_not_accumulate_in_memory():
    import tracemalloc
    with tempfile.TemporaryFile() as stream:
        chunk = b"x" * (64 * 1024)
        for _ in range(128):
            stream.write(chunk)
        stream.flush()
        tracemalloc.start()
        try:
            notifications_mod.mirror_new_events(stream.fileno(), 0, stream.tell())
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert peak < 512 * 1024


def test_mirror_respects_acknowledged_end(monkeypatch):
    calls = []
    monkeypatch.setattr(notifications_mod, "notify_desktop", lambda *a, **kw: calls.append(a))
    line = b'{"kind":"notification_posted","title":"fixture"}\n'
    with tempfile.TemporaryFile() as stream:
        stream.write(line + line)
        stream.flush()
        notifications_mod.mirror_new_events(stream.fileno(), 0, len(line))
    assert calls == [("fixture", "")]


def test_truncated_capture_range_is_reported():
    with tempfile.TemporaryFile() as stream:
        with pytest.raises(OSError, match="unavailable"):
            notifications_mod.mirror_new_events(stream.fileno(), 0, 10)
