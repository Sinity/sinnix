from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

from sinnixd.packet_completion import (
    DelegationCapability,
    EvidenceReceipt,
    GitCompletionEvidence,
    IndependentReviewReceipt,
    PacketCompletionInspector,
    PacketContract,
    VerificationReceipt,
    WorkerDeliveryRecord,
)


START = "1" * 40
FINAL = "2" * 40
OTHER = "3" * 40


def git_evidence(**overrides: object) -> GitCompletionEvidence:
    values = {
        "start_head": START,
        "final_head": FINAL,
        "is_descendant": True,
        "commits": (FINAL,),
        "changed_paths": ("src/changed.py",),
        "working_tree_paths": (),
        "untracked_paths": (),
    }
    return GitCompletionEvidence(**{**values, **overrides})


def delivery(**overrides: object) -> WorkerDeliveryRecord:
    values = {
        "result_ref": "sinnix://jobs/job-1/artifacts/result",
        "last_message": "",
        "commands": ({"argv": ["devtools", "test", "affected"], "result": "passed"},),
        "anti_vacuity": {
            "checked": True,
            "mutation": "replace_inspector_with_process_exit",
            "passed": True,
            "evidence_ref": "sinnix://evidence/anti-vacuity-1",
        },
        "unresolved_items": (),
        "deletion_ledger": ({"path": "retired.py", "action": "retained"},),
    }
    return WorkerDeliveryRecord(**{**values, **overrides})


def verification(*, ref: str = "receipt-1", head: str = FINAL, passed: bool = True) -> VerificationReceipt:
    return VerificationReceipt(ref=ref, operation="verify", head=head, passed=passed, immutable=True)


def base_contract(**overrides: object) -> PacketContract:
    values = {
        "job_id": "job-1",
        "workspace_id": "workspace-1",
        "write_scope": ("src/",),
        "required_verification_refs": ("receipt-1",),
    }
    return PacketContract(**{**values, **overrides})


def inspect(**overrides: object):
    values = {
        "job": {
            "job_id": "job-1",
            "state": {"phase": "succeeded", "terminal": True},
            "checkout": {"checkout_id": "workspace-1", "head": START},
        },
        "workspace": {
            "workspace_id": "workspace-1",
            "checkout_id": "workspace-1",
            "state": "available",
            "identity_matches": True,
            "head": FINAL,
            "dirty": False,
        },
        "git": git_evidence(),
        "contract": base_contract(),
        "worker_result": delivery(),
        "verification_receipts": (verification(),),
        "delegation": DelegationCapability(visibility="supported", pending=False),
    }
    return PacketCompletionInspector().inspect(**{**values, **overrides})


def test_clean_committed_exact_head_delivery_is_complete() -> None:
    result = inspect()

    assert result.complete
    assert result.reasons == ()
    assert result.job_id == "job-1"
    assert result.workspace_id == "workspace-1"
    assert result.start_head == START
    assert result.final_head == FINAL
    assert result.commits == (FINAL,)
    assert result.changed_paths == ("src/changed.py",)


def test_observed_failed_packet_shape_is_rejected_without_prose_matching() -> None:
    result = inspect(
        job={
            "job_id": "job-1",
            "state": {"phase": "succeeded", "terminal": True},
            "checkout": {"checkout_id": "workspace-1", "head": START},
        },
        git=git_evidence(
            final_head=START,
            commits=(),
            changed_paths=(),
            working_tree_paths=("scratch.txt",),
            untracked_paths=("scratch.txt",),
        ),
        worker_result=None,
        delegation=DelegationCapability(visibility="supported", pending=True),
    )

    assert not result.complete
    assert {
        "workspace_dirty",
        "untracked_work",
        "no_commit",
        "worker_result_missing",
        "delegated_work_pending",
    } <= set(result.reasons)


def test_dirty_workspace_is_rejected_even_when_process_succeeded() -> None:
    result = inspect(git=git_evidence(working_tree_paths=("src/changed.py",)))

    assert not result.complete
    assert "workspace_dirty" in result.reasons


def test_stale_receipt_is_distinct_from_missing_receipt() -> None:
    stale = inspect(verification_receipts=(verification(head=START),))
    missing = inspect(verification_receipts=())

    assert "verification_stale" in stale.reasons
    assert "verification_missing" in missing.reasons


def test_out_of_scope_paths_are_rejected() -> None:
    result = inspect(git=git_evidence(changed_paths=("docs/outside.md",)))

    assert not result.complete
    assert "out_of_scope_path" in result.reasons


def test_divergent_head_is_rejected() -> None:
    result = inspect(git=git_evidence(final_head=OTHER, is_descendant=False))

    assert not result.complete
    assert "divergent_head" in result.reasons


def test_evidence_only_requires_explicit_contract_and_immutable_evidence() -> None:
    evidence = EvidenceReceipt(ref="evidence-1", head=START, passed=True, immutable=True)
    result = inspect(
        git=git_evidence(final_head=START, commits=(), changed_paths=()),
        contract=base_contract(
            required_verification_refs=(),
            allow_evidence_only=True,
            evidence_only_refs=("evidence-1",),
        ),
        workspace={
            "workspace_id": "workspace-1",
            "checkout_id": "workspace-1",
            "state": "available",
            "identity_matches": True,
            "head": START,
            "dirty": False,
        },
        evidence_receipts=(evidence,),
    )

    assert result.complete

    accidental = inspect(
        git=git_evidence(final_head=START, commits=(), changed_paths=()),
        contract=base_contract(required_verification_refs=()),
    )
    assert not accidental.complete
    assert "evidence_only_not_authorized" in accidental.reasons


def test_missing_required_review_and_rejected_review_are_structural() -> None:
    missing = inspect(contract=base_contract(require_independent_review=True))
    rejected = inspect(
        contract=base_contract(require_independent_review=True),
        review=IndependentReviewReceipt(ref="review-1", head=FINAL, passed=False, immutable=True),
    )

    assert "review_missing" in missing.reasons
    assert "review_rejected" in rejected.reasons

    accepted = inspect(
        contract=base_contract(require_independent_review=True),
        review=IndependentReviewReceipt(ref="review-1", head=FINAL, passed=True, immutable=True),
    )
    assert accepted.complete


def test_timeout_and_result_loss_are_not_completion() -> None:
    timed_out = inspect(
        job={"job_id": "job-1", "state": {"phase": "timed_out", "terminal": True}, "checkout": {"checkout_id": "workspace-1", "head": START}}
    )
    lost = inspect(worker_result=None)

    assert "job_timeout" in timed_out.reasons
    assert "worker_result_missing" in lost.reasons

    artifact_lost = inspect(
        job={
            "job_id": "job-1",
            "state": {"phase": "succeeded", "terminal": True},
            "checkout": {"checkout_id": "workspace-1", "head": START},
            "artifacts": {"result": None},
        }
    )
    recovered = inspect(
        job={
            "job_id": "job-1",
            "state": {"phase": "succeeded", "terminal": True},
            "checkout": {"checkout_id": "workspace-1", "head": START},
            "artifacts": {"result": {"ref": "sinnix://jobs/job-1/artifacts/result"}},
        }
    )
    assert "job_result_loss" in artifact_lost.reasons
    assert recovered.complete


def test_required_deletion_ledger_cannot_be_omitted() -> None:
    result = inspect(worker_result=replace(delivery(), deletion_ledger=None))

    assert not result.complete
    assert "deletion_ledger_missing" in result.reasons


def test_unsupported_delegation_visibility_is_explicit_but_not_prose_inferred() -> None:
    result = inspect(
        delegation=DelegationCapability(visibility="unsupported", pending=None),
        worker_result=replace(delivery(), last_message="waiting for a background task"),
    )

    assert result.complete
    assert result.delegation.visibility == "unsupported"


def test_pending_delegation_is_consumed_from_structured_capability() -> None:
    result = inspect(
        delegation=DelegationCapability(visibility="supported", pending=True),
        worker_result=replace(delivery(), last_message="completed despite waiting in the text"),
    )

    assert not result.complete
    assert "delegated_work_pending" in result.reasons


def test_disposable_real_git_success_and_failed_packet_pair(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Fixture"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "fixture@example.test"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "--quiet", "--allow-empty", "-m", "base"], check=True)
    start = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "changed.py").write_text("pass\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "src/changed.py"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "--quiet", "-m", "change"], check=True)
    final = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    common = {
        "job": {
            "job_id": "job-1",
            "state": {"phase": "succeeded", "terminal": True},
            "checkout": {"checkout_id": "checkout-1", "head": start},
        },
        "workspace": {
            "workspace_id": "workspace-1",
            "checkout_id": "checkout-1",
            "path": str(tmp_path),
            "state": "available",
            "identity_matches": True,
            "head": final,
            "dirty": False,
        },
        "contract": base_contract(),
        "worker_result": delivery(),
        "verification_receipts": (verification(head=final),),
        "delegation": DelegationCapability(visibility="supported", pending=False),
    }
    assert PacketCompletionInspector().inspect(**common).complete

    (tmp_path / "untracked.txt").write_text("unfinished\n")
    failed = PacketCompletionInspector().inspect(**common)
    assert not failed.complete
    assert "workspace_dirty" in failed.reasons
    assert "untracked_work" in failed.reasons
