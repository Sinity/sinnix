"""Derived lane lifecycle: one state per unit of work, held nowhere.

Beads carry intent, sinnixd job records carry execution, git carries artifacts,
GitHub carries publication. Publication attempts and disposal have no store, so
a lane that finishes and fails to publish is invisible. This derives the join
from those stores alone and keeps nothing, so it is always recomputable.

A unit's state follows its CONTENT, never the existence of a pull request. One
branch ships a sequence of PRs, one PR carries many beads, and content lands
without that branch's PR, so PR presence over-reports work at risk by an order
of magnitude and would send a shipped worktree to disposal.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from .integration import (
    DEFAULT_BASE,
    _git,
    _landed_integration_branches,
    unintegrated_content,
)

WORKTREE_ROOT = Path("/realm/worktrees")

#: Generated files a gate leaves behind. They are not work, so a checkout
#: holding only these is disposable rather than dirty.
GENERATED_PATHS = (".testmondata", ".lane/", ".cache/", ".venv/")

#: Terminal job phases: a unit owned by one of these is not running.
_TERMINAL_PHASES = frozenset(
    {"succeeded", "failed", "cancelled", "timeout", "terminal", "refused"}
)

#: States that gc may dispose. Everything else is either live or holds work.
DISPOSABLE_STATES = frozenset({"integrated", "empty"})


@dataclass(frozen=True)
class LaneUnit:
    """One worktree, with the state derived from the authoritative stores."""

    workspace: str
    path: Path
    branch: str
    state: str
    reason: str
    files: tuple[str, ...]
    dirty: bool
    commits_ahead: int
    job_phase: str | None

    @property
    def actionable(self) -> bool:
        return self.state in {"unpublished", "dirty"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace,
            "path": str(self.path),
            "branch": self.branch,
            "state": self.state,
            "reason": self.reason,
            "files": list(self.files),
            "dirty": self.dirty,
            "commits_ahead": self.commits_ahead,
            "job_phase": self.job_phase,
        }


def live_worktree_cwds() -> set[str]:
    """Directories some process currently has open as its working directory."""
    live: set[str] = set()
    proc = Path("/proc")
    if not proc.is_dir():
        return live
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            live.add(os.readlink(entry / "cwd"))
        except OSError:
            continue
    return live


def _job_phases(jobs_dir: Path) -> dict[str, str]:
    """Map workspace path to the phase of the newest job that claimed it."""
    phases: dict[str, tuple[str, str]] = {}
    if not jobs_dir.is_dir():
        return {}
    for record in jobs_dir.glob("*.json"):
        try:
            payload = json.loads(record.read_text())
        except (OSError, ValueError):
            continue
        checkout = (payload.get("spec") or {}).get("checkout") or {}
        path = checkout.get("path")
        if not isinstance(path, str):
            continue
        state = payload.get("state") or {}
        phase = str(state.get("phase") or "unknown")
        created = str(payload.get("created_at") or "")
        previous = phases.get(path)
        if previous is None or created > previous[0]:
            phases[path] = (created, phase)
    return {path: phase for path, (_created, phase) in phases.items()}


def _has_uncommitted_work(path: Path) -> bool:
    """Whether a checkout holds changes worth preserving.

    A gate leaves generated files behind in every checkout it touches. Counting
    those as work makes almost every gated checkout look dirty and blocks its
    disposal forever.
    """
    for line in _git("status", "--porcelain", cwd=path).stdout.splitlines():
        name = line[3:].strip()
        if name and not _is_generated(name):
            return True
    return False


def _is_generated(name: str) -> bool:
    """Whether a reported path is generated output rather than work.

    `git status` reports an untracked directory with a trailing separator and
    a symlink or file without one, so matching the directory form alone leaves
    a checkout permanently dirty over a path that is not work -- and it says
    so while naming no file the operator could rescue.
    """
    candidate = name.rstrip("/")
    return any(
        candidate == prefix.rstrip("/") or name.startswith(prefix)
        for prefix in GENERATED_PATHS
    )


def _commits_ahead(path: Path, base: str) -> int:
    result = _git("rev-list", "--count", f"{base}..HEAD", cwd=path)
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


def refresh_base(repo: Path, base: str) -> bool:
    """Update the remote-tracking ref the classification is measured against.

    Every state here is relative to `base`. A stale ref reports landed work as
    held, so the fetch is part of deriving the answer, not a convenience.
    """
    remote, _, _branch = base.partition("/")
    if not _branch or remote == ".":
        return False
    return _git("fetch", "--quiet", remote, cwd=repo).returncode == 0


def derive_units(
    worktree_root: Path,
    git_common_dir: Path,
    base: str = DEFAULT_BASE,
    *,
    jobs_dir: Path | None = None,
    live_cwds: Iterable[str] | None = None,
) -> list[LaneUnit]:
    """Every worktree of this repository, classified by what it still holds."""
    if jobs_dir is None:
        jobs_dir = Path.home() / ".local/state/sinnixd/jobs"
    live = set(live_cwds) if live_cwds is not None else live_worktree_cwds()
    phases = _job_phases(jobs_dir)
    landed = set(_landed_integration_branches(git_common_dir.parent, base))
    units: list[LaneUnit] = []
    if not worktree_root.is_dir():
        return units
    for path in sorted(worktree_root.iterdir()):
        if not path.is_dir() or not (path / ".git").exists():
            continue
        common = _git(
            "rev-parse", "--path-format=absolute", "--git-common-dir", cwd=path
        )
        if common.returncode != 0 or Path(common.stdout.strip()) != git_common_dir:
            continue
        branch = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=path).stdout.strip()
        dirty = _has_uncommitted_work(path)
        files = unintegrated_content(path, base, repo=git_common_dir.parent)
        ahead = _commits_ahead(path, base)
        phase = phases.get(str(path))
        running = phase is not None and phase not in _TERMINAL_PHASES
        head = _git("rev-parse", "HEAD", cwd=path).stdout.strip()
        contained = False
        if head and landed:
            containing = _git(
                "branch",
                "--format=%(refname:short)",
                "--contains",
                head,
                cwd=git_common_dir.parent,
            ).stdout.split()
            contained = any(name in landed for name in containing)

        if str(path) in live:
            state, reason = "running", "a process is working in this checkout"
        elif running:
            state, reason = "running", f"owned by a job in phase {phase}"
        elif dirty:
            state, reason = "dirty", "uncommitted changes would be lost"
        elif files and not contained:
            state = "unpublished"
            reason = f"{len(files)} file(s) differ from {base} with no landed copy"
        elif ahead:
            state, reason = (
                "integrated",
                f"{ahead} commit(s) whose content is on {base}",
            )
        else:
            state, reason = "empty", f"no commits beyond {base}"
        units.append(
            LaneUnit(path.name, path, branch, state, reason, files, dirty, ahead, phase)
        )
    return units


def stuck(units: Sequence[LaneUnit]) -> list[LaneUnit]:
    """Units needing a decision. A branch holding work stays here until resolved."""
    return [unit for unit in units if unit.actionable]


def disposable(units: Sequence[LaneUnit]) -> list[LaneUnit]:
    """Units gc may remove: never live, never dirty, never holding own content."""
    return [
        unit
        for unit in units
        if unit.state in DISPOSABLE_STATES and not unit.dirty and not unit.files
    ]
