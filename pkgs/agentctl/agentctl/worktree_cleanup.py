"""Remove published worktrees after saving their commit in a recovery ref."""

from __future__ import annotations

import fcntl
import hashlib
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

from . import gitcmd, github, pueue, worktrunk
from .config import Config
from .projects import ProjectAdapter
from .worktrunk import Worktree, WorktrunkError


class CleanupError(RuntimeError):
    """A checkout cannot be inspected or removed."""


@contextmanager
def project_locked(config: Config, project_id: str) -> Iterator[None]:
    """One cleanup pass per project at a time."""
    path = config.state_dir / "worktree-cleanup" / f"{project_id}.lock"
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _git(path: Path, *arguments: str) -> str:
    return gitcmd.git(path, *arguments, error=CleanupError)


def _has_origin(root: Path) -> bool:
    return "origin" in _git(root, "remote").split()


def _remote_default(project: ProjectAdapter) -> str | None:
    if project.workspace:
        base = project.workspace.default_base
        for prefix in ("refs/remotes/origin/", "origin/"):
            if base.startswith(prefix):
                return base.removeprefix(prefix)
    if not _has_origin(project.root):
        return None
    known = gitcmd.git(
        project.root,
        "symbolic-ref",
        "--quiet",
        "refs/remotes/origin/HEAD",
        ok_statuses=(0, 1),
        error=CleanupError,
    )
    if known.startswith("refs/remotes/origin/"):
        return known.removeprefix("refs/remotes/origin/")
    for line in _git(
        project.root, "ls-remote", "--symref", "origin", "HEAD"
    ).splitlines():
        target, _, name = line.partition("\t")
        if name == "HEAD" and target.startswith("ref: refs/heads/"):
            return target.removeprefix("ref: refs/heads/")
    raise CleanupError("origin's default branch could not be resolved")


class Published:
    """Default-branch history and exact heads of merged pull requests."""

    def __init__(self, project: ProjectAdapter):
        self.root = project.root
        self.default = _remote_default(project)
        if self.default and _has_origin(self.root):
            _git(self.root, "fetch", "--quiet", "--no-tags", "origin", self.default)
            reference = f"refs/remotes/origin/{self.default}"
        else:
            reference = (
                project.workspace.default_base if project.workspace else "master"
            )
            if reference.startswith("origin/") and not _has_origin(self.root):
                reference = reference.removeprefix("origin/")
        self.base = _git(self.root, "rev-parse", "--verify", reference + "^{commit}")
        self.commits = set(_git(self.root, "rev-list", self.base).splitlines())
        self.tree = _git(self.root, "rev-parse", self.base + "^{tree}")
        self.pulls: dict[str, list[dict[str, Any]] | str] = {}

    def _merged_pulls(
        self, head: str, branch: str | None
    ) -> list[dict[str, Any]] | str:
        key = branch or head
        if key not in self.pulls:
            selector = ["--head", branch] if branch else ["--search", head]
            try:
                rows = github.gh_json(
                    [
                        "pr",
                        "list",
                        "--state",
                        "merged",
                        *selector,
                        "--json",
                        "number,headRefOid,mergeCommit",
                    ],
                    cwd=self.root,
                )
                self.pulls[key] = [row for row in rows or [] if isinstance(row, dict)]
            except github.GithubError as error:
                self.pulls[key] = str(error)
        return self.pulls[key]

    def contains(self, head: str, branch: str | None = None) -> bool:
        return self.missing(head, branch) is None

    def missing(self, head: str, branch: str | None = None) -> str | None:
        if (
            head in self.commits
            or _git(self.root, "rev-parse", head + "^{tree}") == self.tree
        ):
            return None
        short = head[:12]
        facts = [f"HEAD {short} is not on {self.base[:12]} of the default branch"]
        pulls = self._merged_pulls(head, branch)
        if isinstance(pulls, str):
            facts.append(f"the forge could not be asked ({pulls})")
        else:
            for row in pulls:
                commit = (row.get("mergeCommit") or {}).get("oid")
                if row.get("headRefOid") == head and commit in self.commits:
                    return None
            matching = [row for row in pulls if row.get("headRefOid") == head]
            if matching:
                facts.append(
                    f"merged PR #{matching[0].get('number')} has head {short} but its "
                    "merge commit is not on the fetched default branch"
                )
            elif pulls:
                facts.append(f"no merged PR has head {short}")
            else:
                facts.append(
                    f"no merged PR for branch {branch}"
                    if branch
                    else f"no merged PR has head {short}"
                )
        return "publication not proved: " + "; ".join(facts)


def _checkout_changes(project: ProjectAdapter, path: Path) -> str | None:
    common = ("rev-parse", "--path-format=absolute", "--git-common-dir")
    if (
        Path(_git(path, *common)).resolve()
        != Path(_git(project.root, *common)).resolve()
    ):
        return "worktree kept; checkout belongs to another Git repository"
    dirty = _git(path, "status", "--porcelain=v1", "--untracked-files=all").splitlines()
    if dirty:
        names = ", ".join(line.split(maxsplit=1)[-1] for line in dirty[:3])
        return f"worktree kept; uncommitted changes: {names}"
    return None


def _external_cache(path: Path) -> Path | None:
    """The compiler selector's exact directory for this checkout."""
    root = Path(os.environ.get("SINNIX_CARGO_CACHE_ROOT", "/realm/state/cache/cargo"))
    key = hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:32]
    parent = root / str(os.getuid()) / key
    if not parent.exists() and not parent.is_symlink():
        return None
    target = parent / "target"
    if any(item.is_symlink() for item in (root, parent.parent, parent, target)):
        raise CleanupError(f"compiler cache is symlinked; inspect {parent}")
    marker = parent / "checkout"
    if marker.is_symlink() or (
        marker.exists() and marker.read_bytes() != os.fsencode(path.resolve()) + b"\n"
    ):
        raise CleanupError(
            f"compiler cache checkout marker names another checkout; inspect {marker}"
        )
    return parent


def _recovery_ref(root: Path, path: Path, head: str) -> str:
    token = hashlib.sha256(str(path).encode()).hexdigest()[:16]
    ref = f"refs/agentctl/recovery/checkouts/{token}/{head}"
    _git(root, "update-ref", ref, head)
    if _git(root, "rev-parse", "--verify", ref + "^{commit}") != head:
        raise CleanupError(f"recovery ref did not retain {head}: {ref}")
    return ref


def _delete_remote_branch(
    project: ProjectAdapter, branch: str, head: str, default: str | None
) -> str | None:
    if default is None or branch == default or not _has_origin(project.root):
        return None
    try:
        advertised = _git(
            project.root, "ls-remote", "--heads", "origin", f"refs/heads/{branch}"
        ).split()
        if not advertised:
            return None
        if advertised[0] != head:
            return f"remote branch kept; it names {advertised[0][:12]}, not the published {head[:12]}"
        _git(
            project.root,
            "push",
            "--quiet",
            f"--force-with-lease=refs/heads/{branch}:{head}",
            "origin",
            f":refs/heads/{branch}",
        )
    except CleanupError as error:
        return f"remote branch kept; {error}"
    return None


def _unfinished_jobs(path: Path, tasks: Sequence[pueue.Task]) -> list[str]:
    return [
        f"task {task.task_id} {task.label!r} {task.status.lower()} cwd {task.path}"
        for task in tasks
        if not task.terminal
        and Path(task.path).is_absolute()
        and Path(task.path).resolve().is_relative_to(path.resolve())
    ]


def _remove(project: ProjectAdapter, tree: Worktree, head: str) -> None:
    path = tree.path
    assert path is not None
    if _git(path, "rev-parse", "HEAD") != head:
        raise CleanupError("checkout HEAD changed after the publication check")
    reason = _checkout_changes(project, path)
    if reason:
        raise CleanupError(reason)
    _recovery_ref(project.root, path, head)
    if _git(path, "rev-parse", "HEAD") != head:
        raise CleanupError("checkout HEAD changed after the publication check")
    jobs = _unfinished_jobs(path, list(pueue.tasks().values()))
    if jobs:
        raise CleanupError("unfinished job: " + jobs[0])
    worktrunk.worktrunk_remove(project.root, str(path), keep_branch=True, reap=False)
    if path.exists() or path.is_symlink():
        raise CleanupError(f"checkout path remains after removal: {path}")


def clean(
    config: Config, project: ProjectAdapter, *, paths: Sequence[Path] | None = None
) -> dict[str, Any]:
    """Remove published registered worktrees, or only the requested paths."""
    selected = {path.absolute() for path in paths} if paths is not None else None
    removed: list[str] = []
    kept: list[dict[str, str]] = []
    with project_locked(config, project.project_id):
        registry = worktrunk.worktrunk_list(project.root)
        candidates = [
            tree
            for tree in registry
            if tree.path is not None
            and not tree.main
            and (selected is None or tree.path in selected)
        ]
        registered = {tree.path for tree in registry}
        for path in sorted((selected or set()) - registered):
            kept.append({"branch": str(path), "reason": "checkout is not registered"})
        if not candidates:
            return {"project": project.project_id, "removed": removed, "kept": kept}
        published = Published(project)
        for tree in candidates:
            path = tree.path
            assert path is not None
            name = tree.branch or str(path)
            try:
                if (
                    tree.locked
                    or tree.branch == published.default
                    or path == project.root
                ):
                    raise CleanupError(
                        "checkout is locked or is the project's main checkout"
                    )
                if path.is_symlink() or not path.is_dir():
                    raise CleanupError("checkout path is a symlink or is unavailable")
                head = _git(path, "rev-parse", "HEAD")
                reason = published.missing(head, tree.branch) or _checkout_changes(
                    project, path
                )
                if reason:
                    raise CleanupError(reason)
                cache = _external_cache(path)
                _remove(project, tree, head)
                removed.append(name)
                if cache:
                    if _external_cache(path) != cache:
                        raise CleanupError(
                            f"compiler cache changed before removal: {cache}"
                        )
                    shutil.rmtree(cache)
                if tree.branch:
                    if any(
                        other.branch == tree.branch
                        for other in worktrunk.worktrunk_list(project.root)
                    ):
                        raise CleanupError(f"branch remains checked out: {tree.branch}")
                    _git(
                        project.root,
                        "update-ref",
                        "-d",
                        f"refs/heads/{tree.branch}",
                        head,
                    )
                if tree.branch:
                    note = _delete_remote_branch(
                        project, tree.branch, head, published.default
                    )
                    if note:
                        kept.append({"branch": f"origin/{tree.branch}", "reason": note})
            except (CleanupError, WorktrunkError, OSError) as error:
                detail = f"checkout removed; {error}" if name in removed else str(error)
                kept.append({"branch": name, "reason": detail})
    return {"project": project.project_id, "removed": removed, "kept": kept}
