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


#: Gitignored lane publication scratch exists in no base; it is not content.
IGNORED_PREFIXES = (".lane/",)

#: How far back along the base to look for a file's content having landed.
HISTORY_DEPTH = 200


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


def _blob(ref_path: str, cwd: Path) -> str | None:
    """The object id of one path at one revision, or None if absent there."""
    result = _git("rev-parse", "--verify", "--quiet", ref_path, cwd=cwd)
    value = result.stdout.strip()
    return value or None


def _content_landed(name: str, base: str, path: Path, repo: Path, depth: int) -> bool:
    """Whether this checkout's version of one file is already on the base.

    Identical content settles it. Otherwise the base may have carried this exact
    version earlier and moved on since, which still means the lane's
    contribution landed, so the base's history for that path is searched for the
    same blob.
    """
    lane = _blob(f"HEAD:{name}", path)
    if lane is None:
        # The lane deletes this path; the deletion landed iff the base lacks it.
        return _blob(f"{base}:{name}", repo) is None
    if _blob(f"{base}:{name}", repo) == lane:
        return True
    history = _git(
        "log", f"--max-count={depth}", "--format=%H", base, "--", name, cwd=repo
    )
    for commit in history.stdout.split():
        if _blob(f"{commit}:{name}", repo) == lane:
            return True
    return False


def unintegrated_content(
    path: Path,
    base: str = DEFAULT_BASE,
    *,
    repo: Path | None = None,
    ignore_prefixes: Sequence[str] = IGNORED_PREFIXES,
    history_depth: int = HISTORY_DEPTH,
) -> tuple[str, ...]:
    """Files this checkout introduces whose content is not on the base yet.

    A branch keeps its commits after a squash-merge lands its content, so
    divergence alone reports finished work as pending. Comparing against the
    base's current files is not enough either: once the base moves, a file the
    lane touched differs for reasons that have nothing to do with this lane.

    Each file is judged on its own. Judging the whole patch at once lets one
    un-appliable file -- gitignored lane scratch, which exists in no base --
    report every other file in the diff as held.
    """
    introduced = _git("diff", f"{base}...HEAD", "--name-only", cwd=path)
    names = [
        line
        for line in introduced.stdout.splitlines()
        if line.strip() and not line.startswith(tuple(ignore_prefixes))
    ]
    if not names:
        return ()
    against = repo or path
    return tuple(
        name
        for name in names
        if not _content_landed(name, base, path, against, history_depth)
    )


def _landed_integration_branches(repo: Path, base: str) -> tuple[str, ...]:
    """Integration branches whose content is already on the base."""
    listed = _git("branch", "--format=%(refname:short)", cwd=repo)
    landed: list[str] = []
    for name in listed.stdout.splitlines():
        name = name.strip()
        if not name.startswith("integration/"):
            continue
        patch = _git("diff", f"{base}...{name}", cwd=repo).stdout
        if not patch.strip():
            landed.append(name)
            continue
        applied = subprocess.run(
            ["git", "apply", "-R", "--check", "-"],
            cwd=repo,
            input=patch,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
        if applied.returncode == 0:
            landed.append(name)
    return tuple(landed)


def discover_units(
    worktree_root: Path, git_common_dir: Path, base: str = DEFAULT_BASE
) -> list[IntegrationUnit]:
    """Every worktree of this repository holding unintegrated content."""
    units: list[IntegrationUnit] = []
    if not worktree_root.is_dir():
        return units
    landed = set(_landed_integration_branches(git_common_dir.parent, base))
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
        # A lane repaired during integration lands as modified content, so its
        # patch no longer reverse-applies. Containment in a landed integration
        # branch says the work is in regardless of how it was adjusted.
        head = _git("rev-parse", "HEAD", cwd=path).stdout.strip()
        if head and landed:
            containing = _git(
                "branch",
                "--format=%(refname:short)",
                "--contains",
                head,
                cwd=git_common_dir.parent,
            ).stdout.split()
            if any(name in landed for name in containing):
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
    contributed_nothing: list[str] = []
    for unit in batch.units:
        before = _git("rev-parse", "HEAD^{tree}", cwd=worktree).stdout.strip()
        result = _git("merge", "--no-ff", "--no-edit", unit.branch, cwd=worktree)
        if result.returncode != 0:
            _git("merge", "--abort", cwd=worktree)
            conflicted.append(unit.branch)
            continue
        after = _git("rev-parse", "HEAD^{tree}", cwd=worktree).stdout.strip()
        if before and after == before:
            # The merge changed no content, so this lane is already in. Branch
            # bookkeeping cannot always tell -- an integration branch that
            # landed and was then deleted leaves no ref to check containment
            # against -- but the resulting tree can.
            _git("reset", "--hard", "HEAD~1", cwd=worktree)
            contributed_nothing.append(unit.branch)
            continue
        merged.append(unit.branch)
    stat = _git("diff", "--shortstat", f"{base}...HEAD", cwd=worktree).stdout.strip()
    return {
        "branch": branch,
        "worktree": str(worktree),
        "merged": merged,
        "conflicted": conflicted,
        "already_integrated": contributed_nothing,
        "diffstat": stat,
    }
