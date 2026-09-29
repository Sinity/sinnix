"""Which lane a `shell.run` command belongs in.

Two pueue groups carry gateway shells (declared as agentctl pools):
``shell-quick`` for reads and short commands, ``shell-long`` for agent CLIs
and anything the caller declares long. A command the classifier leaves in the
quick lane but that keeps running is promoted by agentctl after the pool's
horizon, so a misclassification delays nobody; the classifier only decides
where long work starts.

Nothing is refused here: the gateway is the operator's full-power shell, and a
lane is a placement, not a permission.
"""

from __future__ import annotations

import shlex
from pathlib import PurePosixPath
from typing import Literal

Lane = Literal["quick", "long"]

GROUPS: dict[Lane, str] = {"quick": "shell-quick", "long": "shell-long"}

# Agent command-line harnesses: each one launched from a shell is a session
# that runs for minutes to hours.
AGENT_CLIS = frozenset(
    {"claude", "codex", "gemini", "opencode", "pi", "agentctl-agent", "cursor-agent"}
)
SHELLS = frozenset({"bash", "sh", "zsh", "dash", "fish"})
# Commands that run their remaining arguments as another command.
WRAPPERS = frozenset(
    {
        "env",
        "nohup",
        "setsid",
        "nice",
        "ionice",
        "stdbuf",
        "time",
        "timeout",
        "exec",
        "command",
        "builtin",
        "chrt",
        "taskset",
    }
)
# Wrappers whose first positional argument is a value, not the command.
_WRAPPER_VALUE = {"timeout": 1, "chrt": 1, "taskset": 1}
_SEPARATORS = frozenset({";", "&", "&&", "|", "||", "|&", "(", ")", "\n"})
_KEYWORDS = frozenset(
    {"then", "do", "else", "elif", "if", "while", "until", "{", "}", "!"}
)
_MAX_DEPTH = 4


def _name(word: str) -> str:
    return PurePosixPath(word).name


def _is_assignment(word: str) -> bool:
    name, equals, _ = word.partition("=")
    return bool(equals) and name.replace("_", "a").isalnum() and not name[0].isdigit()


def _command_word(words: list[str]) -> tuple[str | None, list[str]]:
    """The program a simple command runs, past assignments and wrappers."""
    index = 0
    while index < len(words):
        word = words[index]
        if _is_assignment(word) or word in _KEYWORDS:
            index += 1
            continue
        name = _name(word)
        if name not in WRAPPERS:
            return name, words[index + 1 :]
        index += 1
        values = _WRAPPER_VALUE.get(name, 0)
        while index < len(words):
            current = words[index]
            if current == "--":
                index += 1
                break
            if current.startswith("-") or _is_assignment(current):
                index += 1
                # `nice -n 5`, `ionice -c 3`, `env -u NAME`: an option's value.
                if (
                    current in {"-n", "-c", "-u", "-p", "-s", "-k", "-o", "-e", "-i"}
                    and index < len(words)
                    and not words[index].startswith("-")
                ):
                    index += 1
                continue
            if values:
                values -= 1
                index += 1
                continue
            break
    return None, []


# Shell options that consume the next argument (`bash -o pipefail -c ...`).
_SHELL_VALUE_OPTIONS = frozenset({"-o", "+o", "-O", "+O"})


def _script(arguments: list[str]) -> str | None:
    """The script of `sh -c SCRIPT` (also `-lc`, `-ec`, `-xc` and so on)."""
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument in _SHELL_VALUE_OPTIONS:
            index += 2
            continue
        if argument.startswith(("-", "+")) and not argument.startswith("--"):
            if "c" in argument[1:] and index + 1 < len(arguments):
                return arguments[index + 1]
            index += 1
            continue
        if argument.startswith("--"):
            # Long options (--login, --norc) take no value in bash.
            index += 1
            continue
        return None
    return None


def _script_commands(script: str) -> list[list[str]]:
    """The simple commands of a shell script, split at its operators."""
    lexer = shlex.shlex(script, posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split = True
    lexer.commenters = "#"
    try:
        tokens = list(lexer)
    except ValueError:
        # Unbalanced quotes: the words are still the best evidence there is.
        tokens = script.replace(";", " ; ").replace("&", " & ").split()
    commands: list[list[str]] = [[]]
    for token in tokens:
        if token in _SEPARATORS or set(token) <= set(";&|()"):
            commands.append([])
        else:
            commands[-1].append(token)
    return [command for command in commands if command]


def _agent(words: list[str], depth: int) -> str | None:
    if depth > _MAX_DEPTH:
        return None
    program, rest = _command_word(words)
    if program is None:
        return None
    if program in AGENT_CLIS:
        return program
    if program in SHELLS:
        script = _script(rest)
        if script is not None:
            for command in _script_commands(script):
                found = _agent(command, depth + 1)
                if found is not None:
                    return found
    return None


def choose(
    argv: list[str], requested: Literal["auto", "quick", "long"]
) -> tuple[Lane, str]:
    """The lane and the reason, as the response reports them."""
    if requested != "auto":
        return requested, "declared"
    agent = _agent(list(argv), 0)
    if agent is not None:
        return "long", f"agent-cli:{agent}"
    return "quick", "default"
