"""Which working tree a declared operation runs in.

An operation's `checkout` answers one question: which tree holds the code its
receipt is evidence about. The three values differ in whether they *select* a
tree or only constrain one the caller already chose:

- `any` runs wherever the caller pointed it, defaulting to the project root.
- `default` refuses every tree but the project root. It does not select one,
  so a launch that passes no workspace -- a timer's `job fire` -- runs in
  whatever state the operator left that checkout in. A receipt from it names
  the operator's branch and uncommitted work, not a candidate.
- `candidate` selects the tree itself: a worktree agentctl owns, on
  `agentctl/candidate`, reset to the project's declared `default_base` at
  every launch. Correctness stops depending on a caller remembering
  `--workspace`, which is the whole point: the scheduled complete-corpus run
  that silently used a working tree fourteen commits behind its base was
  started by exactly the code path that passes no workspace.

The tree is reset, never cleaned. Untracked build and verification caches
under it are what make a repeated corpus run affordable, and a reset already
discards every tracked difference from the base.
"""

from __future__ import annotations

from pathlib import Path

from . import gitcmd, worktrunk
from .manifest import BatchRefusal
from .projects import ProjectAdapter, WorkspacePolicy

#: The branch of the tree agentctl owns for a project's `candidate`
#: operations. One per project, reused across launches; it is never a batch
#: branch and never carries work.
CANDIDATE_BRANCH = "agentctl/candidate"
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


def candidate_tree(project: ProjectAdapter) -> tuple[Path, str]:
    """The project's candidate worktree at its declared base, and that commit.

    Created on first use and reused afterwards. It is reset to the base on
    every launch rather than only when it drifts: a previous operation may
    have left tracked changes behind, and a receipt is only candidate
    evidence if the tree it ran in is the base commit it names.
    """
    commit = base_commit(project)
    existing = worktrunk.worktrunk_find(project.root, CANDIDATE_BRANCH)
    if existing is None or existing.path is None:
        created = worktrunk.worktrunk_create(
            project.root,
            CANDIDATE_BRANCH,
            path=worktree_path(project, CANDIDATE_BRANCH),
            base=commit,
        )
        if created.path is None:
            raise CheckoutError(
                f"wt created {CANDIDATE_BRANCH} for {project.project_id} without a path"
            )
        return created.path, commit
    path = existing.path
    if not path.is_dir():
        raise CheckoutError(
            f"{project.project_id} candidate worktree is registered at {path}, "
            "which does not exist; remove the stale worktree and retry"
        )
    gitcmd.git(path, "reset", "--hard", commit, error=CheckoutError)
    return path, commit
