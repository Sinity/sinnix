"""Plain rendering and event-line shapes for the operator-facing CLI."""

from __future__ import annotations

from sinnixd.cli import _render_plain


def _ok(value: object) -> dict[str, object]:
    return {"ok": True, "payload": {"kind": "inline", "value": value}}


def test_workspace_listing_renders_one_row_per_workspace() -> None:
    rendered = _render_plain(
        _ok(
            {
                "workspaces": [
                    {
                        "name": "packet-polylogue-x",
                        "project_id": "polylogue",
                        "branch": "feature/packet/polylogue-x",
                        "workspace_id": "11111111-1111-1111-1111-111111111111",
                    }
                ]
            }
        )
    )
    lines = rendered.splitlines()
    assert len(lines) == 1
    assert "packet-polylogue-x" in lines[0]
    assert "11111111-1111-1111-1111-111111111111" in lines[0]


def test_job_record_renders_one_line() -> None:
    rendered = _render_plain(
        _ok(
            {
                "job_id": "22222222-2222-2222-2222-222222222222",
                "operation": "harvest",
                "project_id": "polylogue",
                "state": {"phase": "succeeded"},
                "checkout": {"path": "/realm/worktrees/w"},
            }
        )
    )
    assert rendered.count("\n") == 0
    assert "phase=succeeded" in rendered
    assert "harvest" in rendered


def test_error_envelope_renders_error_line() -> None:
    rendered = _render_plain({"ok": False, "error": {"code": "X", "message": "boom"}})
    assert rendered == "ERROR: boom"
