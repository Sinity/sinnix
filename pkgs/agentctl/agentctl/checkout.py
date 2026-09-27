"""Which working tree a declared operation runs in.

An operation's `checkout` answers one question: which tree holds the code its
receipt is evidence about. The three values differ in whether they *select* a
tree or only constrain one the caller already chose:

- `any` runs wherever the caller pointed it, defaulting to the project root.
- `default` refuses every tree but the project root. It does not select one,
  so a launch that passes no workspace -- a timer's `job fire` -- runs in
  whatever state the operator left that checkout in. A receipt from it names
  the operator's branch and uncommitted work, not a candidate.
- `candidate` selects the tree itself: a worktree agentctl owns for one
  launch, pinned to the project's declared `default_base`. Correctness stops
  depending on a caller remembering
  `--workspace`, which is the whole point: the scheduled complete-corpus run
  that silently used a working tree fourteen commits behind its base was
  started by exactly the code path that passes no workspace.

Completed verification is reused through its execution receipt. A launch's
worktree is removed after its terminal receipt; no later launch may reset it.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from . import gitcmd, worktrunk
from .manifest import BatchRefusal
from .projects import ProjectAdapter, WorkspacePolicy

CANDIDATE_BRANCH_PREFIX = "agentctl/candidate-"
#: A push or fetch runs the repository's own hooks.
PUSH_TIMEOUT_SECONDS = 2_400


class CheckoutError(RuntimeError):
    """A declared checkout could not be resolved."""


def workspace_of(project: ProjectAdapter) -> WorkspacePolicy:
    if project.workspace is None:
        raise BatchRefusal(
            "workspace", f"project {project.project_id} declares no [workspace]"
        )
    return project.workspace


def worktree_path(project: ProjectAdapter, branch: str) -> Path:
    """`<workspace.root>/<repo>-<branch>`, the placement `wt` is configured for."""
    return (
        workspace_of(project).root / f"{project.root.name}-{branch.replace('/', '-')}"
    )


def base_commit(project: ProjectAdapter) -> str:
    """The commit the project's declared base names, fetched first when remote.

    A local ref lags its remote invisibly, and a clean status proves nothing
    about currency. A failed fetch is not fatal -- the last fetched base is
    still a commit, and refusing the launch outright would make an offline
    workstation unable to verify anything -- but it is never silently treated
    as up to date by this function's callers, which record the commit they
    resolved.
    """
    base = workspace_of(project).default_base
    if base.startswith("origin/"):
        try:
            gitcmd.git(
                project.root,
                "fetch",
                "--quiet",
                "origin",
                timeout=PUSH_TIMEOUT_SECONDS,
                error=CheckoutError,
            )
        except CheckoutError:
            pass
    return gitcmd.git(
        project.root, "rev-parse", "--verify", f"{base}^{{commit}}", error=CheckoutError
    )


def candidate_branch(reference: str) -> str:
    return CANDIDATE_BRANCH_PREFIX + reference


def candidate_tree(project: ProjectAdapter, reference: str, commit: str) -> Path:
    """Create or restore one launch's worktree at its pinned commit."""
    branch = candidate_branch(reference)
    existing = worktrunk.worktrunk_find(project.root, branch)
    created_here = False
    if existing is None or existing.path is None:
        created = worktrunk.worktrunk_create(
            project.root, branch, path=worktree_path(project, branch), base=commit
        )
        created_here = True
        if created.path is None:
            raise CheckoutError(f"wt created {branch} without a path")
        path = created.path
    else:
        path = existing.path
    if not path.is_dir():
        raise CheckoutError(f"candidate worktree is missing at {path}")
    head = gitcmd.git(path, "rev-parse", "HEAD", error=CheckoutError)
    if head != commit:
        if created_here:
            worktrunk.worktrunk_remove(project.root, branch, force=True, reap=False)
        raise CheckoutError(f"candidate worktree {path} moved from {commit} to {head}")
    return path


def remove_candidate_tree(project: ProjectAdapter, reference: str) -> None:
    branch = candidate_branch(reference)
    if worktrunk.worktrunk_find(project.root, branch) is not None:
        worktrunk.worktrunk_remove(project.root, branch, force=True, reap=False)


def release_candidate_checkout(
    checkout: Mapping[str, Any] | None, working_directory: str | Path
) -> None:
    """Remove only the registered worktree named by this candidate launch."""
    if not isinstance(checkout, Mapping) or checkout.get("kind") != "candidate":
        return
    root, branch = checkout.get("root"), checkout.get("branch")
    if not isinstance(root, str) or not isinstance(branch, str):
        raise CheckoutError("candidate checkout has no owner")
    if not branch.startswith(CANDIDATE_BRANCH_PREFIX):
        raise CheckoutError("candidate checkout branch is outside agentctl ownership")
    path = Path(working_directory)
    registered = worktrunk.worktrunk_find(Path(root), branch)
    if registered is not None and registered.path == path and path != Path(root):
        cache_path = checkout.get("cache_path")
        cache = path / ".cache"
        retained = Path(cache_path) if isinstance(cache_path, str) else None
        moved = False
        if retained is not None and cache.exists() and not cache.is_symlink():
            retained.parent.mkdir(parents=True, exist_ok=True)
            if retained.exists():
                raise CheckoutError(f"candidate cache already exists at {retained}")
            try:
                os.replace(cache, retained)
            except OSError as error:
                raise CheckoutError(
                    f"candidate cache cannot move to {retained}: {error}"
                ) from error
            moved = True
        elif cache.is_symlink():
            cache.unlink()
        try:
            worktrunk.worktrunk_remove(Path(root), branch, force=True, reap=False)
        except worktrunk.WorktrunkError:
            if moved and path.is_dir():
                os.replace(retained, cache)
            raise
        if retained is not None and retained.is_dir():
            path.mkdir(parents=True, exist_ok=True)
            cache.symlink_to(retained, target_is_directory=True)
