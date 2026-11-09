#!/usr/bin/env -S python3 -I
"""PreToolUse hook for Bash commands.

Blocks dangerous patterns only. Build/test/resource placement is provided by
project dev environments, not by this hook.

One process reads the payload once and applies every guard: this runs before
every agent Bash command, so interpreter and jq starts are the cost to avoid.
`-I` keeps a project's PYTHONPATH or sitecustomize out of the guard.
"""

import json
import os
import re
import shlex
import sys

SEPARATORS = {";", "&", "|", "&&", "||"}


def tokens_of(command):
    try:
        return list(shlex.shlex(command, posix=True, punctuation_chars=";&|"))
    except ValueError:
        return None


def any_line(pattern, text):
    """grep -E semantics: the pattern is matched against each line."""
    compiled = re.compile(pattern)
    return any(compiled.search(line) for line in text.split("\n"))


def strip_heredoc_bodies(command):
    """Drop heredoc bodies so a commit message or doc may quote a hazard.

    The opening line stays; lines up to the terminator are dropped.
    """
    opener = re.compile(r"""<<-?[ \t]*'?"?[A-Za-z_][A-Za-z0-9_]*'?"?""")
    kept, terminator = [], ""
    for line in command.split("\n"):
        if terminator:
            if line == terminator:
                terminator = ""
            continue
        match = opener.search(line)
        if match:
            terminator = re.sub(r"""^<<-?\s*|['"]""", "", match.group(0))
        kept.append(line)
    return "\n".join(kept)


def is_absolute(value):
    return value.startswith("/")


def has_absolute_option(segment, names):
    for position, option in enumerate(segment):
        if option in names and position + 1 < len(segment) and is_absolute(segment[position + 1]):
            return True
        if any(option.startswith(name + "=") and is_absolute(option.split("=", 1)[1]) for name in names):
            return True
    return False


def bd_guard(command, cwd, **_):
    """bd field replace-writes, and commits or exports from a worktree."""
    tokens = tokens_of(command)
    if tokens is None:
        return None
    replace_flags = {"--notes", "--design", "--description", "-d"}
    in_worktree = cwd == "/realm/worktree" or cwd.startswith("/realm/worktree/")
    command_start = True
    for index, token in enumerate(tokens):
        if token in SEPARATORS:
            command_start = True
            continue
        if command_start and token == "bd" and index + 1 < len(tokens) and tokens[index + 1] == "update":
            end = index + 2
            while end < len(tokens) and tokens[end] not in SEPARATORS:
                end += 1
            for option in tokens[index + 2 : end]:
                if option in replace_flags or any(option.startswith(flag + "=") for flag in replace_flags):
                    return ("bd update replace-writes blocked: use --append-notes for note history, --design-file or --body-file for file-backed updates, or read-modify-write when replacing a field is intentional.")
        if in_worktree:
            end = index + 1
            while end < len(tokens) and tokens[end] not in SEPARATORS:
                end += 1
            segment = tokens[index:end]
            if token == "git" and "commit" in segment and not has_absolute_option(segment, {"-C"}):
                return ("wrong-checkout guard: git commit from a worktree requires git -C /absolute/repository; verify the checkout before committing.")
            if token == "bd" and "export" in segment:
                if not has_absolute_option(segment, {"-C", "--directory"}) and not has_absolute_option(segment, {"-o", "--output"}):
                    return ("wrong-checkout guard: bd export from a worktree requires bd -C /absolute/repository export or -o /absolute/output.")
        command_start = False
    return None


def install_guard(command, **_):
    """Imperative package installs, at command start or after a separator."""
    if any_line(r"(^|[;&|]\s*)(nix\s+profile\s+(install|add|remove)|cargo\s+install|pip3?\s+install|npm\s+install\s+-g)", command):
        return ("Use declarative config instead of imperative install")
    return None


def force_push_guard(command, **_):
    """Bare force-push; --force-with-lease and --force-if-includes stay allowed."""
    if any_line(r"git\s+push\s+.*(-f(\s|$)|--force(\s|$))", command):
        return ("Bare force-push blocked — use --force-with-lease or --force-if-includes")
    return None


def git_guard(stripped, **_):
    """Hook bypass and checkout-wide stashes.

    `--no-verify`, `commit -n`, and `-c core.hooksPath=...` skip the
    repository's commit and push gates; the answer to a failing hook is fixing
    what it reports. A `git stash` without a pathspec sweeps every uncommitted
    change in the checkout, including other agents' and the operator's, into
    one entry. Commit work on a branch, or stash only named paths.
    """
    tokens = tokens_of(stripped)
    if tokens is None:
        return None
    segments, current = [], []
    for token in tokens:
        if token in SEPARATORS:
            segments.append(current)
            current = []
        else:
            current.append(token)
    segments.append(current)
    valued = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
    hooked = {"commit", "push", "merge", "rebase", "am", "cherry-pick", "revert"}
    for segment in segments:
        index = 0
        while index < len(segment) and "=" in segment[index] and not segment[index].startswith("-"):
            index += 1
        if index >= len(segment) or os.path.basename(segment[index]) != "git":
            continue
        index += 1
        hooks_moved = False
        while index < len(segment) and segment[index].startswith("-"):
            option = segment[index]
            value = segment[index + 1] if index + 1 < len(segment) else ""
            if option == "-c" and value.lower().startswith("core.hookspath"):
                hooks_moved = True
            index += 2 if option in valued else 1
        if index >= len(segment):
            continue
        subcommand, rest = segment[index], segment[index + 1 :]
        # `commit -n` is --no-verify; in a short cluster it counts only before
        # a letter that takes a value (`-nm msg` bypasses, `-mn` is the
        # message "n"). A value-taking letter ends the cluster; a detached
        # value is skipped.
        short_n = False
        if subcommand == "commit":
            values_follow = False
            for token in rest:
                if values_follow:
                    values_follow = False
                elif token == "--":
                    break
                elif re.match(r"-[^-mFcCtSu]*n", token):
                    short_n = True
                elif re.fullmatch(r"-[a-zA-Z]*[mFcCt]", token):
                    values_follow = True
        if (subcommand in hooked and "--no-verify" in rest) or short_n or hooks_moved:
            return ("git hook bypass blocked (--no-verify, commit -n, or -c core.hooksPath): it skips the repository's hooks. Fix what the hook reports and run it again.")
        if subcommand == "stash":
            action = rest[0] if rest and not rest[0].startswith("-") else "push"
            if action in {"push", "save"} and "--" not in rest:
                return ("git stash without paths blocked: it sweeps every uncommitted change in the checkout, including other agents' and the operator's. Commit your work on a branch, or stash only your own paths: git stash push -m <reason> -- <paths>.")
    return None


def poll_guard(command, stripped, background, **_):
    """Foreground polling loops.

    A loop that sleeps until a job, file or PR changes holds the agent for up
    to ten minutes, then re-issues, and every round re-reads the whole
    context: across lanes on 2026-10-24..26 that was 2,462 requests and about
    1.07 billion cached input tokens. Wait in the background instead
    (`agentctl job wait <task> --job-id <job_id>` with run_in_background, or a
    Monitor). A background loop is allowed, and so is a foreground one that
    carries `# poll-ok: <reason>` for a short, bounded poll with no completion
    event to wait on.
    """
    if background or any_line(r"#\s*poll-ok:\s*\S", command):
        return None
    # The sleep must sit inside the loop body: between `do` and the next `done`.
    flat = stripped.replace("\n", " ")
    if re.search(r"""(^|[;&|({\s'"])(until|while|for)\s.*?[;\s]do\s(?:(?!\bdone\b).)*\bsleep\s+[0-9]""", flat):
        return ("Foreground polling loop blocked: every round re-reads the whole context. Run 'agentctl job wait <task> --job-id <job_id>' (or the command you are waiting on) with run_in_background, or use Monitor, and do other work or end the turn until the notification arrives. If a short, bounded foreground poll is genuinely needed, add a comment '# poll-ok: <reason>' to the command.")
    return None


def store_glob_guard(stripped, **_):
    """Shell glob expansion over /nix/store.

    /nix/store holds ~219k top-level entries on this host. A pattern like
    /nix/store/*/share/doc/pkg/*.html makes the shell readdir all of them and
    opendir one subpath per entry, building the match list in RAM before the
    command runs. Twice that has taken the machine down (8.3 GB RSS + 11.8 GB
    swap in a zsh stuck in D state for 22 minutes). Only an unquoted glob in
    the segment right after /nix/store/ matches, so concrete store paths and
    quoted patterns handed to a lazy tool (find -name, rg --glob) stay allowed.
    """
    if any_line(r"""(^|[^'"])/nix/store/[^\s'"]*[*?]""", stripped):
        return ("Shell glob over /nix/store blocked: ~219k entries make the shell stat the whole store before your command runs (this has OOMed the host twice). Use 'find /nix/store -maxdepth 1 -name PATTERN' which streams, or resolve the one store path first (nix eval --raw, readlink, nix-locate) and search under that.")
    return None


def bootloader_lock_guard(stripped, **_):
    """Bootloader re-lock on the Redmi Note 11 (spes/spesn).

    The phone runs a custom ROM on an unlocked bootloader. Relocking makes the
    bootloader demand Xiaomi-signed vbmeta/boot, so the device neither boots
    nor accepts unsigned flashes: a hard brick recoverable only through EDL
    9008 with an authorized Mi account, which this operator does not have.
    Relock is legitimate only after restoring the full stock HyperOS fastboot
    ROM and confirming it boots green; that path is deliberately not carved
    out here, and its override is running the command outside an agent
    session. 'flashing unlock' stays allowed. Anchored at a command position
    with only known wrapper prefixes, so prose mentioning it is not caught.
    """
    if any_line(r"(^|[;&|])\s*(sudo\s+|doas\s+|time\s+|command\s+|env\s+[^\s;&|]+\s+)*[^\s;&|]*\bfastboot\b[^;&|]*\b(flashing\s+lock(_critical)?|oem\s+lock)\b", stripped):
        return ("Bootloader relock blocked: this device runs a custom ROM on an unlocked bootloader, so locking makes it demand Xiaomi-signed boot images it does not have -- it will neither boot nor accept flashes, which is a hard brick needing EDL 9008 + an authorized Mi account. Relock is only safe after restoring the full stock HyperOS fastboot ROM and confirming it boots green. If that is genuinely what you are doing, run the lock command outside an agent session.")
    return None


GUARDS = (
    bd_guard,
    install_guard,
    force_push_guard,
    git_guard,
    poll_guard,
    store_glob_guard,
    bootloader_lock_guard,
)


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except ValueError:
        return
    if not isinstance(payload, dict):
        return
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    command = tool_input.get("command") or ""
    cwd = payload.get("cwd") or tool_input.get("cwd") or ""
    background = tool_input.get("run_in_background") in (True, "true")
    context = {
        "command": command,
        "cwd": cwd,
        "stripped": strip_heredoc_bodies(command),
        "background": background,
    }
    for guard in GUARDS:
        reason = guard(**context)
        if reason:
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }))
            return


main()
