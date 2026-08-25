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
        workspace, project, receipt = self._verified_workspace(workspace_id, job_id)
        if not title.strip() or len(title) > 256 or len(body.encode()) > 64_000:
            raise DeliveryError("review title or body exceeds its publication bounds")
        base = self._base_branch(project.workspace.default_base)
        path = workspace["path"]
        branch = workspace["branch"]
        self._command([*project.environment.command, "git", "-C", path, "push", "-u", "origin", branch], cwd=path)
        workspace, project, receipt = self._verified_workspace(workspace_id, job_id)
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
        return {**review, "published": True, "created": created, "publication_output": publication_output, "completion": receipt}

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
        _workspace, _project, receipt = self._verified_workspace(workspace_id, job_id)
        self._command(["gh", "pr", "merge", str(review["number"]), "--squash"], cwd=self.workspaces.get(workspace_id)["path"])
        merged = self.review_status(workspace_id)
        if merged["review"]["state"] != "MERGED":
            raise DeliveryError("GitHub did not report the review merged")
        return {**merged, "landed": True, "completion": receipt}

    def finish(self, workspace_id: str) -> dict[str, Any]:
        status = self.review_status(workspace_id)
        if status["review"]["state"] != "MERGED":
            raise DeliveryError("workspace review is not merged")
        workspace = self.workspaces.get(workspace_id)
        self._delete_remote_branch(workspace["path"], workspace["branch"])
        return self.workspaces.finish_merged(workspace_id, status["head"])

    def _verified_workspace(self, workspace_id: str, job_id: str) -> tuple[dict[str, Any], Any, dict[str, Any]]:
        workspace = self.workspaces.get(workspace_id)
        if workspace["state"] != "available" or not workspace["identity_matches"]:
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
            or record.spec.operation not in project.workspace.verification_operations
        ):
            raise DeliveryError("workspace lacks successful declared verification at its exact HEAD")
        try:
            result = self.jobs.result(job_id)
            delivery_result = self._is_delivery_result(result)
            scope = self._packet_scope(record.spec.contract)
            snapshot = self.workspaces.delivery_snapshot(workspace_id, checkout["head"], scope=scope or ())
        except (ValueError, WorkspaceError) as error:
            raise DeliveryError("workspace lacks an authoritative exact-head completion receipt") from error
        if snapshot["head"] != checkout["head"] or not snapshot["descendant"] or snapshot["dirty"]:
            raise DeliveryError("workspace lacks successful declared verification at its exact HEAD")
        if delivery_result and (scope is None or not snapshot["in_scope"]):
            raise DeliveryError("packet delivery is outside its Beads-owned write scope")
        self._validate_delivery_result(result, snapshot)
        artifact = result.get("artifact") if isinstance(result, Mapping) else None
        return workspace, project, {"ref": artifact.get("ref") if isinstance(artifact, Mapping) else f"sinnix://jobs/{job_id}", "job_id": job_id, "workspace_id": workspace_id, "head": snapshot["head"], "verification_operation": record.spec.operation}

    @staticmethod
    def _is_delivery_result(result: Mapping[str, Any]) -> bool:
        value = result.get("value")
        return result.get("kind") in {"json", "pytest"} and isinstance(value, Mapping) and "delivery" in value

    @staticmethod
    def _packet_scope(contract: Mapping[str, Any]) -> tuple[str, ...] | None:
        binding = contract.get("bead_binding")
        if not isinstance(binding, Mapping) or "write_scope" not in binding:
            return None
        scope = binding["write_scope"]
        if not isinstance(scope, list) or not scope or any(not isinstance(path, str) for path in scope):
            raise DeliveryError("Beads-owned write scope is malformed")
        return tuple(scope)

    @staticmethod
    def _validate_delivery_result(result: Mapping[str, Any], snapshot: Mapping[str, Any]) -> None:
        if not GitHubDelivery._is_delivery_result(result):
            return
        value = result.get("value")
        delivery = value.get("delivery") if isinstance(value, Mapping) else None
        if not isinstance(delivery, Mapping) or set(delivery) != {"anti_vacuity", "unresolved_work", "delegation", "deletion_evidence", "evidence_only"}:
            raise DeliveryError("project delivery result is malformed")
        unresolved, delegation, deletions = delivery["unresolved_work"], delivery["delegation"], delivery["deletion_evidence"]
        if delivery["anti_vacuity"] is not True or not isinstance(unresolved, list) or unresolved or not isinstance(deletions, list) or not isinstance(delivery["evidence_only"], bool) or not isinstance(delegation, Mapping) or set(delegation) != {"visibility", "pending"}:
            raise DeliveryError("project delivery result is incomplete")
        visibility, pending = delegation["visibility"], delegation["pending"]
        if visibility not in {"supported", "unsupported"} or (visibility == "supported" and pending is not False) or (visibility == "unsupported" and pending is not None):
            raise DeliveryError("project delivery delegation visibility is invalid")
        changes = snapshot.get("changes")
        if not isinstance(changes, list):
            raise DeliveryError("workspace delivery snapshot is malformed")
        if any(isinstance(change, Mapping) and str(change.get("status", ""))[:1] == "D" for change in changes) and not deletions:
            raise DeliveryError("project delivery result omits deletion evidence")
        if not changes and not delivery["evidence_only"]:
            raise DeliveryError("no-change delivery lacks the evidence-only exception")
        if changes and delivery["evidence_only"]:
            raise DeliveryError("evidence-only delivery contains code changes")

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
