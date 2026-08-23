from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .jobs import GenericJobs
from .projects import ProjectCatalog
from .workspaces import GitWorkspaces, WorkspaceError


class DeliveryError(ValueError):
    """Publication or landing preconditions do not match Git/GitHub authority."""


Run = Callable[..., subprocess.CompletedProcess[str]]


@dataclass
class GitHubDelivery:
    projects: ProjectCatalog
    workspaces: GitWorkspaces
    jobs: GenericJobs
    run: Run = subprocess.run

    def publish(self, workspace_id: str, job_id: str, title: str, body: str) -> dict[str, Any]:
        workspace, project = self._verified_workspace(workspace_id, job_id)
        if not title.strip() or len(title) > 256 or len(body.encode()) > 64_000:
            raise DeliveryError("review title or body exceeds its publication bounds")
        base = self._base_branch(project.workspace.default_base)
        path = workspace["path"]
        branch = workspace["branch"]
        self._command([*project.environment.command, "git", "-C", path, "push", "-u", "origin", branch], cwd=path)
        existing = self.run(
            ["gh", "pr", "view", branch, "--json", "url"],
            cwd=path, capture_output=True, text=True, timeout=60, check=False,
        )
        if existing.returncode == 0:
            publication_output = existing.stdout.strip()
            created = False
        else:
            publication_output = self._command(
                ["gh", "pr", "create", "--head", branch, "--base", base, "--title", title, "--body", body],
                cwd=path,
            ).stdout.strip()
            created = True
        review = self._review_after_push(workspace_id)
        return {**review, "published": True, "created": created, "publication_output": publication_output}

    def _review_after_push(self, workspace_id: str) -> dict[str, Any]:
        for attempt in range(10):
            try:
                return self.review_status(workspace_id)
            except DeliveryError as error:
                if "review head does not match" not in str(error) or attempt == 9:
                    raise
                time.sleep(0.5)
        raise AssertionError("bounded review reconciliation exhausted")

    def review_status(self, workspace_id: str) -> dict[str, Any]:
        workspace = self.workspaces.get(workspace_id)
        if workspace["state"] != "available":
            raise DeliveryError("workspace is unavailable")
        result = self._command(
            [
                "gh", "pr", "view", workspace["branch"], "--json",
                "number,url,state,isDraft,mergeStateStatus,headRefOid,baseRefName,statusCheckRollup",
            ],
            cwd=workspace["path"],
        )
        try:
            review = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise DeliveryError("GitHub returned malformed review state") from error
        required = {"number", "url", "state", "isDraft", "mergeStateStatus", "headRefOid", "baseRefName", "statusCheckRollup"}
        if not isinstance(review, Mapping) or set(review) != required:
            raise DeliveryError("GitHub review state schema is invalid")
        if review["headRefOid"] != workspace["head"]:
            raise DeliveryError("GitHub review head does not match workspace HEAD")
        return {"workspace_id": workspace_id, "head": workspace["head"], "review": dict(review)}

    def land(self, workspace_id: str, job_id: str) -> dict[str, Any]:
        self._verified_workspace(workspace_id, job_id)
        status = self.review_status(workspace_id)
        review = status["review"]
        if (
            review["state"] != "OPEN"
            or review["isDraft"]
            or review["mergeStateStatus"] not in {"CLEAN", "HAS_HOOKS"}
            or not self._checks_pass(review["statusCheckRollup"])
        ):
            raise DeliveryError("review is not in a landable GitHub state")
        self._command(["gh", "pr", "merge", str(review["number"]), "--squash"], cwd=self.workspaces.get(workspace_id)["path"])
        merged = self.review_status(workspace_id)
        if merged["review"]["state"] != "MERGED":
            raise DeliveryError("GitHub did not report the review merged")
        return {**merged, "landed": True}

    def finish(self, workspace_id: str) -> dict[str, Any]:
        status = self.review_status(workspace_id)
        if status["review"]["state"] != "MERGED":
            raise DeliveryError("workspace review is not merged")
        workspace = self.workspaces.get(workspace_id)
        self._delete_remote_branch(workspace["path"], workspace["branch"])
        return self.workspaces.finish_merged(workspace_id, status["head"])

    def _verified_workspace(self, workspace_id: str, job_id: str) -> tuple[dict[str, Any], Any]:
        workspace = self.workspaces.get(workspace_id)
        if workspace["state"] != "available" or workspace["dirty"] or not workspace["identity_matches"]:
            raise DeliveryError("publication requires an available clean identity-matching workspace")
        project = self.projects.get(workspace["project_id"])
        assert project.workspace is not None
        job = self.jobs.get(job_id)
        record = self.jobs.store.load(job_id)
        checkout = record.spec.checkout
        if (
            job["state"].get("phase") != "succeeded"
            or checkout is None
            or checkout.get("checkout_id") != workspace["checkout_id"]
            or checkout.get("head") != workspace["head"]
            or record.spec.operation not in project.workspace.verification_operations
        ):
            raise DeliveryError("workspace lacks successful declared verification at its exact HEAD")
        return workspace, project

    @staticmethod
    def _base_branch(default_base: str) -> str:
        remote, separator, branch = default_base.partition("/")
        if remote != "origin" or not separator or not branch:
            raise DeliveryError("publication requires workspace.default_base in origin/<branch> form")
        return branch

    def _command(self, argv: Sequence[str], *, cwd: str | None = None) -> subprocess.CompletedProcess[str]:
        try:
            result = self.run(argv, cwd=cwd, capture_output=True, text=True, timeout=60, check=False)
        except (OSError, subprocess.SubprocessError) as error:
            raise DeliveryError("GitHub delivery command failed") from error
        if result.returncode != 0:
            raise DeliveryError(result.stderr.strip() or "GitHub delivery command failed")
        return result

    def _delete_remote_branch(self, path: str, branch: str) -> None:
        probe = self.run(
            ["git", "-C", path, "ls-remote", "--exit-code", "--heads", "origin", f"refs/heads/{branch}"],
            capture_output=True, text=True, timeout=60, check=False,
        )
        if probe.returncode == 2:
            return
        if probe.returncode != 0:
            raise DeliveryError(probe.stderr.strip() or "could not inspect remote branch")
        self._command(["git", "-C", path, "push", "origin", "--delete", branch])

    @staticmethod
    def _checks_pass(checks: Any) -> bool:
        if not isinstance(checks, list):
            return False
        for check in checks:
            if not isinstance(check, Mapping):
                return False
            if check.get("__typename") == "StatusContext":
                if check.get("state") != "SUCCESS":
                    return False
            elif check.get("__typename") == "CheckRun":
                if check.get("status") != "COMPLETED" or check.get("conclusion") not in {
                    "SUCCESS", "NEUTRAL", "SKIPPED",
                }:
                    return False
            else:
                return False
        return True
