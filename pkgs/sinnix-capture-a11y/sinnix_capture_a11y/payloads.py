"""Pure payload builders for the a11y capture lane's three record kinds.

Each function returns a plain, JSON-serializable dict that daemon.py hands
to ``sinnix_capture.writer.CaptureWriter.write`` as the envelope payload.
"""

from __future__ import annotations


def focus_payload(*, app: str, role: str, name: str, window_name: str | None) -> dict:
    return {
        "kind": "focus",
        "app": app,
        "role": role,
        "name": name,
        "window": window_name,
    }


def text_changed_payload(
    *,
    app: str,
    role: str,
    name: str,
    change_type: str,
    detail: str | None,
) -> dict:
    return {
        "kind": "text-changed",
        "app": app,
        "role": role,
        "name": name,
        "change_type": change_type,
        "detail": detail,
    }


def subtree_payload(*, app: str, window_name: str | None, tree: dict) -> dict:
    return {
        "kind": "subtree",
        "app": app,
        "window": window_name,
        "tree": tree,
    }
