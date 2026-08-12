from __future__ import annotations

from sinnix_capture_a11y.subtree import build_subtree


class FakeNode:
    def __init__(self, role, name, text=None, children=None):
        self._role = role
        self._name = name
        self._text = text
        self._children = children or []

    def role_name(self):
        return self._role

    def name(self):
        return self._name

    def text(self):
        return self._text

    def children(self):
        return self._children


def test_build_subtree_basic_shape():
    tree = FakeNode(
        "frame",
        "Main Window",
        children=[
            FakeNode("push button", "OK"),
            FakeNode("entry", "Search", text="hello world"),
        ],
    )
    out = build_subtree(tree)
    assert out["role"] == "frame"
    assert out["name"] == "Main Window"
    assert "truncated" not in out
    assert [c["name"] for c in out["children"]] == ["OK", "Search"]
    assert out["children"][1]["text"] == "hello world"


def test_build_subtree_respects_max_depth():
    leaf = FakeNode("label", "leaf")
    mid = FakeNode("panel", "mid", children=[leaf])
    root = FakeNode("frame", "root", children=[mid])

    out = build_subtree(root, max_depth=1)

    assert out["role"] == "frame"
    assert out["children"][0]["role"] == "panel"
    assert out["children"][0].get("truncated") == "max_depth"
    assert "children" not in out["children"][0]


def test_build_subtree_respects_max_nodes():
    children = [FakeNode("label", f"child-{i}") for i in range(10)]
    root = FakeNode("frame", "root", children=children)

    out = build_subtree(root, max_nodes=3)

    # root itself is node 1, so only 2 of the 10 children fit under the cap.
    assert len(out["children"]) == 2
    assert out.get("truncated") == "max_nodes"


def test_build_subtree_omits_empty_text():
    node = FakeNode("label", "x", text=None)

    out = build_subtree(node)

    assert "text" not in out
