"""Worktree placement and the base commit a batch starts from."""

from __future__ import annotations

from pathlib import Path

from . import gitcmd
from .manifest import BatchRefusal
from .projects import ProjectAdapter, WorkspacePolicy

#: A push or fetch runs the repository's own hooks.
PUSH_TIMEOUT_SECONDS = 2_400


class CheckoutError(RuntimeError):
    """The base commit could not be resolved."""


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
