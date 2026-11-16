"""Build output of the checkouts under the worktree roots.

A report of what each checkout's build output occupies and when the checkout
was last used, and an explicit removal of that output for checkouts idle long
enough. Only regenerable output is ever removed: named directories inside the
checkout that Git ignores and tracks nothing in, and the checkout's own Cargo
target in the compiler cache. Sources, the Git state and the checkout itself
stay.

Checkouts whose directory name matches a configured exempt pattern are listed
by name only: nothing under them is read, sized or removed.
"""

from __future__ import annotations

import fcntl
import fnmatch
import hashlib
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from . import gitcmd, pueue
from .config import Config

# Directory names, directly inside a checkout, that hold regenerable output.
IN_TREE_OUTPUT = (
    "target",
    "node_modules",
    ".venv",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
)
DEFAULT_ROOT = Path("/realm/worktree")
DU_TIMEOUT_SECONDS = 600


class BuildOutputError(RuntimeError):
    pass


def worktree_roots(config: Config) -> list[Path]:
    """The directories the registered projects keep their worktrees in."""
    roots = {
        Path(row["workspace"]["root"])
        for row in config.catalog().list()
        if row.get("workspace")
    }
    return sorted(roots) or [DEFAULT_ROOT]


def cargo_cache_entries(path: Path) -> list[Path]:
    """This checkout's directories in the compiler cache.

    `sinnix-cargo-target` keys the entry by the checkout's real path. A
    removal that was interrupted leaves it under the `.evicting.` name.
    """
    root = Path(os.environ.get("SINNIX_CARGO_CACHE_ROOT", "/realm/state/cache/cargo"))
    key = hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:32]
    parent = root / str(os.getuid())
    entries = []
    for entry in (parent / key, parent / f".evicting.{key}"):
        if entry.is_symlink() or not entry.is_dir():
            continue
        marker = entry / "checkout"
        if marker.is_symlink() or not marker.is_file():
            continue
        if marker.read_bytes() != os.fsencode(path.resolve()) + b"\n":
            continue  # the entry names another checkout; it is not ours to judge
        entries.append(entry)
    return entries


def in_tree_outputs(path: Path) -> list[Path]:
    """The named output directories Git ignores and tracks nothing in."""
    present = [
        name
        for name in IN_TREE_OUTPUT
        if (path / name).is_dir() and not (path / name).is_symlink()
    ]
    if not present or gitcmd.git_directories(path) is None:
        return []
    try:
        ignored = set(
            gitcmd.git(
                path,
                "check-ignore",
                "--",
                *present,
                error=BuildOutputError,
                ok_statuses=(0, 1),
            ).split("\n")
        )
        tracked = {
            line.split("/", 1)[0]
            for line in gitcmd.git(
                path, "ls-files", "--", *present, error=BuildOutputError
            ).split("\n")
            if line
        }
    except BuildOutputError:
        return []
    return [path / name for name in present if name in ignored and name not in tracked]


def disk_bytes(path: Path) -> int | None:
    try:
        result = subprocess.run(
            ["du", "-sx", "--block-size=1", "--", str(path)],
            capture_output=True,
            text=True,
            timeout=DU_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    field = result.stdout.split("\t", 1)[0]
    return int(field) if field.isdecimal() else None


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def last_used(path: Path, outputs: Sequence[Path], cache: Sequence[Path]) -> float:
    """The newest sign of use: Git activity, the checkout, or its build output."""
    stamps = [_mtime(path), *(_mtime(output) for output in outputs)]
    directories = gitcmd.git_directories(path)
    if directories is not None:
        git_dir = directories.git_dir
        stamps += [_mtime(git_dir / name) for name in ("HEAD", "index", "logs/HEAD")]
    for entry in cache:
        # The marker is rewritten at every selection of the target.
        stamps += [_mtime(entry / "checkout"), _mtime(entry / "target")]
        stamps += [_mtime(profile) for profile in (entry / "target").glob("*/")]
        stamps += [_mtime(deps) for deps in (entry / "target").glob("*/deps")]
    return max(stamps)


def _held_locks(entry: Path) -> list[Path]:
    held = []
    for pattern in (".cargo-lock", "*/.cargo-lock", "*/*/.cargo-lock"):
        for lock in (entry / "target").glob(pattern):
            try:
                with lock.open("rb") as handle:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                held.append(lock)
            except OSError:
                continue
    return held


def _processes_inside(roots: Sequence[Path]) -> dict[Path, list[int]]:
    """Processes whose working directory is in one of these checkouts."""
    inside: dict[Path, list[int]] = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            cwd = Path(os.readlink(entry / "cwd"))
        except OSError:
            continue
        for root in roots:
            if cwd == root or root in cwd.parents:
                inside.setdefault(root, []).append(int(entry.name))
    return inside


def report(
    config: Config,
    *,
    roots: Sequence[Path] | None = None,
    now: datetime | None = None,
    measure: bool = True,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    roots = list(roots) if roots else worktree_roots(config)
    checkouts = sorted(
        child
        for root in roots
        if root.is_dir()
        for child in root.iterdir()
        if child.is_dir() and not child.is_symlink()
    )
    exempt = {
        child
        for child in checkouts
        if any(fnmatch.fnmatchcase(child.name, p) for p in config.build_output_exempt)
    }
    examined = [child for child in checkouts if child not in exempt]
    processes = _processes_inside([child.resolve() for child in examined])
    tasks = [task for task in pueue.tasks().values() if not task.terminal]
    rows = []
    for child in checkouts:
        if child in exempt:
            rows.append({"path": str(child), "name": child.name, "exempt": True})
            continue
        resolved = child.resolve()
        outputs = in_tree_outputs(child)
        cache = cargo_cache_entries(child)
        live = []
        if pids := processes.get(resolved):
            live.append(f"{len(pids)} process(es) work here (first pid {min(pids)})")
        for task in tasks:
            if Path(task.path).is_absolute() and (
                Path(task.path).resolve() == resolved
                or resolved in Path(task.path).resolve().parents
            ):
                live.append(f"job #{task.task_id} {task.label} {task.status.lower()}")
        for entry in cache:
            if _held_locks(entry):
                live.append("a build holds its Cargo target lock")
        used = last_used(child, outputs, cache)
        items = [
            {
                "path": str(item),
                "kind": kind,
                "bytes": disk_bytes(item) if measure else None,
            }
            for kind, group in (
                ("in-tree", outputs),
                ("cargo-cache", [entry / "target" for entry in cache]),
            )
            for item in group
        ]
        sizes = [item["bytes"] for item in items]
        rows.append(
            {
                "path": str(child),
                "name": child.name,
                "exempt": False,
                "git": gitcmd.git_directories(child) is not None,
                "outputs": items,
                "bytes": sum(size for size in sizes if size is not None)
                if all(size is not None for size in sizes)
                else None,
                "last_used_at": datetime.fromtimestamp(used, UTC).isoformat(
                    timespec="seconds"
                ),
                "idle_days": round(max(0.0, now.timestamp() - used) / 86400, 1),
                "live": live,
            }
        )
    return {
        "roots": [str(root) for root in roots],
        "exempt_patterns": list(config.build_output_exempt),
        "worktrees": rows,
    }


def _remove_cache_entry(entry: Path) -> None:
    """Remove one compiler cache entry no build is using.

    The entry is renamed while its primary build lock is held, as
    `sinnix-cargo-target-evict` does, so a build that starts afterwards
    selects a fresh target instead of writing into one being deleted.
    """
    trash = entry.with_name(f".evicting.{entry.name.removeprefix('.evicting.')}")
    if entry != trash:
        primary = entry / "target" / "debug" / ".cargo-lock"
        if primary.is_file():
            with primary.open("rb") as handle:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                entry.rename(trash)
        else:
            entry.rename(trash)
    shutil.rmtree(trash)


def expire(
    config: Config,
    *,
    idle_days: float,
    apply: bool = False,
    roots: Sequence[Path] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Remove the build output of checkouts idle for at least ``idle_days``.

    Without ``apply`` nothing is removed and the result lists what would be.
    """
    if idle_days < 0:
        raise BuildOutputError("--expire-idle-days must not be negative")
    listing = report(config, roots=roots, now=now, measure=True)
    selected, kept = [], []
    for row in listing["worktrees"]:
        if row["exempt"]:
            kept.append({"name": row["name"], "reason": "exempt by configuration"})
            continue
        if not row["outputs"]:
            continue
        if row["live"]:
            kept.append({"name": row["name"], "reason": "; ".join(row["live"])})
        elif row["idle_days"] < idle_days:
            kept.append(
                {
                    "name": row["name"],
                    "reason": f"used {row['idle_days']} day(s) ago, "
                    f"under the {idle_days:g}-day limit",
                }
            )
        else:
            selected.append(row)
    removed, freed = [], 0
    for row in selected:
        for item in row["outputs"]:
            path = Path(item["path"])
            entry = {"worktree": row["name"], **item}
            if apply:
                try:
                    if item["kind"] == "cargo-cache":
                        _remove_cache_entry(path.parent)
                    else:
                        if path.parent != Path(row["path"]) or path.is_symlink():
                            raise BuildOutputError("not a directory of this checkout")
                        shutil.rmtree(path)
                except (OSError, BuildOutputError) as error:
                    kept.append(
                        {"name": row["name"], "reason": f"{path}: {error}"[:240]}
                    )
                    continue
            removed.append(entry)
            freed += item["bytes"] or 0
    return {
        "applied": apply,
        "idle_days": idle_days,
        "removed": removed,
        "bytes": freed,
        "kept": kept,
        "exempt_patterns": listing["exempt_patterns"],
    }


def size_text(value: int | None) -> str:
    if value is None:
        return "?"
    for unit, scale in (("GiB", 2**30), ("MiB", 2**20), ("KiB", 2**10)):
        if value >= scale:
            return f"{value / scale:.1f} {unit}"
    return f"{value} B"


def render_report(listing: dict[str, Any]) -> str:
    lines = [f"{'worktree':<40} {'build output':>12} {'last used':<20} state"]
    for row in listing["worktrees"]:
        if row["exempt"]:
            lines.append(f"{row['name']:<40} {'-':>12} {'-':<20} exempt, not examined")
            continue
        state = "live: " + "; ".join(row["live"]) if row["live"] else "idle"
        lines.append(
            f"{row['name']:<40} {size_text(row['bytes']) if row['outputs'] else 'none':>12} "
            f"{row['last_used_at'][:16]:<20} {state} ({row['idle_days']} d)"
        )
    return "\n".join(lines)


def render_expiry(result: dict[str, Any]) -> str:
    verb = "removed" if result["applied"] else "would remove"
    lines = [
        f"{verb} {item['path']} ({size_text(item['bytes'])})"
        for item in result["removed"]
    ]
    lines += [f"kept {item['name']}: {item['reason']}" for item in result["kept"]]
    lines.append(
        f"{verb} {size_text(result['bytes'])} of build output in "
        f"{len({item['worktree'] for item in result['removed']})} worktree(s)"
        + ("" if result["applied"] else "; pass --apply to remove it")
    )
    return "\n".join(lines)
