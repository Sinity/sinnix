"""Per-lane facts and the one next action they imply.

Every lane decision follows from facts read fresh: the worktree head, the
pushed head, who holds the worktree, the newest receipt, the PR worktrunk
sees, and master. ``advance`` is the pure function from those facts to the
next action; it keeps no dispatch records, because an action already in
flight is itself a fact (a running job on the checkout). ``collect`` reads
the facts from the daemon's own state, so `campaign view` and `campaign run`
cannot disagree about a lane.

GitHub owns the merge decision (required checks + review). PR facts come
from ``wt list --full`` (mergeable, checks status); review state is not
published there, so ``collect`` makes the one forge call this module is
allowed — ``gh pr view --json reviewDecision`` — and only for a lane that
already has a PR.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .worktrunk import Worktree

Run = Callable[..., subprocess.CompletedProcess[str]]

INTEGRATOR_LABELS = frozenset({"integrator", "rebase", "review-fix"})
# A workspace whose lane finished longer ago than this, with no open PR, is
# dormant: advancing it would verify and harvest dozens of abandoned
# worktrees every tick (the first fact-driven tick did, 2026-09-02 12:19Z).
DORMANT_AFTER_SECONDS = 3 * 24 * 60 * 60
REVIEW_DECISION_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class Receipt:
    packet_id: str
    head: str
    flags: tuple[str, ...]
    flagged: bool
    authorized: bool
    verification: str
    bead: str | None
    created_at: str


@dataclass(frozen=True)
class Pull:
    """What ``wt list --full`` publishes for a lane's PR."""

    number: int
    url: str
    mergeable: bool | None
    checks_status: str | None


@dataclass(frozen=True)
class LaneFacts:
    name: str
    checkout_id: str
    project: str
    branch: str
    bead: str | None
    head: str
    pushed_head: str | None
    master_head: str
    holder: str | None
    running_ops: tuple[str, ...]
    lane_phase: str | None
    receipt: Receipt | None
    pull: Pull | None
    review_decision: str | None = None
    lane_job: str | None = None
    integrators_at_head: tuple[str, ...] = ()
    authorization_head: str | None = None
    verify_job: tuple[str, str] | None = None
    harvest_at_head: tuple[str, str] | None = None
    published_at_head: bool = False
    lane_finished_at: str = ""
    bead_closed: bool = False
    agent_launched_at: str = ""
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Action:
    kind: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "reason": self.reason}


# Actions that name work a dispatcher can start; every other action (wait,
# idle, done, park, await-merge) is a fact for the status view, not a step.
DISPATCHABLE_ACTIONS = frozenset(
    {"verify", "harvest", "publish", "integrate", "rebase", "review-fix", "retry"}
)


def _dormant(facts: LaneFacts, now: datetime | None) -> bool:
    if facts.pull is not None or facts.holder is not None or facts.running_ops:
        return False
    if not facts.lane_finished_at:
        # No lane record at all: the records were pruned, so the lane ended
        # at least a retention window ago.
        return facts.lane_phase is None
    try:
        finished = datetime.fromisoformat(facts.lane_finished_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if finished.tzinfo is None:
        finished = finished.replace(tzinfo=UTC)
    moment = now or datetime.now(UTC)
    return (moment - finished).total_seconds() > DORMANT_AFTER_SECONDS


def _rebase_or_park(facts: LaneFacts, reason: str) -> Action:
    """One rebase integrator per head; a second conflict at the same head parks."""
    if any(label == "rebase" for label in facts.integrators_at_head):
        return Action("park", "rebase integrator ran at this head and it still conflicts")
    return Action("rebase", reason)


def advance(facts: LaneFacts, *, now: datetime | None = None) -> Action:
    """The next action for one lane, from its facts alone.

    Ordered by what must be true before anything else may happen; every
    branch names its reason so the status view and the dispatcher say the
    same thing.
    """
    if facts.bead_closed:
        return Action("done", "bead closed")
    if _dormant(facts, now):
        return Action("idle", "dormant workspace")
    if facts.holder is not None:
        return Action("wait", f"held by {facts.holder}")
    if facts.running_ops:
        return Action("wait", "running: " + ", ".join(sorted(facts.running_ops)))
    if facts.lane_phase in {"queued", "submitted", "running", "launch-unknown"}:
        return Action("wait", f"lane {facts.lane_phase}")
    if facts.lane_phase is None and facts.receipt is None:
        return Action("wait", "no finished lane")
    if (
        facts.lane_phase in {"failed", "cancelled", "timeout", "timed_out"}
        and facts.receipt is None
    ):
        return Action("retry", f"lane {facts.lane_phase}")
    receipt = facts.receipt
    if receipt is None or receipt.head != facts.head:
        if facts.harvest_at_head is not None:
            job_id, outcome = facts.harvest_at_head
            if outcome == "REBASE_CONFLICT":
                return _rebase_or_park(facts, "harvest could not rebase onto master")
            if outcome == "HARVEST_ERROR":
                # A harvest error is a refusal before any mutation (title,
                # bead, receipt inputs); the next planner run retries it once
                # the cause is corrected, and the reason names the last job.
                return Action("harvest", f"retry after harvest error {job_id[:8]}")
            return Action(
                "park", f"harvest {outcome} at this head left no receipt"
            )
        if facts.verify_job is not None and facts.verify_job[1] != "succeeded":
            return Action(
                "park", f"affected verification {facts.verify_job[1]} at this head"
            )
        if facts.verify_job is not None:
            return Action("harvest", f"verified by {facts.verify_job[0][:8]}")
        return Action("verify", "no receipt at head")
    pull = facts.pull
    if facts.published_at_head and (pull is None or facts.pushed_head != facts.head):
        return Action("await-merge", "published; waiting for GitHub to see the head")
    if pull is not None and facts.pushed_head == facts.head:
        if pull.mergeable is False:
            return _rebase_or_park(facts, "PR conflicts with master")
        if pull.checks_status == "failed":
            return Action("park", "CI red on the PR")
        if facts.review_decision == "CHANGES_REQUESTED":
            if "review-fix" in facts.integrators_at_head:
                return Action(
                    "park",
                    "review-fix ran at this head and changes are still requested",
                )
            return Action("review-fix", "review requested changes")
        return Action("await-merge", pull.checks_status or "checks pending")
    if pull is not None and facts.pushed_head != facts.head:
        return Action("publish", "head moved past the PR; push and re-mint")
    if facts.harvest_at_head is not None and facts.harvest_at_head[1] == "REBASE_CONFLICT":
        return _rebase_or_park(facts, "harvest could not rebase onto master")
    if receipt.flagged and not receipt.authorized:
        if "integrator" in facts.integrators_at_head:
            return Action(
                "park",
                "integrator ran at this head and flags remain: "
                + ", ".join(receipt.flags[:4]),
            )
        return Action("integrate", ", ".join(receipt.flags[:4]))
    if receipt.verification != "from-job" and not receipt.authorized:
        # Test evidence comes only from the declared verify_affected job: the
        # receipt records whether it was minted against one.
        if facts.verify_job is None:
            return Action("verify", "receipt has no test evidence")
        if facts.verify_job[1] != "succeeded":
            return Action(
                "park", f"affected verification {facts.verify_job[1]} at this head"
            )
        return Action("harvest", f"re-mint with verdict {facts.verify_job[0][:8]}")
    return Action("publish", "clean receipt at head")


def derived_checkout_id(path: str) -> str:
    return "worktree-" + hashlib.sha256(path.encode()).hexdigest()[:16]


def _git(run: Run, cwd: Path, *args: str) -> str:
    try:
        result = run(
            ["git", "-C", str(cwd), *args],
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _receipt_from(payload: Mapping[str, Any]) -> Receipt | None:
    packet_id = payload.get("packet_id")
    head = payload.get("head")
    if not isinstance(packet_id, str) or not isinstance(head, str):
        return None
    flags = tuple(
        str(flag)
        for flag in payload.get("redflags", [])
        if str(flag).startswith("FLAG:")
    )
    authorization = payload.get("authorization")
    verification = payload.get("verification")
    state = (
        str(verification.get("state") or "")
        if isinstance(verification, Mapping)
        else ""
    )
    bead = payload.get("bead_id")
    return Receipt(
        packet_id=packet_id,
        head=head,
        flags=flags,
        flagged=bool(payload.get("redflag_status")),
        authorized=isinstance(authorization, Mapping)
        and authorization.get("head") == head,
        verification=state,
        bead=bead if isinstance(bead, str) else None,
        created_at=str(payload.get("created_at") or ""),
    )


def _pull_from_worktree(worktree: Worktree) -> Pull | None:
    if worktree.pr is None:
        return None
    return Pull(
        number=worktree.pr.number,
        url=worktree.pr.url,
        mergeable=worktree.pr.mergeable,
        checks_status=worktree.checks.status if worktree.checks else None,
    )


def _review_decision(run: Run, number: int) -> str | None:
    try:
        result = run(
            [
                "gh",
                "pr",
                "view",
                str(number),
                "--json",
                "reviewDecision",
                "--jq",
                ".reviewDecision",
            ],
            capture_output=True,
            text=True,
            timeout=REVIEW_DECISION_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def collect(
    project: str,
    *,
    state_root: Path,
    worktrees: Sequence[Worktree] = (),
    run: Run = subprocess.run,
    master_head: str | None = None,
    closed_beads: Sequence[str] = (),
) -> list[LaneFacts]:
    """Read every managed workspace of the project into facts.

    PR number, check status and mergeability come from ``worktrees``
    (``wt list --format=json --full``), matched to a lane by branch.
    """
    index_path = state_root / "workspaces" / "index.json"
    try:
        records = json.loads(index_path.read_text()).get("workspaces", [])
    except (OSError, json.JSONDecodeError, AttributeError):
        return []
    jobs = _job_records(state_root / "jobs")
    receipts = _receipts(state_root / "harvest-packets")
    facts: list[LaneFacts] = []
    resolved_master = master_head
    for record in records:
        if not isinstance(record, Mapping) or record.get("project_id") != project:
            continue
        path = record.get("path")
        name = record.get("name")
        branch = str(record.get("branch") or "")
        if not isinstance(path, str) or not isinstance(name, str):
            continue
        worktree = Path(path)
        if not worktree.is_dir():
            continue
        checkout_id = derived_checkout_id(path)
        if resolved_master is None:
            resolved_master = _git(run, worktree, "rev-parse", "origin/master")
        head = _git(run, worktree, "rev-parse", "HEAD")
        pushed = (
            _git(run, worktree, "rev-parse", f"refs/remotes/origin/{branch}")
            if branch
            else ""
        )
        holder: str | None = None
        running_ops: list[str] = []
        lane_phase: str | None = None
        lane_job: str | None = None
        lane_created = ""
        integrators: list[str] = []
        bead: str | None = None
        verify_job: tuple[str, str] | None = None
        verify_created = ""
        lane_finished = ""
        harvest_at_head: tuple[str, str] | None = None
        published_at_head = False
        agent_launched = ""
        for job in jobs:
            spec = job.get("spec") or {}
            state = job.get("state") or {}
            checkout = spec.get("checkout") or {}
            if checkout.get("checkout_id") != checkout_id:
                continue
            kind = spec.get("kind")
            terminal = bool(state.get("terminal"))
            phase = str(state.get("phase") or "")
            if kind == "attested-agent":
                label = _agent_label(spec)
                agent_launched = max(agent_launched, str(job.get("created_at") or ""))
                if not terminal:
                    holder = label
                if (
                    label in INTEGRATOR_LABELS
                    and checkout.get("head") == head
                    and terminal
                    and phase == "succeeded"
                ):
                    integrators.append(label)
                if label == "lane":
                    created = str(job.get("created_at") or "")
                    if created >= lane_created:
                        lane_created, lane_phase = created, phase
                        lane_job = str(job.get("job_id") or "") or None
                        lane_finished = str(
                            state.get("completed_at")
                            or state.get("observed_at")
                            or created
                        )
                    bead = bead or _campaign_bead(spec)
            elif kind == "declared-operation" and not terminal:
                running_ops.append(str(spec.get("operation") or "operation"))
            elif (
                kind == "declared-operation"
                and spec.get("operation") == "harvest"
                and checkout.get("head") == head
            ):
                outcome, result_phase = _harvest_result(job)
                if result_phase == "published":
                    published_at_head = True
                elif outcome in {"HARVEST_ERROR", "GATE_RED", "REBASE_CONFLICT"} or (
                    phase == "failed"
                ):
                    harvest_at_head = (str(job.get("job_id") or ""), outcome or phase)
            elif (
                kind == "declared-operation"
                and spec.get("operation") == "verify_affected"
                and checkout.get("head") == head
                and phase in {"succeeded", "failed"}
            ):
                created = str(job.get("created_at") or "")
                if created >= verify_created:
                    verify_created, verify_job = (
                        created,
                        (str(job.get("job_id") or ""), phase),
                    )
        receipt = receipts.get(checkout_id)
        wt_item = next((item for item in worktrees if item.branch == branch), None)
        pull = _pull_from_worktree(wt_item) if wt_item is not None else None
        review_decision = (
            _review_decision(run, pull.number) if pull is not None else None
        )
        authorization_head = _authorization_head(worktree)
        facts.append(
            LaneFacts(
                name=name,
                checkout_id=checkout_id,
                project=project,
                branch=branch,
                bead=bead or (receipt.bead if receipt else None),
                head=head,
                pushed_head=pushed or None,
                master_head=resolved_master or "",
                holder=holder,
                running_ops=tuple(sorted(set(running_ops))),
                lane_phase=lane_phase,
                lane_job=lane_job,
                receipt=receipt,
                pull=pull,
                review_decision=review_decision,
                integrators_at_head=tuple(integrators),
                authorization_head=authorization_head,
                verify_job=verify_job,
                harvest_at_head=harvest_at_head,
                published_at_head=published_at_head,
                lane_finished_at=lane_finished,
                bead_closed=(bead or (receipt.bead if receipt else None))
                in set(closed_beads),
                agent_launched_at=agent_launched,
            )
        )
    return facts


def _harvest_result(job: Mapping[str, Any]) -> tuple[str | None, str | None]:
    """(outcome, phase) from a terminal harvest job's result artifact."""
    artifacts = job.get("artifacts") or {}
    path = artifacts.get("result") if isinstance(artifacts, Mapping) else None
    if not isinstance(path, str):
        return None, None
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return None, None
    if isinstance(value, Mapping) and isinstance(value.get("value"), Mapping):
        value = value["value"]
    if not isinstance(value, Mapping):
        return None, None
    outcome = value.get("outcome")
    result_phase = value.get("phase")
    return (
        outcome if isinstance(outcome, str) else None,
        result_phase if isinstance(result_phase, str) else None,
    )


def _agent_label(spec: Mapping[str, Any]) -> str:
    contract = spec.get("contract") or {}
    label = contract.get("coordinator_label") if isinstance(contract, Mapping) else None
    if isinstance(label, str) and label:
        return label
    parameters = contract.get("parameters") if isinstance(contract, Mapping) else None
    if isinstance(parameters, Mapping) and isinstance(
        parameters.get("campaign"), Mapping
    ):
        return "lane"
    return "agent"


def _campaign_bead(spec: Mapping[str, Any]) -> str | None:
    contract = spec.get("contract") or {}
    parameters = contract.get("parameters") if isinstance(contract, Mapping) else None
    campaign = parameters.get("campaign") if isinstance(parameters, Mapping) else None
    beads = campaign.get("bead_ids") if isinstance(campaign, Mapping) else None
    if isinstance(beads, list) and beads and isinstance(beads[0], str):
        return beads[0]
    return None


def _authorization_head(worktree: Path) -> str | None:
    try:
        value = json.loads((worktree / ".lane" / "authorization.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None
    head = value.get("head") if isinstance(value, Mapping) else None
    return head if isinstance(head, str) else None


def _job_records(root: Path) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    try:
        paths = sorted(root.glob("*.json"))
    except OSError:
        return records
    for path in paths:
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, Mapping):
            records.append(value)
    return records


def _receipts(root: Path) -> dict[str, Receipt]:
    """The newest receipt per workspace."""
    newest: dict[str, tuple[float, Receipt]] = {}
    try:
        paths = list(root.glob("harvest-*.json"))
    except OSError:
        return {}
    for path in paths:
        try:
            value = json.loads(path.read_text())
            stamp = path.stat().st_mtime
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(value, Mapping):
            continue
        workspace = value.get("workspace_id")
        receipt = _receipt_from(value)
        if not isinstance(workspace, str) or receipt is None:
            continue
        if workspace not in newest or newest[workspace][0] < stamp:
            newest[workspace] = (stamp, receipt)
    return {workspace: receipt for workspace, (_stamp, receipt) in newest.items()}


_CLOSED_BEADS_TTL_SECONDS = 300.0
_closed_beads_lock = threading.Lock()
_closed_beads_cache: dict[Path, tuple[float, tuple[str, ...]]] = {}
_closed_beads_refreshing: set[Path] = set()


def _query_closed_beads(
    project_root: Path, run: Run, timeout: float
) -> tuple[str, ...] | None:
    try:
        result = run(
            ["bd", "list", "--status", "closed", "--json"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
        rows = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None
    return tuple(
        str(row.get("id"))
        for row in (rows if isinstance(rows, list) else [])
        if isinstance(row, Mapping) and row.get("id")
    )


def closed_bead_ids(
    project_root: Path,
    *,
    run: Run = subprocess.run,
    timeout: float = 180,
    wait: bool | None = None,
) -> tuple[str, ...]:
    """Closed bead ids for the project.

    The cached answer is returned and refreshed on a background thread once
    it is older than five minutes, so a slow ``bd`` never stalls the caller.
    ``wait=None`` (default) answers the first call for a root inline;
    ``wait=False`` never blocks; ``wait=True`` always refreshes inline.
    ``()`` means bd has not answered yet.
    """
    root = project_root.resolve()
    now = time.monotonic()
    with _closed_beads_lock:
        cached = _closed_beads_cache.get(root)
        fresh = cached is not None and now - cached[0] < _CLOSED_BEADS_TTL_SECONDS
        known = cached[1] if cached is not None else ()
        if cached is not None and fresh and wait is not True:
            return known
        inline = wait is True or (wait is None and cached is None)
        if not inline and root in _closed_beads_refreshing:
            return known
        if not inline:
            _closed_beads_refreshing.add(root)

    def refresh() -> tuple[str, ...]:
        answer = _query_closed_beads(root, run, timeout)
        with _closed_beads_lock:
            _closed_beads_refreshing.discard(root)
            if answer is not None:
                _closed_beads_cache[root] = (time.monotonic(), answer)
                return answer
            previous = _closed_beads_cache.get(root)
            return previous[1] if previous is not None else ()

    if inline:
        return refresh()
    threading.Thread(target=refresh, name="closed-beads", daemon=True).start()
    return known


def _corpus_outcomes(job: Mapping[str, Any]) -> tuple[Mapping[str, Any], Any]:
    artifacts = job.get("artifacts") or {}
    path = artifacts.get("result") if isinstance(artifacts, Mapping) else None
    if not isinstance(path, str):
        return {}, None
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return {}, None
    if isinstance(value, Mapping) and isinstance(value.get("value"), Mapping):
        value = value["value"]
    if not isinstance(value, Mapping):
        return {}, None
    pytest_outcomes = value.get("pytest_outcomes")
    outcomes = (
        pytest_outcomes.get("outcomes")
        if isinstance(pytest_outcomes, Mapping)
        else None
    )
    diagnostics = value.get("diagnostics")
    diagnosis = (
        diagnostics.get("diagnosis") if isinstance(diagnostics, Mapping) else None
    )
    return (outcomes if isinstance(outcomes, Mapping) else {}), diagnosis


def latest_corpus(state_root: Path, project: str) -> dict[str, Any] | None:
    """The newest finished complete-corpus run: head, outcome counts, age.

    Read from the verify_all job's result so the number never depends on a
    memory of what was reported.
    """
    # The newest run that produced outcomes; a cancelled or vanished run
    # carries no number and must not hide the last real one.
    newest: tuple[str, Mapping[str, Any], Mapping[str, Any], Any] | None = None
    for job in _job_records(state_root / "jobs"):
        spec = job.get("spec") or {}
        state = job.get("state") or {}
        if (
            spec.get("operation") != "verify_all"
            or spec.get("project_id") != project
            or not state.get("terminal")
        ):
            continue
        created = str(job.get("created_at") or "")
        if newest is not None and created <= newest[0]:
            continue
        outcomes, diagnosis = _corpus_outcomes(job)
        if outcomes:
            newest = (created, job, outcomes, diagnosis)
    if newest is None:
        return None
    _, job, outcomes, diagnosis = newest
    state = job.get("state") or {}
    checkout = (job.get("spec") or {}).get("checkout") or {}
    red = int(outcomes.get("failed", 0) or 0) + int(outcomes.get("error", 0) or 0)
    return {
        "job_id": str(job.get("job_id") or ""),
        "head": str(checkout.get("head") or "")[:12],
        "phase": str(state.get("phase") or ""),
        "finished_at": str(state.get("completed_at") or state.get("observed_at") or ""),
        "passed": int(outcomes.get("passed", 0) or 0),
        "red": red,
        "diagnosis": diagnosis,
        "green": bool(outcomes) and red == 0 and str(state.get("phase")) == "succeeded",
    }


def lane_view(facts: LaneFacts) -> dict[str, Any]:
    """One status row: the facts and the action they imply."""
    action = advance(facts)
    return {
        "workspace": facts.name,
        "bead": facts.bead,
        "head": facts.head[:12],
        "pushed": (facts.pushed_head or "")[:12] or None,
        "holder": facts.holder,
        "running": list(facts.running_ops),
        "lane": facts.lane_phase,
        "receipt": (
            {
                "id": facts.receipt.packet_id,
                "at_head": facts.receipt.head == facts.head,
                "flags": list(facts.receipt.flags),
                "authorized": facts.receipt.authorized,
                "verification": facts.receipt.verification,
            }
            if facts.receipt
            else None
        ),
        "pr": (
            {
                "number": facts.pull.number,
                "url": facts.pull.url,
                "mergeable": facts.pull.mergeable,
                "checks_status": facts.pull.checks_status,
                "review_decision": facts.review_decision,
            }
            if facts.pull
            else None
        ),
        "next": action.to_dict(),
    }


__all__ = [
    "Action",
    "DISPATCHABLE_ACTIONS",
    "LaneFacts",
    "Pull",
    "Receipt",
    "advance",
    "closed_bead_ids",
    "collect",
    "latest_corpus",
    "derived_checkout_id",
    "lane_view",
]
