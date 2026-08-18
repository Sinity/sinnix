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

import sinnix_phone_dispatcher.notifications as notifications_mod


def _reset():
    notifications_mod._tail_by_day.clear()


def test_notification_posted_is_forwarded_to_the_desktop(monkeypatch) -> None:
    _reset()
    calls = []
    monkeypatch.setattr(
        notifications_mod,
        "notify_desktop",
        lambda title, body, **kw: calls.append((title, body, kw)),
    )

    notifications_mod.mirror_new_events(
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

    notifications_mod.mirror_new_events(
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

    notifications_mod.mirror_new_events(
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

    notifications_mod.mirror_new_events("20260818", first)
    assert calls == []  # the line has not ended yet -- nothing to forward
    notifications_mod.mirror_new_events("20260818", second)

    assert len(calls) == 1


def test_malformed_json_is_dropped_not_raised(monkeypatch) -> None:
    _reset()
    calls = []
    monkeypatch.setattr(
        notifications_mod, "notify_desktop", lambda *a, **kw: calls.append(a)
    )

    notifications_mod.mirror_new_events("20260818", b"not json at all\n")

    assert calls == []


def test_empty_bytes_are_a_no_op(monkeypatch) -> None:
    _reset()
    calls = []
    monkeypatch.setattr(
        notifications_mod, "notify_desktop", lambda *a, **kw: calls.append(a)
    )

    notifications_mod.mirror_new_events("20260818", b"")

    assert calls == []


def test_tail_buffer_is_kept_per_day(monkeypatch) -> None:
    _reset()
    calls = []
    monkeypatch.setattr(
        notifications_mod, "notify_desktop", lambda *a, **kw: calls.append(a)
    )

    notifications_mod.mirror_new_events("20260818", b'{"kind":"notification_posted"')
    notifications_mod.mirror_new_events("20260819", b'{"kind":"mark"}\n')

    assert calls == []
    assert (
        notifications_mod._tail_by_day["20260818"] == b'{"kind":"notification_posted"'
    )
    assert "20260819" not in notifications_mod._tail_by_day
