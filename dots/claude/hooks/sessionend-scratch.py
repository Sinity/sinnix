#!/usr/bin/env python3
"""SessionEnd hook: a Claude Code session's scratch ends with the session.

A session owns two directories under ``$CLAUDE_CODE_TMPDIR/claude-<uid>/``:
Claude Code's own ``<project>/<session-id>/`` (the scratchpad and background
task output) and ``session-tmp/<session-id>/``, the TMPDIR claude-tool-scope
gives its tool commands. When the session ends this hook records the end in
``.ended/<session-id>`` and starts a detached remover, so the harness never
waits on a large deletion.

A session being parked (``sinnix sessions park``) is meant to be resumed: the
parking tool leaves ``/realm/state/hub/parking/<session-id>`` before it ends
the process, and this hook consumes that marker and keeps the scratch. A
session that never reaches SessionEnd (killed, crashed) is resumable too and
keeps its scratch; resuming it and ending it later removes it.

The remover waits while any process still carries the session id or works
inside its directories (a tool command finishing after the session), up to
WAIT_SECONDS, and handles every session recorded as ended, so a tree kept by
a straggler goes at the next session end. Removal renames each tree into
``.released/`` first, so a half-deleted tree never sits at a session's path.

Usage: sessionend-scratch.py            (the hook; the event on stdin)
       sessionend-scratch.py --remove   (the detached remover)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

SESSION_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
PARKING = Path(os.environ.get("SINNIX_PARKING_DIR", "/realm/state/hub/parking"))
WAIT_SECONDS = 600
POLL_SECONDS = 5


def scratch_base() -> Path:
    root = os.environ.get("CLAUDE_CODE_TMPDIR") or os.environ.get("TMPDIR") or "/tmp"
    return Path(root) / f"claude-{os.getuid()}"


def session_trees(base: Path, session: str) -> list[Path]:
    """The session's directories: ``<base>/<group>/<session>``, real and ours."""
    trees = []
    try:
        groups = list(base.iterdir())
    except OSError:
        return []
    for group in groups:
        if group.name.startswith(".") or group.is_symlink() or not group.is_dir():
            continue
        tree = group / session
        try:
            if tree.is_dir() and not tree.is_symlink() and tree.stat().st_uid == os.getuid():
                trees.append(tree)
        except OSError:
            continue
    return trees


def holders(session: str, trees: list[Path]) -> list[int]:
    """Processes, other than this one, that carry the session or work in it."""
    found = []
    resolved = [tree.resolve() for tree in trees]
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal() or int(entry.name) == os.getpid():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            environ = (entry / "environ").read_bytes().split(b"\0")
            if f"CLAUDE_CODE_SESSION_ID={session}".encode() in environ:
                found.append(int(entry.name))
                continue
            cwd = Path(os.readlink(entry / "cwd"))
        except OSError:
            continue
        if any(cwd == tree or tree in cwd.parents for tree in resolved):
            found.append(int(entry.name))
    return found


def release(base: Path, session: str) -> bool:
    """Remove one ended session's trees unless something still uses them."""
    trees = session_trees(base, session)
    if trees and holders(session, trees):
        return False
    released = base / ".released"
    released.mkdir(mode=0o700, exist_ok=True)
    for tree in trees:
        trash = released / f"{session}.{tree.parent.name}"
        # An interrupted earlier removal can have left the same name behind.
        shutil.rmtree(trash, ignore_errors=True)
        try:
            tree.rename(trash)
        except FileNotFoundError:
            continue  # another remover took it
    for trash in released.glob(f"{session}.*"):
        shutil.rmtree(trash, ignore_errors=True)
    (base / ".ended" / session).unlink(missing_ok=True)
    return True


def remove_ended(base: Path, *, wait: float = WAIT_SECONDS) -> None:
    deadline = time.monotonic() + wait
    while True:
        try:
            pending = [p.name for p in (base / ".ended").iterdir() if SESSION_ID.fullmatch(p.name)]
        except FileNotFoundError:
            return
        pending = [session for session in pending if not release(base, session)]
        if not pending or time.monotonic() >= deadline:
            return
        time.sleep(POLL_SECONDS)


def on_session_end(payload: dict, base: Path) -> bool:
    """Record the end; True when a remover should run."""
    session = payload.get("session_id")
    if not isinstance(session, str) or not SESSION_ID.fullmatch(session):
        return False
    marker = PARKING / session
    if marker.exists():
        marker.unlink(missing_ok=True)
        return False
    if not session_trees(base, session):
        return False
    ended = base / ".ended"
    ended.mkdir(mode=0o700, parents=True, exist_ok=True)
    (ended / session).touch()
    return True


def main(argv: list[str]) -> int:
    base = scratch_base()
    if argv[1:] == ["--remove"]:
        remove_ended(base)
        return 0
    try:
        payload = json.load(sys.stdin)
    except (OSError, ValueError):
        return 0
    if not isinstance(payload, dict) or not on_session_end(payload, base):
        return 0
    idle = ["ionice", "-c", "3"] if shutil.which("ionice") else []
    subprocess.Popen(
        [*idle, sys.executable, os.path.abspath(__file__), "--remove"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env={**os.environ, "CLAUDE_CODE_TMPDIR": str(base.parent)},
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
