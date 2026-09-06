from __future__ import annotations

import subprocess
from pathlib import Path

from agentctl import gitcmd


def test_git_calls_disable_optional_index_refreshes(
    tmp_path: Path, monkeypatch
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setenv("GIT_OPTIONAL_LOCKS", "1")

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["env"] = kwargs["env"]
        return subprocess.CompletedProcess(argv, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert gitcmd.git(tmp_path, "status", error=RuntimeError) == "ok"
    assert captured["env"]["GIT_OPTIONAL_LOCKS"] == "0"
