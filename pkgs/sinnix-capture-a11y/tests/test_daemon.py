"""Exercises the daemon's event-wiring logic against fake AT-SPI2-shaped
objects, never importing pyatspi/gi. Only ``daemon.run()`` (never called
here) touches the real bindings -- see daemon.py's module docstring.
"""

from __future__ import annotations

from pathlib import Path

from sinnix_capture_a11y.daemon import A11yDaemon, _AccessibleAdapter, _top_level_window


class _FakeTextIface:
    def __init__(self, text):
        self._text = text

    def getText(self, start, end):
        return self._text


class FakeAccessible:
    def __init__(self, role, name, children=None, text=None, app_name="TestApp", parent=None):
        self._role = role
        self.name = name
        self._children = children or []
        self._text = text
        self._app_name = app_name
        self.parent = parent

    def getRoleName(self):
        return self._role

    def getChildCount(self):
        return len(self._children)

    def getChildAtIndex(self, i):
        return self._children[i]

    def queryText(self):
        if self._text is None:
            raise NotImplementedError
        return _FakeTextIface(self._text)

    class _App:
        def __init__(self, name):
            self.name = name

    def getApplication(self):
        return FakeAccessible._App(self._app_name)


class FakeEvent:
    def __init__(self, source, type_="focus:", any_data=None):
        self.source = source
        self.type = type_
        self.any_data = any_data


def test_accessible_adapter_reads_role_name_text_and_children():
    child = FakeAccessible("push button", "OK")
    root = FakeAccessible("frame", "Main", children=[child], text="ignored-on-frame")

    adapter = _AccessibleAdapter(root)

    assert adapter.role_name() == "frame"
    assert adapter.name() == "Main"
    assert adapter.text() == "ignored-on-frame"
    kids = adapter.children()
    assert len(kids) == 1
    assert kids[0].name() == "OK"


def test_accessible_adapter_text_returns_none_without_text_interface():
    node = FakeAccessible("push button", "OK", text=None)

    assert _AccessibleAdapter(node).text() is None


def test_top_level_window_walks_up_to_nearest_frame():
    frame = FakeAccessible("frame", "Main Window")
    panel = FakeAccessible("panel", "Toolbar", parent=frame)
    entry = FakeAccessible("entry", "Search", parent=panel)

    assert _top_level_window(entry) is frame


def test_top_level_window_falls_back_to_self_without_a_frame_ancestor():
    orphan = FakeAccessible("entry", "Search", parent=None)

    assert _top_level_window(orphan) is orphan


def _make_daemon(tmp_path: Path, **overrides) -> tuple[A11yDaemon, list[dict]]:
    written: list[dict] = []
    daemon = A11yDaemon(
        capture_root=tmp_path,
        subtree_interval_seconds=overrides.get("subtree_interval_seconds", 9999),
        text_debounce_seconds=overrides.get("text_debounce_seconds", 1.0),
        max_depth=10,
        max_nodes=100,
    )
    daemon._writer.write = lambda payload, **kw: written.append(payload) or {}
    return daemon, written


def test_on_focus_emits_focus_record_then_a_bounded_subtree_dump(tmp_path: Path):
    daemon, written = _make_daemon(tmp_path)
    acc = FakeAccessible("entry", "Search")

    daemon.on_focus(FakeEvent(acc))

    assert [p["kind"] for p in written] == ["focus", "subtree"]
    assert written[0]["name"] == "Search"
    assert written[1]["tree"]["role"] == "entry"


def test_on_text_changed_debounces_rapid_repeat_events(tmp_path: Path):
    daemon, written = _make_daemon(tmp_path, text_debounce_seconds=1000.0)
    acc = FakeAccessible("entry", "Search")

    daemon.on_text_changed(FakeEvent(acc, type_="object:text-changed:insert", any_data="h"))
    daemon.on_text_changed(FakeEvent(acc, type_="object:text-changed:insert", any_data="he"))

    assert len(written) == 1
    assert written[0]["kind"] == "text-changed"
    assert written[0]["detail"] == "h"


def test_on_text_changed_treats_distinct_accessibles_independently(tmp_path: Path):
    daemon, written = _make_daemon(tmp_path, text_debounce_seconds=1000.0)
    acc_a = FakeAccessible("entry", "Search A")
    acc_b = FakeAccessible("entry", "Search B")

    daemon.on_text_changed(FakeEvent(acc_a, type_="object:text-changed:insert", any_data="x"))
    daemon.on_text_changed(FakeEvent(acc_b, type_="object:text-changed:insert", any_data="y"))

    assert len(written) == 2
    assert {p["name"] for p in written} == {"Search A", "Search B"}


def test_periodic_dump_respects_interval_between_focus_events(tmp_path: Path):
    daemon, written = _make_daemon(tmp_path, subtree_interval_seconds=9999)
    acc = FakeAccessible("entry", "Search")
    daemon.on_focus(FakeEvent(acc))
    written.clear()

    # A periodic-timer tick shortly after should be suppressed by the
    # interval (force=False path), unlike the focus event itself.
    daemon.maybe_dump_subtree()

    assert written == []
