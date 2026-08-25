from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_codex_backend_inherits_the_declared_project_environment(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    runner = repo_root / "dots/_ai/skills/agent-runtime/scripts/run_agent_prompt.sh"
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    prompt = tmp_path / "prompt"
    prompt.write_text("test prompt", encoding="utf-8")
    result = tmp_path / "result"
    args_file = tmp_path / "codex-args"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_codex = fake_bin / "codex"
    fake_codex.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        "printf '%s\\n' \"$@\" > \"$CODEX_ARGS\"\n",
        encoding="utf-8",
    )
    fake_codex.chmod(0o700)

    environment = dict(os.environ)
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    environment["CODEX_ARGS"] = str(args_file)
    completed = subprocess.run(
        [
            runner,
            "--agent",
            "codex",
            "--workdir",
            worktree,
            "--prompt-file",
            prompt,
            "--last-file",
            result,
            "--model",
            "fixture-model",
            "--reasoning-effort",
            "medium",
        ],
        env=environment,
        check=False,
    )

    assert completed.returncode == 0
    argv = args_file.read_text(encoding="utf-8").splitlines()
    policy_index = argv.index("shell_environment_policy.inherit=all")
    assert ["-c", "shell_environment_policy.inherit=all"] == argv[policy_index - 1 : policy_index + 1]
