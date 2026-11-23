"""Who owns each entry under the managed temporary root and the worktree roots.

Everything that writes bulk data there is responsible for removing it: a
job's scratch ends with the job, a Claude Code session's with the session, a
worktree's compiler target with the worktree. This report lists each entry
with the owner that will remove it and marks the entries that have none, so a
broken invariant shows up as a named path instead of a full disk. It reads
and deletes nothing beyond directory listings, Git's worktree metadata, the
queue and /proc.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from . import build_output, pueue
from .config import Config
from .job_queries import job_id_of
from .launch_input import scratch_root

TEMPORARY_ROOT = Path(os.environ.get("SINNIX_TEMPORARY_ROOT", "/realm/tmp/work"))
PARKING = Path("/realm/state/hub/parking")
SESSION_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
DEVSHELL = re.compile(r"nix-shell\..+|nix-develop-.+")
# Producers that name their scratch after their own PID (docs/scratch.md).
PID_SCRATCH = re.compile(
    r"sinnix-(?:chatgpt-(?:native|download)|router-poll)\.([1-9][0-9]*)\.[A-Za-z0-9]{6}"
)
HOLDER_VARIABLES = (b"TMPDIR=", b"AGENTCTL_SCRATCH=", b"CLAUDE_CODE_SESSION_ID=")


def _processes() -> tuple[dict[Path, int], set[str]]:
    """The user's processes: directories they use (cwd, TMPDIR) and session ids."""
    used: dict[Path, int] = {}
    sessions: set[str] = set()
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        pid = int(entry.name)
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            used.setdefault(Path(os.readlink(entry / "cwd")), pid)
            environ = (entry / "environ").read_bytes().split(b"\0")
        except OSError:
            continue
        for item in environ:
            for variable in HOLDER_VARIABLES:
                if not item.startswith(variable):
                    continue
                value = item[len(variable) :].decode(errors="replace")
                if variable == b"CLAUDE_CODE_SESSION_ID=":
                    sessions.add(value)
                elif value.startswith("/"):
                    used.setdefault(Path(value), pid)
    return used, sessions


def _holder(path: Path, used: dict[Path, int]) -> int | None:
    for directory, pid in used.items():
        if directory == path or path in directory.parents:
            return pid
    return None


def _live_claude_sessions(home: Path) -> set[str]:
    """Sessions a running Claude Code process has recorded as its own."""
    live = set()
    for config in {home / ".claude", home / ".config" / "claude"}:
        for record in (config / "sessions").glob("*.json"):
            try:
                document = json.loads(record.read_text())
                stat = Path(f"/proc/{int(document['pid'])}/stat").read_text()
            except (OSError, ValueError, KeyError, TypeError):
                continue
            started = stat.rsplit(")", 1)[1].split()[19]
            if str(document.get("procStart")) == started:
                live.add(str(document.get("sessionId")))
    return live


def _row(path: Path, owner: str | None, state: str) -> dict[str, Any]:
    return {"path": str(path), "owner": owner, "state": state}


def _job_rows(root: Path) -> list[dict[str, Any]]:
    tasks = {job_id_of(task): task for task in pueue.tasks().values()}
    rows = []
    for child in sorted(root.iterdir()) if root.is_dir() else []:
        task = tasks.get(child.name)
        if task is not None and not task.terminal:
            rows.append(_row(child, f"job {child.name}", f"task {task.task_id} {task.status.lower()}"))
        elif task is not None:
            rows.append(_row(child, None, f"job ended ({task.result}) but its scratch remains"))
        else:
            rows.append(_row(child, None, "no queued job has this id"))
    return rows


def _session_rows(base: Path, live: set[str], carried: set[str]) -> list[dict[str, Any]]:
    ended = {p.name for p in (base / ".ended").glob("*")}
    rows = []
    for group in sorted(base.iterdir()):
        if group.name in {".ended", ".released"} or group.is_symlink():
            continue
        if not group.is_dir():
            rows.append(_row(group, None, "loose file in the session area"))
            continue
        children = sorted(group.iterdir())
        sessions = [c for c in children if SESSION_ID.fullmatch(c.name) and c.is_dir()]
        if not sessions:
            rows.append(_row(group, None, "not a session's directory"))
            continue
        for tree in sessions:
            session = tree.name
            owner = f"session {session}"
            if session in live or session in carried:
                rows.append(_row(tree, owner, "session is open"))
            elif (PARKING / session).exists():
                rows.append(_row(tree, owner, "session parked; kept for its resume"))
            elif session in ended:
                rows.append(_row(tree, owner, "session ended; removal pending"))
            else:
                rows.append(_row(tree, owner, "session stopped without ending; kept until resumed and ended"))
        for other in children:
            if other not in sessions:
                rows.append(_row(other, None, "not a session's directory"))
    for trash in sorted((base / ".released").glob("*")):
        rows.append(_row(trash, None, "released session scratch whose deletion stopped"))
    return rows


def temporary_rows() -> list[dict[str, Any]]:
    root = TEMPORARY_ROOT
    used, carried = _processes()
    live = _live_claude_sessions(Path.home())
    jobs = scratch_root("nvme")
    rows: list[dict[str, Any]] = []
    for entry in sorted(root.iterdir()) if root.is_dir() else []:
        name = entry.name
        if entry == jobs:
            rows += _job_rows(entry)
        elif name == f"claude-{os.getuid()}" and entry.is_dir():
            rows += _session_rows(entry, live, carried)
        elif DEVSHELL.fullmatch(name):
            pid = _holder(entry, used)
            rows.append(
                _row(entry, f"process {pid}", "devshell in use")
                if pid
                else _row(entry, "sinnix-tmp-sweep", "devshell nothing holds; swept")
            )
        elif match := PID_SCRATCH.fullmatch(name):
            alive = Path(f"/proc/{match[1]}").exists()
            rows.append(
                _row(entry, f"process {match[1]}", "producer running")
                if alive
                else _row(entry, "sinnix-tmp-sweep", "producer gone; swept after 24 hours")
            )
        elif pid := _holder(entry, used):
            rows.append(_row(entry, f"process {pid}", "in use by a running process"))
        else:
            rows.append(_row(entry, None, "nothing names an owner"))
    tmpfs = scratch_root("tmpfs")
    if tmpfs is not None and tmpfs != jobs:
        rows += _job_rows(tmpfs)
    return rows


def _registered(checkout: Path) -> tuple[str | None, str]:
    """The repository whose worktree registry names this checkout."""
    marker = checkout / ".git"
    if marker.is_dir():
        return None, "a standalone clone; no repository registers it"
    try:
        text = marker.read_text().strip()
    except OSError:
        return None, "not a Git checkout"
    if not text.startswith("gitdir: "):
        return None, "unreadable .git file"
    admin = Path(text.removeprefix("gitdir: "))
    try:
        back = Path((admin / "gitdir").read_text().strip()).parent
    except OSError:
        return None, f"its repository no longer registers it ({admin})"
    if back.resolve() != checkout.resolve():
        return None, f"its registration names {back}"
    repository = admin.parent.parent
    locked = " (locked)" if (admin / "locked").exists() else ""
    return f"worktree of {repository.parent if repository.name == '.git' else repository}{locked}", "registered worktree"


def worktree_rows(roots: Iterable[Path]) -> list[dict[str, Any]]:
    rows = []
    for root in roots:
        for child in sorted(root.iterdir()) if root.is_dir() else []:
            if child.is_symlink() or not child.is_dir():
                rows.append(_row(child, None, "not a checkout directory"))
                continue
            owner, state = _registered(child)
            rows.append(_row(child, owner, state))
    return rows


def cargo_rows() -> list[dict[str, Any]]:
    root = Path(os.environ.get("SINNIX_CARGO_CACHE_ROOT", "/realm/state/cache/cargo"))
    rows = []
    directory = root / str(os.getuid())
    for entry in sorted(directory.iterdir()) if directory.is_dir() else []:
        try:
            checkout = (entry / "checkout").read_text().splitlines()[0]
        except (OSError, IndexError):
            rows.append(_row(entry, None, "compiler target without a checkout marker"))
            continue
        key = hashlib.sha256(checkout.encode()).hexdigest()[:32]
        if entry.name.removeprefix(".evicting.") != key:
            rows.append(_row(entry, None, f"marker names {checkout}, another key"))
        elif entry.name.startswith(".evicting."):
            rows.append(_row(entry, None, "interrupted release; the next new target finishes it"))
        elif Path(checkout).exists() or Path(checkout).is_symlink():
            rows.append(_row(entry, f"checkout {checkout}", "compiler target of an existing checkout"))
        else:
            rows.append(_row(entry, None, f"checkout {checkout} is gone; the next new target releases it"))
    return rows


def report(
    config: Config, *, sizes: bool = False, unowned_only: bool = False
) -> dict[str, Any]:
    sections = {
        "temporary": temporary_rows(),
        "worktrees": worktree_rows(build_output.worktree_roots(config)),
        "compiler_targets": cargo_rows(),
    }
    unowned = sum(1 for rows in sections.values() for row in rows if row["owner"] is None)
    if unowned_only:
        sections = {
            name: [row for row in rows if row["owner"] is None]
            for name, rows in sections.items()
        }
    if sizes:
        for rows in sections.values():
            for row in rows:
                row["bytes"] = build_output.disk_bytes(Path(row["path"]))
    return {"sections": sections, "unowned": unowned}


def render(listing: dict[str, Any]) -> str:
    lines = []
    for section, rows in listing["sections"].items():
        lines.append(f"{section.replace('_', ' ')}:")
        for row in rows:
            size = (
                f" {build_output.size_text(row['bytes']):>9}" if "bytes" in row else ""
            )
            mark = "UNOWNED" if row["owner"] is None else row["owner"]
            lines.append(f"  {row['path']}{size}  {mark}: {row['state']}")
    lines.append(f"{listing['unowned']} unowned entr{'y' if listing['unowned'] == 1 else 'ies'}")
    return "\n".join(lines)
