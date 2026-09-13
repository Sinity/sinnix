"""Native-work evidence: immutable result records without a batch lifecycle.

The file route stores a submitted worker-result claim beside observations that
AgentCTL can make at filing time.  It does not create a run, claim a Beads
task, make a worktree, or schedule work.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import gitcmd, github, launch, results
from .config import Config
from .launch import JobError
from .projects import ProjectAdapter
from .prompts import PromptError, SubprocessBdReader, evidence_binding

RECORD_SCHEMA_VERSION = 1
MAX_EVIDENCE_BYTES = 256 * 1024
MAX_RECORDS = 1_000
MAX_BEADS = 100
MAX_VERIFICATIONS = 100
_RECEIPT = re.compile(r"^agentctl://jobs/([0-9]+)/([A-Za-z0-9._-]+)$")


def _records_dir(config: Config) -> Path:
    return config.state_dir / "native-evidence"


def _read_input(path: Path) -> Mapping[str, Any]:
    raw = launch.read_bounded(path, MAX_EVIDENCE_BYTES + 1)
    if raw is None:
        raise JobError(f"native evidence input is not a bounded regular file: {path}")
    if len(raw) > MAX_EVIDENCE_BYTES:
        raise JobError(f"native evidence input exceeds {MAX_EVIDENCE_BYTES} bytes")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise JobError(f"native evidence input is not JSON: {path}") from error
    if not isinstance(value, Mapping):
        raise JobError("native evidence input must be an object")
    return value


def _binding_errors(
    snapshot: list[dict[str, Any]], claim: Mapping[str, Any]
) -> list[str]:
    """Version two claims may only repeat the owner facts filed with them."""
    if claim.get("schema_version") != results.RESULT_SCHEMA_VERSION:
        return []
    if claim.get("execution") != "native":
        return ["v2 native evidence requires execution=native"]
    expected = {
        row["id"]: row["evidence_binding"]
        for row in snapshot
        if row["evidence_binding"].get("v2_available") is True
    }
    submitted = {
        row.get("id"): row
        for row in claim.get("beads") or ()
        if isinstance(row, Mapping) and isinstance(row.get("id"), str)
    }
    if set(submitted) != set(expected):
        return ["v2 native evidence requires stable Beads acceptance bindings"]
    errors: list[str] = []
    for bead_id, binding in expected.items():
        actual = submitted[bead_id]
        if actual.get("bead_revision") != binding.get("bead_revision"):
            errors.append(
                f"v2 result {bead_id} bead_revision differs from filing snapshot"
            )
        expected_criteria = {
            (criterion.get("ac_id"), criterion.get("text"))
            for criterion in binding.get("criteria") or ()
            if isinstance(criterion, Mapping)
        }
        actual_criteria = {
            (criterion.get("ac_id"), criterion.get("text"))
            for criterion in actual.get("criteria") or ()
            if isinstance(criterion, Mapping)
        }
        if actual_criteria != expected_criteria:
            errors.append(f"v2 result {bead_id} criteria differ from filing snapshot")
    return errors


def _acceptance_criteria(bead: Mapping[str, Any]) -> Any:
    """The exact owner-authored criteria value, including legacy prose."""
    if "acceptance_criteria" in bead:
        return bead["acceptance_criteria"]
    metadata = bead.get("metadata")
    return (
        metadata.get("acceptance_criteria") if isinstance(metadata, Mapping) else None
    )


def _task_snapshot(
    project: ProjectAdapter, claim: Mapping[str, Any]
) -> list[dict[str, Any]]:
    reader = SubprocessBdReader(project.root)
    snapshots: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in claim.get("beads") or ():
        bead_id = entry.get("id") if isinstance(entry, Mapping) else None
        if not isinstance(bead_id, str) or not bead_id:
            continue
        if bead_id in seen:
            raise JobError(f"native evidence names bead {bead_id} more than once")
        seen.add(bead_id)
        try:
            bead = reader.show(bead_id)
        except PromptError as error:
            raise JobError(str(error)) from error
        if bead.get("id") != bead_id:
            raise JobError(f"bd show {bead_id} returned the wrong bead")
        snapshots.append(
            {
                "id": bead_id,
                "source": "beads",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "evidence_binding": evidence_binding(bead),
                "acceptance_criteria": _acceptance_criteria(bead),
            }
        )
    return snapshots


def _receipt_observation(
    config: Config, claim: Mapping[str, Any], candidate: str, *, project_id: str
) -> dict[str, Any]:
    receipt = claim.get("receipt")
    match = _RECEIPT.fullmatch(receipt) if isinstance(receipt, str) else None
    if match is None:
        raise JobError(
            "native verification receipt must be agentctl://jobs/<id>/<launch-reference>"
        )
    task_id, reference = int(match.group(1)), match.group(2)
    try:
        task = launch._read_task(config, task_id, reference)
        job = launch.get_job(task.task_id, config, reference)
    except JobError as error:
        raise JobError(
            f"native verification receipt does not resolve: {receipt}"
        ) from error
    launch_input = launch._launch_input(config, task)
    if launch_input is None:
        raise JobError(
            f"native verification receipt has no AgentCTL launch input: {receipt}"
        )
    if launch_input.get("project_id") != project_id:
        raise JobError(
            f"native verification receipt belongs to another project: {receipt}"
        )
    launch_tree = launch_input.get("tree_receipt")
    tree_receipt = (
        {key: launch_tree.get(key) for key in ("head", "tree", "dirty")}
        if isinstance(launch_tree, Mapping)
        else None
    )
    outcome = job.get("outcome")
    execution_receipt = (
        outcome.get("execution_receipt") if isinstance(outcome, Mapping) else None
    )
    start = (
        execution_receipt.get("start")
        if isinstance(execution_receipt, Mapping)
        else None
    )
    end = (
        execution_receipt.get("end") if isinstance(execution_receipt, Mapping) else None
    )
    outcome_succeeded = bool(
        isinstance(outcome, Mapping)
        and outcome.get("outcome") == "success"
        and outcome.get("exit_code") == 0
    )
    endpoint_candidate = all(
        isinstance(endpoint, Mapping)
        and endpoint.get("status") == "observed"
        and endpoint.get("head") == candidate
        and endpoint.get("dirty") is False
        for endpoint in (start, end)
    )
    clean_candidate = bool(
        job["terminal"]
        and job["phase"] == "succeeded"
        and outcome_succeeded
        and isinstance(execution_receipt, Mapping)
        and execution_receipt.get("binding") == "unchanged_endpoints"
        and endpoint_candidate
    )
    gaps: list[str] = []
    if not job["terminal"]:
        gaps.append("receipt job is not terminal")
    elif job["phase"] != "succeeded":
        gaps.append("receipt job did not succeed")
    if not outcome_succeeded:
        gaps.append("receipt job outcome is not successful with exit code 0")
    if not isinstance(execution_receipt, Mapping):
        gaps.append("receipt job has no execution checkout receipt")
    elif execution_receipt.get("binding") != "unchanged_endpoints":
        gaps.append("receipt job checkout changed or was unavailable during execution")
    elif not endpoint_candidate:
        gaps.append("receipt job endpoints are not both observed, clean candidate_sha")
    return {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source": "agentctl",
        "job_id": job["job_id"],
        "reference": reference,
        "attempt": job["attempt"],
        "artifacts": job["artifacts"],
        "queue_present": job["queue_present"],
        "phase": job["phase"],
        "exit_code": job["exit_code"],
        "operation": launch_input.get("operation"),
        "argv": list(launch_input.get("argv") or ()),
        # Diagnostic launch-time cache observation only. Eligibility uses the
        # runner's endpoint receipt below, never this enqueue-time snapshot.
        "tree_receipt": tree_receipt,
        "execution_receipt": execution_receipt,
        "result_kind": launch_input.get("result_kind"),
        "checked": True,
        "eligible": clean_candidate,
        "gaps": gaps,
    }


def _publication(project: ProjectAdapter, candidate: str) -> dict[str, Any]:
    """Observe the advertised base ref and the matching local ancestry.

    Neither a local branch nor a successful `git push` is publication proof.
    The local remote-tracking ref must equal the advertised remote head before
    it can prove that the candidate is reachable from that head.
    """
    branch = project.workspace.base_branch
    document: dict[str, Any] = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source": "git+origin",
        "policy": project.workspace.publish,
        "branch": branch,
        "remote_head": None,
        "local_remote_head": None,
        "candidate_reachable": None,
        "checked": False,
        "state": "unknown",
        "gaps": [],
    }
    try:
        remote_head = github.remote_head(project.root, branch)
        document["remote_head"] = remote_head
        local_head = gitcmd.git(
            project.root,
            "rev-parse",
            "--verify",
            f"refs/remotes/origin/{branch}^{{commit}}",
            error=JobError,
        )
        document["local_remote_head"] = local_head
        document["checked"] = True
        if remote_head is None:
            document["gaps"].append("the advertised base branch does not exist")
        elif local_head != remote_head:
            document["gaps"].append(
                "local origin tracking ref differs from the advertised remote base head"
            )
        else:
            try:
                gitcmd.git(
                    project.root,
                    "merge-base",
                    "--is-ancestor",
                    candidate,
                    local_head,
                    error=JobError,
                )
            except JobError:
                document["candidate_reachable"] = False
                document["gaps"].append(
                    "candidate is not an ancestor of the advertised base branch"
                )
            else:
                document["candidate_reachable"] = True
                document["state"] = "published"
    except (JobError, github.GithubError) as error:
        document["gaps"].append(f"publication observation unavailable: {error}")
    return document


def _candidate(project: ProjectAdapter, candidate: str) -> dict[str, Any]:
    try:
        resolved = gitcmd.git(
            project.root,
            "rev-parse",
            "--verify",
            f"{candidate}^{{commit}}",
            error=JobError,
        )
        head = gitcmd.git(project.root, "rev-parse", "HEAD", error=JobError)
        dirty = bool(
            gitcmd.git(
                project.root,
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                error=JobError,
            )
        )
    except JobError as error:
        return {
            "candidate_sha": candidate,
            "source": "git",
            "current_head": None,
            "current_dirty": None,
            "checked": False,
            "gaps": [f"candidate observation unavailable: {error}"],
        }
    gaps = []
    if head != candidate:
        gaps.append(
            "current project HEAD does not match candidate_sha; receipt and publication observations decide candidate eligibility"
        )
    if dirty:
        gaps.append("current project checkout is dirty")
    return {
        "candidate_sha": candidate,
        "source": "git",
        "resolved_commit": resolved,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "current_head": head,
        "current_dirty": dirty,
        "checked": True,
        "gaps": gaps,
    }


def _write_record(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded) > MAX_EVIDENCE_BYTES:
        raise JobError(f"native evidence record exceeds {MAX_EVIDENCE_BYTES} bytes")
    descriptor = os.open(
        path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(encoded)


def file(config: Config, project: ProjectAdapter, path: Path) -> dict[str, Any]:
    """File native work's claim and AgentCTL's contemporaneous observations."""
    claim = _read_input(path)
    errors = results.validate_worker_result(claim)
    if errors:
        raise JobError("invalid native evidence: " + "; ".join(errors[:6]))
    candidate_sha = claim["candidate_sha"]
    if len(claim.get("beads") or ()) > MAX_BEADS:
        raise JobError(f"native evidence is bounded to {MAX_BEADS} beads")
    if len(claim.get("verification") or ()) > MAX_VERIFICATIONS:
        raise JobError(
            f"native evidence is bounded to {MAX_VERIFICATIONS} verification receipts"
        )
    snapshot = _task_snapshot(project, claim)
    binding_errors = _binding_errors(snapshot, claim)
    if binding_errors:
        raise JobError("invalid native evidence binding: " + "; ".join(binding_errors))
    verifications = [
        {
            "claim": check,
            "observation": _receipt_observation(
                config, check, candidate_sha, project_id=project.project_id
            ),
        }
        for check in claim.get("verification") or ()
        if isinstance(check, Mapping)
    ]
    evidence_id = uuid.uuid4().hex
    document = {
        "schema_version": RECORD_SCHEMA_VERSION,
        "kind": "native_evidence",
        "source": "agentctl",
        "evidence_id": evidence_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "project": project.project_id,
        "worker_result": claim,
        "task_snapshot": snapshot,
        "candidate": _candidate(project, candidate_sha),
        "verification": verifications,
        "publication": _publication(project, candidate_sha),
        "session_claims": {
            key: claim.get(key)
            for key in ("parent_session_ref", "child_session_ref")
            if key in claim
        },
    }
    _write_record(_records_dir(config) / f"{evidence_id}.json", document)
    return document


def list_records(config: Config, project_id: str) -> dict[str, Any]:
    """The bounded read route for retained native evidence records."""
    directory = _records_dir(config)
    document: dict[str, Any] = {
        "schema_version": 1,
        "owner": "agentctl",
        "interface": "agentctl.evidence.list",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "project": project_id,
        "records": [],
        "coverage": "retained_records",
        "gaps": [],
    }
    try:
        entries = os.scandir(directory)
    except FileNotFoundError:
        return document
    except OSError as error:
        return {**document, "coverage": "unavailable", "gaps": [str(error)]}
    records: list[dict[str, Any]] = []
    try:
        paths = (Path(entry.path) for entry in entries if entry.name.endswith(".json"))
        for index, path in enumerate(paths):
            if index >= MAX_RECORDS:
                document["coverage"] = "partial"
                document["gaps"].append(
                    f"native evidence read is bounded to {MAX_RECORDS} records"
                )
                break
            raw = launch.read_bounded(path, MAX_EVIDENCE_BYTES + 1)
            if raw is None or len(raw) > MAX_EVIDENCE_BYTES:
                document["coverage"] = "partial"
                document["gaps"].append(f"unreadable or oversized record: {path.name}")
                continue
            try:
                value = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                document["coverage"] = "partial"
                document["gaps"].append(f"invalid record: {path.name}")
                continue
            if (
                isinstance(value, dict)
                and value.get("schema_version") == RECORD_SCHEMA_VERSION
                and value.get("kind") == "native_evidence"
                and value.get("project") == project_id
            ):
                records.append(value)
    except OSError as error:
        return {**document, "coverage": "unavailable", "gaps": [str(error)]}
    finally:
        entries.close()
    document["records"] = sorted(
        records, key=lambda row: str(row.get("evidence_id") or "")
    )
    return document
