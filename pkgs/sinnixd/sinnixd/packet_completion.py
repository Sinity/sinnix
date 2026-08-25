"""Provider-neutral completion inspection for AgentCTL delivery packets.

Process termination is deliberately only one input.  This module composes
durable AgentCTL job/workspace state with Git and typed provider receipts; it
does not interpret worker prose or own task/campaign state.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol, Sequence


CompletionReason = Literal[
    "job_not_succeeded",
    "job_timeout",
    "job_result_loss",
    "job_binding_mismatch",
    "workspace_unavailable",
    "workspace_dirty",
    "untracked_work",
    "workspace_identity_mismatch",
    "head_binding_mismatch",
    "divergent_head",
    "no_commit",
    "out_of_scope_path",
    "worker_result_missing",
    "worker_result_invalid",
    "worker_command_failed",
    "anti_vacuity_missing",
    "unresolved_items",
    "delegated_work_pending",
    "verification_missing",
    "verification_stale",
    "verification_failed",
    "evidence_only_not_authorized",
    "evidence_only_evidence_missing",
    "review_missing",
    "review_stale",
    "review_rejected",
    "deletion_ledger_missing",
]

_HEAD = re.compile(r"[0-9a-fA-F]{40,64}\Z")


def _require_head(value: object, name: str) -> str:
    if not isinstance(value, str) or _HEAD.fullmatch(value) is None:
        raise ValueError(f"{name} must be a Git object ID")
    return value


def _require_ref(value: object, name: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError(f"{name} must be a bounded non-empty reference")
    return value


def _relative_path(value: object, name: str) -> str:
    if not isinstance(value, str) or not value or value.startswith("/"):
        raise ValueError(f"{name} must be a relative path")
    parts = value.rstrip("/").split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"{name} must be a normalized relative path")
    return value


@dataclass(frozen=True)
class PacketContract:
    """The immutable delivery requirements declared for one AgentCTL packet."""

    job_id: str
    workspace_id: str
    write_scope: tuple[str, ...]
    required_verification_refs: tuple[str, ...] = ()
    allow_evidence_only: bool = False
    evidence_only_refs: tuple[str, ...] = ()
    require_independent_review: bool = False
    require_deletion_ledger: bool = True

    def __post_init__(self) -> None:
        if not self.job_id or not self.workspace_id:
            raise ValueError("packet job_id and workspace_id are required")
        if not self.write_scope or len(set(self.write_scope)) != len(self.write_scope):
            raise ValueError("packet write_scope must be non-empty and unique")
        for path in self.write_scope:
            _relative_path(path, "packet write_scope")
        refs = (*self.required_verification_refs, *self.evidence_only_refs)
        if len(set(refs)) != len(refs):
            raise ValueError("packet receipt references must be unique")
        for ref in refs:
            _require_ref(ref, "packet receipt reference")
        if self.evidence_only_refs and not self.allow_evidence_only:
            raise ValueError("evidence-only references require an explicit evidence-only contract")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> PacketContract:
        allowed = {
            "job_id", "workspace_id", "write_scope", "required_verification_refs",
            "allow_evidence_only", "evidence_only_refs", "require_independent_review",
            "require_deletion_ledger",
        }
        if set(value) - allowed:
            raise ValueError("packet contract has unknown fields")
        try:
            return cls(
                job_id=value["job_id"],
                workspace_id=value["workspace_id"],
                write_scope=tuple(value["write_scope"]),
                required_verification_refs=tuple(value.get("required_verification_refs", ())),
                allow_evidence_only=value.get("allow_evidence_only", False),
                evidence_only_refs=tuple(value.get("evidence_only_refs", ())),
                require_independent_review=value.get("require_independent_review", False),
                require_deletion_ledger=value.get("require_deletion_ledger", True),
            )
        except (KeyError, TypeError) as error:
            raise ValueError("packet contract is malformed") from error


@dataclass(frozen=True)
class DelegationCapability:
    """Backend/runtime delegation visibility, never inferred from model text."""

    visibility: Literal["supported", "unsupported"]
    pending: bool | None

    def __post_init__(self) -> None:
        if self.visibility not in {"supported", "unsupported"}:
            raise ValueError("delegation visibility is invalid")
        if self.visibility == "supported" and not isinstance(self.pending, bool):
            raise ValueError("supported delegation visibility requires pending state")
        if self.visibility == "unsupported" and self.pending is not None:
            raise ValueError("unsupported delegation visibility cannot claim pending state")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DelegationCapability:
        if set(value) != {"visibility", "pending"}:
            raise ValueError("delegation capability is malformed")
        return cls(visibility=value["visibility"], pending=value["pending"])

    def to_dict(self) -> dict[str, Any]:
        return {"visibility": self.visibility, "pending": self.pending}


@dataclass(frozen=True)
class VerificationReceipt:
    ref: str
    operation: str
    head: str
    passed: bool
    immutable: bool

    def __post_init__(self) -> None:
        _require_ref(self.ref, "verification receipt ref")
        _require_ref(self.operation, "verification receipt operation")
        _require_head(self.head, "verification receipt head")
        if not isinstance(self.passed, bool) or not isinstance(self.immutable, bool):
            raise ValueError("verification receipt outcome is invalid")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> VerificationReceipt:
        try:
            return cls(
                ref=value["ref"],
                operation=value["operation"],
                head=value["head"],
                passed=value["passed"],
                immutable=value["immutable"],
            )
        except (KeyError, TypeError) as error:
            raise ValueError("verification receipt is malformed") from error


class VerificationReceiptProvider(Protocol):
    """Project-owned seam for immutable semantic receipts; no project import is needed."""

    def get_receipts(self, refs: Sequence[str]) -> Sequence[VerificationReceipt]:
        """Return the requested receipts, preserving their provider references."""


@dataclass(frozen=True)
class EvidenceReceipt:
    ref: str
    head: str
    passed: bool
    immutable: bool

    def __post_init__(self) -> None:
        _require_ref(self.ref, "evidence receipt ref")
        _require_head(self.head, "evidence receipt head")
        if not isinstance(self.passed, bool) or not isinstance(self.immutable, bool):
            raise ValueError("evidence receipt outcome is invalid")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> EvidenceReceipt:
        try:
            return cls(
                ref=value["ref"],
                head=value["head"],
                passed=value["passed"],
                immutable=value["immutable"],
            )
        except (KeyError, TypeError) as error:
            raise ValueError("evidence receipt is malformed") from error


@dataclass(frozen=True)
class IndependentReviewReceipt:
    ref: str
    head: str
    passed: bool
    immutable: bool

    def __post_init__(self) -> None:
        _require_ref(self.ref, "review receipt ref")
        _require_head(self.head, "review receipt head")
        if not isinstance(self.passed, bool) or not isinstance(self.immutable, bool):
            raise ValueError("review receipt outcome is invalid")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> IndependentReviewReceipt:
        try:
            return cls(
                ref=value["ref"],
                head=value["head"],
                passed=value["passed"],
                immutable=value["immutable"],
            )
        except (KeyError, TypeError) as error:
            raise ValueError("review receipt is malformed") from error


@dataclass(frozen=True)
class GitCompletionEvidence:
    """A bounded snapshot of Git facts used by completion inspection."""

    start_head: str
    final_head: str
    is_descendant: bool
    commits: tuple[str, ...]
    changed_paths: tuple[str, ...]
    working_tree_paths: tuple[str, ...]
    untracked_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_head(self.start_head, "Git start_head")
        _require_head(self.final_head, "Git final_head")
        if not isinstance(self.is_descendant, bool):
            raise ValueError("Git ancestry evidence is invalid")
        for commit in self.commits:
            _require_head(commit, "Git commit")
        for path in (*self.changed_paths, *self.working_tree_paths, *self.untracked_paths):
            _relative_path(path, "Git changed path")

    @property
    def dirty(self) -> bool:
        return bool(self.working_tree_paths)


class GitCompletionEvidenceProvider(Protocol):
    def inspect(self, *, path: str, start_head: str, final_head: str) -> GitCompletionEvidence:
        """Return one bounded, same-checkout Git snapshot."""


class SubprocessGitCompletionEvidence:
    """Read Git authority without making any repository mutation."""

    def inspect(self, *, path: str, start_head: str, final_head: str) -> GitCompletionEvidence:
        root = Path(path)
        status = self._run(root, "status", "--porcelain=v1", "--untracked-files=all").stdout
        working_tree_paths = tuple(
            line[3:].strip() for line in status.splitlines() if len(line) >= 4 and line[3:].strip()
        )
        changed = self._run(root, "diff", "--name-only", f"{start_head}..{final_head}", "--").stdout
        commits = self._run(root, "rev-list", "--reverse", f"{start_head}..{final_head}").stdout
        ancestry = subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", start_head, final_head],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if ancestry.returncode not in {0, 1}:
            raise ValueError("could not inspect Git ancestry")
        paths = tuple(line for line in changed.splitlines() if line)
        working = tuple(path for path in working_tree_paths if path)
        return GitCompletionEvidence(
            start_head=start_head,
            final_head=final_head,
            is_descendant=ancestry.returncode == 0,
            commits=tuple(line for line in commits.splitlines() if line),
            changed_paths=paths,
            working_tree_paths=working,
            untracked_paths=tuple(
                line[3:].strip() for line in status.splitlines()
                if line.startswith("?? ") and line[3:].strip()
            ),
        )

    @staticmethod
    def _run(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                ["git", "-C", str(root), *arguments],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise ValueError("could not inspect Git workspace") from error
        if result.returncode != 0:
            raise ValueError("could not inspect Git workspace")
        return result


@dataclass(frozen=True)
class WorkerDeliveryRecord:
    """Structured worker handoff; ``last_message`` is intentionally ignored."""

    result_ref: str
    commands: tuple[Mapping[str, Any], ...]
    anti_vacuity: Mapping[str, Any]
    unresolved_items: tuple[str, ...]
    deletion_ledger: tuple[Mapping[str, Any], ...] | None
    last_message: str = ""

    def __post_init__(self) -> None:
        _require_ref(self.result_ref, "worker result ref")
        if not self.commands:
            raise ValueError("worker delivery commands are missing")
        for command in self.commands:
            if (
                not isinstance(command, Mapping)
                or set(command) != {"argv", "result"}
                or not isinstance(command["argv"], (list, tuple))
                or not command["argv"]
                or any(not isinstance(item, str) or not item for item in command["argv"])
                or command["result"] not in {"passed", "failed"}
            ):
                raise ValueError("worker delivery command result is malformed")
        expected = {"checked", "mutation", "passed", "evidence_ref"}
        if (
            not isinstance(self.anti_vacuity, Mapping)
            or set(self.anti_vacuity) != expected
            or not isinstance(self.anti_vacuity["checked"], bool)
            or not isinstance(self.anti_vacuity["passed"], bool)
            or not isinstance(self.anti_vacuity["mutation"], str)
        ):
            raise ValueError("worker anti-vacuity evidence is malformed")
        _require_ref(self.anti_vacuity["evidence_ref"], "worker anti-vacuity evidence ref")
        if any(not isinstance(item, str) or not item for item in self.unresolved_items):
            raise ValueError("worker unresolved items are malformed")
        if self.deletion_ledger is not None:
            for item in self.deletion_ledger:
                if not isinstance(item, Mapping) or set(item) != {"path", "action"}:
                    raise ValueError("worker deletion ledger is malformed")
                _relative_path(item["path"], "worker deletion ledger path")
                if not isinstance(item["action"], str) or not item["action"]:
                    raise ValueError("worker deletion ledger action is malformed")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> WorkerDeliveryRecord:
        required = {"result_ref", "commands", "anti_vacuity", "unresolved_items", "deletion_ledger"}
        if not isinstance(value, Mapping) or not required <= set(value):
            raise ValueError("worker delivery record is missing fields")
        try:
            return cls(
                result_ref=value["result_ref"],
                commands=tuple(value["commands"]),
                anti_vacuity=value["anti_vacuity"],
                unresolved_items=tuple(value["unresolved_items"]),
                deletion_ledger=(
                    tuple(value["deletion_ledger"]) if value["deletion_ledger"] is not None else None
                ),
                last_message=value.get("last_message", ""),
            )
        except (KeyError, TypeError) as error:
            raise ValueError("worker delivery record is malformed") from error

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_ref": self.result_ref,
            "commands": [dict(item) for item in self.commands],
            "anti_vacuity": dict(self.anti_vacuity),
            "unresolved_items": list(self.unresolved_items),
            "deletion_ledger": [dict(item) for item in self.deletion_ledger] if self.deletion_ledger is not None else None,
        }


@dataclass(frozen=True)
class PacketCompletionResult:
    complete: bool
    reasons: tuple[CompletionReason, ...]
    job_id: str
    workspace_id: str
    start_head: str | None
    final_head: str | None
    commits: tuple[str, ...]
    changed_paths: tuple[str, ...]
    write_scope: tuple[str, ...]
    dirty: bool | None
    divergent: bool | None
    worker_delivery: WorkerDeliveryRecord | None
    required_verification_refs: tuple[str, ...]
    verification_refs: tuple[str, ...]
    delegation: DelegationCapability
    review_ref: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "complete": self.complete,
            "reasons": list(self.reasons),
            "job_id": self.job_id,
            "workspace_id": self.workspace_id,
            "start_head": self.start_head,
            "final_head": self.final_head,
            "commits": list(self.commits),
            "changed_paths": list(self.changed_paths),
            "write_scope": list(self.write_scope),
            "dirty": self.dirty,
            "divergent": self.divergent,
            "worker_delivery": self.worker_delivery.to_dict() if self.worker_delivery else None,
            "required_verification_refs": list(self.required_verification_refs),
            "verification_refs": list(self.verification_refs),
            "delegation": self.delegation.to_dict(),
            "review_ref": self.review_ref,
        }


class PacketCompletionInspector:
    """Compose one job/workspace snapshot into a typed completion verdict."""

    def __init__(self, git_provider: GitCompletionEvidenceProvider | None = None) -> None:
        self.git_provider = git_provider or SubprocessGitCompletionEvidence()

    def inspect(
        self,
        *,
        job: Mapping[str, Any],
        workspace: Mapping[str, Any],
        contract: PacketContract,
        worker_result: WorkerDeliveryRecord | None,
        verification_receipts: Sequence[VerificationReceipt] | None,
        delegation: DelegationCapability,
        evidence_receipts: Sequence[EvidenceReceipt] = (),
        review: IndependentReviewReceipt | None = None,
        git: GitCompletionEvidence | None = None,
        verification_provider: VerificationReceiptProvider | None = None,
    ) -> PacketCompletionResult:
        if verification_receipts is None:
            if verification_provider is None:
                raise ValueError("completion inspection requires verification receipts or a provider")
            verification_receipts = verification_provider.get_receipts(contract.required_verification_refs)
        reasons: list[CompletionReason] = []
        state = job.get("state") if isinstance(job.get("state"), Mapping) else {}
        checkout = job.get("checkout") if isinstance(job.get("checkout"), Mapping) else {}
        start_head = checkout.get("head") if isinstance(checkout.get("head"), str) else None
        final_head = workspace.get("head") if isinstance(workspace.get("head"), str) else None
        if job.get("job_id") != contract.job_id or workspace.get("workspace_id") != contract.workspace_id:
            reasons.append("job_binding_mismatch")
        if checkout.get("checkout_id") != workspace.get("checkout_id"):
            reasons.append("job_binding_mismatch")

        phase = state.get("phase")
        if phase == "timed_out":
            reasons.append("job_timeout")
        if phase != "succeeded" or state.get("terminal") is not True:
            reasons.append("job_not_succeeded")
        systemd = state.get("systemd") if isinstance(state.get("systemd"), Mapping) else {}
        exit_status = systemd.get("ExecMainStatus", state.get("exit_status"))
        if exit_status is not None and str(exit_status) != "0":
            reasons.append("job_result_loss" if phase == "succeeded" else "job_not_succeeded")

        if workspace.get("state") != "available":
            reasons.append("workspace_unavailable")
        if workspace.get("dirty") is True:
            reasons.append("workspace_dirty")
        if workspace.get("identity_matches") is not True:
            reasons.append("workspace_identity_mismatch")

        if git is None:
            if not isinstance(workspace.get("path"), str) or start_head is None or final_head is None:
                git = None
            else:
                try:
                    git = self.git_provider.inspect(path=workspace["path"], start_head=start_head, final_head=final_head)
                except ValueError:
                    git = None
        if git is not None:
            if start_head != git.start_head or final_head != git.final_head:
                reasons.append("head_binding_mismatch")
            if not git.is_descendant:
                reasons.append("divergent_head")
            if git.dirty and "workspace_dirty" not in reasons:
                reasons.append("workspace_dirty")
            if git.untracked_paths:
                reasons.append("untracked_work")
            if not git.commits and not contract.allow_evidence_only:
                reasons.append("no_commit")
            if any(
                not self._in_scope(path, contract.write_scope)
                for path in (*git.changed_paths, *git.working_tree_paths, *git.untracked_paths)
            ):
                reasons.append("out_of_scope_path")
        else:
            reasons.append("head_binding_mismatch")

        if worker_result is None:
            reasons.append("worker_result_missing")
        else:
            artifacts = job.get("artifacts")
            if isinstance(artifacts, Mapping):
                result_artifact = artifacts.get("result")
                if result_artifact is None:
                    reasons.append("job_result_loss")
                elif isinstance(result_artifact, Mapping) and result_artifact.get("ref") != worker_result.result_ref:
                    reasons.append("worker_result_invalid")
            if any(command["result"] != "passed" for command in worker_result.commands):
                reasons.append("worker_command_failed")
            if not worker_result.anti_vacuity["checked"] or not worker_result.anti_vacuity["passed"]:
                reasons.append("anti_vacuity_missing")
            if worker_result.unresolved_items:
                reasons.append("unresolved_items")
            if contract.require_deletion_ledger and worker_result.deletion_ledger is None:
                reasons.append("deletion_ledger_missing")
        if delegation.visibility == "supported" and delegation.pending:
            reasons.append("delegated_work_pending")

        receipts = {receipt.ref: receipt for receipt in verification_receipts}
        for ref in contract.required_verification_refs:
            receipt = receipts.get(ref)
            if receipt is None:
                reasons.append("verification_missing")
            elif git is None or receipt.head != final_head:
                reasons.append("verification_stale")
            elif not receipt.immutable or not receipt.passed:
                reasons.append("verification_failed")

        if git is not None and not git.commits:
            if not contract.allow_evidence_only:
                reasons.append("evidence_only_not_authorized")
            else:
                evidence = {receipt.ref: receipt for receipt in evidence_receipts}
                for ref in contract.evidence_only_refs:
                    receipt = evidence.get(ref)
                    if receipt is None or receipt.head != final_head or not receipt.immutable or not receipt.passed:
                        reasons.append("evidence_only_evidence_missing")
                if not contract.evidence_only_refs:
                    reasons.append("evidence_only_evidence_missing")

        if contract.require_independent_review:
            if review is None:
                reasons.append("review_missing")
            elif review.head != final_head:
                reasons.append("review_stale")
            elif not review.immutable or not review.passed:
                reasons.append("review_rejected")

        unique_reasons = tuple(dict.fromkeys(reasons))
        return PacketCompletionResult(
            complete=not unique_reasons,
            reasons=unique_reasons,
            job_id=contract.job_id,
            workspace_id=contract.workspace_id,
            start_head=start_head,
            final_head=final_head,
            commits=git.commits if git is not None else (),
            changed_paths=git.changed_paths if git is not None else (),
            write_scope=contract.write_scope,
            dirty=git.dirty if git is not None else workspace.get("dirty") if isinstance(workspace.get("dirty"), bool) else None,
            divergent=(not git.is_descendant) if git is not None else None,
            worker_delivery=worker_result,
            required_verification_refs=contract.required_verification_refs,
            verification_refs=tuple(receipt.ref for receipt in verification_receipts),
            delegation=delegation,
            review_ref=review.ref if review is not None else None,
        )

    @staticmethod
    def _in_scope(path: str, scopes: Sequence[str]) -> bool:
        return any(path == scope.rstrip("/") or path.startswith(scope.rstrip("/") + "/") for scope in scopes)
