from __future__ import annotations

import json

import pytest

from sinnix_ops_reducer import actions


def test_focus_verifies_kitty_and_hyprland_target(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    class Result:
        returncode = 0
        stderr = ""

        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    def run(command, **_kwargs):
        calls.append(command)
        if command[-1] == "ls":
            return Result(json.dumps([{"tabs": [{"windows": [{"id": 42}]}]}]))
        if command[:2] == ["hyprctl", "-j"]:
            return Result('{"address":"0xabc"}')
        return Result("")

    monkeypatch.setattr(actions.subprocess, "run", run)
    receipt = actions.focus_registered_session(
        {"correlation": {"kitty_socket": "/tmp/kitty.sock", "kitty_window_id": "42", "hyprland_address": "0xabc"}}
    )
    assert receipt["status"] == "verified"
    assert calls[0][:4] == ["kitty", "@", "--to", "unix:/tmp/kitty.sock"]
    assert calls[-1] == ["hyprctl", "-j", "activewindow"]


def test_focus_rejects_duplicate_kitty_window(monkeypatch: pytest.MonkeyPatch) -> None:
    class Result:
        returncode = 0
        stderr = ""
        stdout = '[{"tabs":[{"windows":[{"id":42},{"id":42}]}]}]'

    monkeypatch.setattr(actions.subprocess, "run", lambda *_args, **_kwargs: Result())
    with pytest.raises(actions.ActionError, match="not unique"):
        actions.focus_registered_session(
            {"correlation": {"kitty_socket": "/tmp/kitty.sock", "kitty_window_id": "42", "hyprland_address": "0xabc"}}
        )
