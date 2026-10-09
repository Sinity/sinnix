"""Where shell.run places a command: agent CLIs start in the long lane."""

from __future__ import annotations

import pytest
from sinnix_agent_gateway import shell_lanes


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["claude", "-p", "review the diff"], ("long", "agent-cli:claude")),
        (
            ["/nix/store/abc-codex/bin/codex", "exec", "task"],
            ("long", "agent-cli:codex"),
        ),
        (
            [
                "bash",
                "-lc",
                "cd /realm/x && timeout 3600 claude -p 'do it' > out.log 2>&1",
            ],
            ("long", "agent-cli:claude"),
        ),
        (
            ["env", "FOO=1", "nohup", "codex", "exec", "task"],
            ("long", "agent-cli:codex"),
        ),
        (["nice", "-n", "5", "gemini", "-p", "x"], ("long", "agent-cli:gemini")),
        (["env", "-i", "codex", "exec", "x"], ("long", "agent-cli:codex")),
        (["env", "--unset", "X", "claude", "-p", "x"], ("long", "agent-cli:claude")),
        (["env", "-C", "/fixture", "codex", "exec", "x"], ("long", "agent-cli:codex")),
        (["env", "-iu", "X", "codex", "exec", "x"], ("long", "agent-cli:codex")),
        (["taskset", "-c", "0", "codex", "exec", "x"], ("long", "agent-cli:codex")),
        (["taskset", "--", "1", "codex", "exec", "x"], ("long", "agent-cli:codex")),
        (["timeout", "--", "30s", "claude", "-p", "x"], ("long", "agent-cli:claude")),
        (
            ["timeout", "--signal", "TERM", "30s", "claude", "-p", "x"],
            ("long", "agent-cli:claude"),
        ),
        (
            ["nice", "--adjustment", "5", "codex", "exec", "x"],
            ("long", "agent-cli:codex"),
        ),
        (["stdbuf", "-i", "0", "codex", "exec", "x"], ("long", "agent-cli:codex")),
        (["env", "-S", "codex exec x"], ("long", "agent-cli:codex")),
        (["env", "-iS", "codex exec x"], ("long", "agent-cli:codex")),
        (["env", "--split-string=codex exec x"], ("long", "agent-cli:codex")),
        (
            ["timeout", "--signal=TERM", "30s", "claude", "-p", "x"],
            ("long", "agent-cli:claude"),
        ),
        # Agent names used as option values must not become command words.
        (["env", "--unset", "claude", "rg", "fixture"], ("quick", "default")),
        (["exec", "-a", "codex", "printf", "fixture"], ("quick", "default")),
        (["env", "-S", "printf codex"], ("quick", "default")),
        (["env", "--unset=codex", "printf", "fixture"], ("quick", "default")),
        (["bash", "-c", 'bash -lc "codex exec hi"'], ("long", "agent-cli:codex")),
        (["sh", "-c", "set -e; X=1 claude -p go &"], ("long", "agent-cli:claude")),
        (["bash", "-c", "printf fixture\ncodex exec x"], ("long", "agent-cli:codex")),
        (
            ["bash", "-c", "printf fixture # comment\ncodex exec x"],
            ("long", "agent-cli:codex"),
        ),
        (["bash", "-c", 'printf "codex\nexec fixture"'], ("quick", "default")),
        (
            ["bash", "-o", "pipefail", "--login", "-c", "codex exec x | tee log"],
            ("long", "agent-cli:codex"),
        ),
        # The name as an argument or inside a string is not a launch.
        (["rg", "claude", "docs"], ("quick", "default")),
        (["bash", "-c", "echo claude; grep -r codex ."], ("quick", "default")),
        (["sed", "-n", "1,40p", "AGENTS.md"], ("quick", "default")),
        (["bash", "-lc", "git status --short; git log -1"], ("quick", "default")),
        # Unbalanced quoting still classifies from the words it has.
        (["bash", "-c", "claude -p 'unterminated"], ("long", "agent-cli:claude")),
    ],
)
def test_auto_lane_follows_the_command_word(
    argv: list[str], expected: tuple[str, str]
) -> None:
    assert shell_lanes.choose(argv, "auto") == expected


def test_a_declared_lane_is_taken_as_given() -> None:
    assert shell_lanes.choose(["claude", "-p", "x"], "quick") == ("quick", "declared")
    assert shell_lanes.choose(["make", "all"], "long") == ("long", "declared")


def test_each_lane_is_its_own_pueue_group() -> None:
    assert shell_lanes.GROUPS == {"quick": "shell-quick", "long": "shell-long"}
