from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
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

    def publish(
        self,
        workspace_id: str,
        job_id: str,
        title: str,
        body: str,
        packet_job_id: str | None = None,
    ) -> dict[str, Any]:
        workspace, project, receipt = self._verified_workspace(
            workspace_id, job_id, packet_job_id
        )
        if not title.strip() or len(title) > 256 or len(body.encode()) > 64_000:
            raise DeliveryError("review title or body exceeds its publication bounds")
        base = self._base_branch(project.workspace.default_base)
        path = workspace["path"]
        branch = workspace["branch"]
        self._command(
            [
                *project.environment.command,
                "git",
                "-C",
                path,
                "push",
                "-u",
                "origin",
                branch,
            ],
            cwd=path,
        )
        workspace, project, receipt = self._verified_workspace(
            workspace_id, job_id, packet_job_id
        )
        existing = self.run(
            ["gh", "pr", "view", branch, "--json", "url"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if existing.returncode == 0:
            publication_output = existing.stdout.strip()
            created = False
        else:
            publication_output = self._command(
                [
                    "gh",
                    "pr",
                    "create",
                    "--head",
                    branch,
                    "--base",
                    base,
                    "--title",
                    title,
                    "--body",
                    body,
                ],
                cwd=path,
            ).stdout.strip()
            created = True
        review = self._review_after_push(workspace_id)
        return {
            **review,
            "published": True,
            "created": created,
            "publication_output": publication_output,
            "completion": receipt,
        }

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
                "gh",
                "pr",
                "view",
                workspace["branch"],
                "--json",
                "number,url,state,isDraft,mergeStateStatus,headRefOid,baseRefName,statusCheckRollup",
            ],
            cwd=workspace["path"],
        )
        try:
            review = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise DeliveryError("GitHub returned malformed review state") from error
        required = {
            "number",
            "url",
            "state",
            "isDraft",
            "mergeStateStatus",
            "headRefOid",
            "baseRefName",
            "statusCheckRollup",
        }
        if not isinstance(review, Mapping) or set(review) != required:
            raise DeliveryError("GitHub review state schema is invalid")
        if review["headRefOid"] != workspace["head"]:
            raise DeliveryError("GitHub review head does not match workspace HEAD")
        return {
            "workspace_id": workspace_id,
            "head": workspace["head"],
            "review": dict(review),
        }

    def land(
        self, workspace_id: str, job_id: str, packet_job_id: str | None = None
    ) -> dict[str, Any]:
        self._verified_workspace(workspace_id, job_id, packet_job_id)
        status = self.review_status(workspace_id)
        review = status["review"]
        if review["state"] == "MERGED":
            _workspace, _project, receipt = self._verified_workspace(
                workspace_id, job_id, packet_job_id
            )
            return {
                **status,
                "landed": True,
                "already_landed": True,
                "completion": receipt,
            }
        if (
            review["state"] != "OPEN"
            or review["isDraft"]
            or review["mergeStateStatus"] not in {"CLEAN", "HAS_HOOKS"}
            or not self._checks_pass(review["statusCheckRollup"])
        ):
            raise DeliveryError("review is not in a landable GitHub state")
        _workspace, _project, receipt = self._verified_workspace(
            workspace_id, job_id, packet_job_id
        )
        self._command(
            ["gh", "pr", "merge", str(review["number"]), "--squash"],
            cwd=self.workspaces.get(workspace_id)["path"],
        )
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

    def _verified_workspace(
        self, workspace_id: str, job_id: str, packet_job_id: str | None = None
    ) -> tuple[dict[str, Any], Any, dict[str, Any]]:
        workspace = self.workspaces.get(workspace_id)
        if workspace["state"] != "available" or not workspace["identity_matches"]:
            raise DeliveryError(
                "publication requires an available clean identity-matching workspace"
            )
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
            raise DeliveryError(
                "workspace lacks successful declared verification at its exact HEAD"
            )
        try:
            self.jobs.result(job_id)
            binding = (
                self._binding(record, checkout, workspace)
                if packet_job_id is not None
                else None
            )
            packet = (
                self._packet(packet_job_id, workspace, binding)
                if packet_job_id is not None
                else None
            )
            start_head = (
                packet["start_head"] if packet is not None else checkout["head"]
            )
            scope = packet["scope"] if packet is not None else ()
            snapshot = self.workspaces.delivery_snapshot(workspace_id, start_head)
            publication_snapshot = (
                self.workspaces.delivery_snapshot(
                    workspace_id,
                    project.workspace.default_base,
                    scope=scope,
                    merge_base=True,
                )
                if packet is not None
                else snapshot
            )
        except DeliveryError:
            raise
        except (ValueError, WorkspaceError) as error:
            raise DeliveryError(
                "workspace lacks an authoritative exact-head completion receipt"
            ) from error
        if (
            snapshot["head"] != checkout["head"]
            or not snapshot["descendant"]
            or snapshot["dirty"]
        ):
            raise DeliveryError(
                "workspace lacks successful declared verification at its exact HEAD"
            )
        if packet is not None and (
            packet["final_head"] != snapshot["head"]
            or not publication_snapshot["in_scope"]
        ):
            raise DeliveryError(
                "packet delivery is outside its Beads-owned write scope"
            )
        if packet is not None:
            self._validate_delivery_result(packet["delivery"], snapshot)
        return (
            workspace,
            project,
            {
                "ref": packet["artifact_ref"]
                if packet is not None
                else f"sinnix://jobs/{job_id}",
                "job_id": job_id,
                "packet_job_id": packet_job_id,
                "bead_ref": packet["bead_ref"] if packet is not None else None,
                "workspace_id": workspace_id,
                "head": snapshot["head"],
                "verification_operation": record.spec.operation,
            },
        )

    def _binding(
        self, record: Any, checkout: Mapping[str, Any], workspace: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        binding = record.spec.contract.get("bead_binding")
        scope = binding.get("write_scope") if isinstance(binding, Mapping) else None
        if (
            not isinstance(binding, Mapping)
            or not isinstance(scope, list)
            or not scope
            or len(scope) > 128
            or any(
                not isinstance(path, str)
                or not path
                or len(path.encode()) > 1024
                or path.startswith("/")
                or ".." in Path(path).parts
                for path in scope
            )
            or checkout.get("checkout_id") != workspace.get("checkout_id")
        ):
            raise DeliveryError(
                "declared verification lacks an authoritative Beads packet binding"
            )
        return binding

    def _packet(
        self, job_id: str, workspace: Mapping[str, Any], binding: Mapping[str, Any]
    ) -> dict[str, Any]:
        job = self.jobs.get(job_id)
        record = self.jobs.store.load(job_id)
        checkout = record.spec.checkout
        packet_binding = record.spec.contract.get("bead_binding")
        result = self.jobs.result(job_id)
        if (
            job["state"].get("phase") != "succeeded"
            or record.spec.kind != "attested-agent"
            or not isinstance(checkout, Mapping)
            or checkout.get("checkout_id") != workspace.get("checkout_id")
            or packet_binding != binding
            or result.get("kind") != "last-message"
            or result.get("truncated") is not False
            or not isinstance(result.get("content"), str)
        ):
            raise DeliveryError("packet job lacks an authoritative Beads-bound result")
        try:
            envelope = json.loads(result["content"])
        except json.JSONDecodeError as error:
            raise DeliveryError("packet job result is malformed") from error
        if (
            not isinstance(envelope, Mapping)
            or set(envelope)
            != {"schema_version", "job_id", "start_head", "final_head", "delivery"}
            or envelope.get("schema_version") != 1
            or envelope.get("job_id") != job_id
            or envelope.get("start_head") != checkout.get("head")
            or not isinstance(envelope.get("final_head"), str)
            or len(envelope["final_head"]) != 40
            or any(value not in "0123456789abcdef" for value in envelope["final_head"])
        ):
            raise DeliveryError("packet job result identity is malformed")
        artifact = result.get("artifact")
        return {
            "start_head": envelope["start_head"],
            "final_head": envelope["final_head"],
            "delivery": envelope["delivery"],
            "scope": tuple(binding["write_scope"]),
            "bead_ref": binding.get("bead_ref"),
            "artifact_ref": artifact.get("ref")
            if isinstance(artifact, Mapping)
            else f"sinnix://jobs/{job_id}",
        }

    @staticmethod
    def _validate_delivery_result(delivery: Any, snapshot: Mapping[str, Any]) -> None:
        if not isinstance(delivery, Mapping) or set(delivery) != {
            "anti_vacuity",
            "unresolved_work",
            "delegation",
            "deletion_evidence",
            "evidence_only",
        }:
            raise DeliveryError("project delivery result is malformed")
        unresolved, delegation, deletions = (
            delivery["unresolved_work"],
            delivery["delegation"],
            delivery["deletion_evidence"],
        )
        if (
            delivery["anti_vacuity"] is not True
            or not isinstance(unresolved, list)
            or unresolved
            or not isinstance(deletions, list)
            or not isinstance(delivery["evidence_only"], bool)
            or not isinstance(delegation, Mapping)
            or set(delegation) != {"visibility", "pending"}
        ):
            raise DeliveryError("project delivery result is incomplete")
        visibility, pending = delegation["visibility"], delegation["pending"]
        if (
            visibility not in {"supported", "unsupported"}
            or (visibility == "supported" and pending is not False)
            or (visibility == "unsupported" and pending is not None)
        ):
            raise DeliveryError("project delivery delegation visibility is invalid")
        changes = snapshot.get("changes")
        if not isinstance(changes, list):
            raise DeliveryError("workspace delivery snapshot is malformed")
        deleted = {
            path
            for change in changes
            if isinstance(change, Mapping) and str(change.get("status", ""))[:1] == "D"
            for path in change.get("paths", [])
            if isinstance(path, str)
        }
        if (
            any(not isinstance(path, str) for path in deletions)
            or len(deletions) != len(set(deletions))
            or deleted != set(deletions)
        ):
            raise DeliveryError(
                "project delivery result does not exactly match deletion evidence"
            )
        if not changes and not delivery["evidence_only"]:
            raise DeliveryError("no-change delivery lacks the evidence-only exception")
        if changes and delivery["evidence_only"]:
            raise DeliveryError("evidence-only delivery contains code changes")

    @staticmethod
    def _base_branch(default_base: str) -> str:
        remote, separator, branch = default_base.partition("/")
        if remote != "origin" or not separator or not branch:
            raise DeliveryError(
                "publication requires workspace.default_base in origin/<branch> form"
            )
        return branch

    def _command(
        self, argv: Sequence[str], *, cwd: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = self.run(
                argv, cwd=cwd, capture_output=True, text=True, timeout=60, check=False
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise DeliveryError("GitHub delivery command failed") from error
        if result.returncode != 0:
            raise DeliveryError(
                result.stderr.strip() or "GitHub delivery command failed"
            )
        return result

    def _delete_remote_branch(self, path: str, branch: str) -> None:
        probe = self.run(
            [
                "git",
                "-C",
                path,
                "ls-remote",
                "--exit-code",
                "--heads",
                "origin",
                f"refs/heads/{branch}",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if probe.returncode == 2:
            return
        if probe.returncode != 0:
            raise DeliveryError(
                probe.stderr.strip() or "could not inspect remote branch"
            )
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
                if check.get("status") != "COMPLETED" or check.get(
                    "conclusion"
                ) not in {
                    "SUCCESS",
                    "NEUTRAL",
                    "SKIPPED",
                }:
                    return False
            else:
                return False
        return True
