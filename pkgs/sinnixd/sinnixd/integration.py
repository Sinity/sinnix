"""Batch lane branches into conflict-free integration units.

A lane is not a unit of publication. Several lanes whose file sets are disjoint
integrate onto one branch, gate together, and land as one change -- which is
also the only point where a defect visible across lanes can be seen at all.
"""

from __future__ import annotations

import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

DEFAULT_BASE = "origin/master"
MAX_UNITS_PER_BATCH = 8
GIT_TIMEOUT_SECONDS = 120


class IntegrationError(ValueError):
    """A batch cannot be derived or assembled."""


@dataclass(frozen=True)
class IntegrationUnit:
    """One lane branch holding content that is not yet on the base."""

    workspace: str
    path: Path
    branch: str
    files: tuple[str, ...]
    dirty: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace,
            "branch": self.branch,
            "files": list(self.files),
            "dirty": self.dirty,
        }


@dataclass
class IntegrationBatch:
    units: list[IntegrationUnit] = field(default_factory=list)
    files: set[str] = field(default_factory=set)

    @property
    def area(self) -> str:
        areas: Counter[str] = Counter()
        for unit in self.units:
            for name in unit.files:
                parts = name.split("/")
                if len(parts) > 1:
                    areas["/".join(parts[:2])] += 1
        return areas.most_common(1)[0][0] if areas else "tests"

    def to_dict(self) -> dict[str, Any]:
        return {
            "area": self.area,
            "units": [unit.to_dict() for unit in self.units],
            "file_count": len(self.files),
        }


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise IntegrationError(f"git {' '.join(args)} failed in {cwd}") from error


def unintegrated_content(
    path: Path, base: str = DEFAULT_BASE, *, repo: Path | None = None
) -> tuple[str, ...]:
    """Files this checkout introduces whose content is not on the base yet.

    A branch keeps its commits after a squash-merge lands its content, so
    divergence alone reports finished work as pending. Comparing the files
    against the base is not enough either: once the base moves, any file the
    lane touched differs for reasons that have nothing to do with this lane.

    The patch itself is the evidence. If it reverse-applies to the base, the
    base already contains it.
    """
    introduced = _git("diff", f"{base}...HEAD", "--name-only", cwd=path)
    names = [line for line in introduced.stdout.splitlines() if line.strip()]
    if not names:
        return ()
    patch = _git("diff", f"{base}...HEAD", cwd=path).stdout
    if patch.strip():
        applied = subprocess.run(
            ["git", "apply", "-R", "--check", "-"],
            cwd=repo or path,
            input=patch,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
        if applied.returncode == 0:
            return ()
    return tuple(names)


def discover_units(
    worktree_root: Path, git_common_dir: Path, base: str = DEFAULT_BASE
) -> list[IntegrationUnit]:
    """Every worktree of this repository holding unintegrated content."""
    units: list[IntegrationUnit] = []
    if not worktree_root.is_dir():
        return units
    for path in sorted(worktree_root.iterdir()):
        if not path.is_dir() or not (path / ".git").exists():
            continue
        branch_name = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=path).stdout.strip()
        if branch_name.startswith("integration/"):
            # An integration branch is an output of this process, not an input.
            continue
        common = _git(
            "rev-parse", "--path-format=absolute", "--git-common-dir", cwd=path
        )
        if common.returncode != 0:
            continue
        if Path(common.stdout.strip()) != git_common_dir:
            continue
        files = unintegrated_content(path, base, repo=git_common_dir.parent)
        if not files:
            continue
        branch = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=path).stdout.strip()
        dirty = bool(_git("status", "--porcelain", cwd=path).stdout.strip())
        units.append(IntegrationUnit(path.name, path, branch, files, dirty))
    return units


def pack(
    units: Sequence[IntegrationUnit], max_units: int = MAX_UNITS_PER_BATCH
) -> list[IntegrationBatch]:
    """Group units so no two in a batch touch the same file.

    Disjoint file sets are what make a batch reviewable: a conflict inside one
    is a real disagreement rather than two lanes editing the same lines.
    """
    if max_units < 1:
        raise IntegrationError("batch size must be positive")
    ordered = sorted(units, key=lambda unit: (-len(unit.files), unit.workspace))
    batches: list[IntegrationBatch] = []
    for unit in ordered:
        if unit.dirty:
            continue
        for batch in batches:
            if len(batch.units) >= max_units:
                continue
            if batch.files.intersection(unit.files):
                continue
            batch.units.append(unit)
            batch.files.update(unit.files)
            break
        else:
            batches.append(IntegrationBatch([unit], set(unit.files)))
    return batches


def assemble(
    batch: IntegrationBatch,
    *,
    repo: Path,
    worktree: Path,
    branch: str,
    base: str = DEFAULT_BASE,
) -> dict[str, Any]:
    """Merge a batch onto a fresh branch, reporting what would not merge.

    A lane that conflicts is left out rather than force-resolved: a conflict
    between disjoint file sets means the base moved under it, which is the
    lane's rebase to do.
    """
    if worktree.exists():
        _git("worktree", "remove", "--force", str(worktree), cwd=repo)
    _git("fetch", "-q", "origin", cwd=repo)
    created = _git("worktree", "add", "-q", str(worktree), "-b", branch, base, cwd=repo)
    if created.returncode != 0:
        raise IntegrationError(
            created.stderr.strip() or f"could not create worktree {worktree}"
        )
    merged: list[str] = []
    conflicted: list[str] = []
    for unit in batch.units:
        result = _git("merge", "--no-ff", "--no-edit", unit.branch, cwd=worktree)
        if result.returncode != 0:
            _git("merge", "--abort", cwd=worktree)
            conflicted.append(unit.branch)
        else:
            merged.append(unit.branch)
    stat = _git("diff", "--shortstat", f"{base}...HEAD", cwd=worktree).stdout.strip()
    return {
        "branch": branch,
        "worktree": str(worktree),
        "merged": merged,
        "conflicted": conflicted,
        "diffstat": stat,
    }
