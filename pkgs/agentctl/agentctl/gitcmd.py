"""One local `git` call; the caller names the exception class a failure raises.

A Git command that writes the index holds `index.lock` in its worktree's Git
directory until it finishes. Git removes that lock when it exits or receives a
catchable signal, but a SIGKILL strands it, and the stranded lock blocks
every later writer in that worktree. Three rules keep agentctl from doing that
to a checkout, and make it visible when something does:

- A call that writes the index refuses a main checkout unless the caller
  declares ``main_checkout=True``. Queued work writes only worktrees it owns.
- A timeout sends SIGTERM first, so Git can release its lock, and sends
  SIGKILL only after ``TERMINATE_GRACE_SECONDS``.
- After a failed index-writing call, an unheld `index.lock` that appeared
  while the call ran is reported as ``StrandedIndexLock``, the cause of the raised error. It is
  removed only from a linked worktree that the caller owns
  (``owned=True``), never from a main checkout.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, Sequence

from .limits import CALL_TIMEOUT_SECONDS

# Git verbs that take `index.lock` or rewrite checked-out files. Any other
# verb agentctl runs is a read, or a ref write that uses the ref's own lock.
INDEX_WRITING_VERBS = frozenset(
    {
        "add",
        "am",
        "apply",
        "checkout",
        "checkout-index",
        "cherry-pick",
        "commit",
        "merge",
        "mv",
        "pull",
        "read-tree",
        "rebase",
        "reset",
        "restore",
        "revert",
        "rm",
        "stash",
        "switch",
        "update-index",
    }
)
# How long a timed-out git has after SIGTERM to release its lock and exit.
TERMINATE_GRACE_SECONDS = 10.0
# File timestamps come from the kernel's coarse clock, which can trail
# `time.time_ns()` by a tick; a lock made right after a call started may
# carry an mtime just before it.
MTIME_SLACK_NS = 100_000_000


class StrandedIndexLock(Exception):
    """An `index.lock` that appeared while a failed call ran and that no process holds."""

    def __init__(self, lock: Path, *, removed: bool) -> None:
        super().__init__(str(lock))
        self.lock = lock
        self.removed = removed

    def __str__(self) -> str:
        if self.removed:
            return f"removed the stranded {self.lock}"
        return f"left a stranded {self.lock}; no process holds it, remove it by hand"


@dataclass(frozen=True)
class GitDirectories:
    """Where one worktree's index lives, and whether it is the main checkout."""

    git_dir: Path
    main: bool


def git_directories(path: Path) -> GitDirectories | None:
    """The Git directory of the worktree containing ``path``, read from disk.

    A main checkout has a `.git` directory; a linked worktree has a `.git` file
    naming its private directory under the common one. None means ``path`` is
    in no worktree that this can read.
    """
    for candidate in (path, *path.parents):
        dot_git = candidate / ".git"
        if dot_git.is_dir():
            return GitDirectories(git_dir=dot_git, main=True)
        if dot_git.is_file():
            try:
                pointer = dot_git.read_text().strip()
            except OSError:
                return None
            if not pointer.startswith("gitdir:"):
                return None
            directory = Path(pointer.removeprefix("gitdir:").strip())
            if not directory.is_absolute():
                directory = candidate / directory
            return GitDirectories(git_dir=directory, main=False)
    return None


def common_git_dir(directories: GitDirectories) -> Path:
    """The `.git` shared by every worktree; the main checkout's index is in it."""
    if directories.main:
        return directories.git_dir
    try:
        common = (directories.git_dir / "commondir").read_text().strip()
    except OSError:
        return directories.git_dir
    return Path(os.path.normpath(directories.git_dir / common))


def lock_holders(lock: Path) -> list[int]:
    """Processes with ``lock`` open; Git keeps the descriptor until it commits or rolls back."""
    target = str(lock)
    holders: list[int] = []
    try:
        entries = os.listdir("/proc")
    except OSError:
        return holders
    for entry in entries:
        if not entry.isdigit():
            continue
        descriptors = f"/proc/{entry}/fd"
        try:
            names = os.listdir(descriptors)
        except OSError:
            continue
        for name in names:
            try:
                if os.readlink(f"{descriptors}/{name}") == target:
                    holders.append(int(entry))
                    break
            except OSError:
                continue
    return holders


def stranded_lock(lock: Path, *, since_ns: int) -> bool:
    """Whether ``lock`` exists, was created at or after ``since_ns``, and is unheld."""
    try:
        created = lock.lstat().st_mtime_ns
    except OSError:
        return False
    return created >= since_ns - MTIME_SLACK_NS and not lock_holders(lock)


def clear_stranded_lock(path: Path, *, min_age_seconds: float = 5.0) -> Path | None:
    """Remove an unheld `index.lock` from the linked worktree at ``path``; return it.

    Only for a worktree the caller owns and no other writer uses: a landing's
    integration worktree, whose previous landing may have been killed
    mid-merge. A live Git holds its lock from the moment it creates it, so an
    unheld lock older than ``min_age_seconds`` has no writer left. A main
    checkout's lock is never touched.
    """
    directories = git_directories(path)
    if directories is None or directories.main:
        return None
    lock = directories.git_dir / "index.lock"
    try:
        created = lock.lstat().st_mtime_ns
    except OSError:
        return None
    if time.time_ns() - created < min_age_seconds * 1e9 or lock_holders(lock):
        return None
    try:
        lock.unlink()
    except OSError:
        return None
    return lock


def _run(
    argv: Sequence[str], *, timeout: float, environment: dict[str, str]
) -> tuple[int, str, str]:
    process = subprocess.Popen(
        list(argv),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.communicate(timeout=TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
        raise
    return process.returncode, stdout, stderr


def _raise_failure(
    error: type[Exception],
    detail: str,
    *,
    verb: str,
    path: Path,
    since_ns: int,
    owned: bool,
    cause: BaseException | None,
) -> NoReturn:
    # Only an index-writing verb can strand the lock; with optional locks off,
    # a read that fails beside another writer's lock is not its author.
    directories = git_directories(path) if verb in INDEX_WRITING_VERBS else None
    lock = directories.git_dir / "index.lock" if directories is not None else None
    if lock is None or not stranded_lock(lock, since_ns=since_ns):
        raise error(detail) from cause
    removed = False
    if owned and directories is not None and not directories.main:
        try:
            lock.unlink()
            removed = True
        except FileNotFoundError:
            removed = True
        except OSError:
            removed = False
    stranded = StrandedIndexLock(lock=lock, removed=removed)
    raise error(f"{detail}; {stranded}") from stranded


def git(
    path: Path,
    *arguments: str,
    timeout: float = CALL_TIMEOUT_SECONDS,
    error: type[Exception],
    ok_statuses: Sequence[int] = (0,),
    owned: bool = False,
    main_checkout: bool = False,
) -> str:
    """stdout of the call; any exit status outside ``ok_statuses`` raises ``error``.

    ``owned`` says the caller owns the linked worktree at ``path``, so a lock
    this call strands there is removed. ``main_checkout`` is the explicit
    permission an index-writing verb needs to run in a main checkout.
    """
    verb = arguments[0] if arguments else ""
    if verb in INDEX_WRITING_VERBS and not main_checkout:
        directories = git_directories(path)
        if directories is not None and directories.main:
            raise error(
                f"git {verb} refused in the main checkout {path}: "
                "agentctl writes the index only of a worktree it owns"
            )
    started = time.time_ns()
    try:
        returncode, stdout, stderr = _run(
            ["git", "-C", str(path), *arguments],
            timeout=timeout,
            environment={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
    except OSError as failure:
        raise error(f"git {verb} failed in {path}: {failure}") from failure
    except subprocess.TimeoutExpired as failure:
        _raise_failure(
            error,
            f"git {verb} failed in {path}: {failure}",
            verb=verb,
            path=path,
            since_ns=started,
            owned=owned,
            cause=failure,
        )
    if returncode not in ok_statuses:
        detail = stderr.strip() or stdout.strip()
        _raise_failure(
            error,
            f"git {' '.join(arguments[:2])}: {detail}",
            verb=verb,
            path=path,
            since_ns=started,
            owned=owned,
            cause=None,
        )
    return stdout.strip()


def stranded_index_lock(failure: BaseException) -> StrandedIndexLock | None:
    """The stranded lock a failed `git` call reported, if any."""
    cause = failure.__cause__
    return cause if isinstance(cause, StrandedIndexLock) else None
