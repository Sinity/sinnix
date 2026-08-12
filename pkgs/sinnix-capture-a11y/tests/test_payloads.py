from __future__ import annotations

from sinnix_capture_a11y.payloads import (
    focus_payload,
    subtree_payload,
    text_changed_payload,
)


def test_focus_payload_shape():
    p = focus_payload(app="firefox", role="entry", name="Search", window_name="Mozilla Firefox")
    assert p == {
        "kind": "focus",
        "app": "firefox",
        "role": "entry",
        "name": "Search",
        "window": "Mozilla Firefox",
    }


def test_text_changed_payload_shape():
    p = text_changed_payload(
        app="kate",
        role="text",
        name="doc",
        change_type="object:text-changed:insert",
        detail="h",
    )
    assert p["kind"] == "text-changed"
    assert p["change_type"] == "object:text-changed:insert"
    assert p["detail"] == "h"


def test_subtree_payload_shape():
    tree = {"role": "frame", "name": "root"}
    p = subtree_payload(app="kate", window_name="Kate", tree=tree)
    assert p["kind"] == "subtree"
    assert p["window"] == "Kate"
    assert p["tree"] is tree
