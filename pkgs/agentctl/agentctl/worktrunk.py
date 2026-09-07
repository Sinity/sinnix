"""The worktree adapter: ``wt`` mutates, Git's own registry reports.

agentctl does not create, provision, classify, or remove worktrees. ``wt``
does, against the project's ``.config/wt.toml`` hooks, and this module is the
only place that shells out to it.

Reading is `git worktree list`, which publishes every worktree's path and
branch from the registry without entering a working tree. A listing that
statuses each worktree instead costs the whole content of every worktree on
every call, and agentctl looks a branch up on each batch start, land, status
and abandon.

Creation and removal write the repository's shared Git state: they hold one
lock per repository and return only once Git has released that repository's
index.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from . import gitcmd
from .limits import CALL_TIMEOUT_SECONDS

# Removal is asynchronous by default; a caller that drops a workspace and then
# reports it gone must observe the removal, so every call passes --foreground.
_REMOVE_ARGUMENTS = ("--reap", "--foreground", "-y", "--format", "json")

# `--porcelain -z` terminates every attribute with a NUL and every worktree
# with an empty one, so a path is read exactly as Git holds it.
_REGISTRY_ARGUMENTS = ("worktree", "list", "--porcelain", "-z")

# A mutation returns while the Git process it started may still hold the
# repository index. The next writer then finds an `index.lock` no process
# owns. This is how long a mutation waits for that lock to be released; the
# lock is never removed here, because it belongs to Git.
GIT_SETTLE_SECONDS = 30
_SETTLE_POLL_SECONDS = 0.05


def _read_only_git_environment() -> dict[str, str]:
    """`wt` that reports without taking `.git/index.lock`.

    `wt` refreshes the index of the worktrees it inspects, and a call killed at
    the timeout below leaves the lock behind, blocking every later write in a
    repository agentctl does not own.
    """
    return {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}


class WorktrunkError(RuntimeError):
    """``wt`` refused a request or Git published a registry this module cannot read."""


@dataclass(frozen=True)
class Worktree:
    """One entry of the repository's worktree registry.

    A detached worktree publishes no branch and a branch with no worktree
    publishes no path. Both are ordinary entries, not read failures.
    """

    branch: str | None
    path: Path | None
    main: bool = False


def _run(root: Path, arguments: Sequence[str]) -> str:
    try:
        completed = subprocess.run(
            ["wt", "-C", str(root), *arguments],
            capture_output=True,
            text=True,
            timeout=CALL_TIMEOUT_SECONDS,
            env=_read_only_git_environment(),
        )
    except FileNotFoundError as error:
        raise WorktrunkError("wt is not installed") from error
    except subprocess.TimeoutExpired as error:
        raise WorktrunkError(f"wt {arguments[0]} timed out") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise WorktrunkError(detail or f"wt {arguments[0]} failed")
    return completed.stdout


def _common_git_directory(root: Path) -> Path | None:
    """The `.git` every worktree of this repository shares, or None.

    Creation and removal write there, whichever worktree they are asked from,
    so it names both the lock and the index they contend for.
    """
    try:
        directory = gitcmd.git(
            root,
            "rev-parse",
            "--path-format=absolute",
            "--git-common-dir",
            error=WorktrunkError,
        )
    except WorktrunkError:
        return None
    return Path(directory) if directory else None


def _lock_directory() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        return Path(runtime) / "agentctl"
    return Path(tempfile.gettempdir()) / f"agentctl-{os.getuid()}"


@contextmanager
def _repository_locked(root: Path, common: Path | None) -> Iterator[None]:
    """One worktrunk mutation per repository at a time.

    `wt` mutates the repository's shared registry, index and refs; two
    concurrent mutations interleave there whichever worktrees they were asked
    from. The lock is keyed by the common `.git` so every worktree of one
    repository takes the same one, and it lives outside the repository:
    agentctl does not own that checkout.
    """
    key = str((common or root).resolve())
    directory = _lock_directory()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"worktrunk-{hashlib.sha256(key.encode()).hexdigest()[:16]}.lock"
    with path.open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _index_lock_state(path: Path) -> tuple[int, int] | None:
    try:
        info = path.lstat()
    except OSError:
        return None
    return (info.st_ino, info.st_mtime_ns)


def _mutate(root: Path, arguments: Sequence[str], verb: str) -> str:
    """Run one `wt` mutation, and return only once Git has released the index.

    A mutation whose Git process is still finishing leaves an `index.lock`
    behind it; a caller that returned already would hand the next writer a
    repository it cannot write. A lock that was there before the mutation
    belongs to somebody else and is neither waited for nor removed.
    """
    common = _common_git_directory(root)
    with _repository_locked(root, common):
        if common is None:
            return _run(root, arguments)
        index_lock = common / "index.lock"
        before = _index_lock_state(index_lock)
        output = _run(root, arguments)
        deadline = time.monotonic() + GIT_SETTLE_SECONDS
        while True:
            current = _index_lock_state(index_lock)
            if current is None or current == before:
                return output
            if time.monotonic() >= deadline:
                raise WorktrunkError(
                    f"wt {verb} left {index_lock} held after "
                    f"{GIT_SETTLE_SECONDS} seconds"
                )
            time.sleep(_SETTLE_POLL_SECONDS)


def _decode(payload: str, what: str) -> Any:
    # wt pretty-prints its JSON across lines and may precede it with progress
    # output, so the document runs from the first brace to the end of stdout.
    for index, character in enumerate(payload):
        if character in "{[":
            try:
                return json.loads(payload[index:])
            except json.JSONDecodeError:
                break
    raise WorktrunkError(f"wt {what} did not print a JSON document")


def _entry(fields: Mapping[str, str], *, main: bool) -> Worktree:
    branch = fields.get("branch")
    path = fields.get("worktree")
    return Worktree(
        branch=branch.removeprefix("refs/heads/") if branch else None,
        path=Path(path) if path else None,
        main=main,
    )


def worktrunk_list(root: Path) -> tuple[Worktree, ...]:
    """Every worktree Git has registered for the repository at ``root``.

    Git lists its own checkout first, so that entry is the main worktree.
    """
    payload = gitcmd.git(root, *_REGISTRY_ARGUMENTS, error=WorktrunkError)
    trees: list[Worktree] = []
    fields: dict[str, str] = {}
    for record in payload.split("\0"):
        if not record:
            if fields:
                trees.append(_entry(fields, main=not trees))
                fields = {}
            continue
        key, _separator, value = record.partition(" ")
        fields[key] = value
    if fields:
        trees.append(_entry(fields, main=not trees))
    return tuple(trees)


def worktrunk_find(root: Path, branch: str) -> Worktree | None:
    """``branch``'s worktree, or the branch alone when it has no worktree.

    A branch that exists without a worktree is published with no path: a
    caller about to create one must tell it from a branch that does not exist.
    """
    for tree in worktrunk_list(root):
        if tree.branch == branch:
            return tree
    reference = gitcmd.git(
        root,
        "rev-parse",
        "--verify",
        "--quiet",
        f"refs/heads/{branch}",
        ok_statuses=(0, 1),
        error=WorktrunkError,
    )
    return Worktree(branch=branch, path=None) if reference else None


def worktrunk_create(
    root: Path, branch: str, *, path: Path, base: str | None = None
) -> Worktree:
    """Create ``branch``'s worktree at ``path``, running the project's own hooks.

    The path is passed explicitly rather than left to the user's worktrunk
    config, because the project descriptor declares where its workspaces live and
    agentctl validates the result against that declaration.
    """
    arguments = [
        "--config-set",
        f"worktree-path={json.dumps(str(path))}",
        "switch",
        branch,
        "--create",
        "--no-cd",
        "-y",
        "--format",
        "json",
    ]
    if base is not None:
        arguments.extend(["--base", base])
    document = _decode(_mutate(root, arguments, "switch"), "switch")
    if not isinstance(document, Mapping) or not document.get("path"):
        raise WorktrunkError("wt switch published no worktree path")
    created = worktrunk_find(root, branch)
    if created is None:
        raise WorktrunkError(f"wt created {branch} but does not list it")
    return created


def worktrunk_remove(root: Path, branch: str, *, force: bool = False) -> None:
    """Remove ``branch``'s worktree and its local branch, killing its processes."""
    arguments = ["remove", branch, *_REMOVE_ARGUMENTS]
    if force:
        arguments.append("--force")
    _mutate(root, arguments, "remove")
