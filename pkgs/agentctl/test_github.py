"""Read-only historical PR observation distinguishes absence from unavailable upstream."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from agentctl import github
from agentctl.github import GithubError


@pytest.fixture
def recorded_gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """A `gh` on PATH that records argv and replays a scripted stdout/exit."""
    ledger = tmp_path / "calls"
    script = tmp_path / "script.json"
    script.write_text(json.dumps({"stdout": "", "exit": 0}))
    binary = tmp_path / "bin" / "gh"
    binary.parent.mkdir()
    binary.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$*" >> {ledger}\n'
        f"python3 -c \"import json,sys; d=json.load(open('{script}')); sys.stdout.write(d['stdout']); sys.stderr.write(d.get('stderr','')); sys.exit(d['exit'])\"\n"
    )
    binary.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binary.parent}{os.pathsep}{os.environ['PATH']}")
    return {"ledger": ledger, "script": script}


def _calls(ledger: Path) -> list[str]:
    return ledger.read_text().splitlines() if ledger.exists() else []


def test_pull_request_is_read_by_number_and_absent_when_unknown(
    recorded_gh: dict[str, Any], tmp_path: Path
) -> None:
    recorded_gh["script"].write_text(
        json.dumps({"stdout": '{"number": 7, "state": "OPEN"}', "exit": 0})
    )
    assert github.pull_request(tmp_path, 7) == {"number": 7, "state": "OPEN"}
    assert _calls(recorded_gh["ledger"])[0].startswith("pr view 7 --json number,")

    recorded_gh["script"].write_text(
        json.dumps(
            {
                "stdout": "",
                "stderr": "GraphQL: Could not resolve to a PullRequest with the number of 99.",
                "exit": 1,
            }
        )
    )
    assert github.pull_request(tmp_path, 99) is None

    recorded_gh["script"].write_text(
        json.dumps({"stdout": "", "stderr": "HTTP 502", "exit": 1})
    )
    with pytest.raises(GithubError, match="502"):
        github.pull_request(tmp_path, 7)
