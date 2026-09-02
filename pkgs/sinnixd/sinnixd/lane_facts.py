"""Per-lane facts and the one next action they imply.

Every lane decision the reactor makes can be computed from facts read fresh
each tick: the worktree head, the pushed head, who holds the worktree, the
newest receipt, the PR the sweep sees, and master. ``advance`` is the pure
function from those facts to the next action; it keeps no dispatch records,
because an action already in flight is itself a fact (a running job on the
checkout). ``collect`` reads the facts from the daemon's own state.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

Run = Callable[..., subprocess.CompletedProcess[str]]

INTEGRATOR_LABELS = frozenset({"integrator", "rebase", "review-fix"})
ANSWERED_ROUNDS_TO_MERGE = 2


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
    number: int
    head: str
    verdict: str
    findings: int
    answered_rounds: int = 0


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
    integrators_at_head: tuple[str, ...] = ()
    authorization_head: str | None = None
    verify_job: tuple[str, str] | None = None
    harvest_at_head: tuple[str, str] | None = None
    published_at_head: bool = False
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Action:
    kind: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "reason": self.reason}


def advance(facts: LaneFacts) -> Action:
    """The next action for one lane, from its facts alone.

    Ordered by what must be true before anything else may happen; every
    branch names its reason so the status view and the reactor say the same
    thing.
    """
    if facts.holder is not None:
        return Action("wait", f"held by {facts.holder}")
    if facts.running_ops:
        return Action("wait", "running: " + ", ".join(sorted(facts.running_ops)))
    if facts.lane_phase in {"queued", "submitted", "running", "launch-unknown"}:
        return Action("wait", f"lane {facts.lane_phase}")
    if facts.lane_phase is None and facts.receipt is None:
        return Action("wait", "no finished lane")
    if facts.lane_phase in {"failed", "cancelled", "timeout", "timed_out"} and facts.receipt is None:
        return Action("retry", f"lane {facts.lane_phase}")
    receipt = facts.receipt
    if receipt is None or receipt.head != facts.head:
        if facts.harvest_at_head is not None:
            return Action("park", f"harvest {facts.harvest_at_head[1]} at this head left no receipt")
        if facts.verify_job is not None and facts.verify_job[1] != "succeeded":
            return Action("park", f"affected verification {facts.verify_job[1]} at this head")
        if facts.verify_job is not None:
            return Action("harvest", f"verified by {facts.verify_job[0][:8]}")
        return Action("verify", "no receipt at head")
    pull = facts.pull
    if facts.published_at_head and (pull is None or pull.head != facts.head):
        return Action("await-sweep", "published; waiting for the sweep to see the head")
    if pull is not None and pull.head == facts.head:
        if pull.verdict == "conflict":
            if any(label == "rebase" for label in facts.integrators_at_head):
                return Action("park", "rebase integrator ran at this head and it still conflicts")
            return Action("rebase", "PR conflicts with master")
        if pull.verdict == "ci-red":
            return Action("park", "CI red on the PR")
        if pull.findings > 0 and pull.answered_rounds < ANSWERED_ROUNDS_TO_MERGE:
            if "review-fix" in facts.integrators_at_head:
                return Action("park", "review-fix ran at this head and findings remain")
            return Action("review-fix", f"{pull.findings} finding(s)")
        return Action("await-sweep", pull.verdict)
    if pull is not None and pull.head != facts.head and facts.pushed_head != facts.head:
        return Action("publish", "head moved past the PR; push and re-mint")
    if receipt.flagged and not receipt.authorized:
        if "integrator" in facts.integrators_at_head:
            return Action("park", "integrator ran at this head and flags remain: " + ", ".join(receipt.flags[:4]))
        return Action("integrate", ", ".join(receipt.flags[:4]))
    if receipt.verification in {"static-only", "unavailable"} and not receipt.authorized:
        if facts.master_head and facts.master_head[:12] in facts.extra.get("rebased_on", ()):
            return Action("park", f"no test evidence after rebase ({receipt.verification})")
        return Action("rebase", f"no test evidence ({receipt.verification}); rebase onto master")
    return Action("publish", "clean receipt at head")


def derived_checkout_id(path: str) -> str:
    return "worktree-" + hashlib.sha256(path.encode()).hexdigest()[:16]


def _git(run: Run, cwd: Path, *args: str) -> str:
    try:
        result = run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _receipt_from(payload: Mapping[str, Any]) -> Receipt | None:
    packet_id = payload.get("packet_id")
    head = payload.get("head")
    if not isinstance(packet_id, str) or not isinstance(head, str):
        return None
    flags = tuple(str(flag) for flag in payload.get("redflags", []) if str(flag).startswith("FLAG:"))
    authorization = payload.get("authorization")
    verification = payload.get("verification")
    state = str(verification.get("state") or "") if isinstance(verification, Mapping) else ""
    bead = payload.get("bead_id")
    return Receipt(
        packet_id=packet_id,
        head=head,
        flags=flags,
        flagged=bool(payload.get("redflag_status")),
        authorized=isinstance(authorization, Mapping) and authorization.get("head") == head,
        verification=state,
        bead=bead if isinstance(bead, str) else None,
        created_at=str(payload.get("created_at") or ""),
    )


def collect(
    project: str,
    *,
    state_root: Path,
    pulls: Sequence[Pull] = (),
    receipt_pulls: Mapping[str, Pull] | None = None,
    run: Run = subprocess.run,
    master_head: str | None = None,
) -> list[LaneFacts]:
    """Read every managed workspace of the project into facts."""
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
        pushed = _git(run, worktree, "rev-parse", f"refs/remotes/origin/{branch}") if branch else ""
        holder: str | None = None
        running_ops: list[str] = []
        lane_phase: str | None = None
        lane_created = ""
        integrators: list[str] = []
        bead: str | None = None
        verify_job: tuple[str, str] | None = None
        verify_created = ""
        harvest_at_head: tuple[str, str] | None = None
        published_at_head = False
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
                if not terminal:
                    holder = label
                if label in INTEGRATOR_LABELS and checkout.get("head") == head and terminal and phase == "succeeded":
                    integrators.append(label)
                if label == "lane":
                    created = str(job.get("created_at") or "")
                    if created >= lane_created:
                        lane_created, lane_phase = created, phase
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
                elif outcome in {"HARVEST_ERROR", "GATE_RED"} or (phase != "succeeded" and outcome is None):
                    harvest_at_head = (str(job.get("job_id") or ""), outcome or phase)
            elif (
                kind == "declared-operation"
                and spec.get("operation") == "verify_affected"
                and checkout.get("head") == head
                and phase in {"succeeded", "failed"}
            ):
                created = str(job.get("created_at") or "")
                if created >= verify_created:
                    verify_created, verify_job = created, (str(job.get("job_id") or ""), phase)
        receipt = receipts.get(checkout_id)
        pull = None
        if receipt is not None and receipt_pulls:
            pull = receipt_pulls.get(receipt.packet_id)
        if pull is None:
            pull = next((item for item in pulls if item.head in {head, pushed}), None)
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
                receipt=receipt,
                pull=pull,
                integrators_at_head=tuple(integrators),
                authorization_head=authorization_head,
                verify_job=verify_job,
                harvest_at_head=harvest_at_head,
                published_at_head=published_at_head,
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
    return (outcome if isinstance(outcome, str) else None, result_phase if isinstance(result_phase, str) else None)


def _agent_label(spec: Mapping[str, Any]) -> str:
    contract = spec.get("contract") or {}
    label = contract.get("coordinator_label") if isinstance(contract, Mapping) else None
    if isinstance(label, str) and label:
        return label
    parameters = contract.get("parameters") if isinstance(contract, Mapping) else None
    if isinstance(parameters, Mapping) and isinstance(parameters.get("campaign"), Mapping):
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


def pulls_from_sweep_actions(actions: Sequence[Mapping[str, Any]]) -> dict[str, Pull]:
    """PRs keyed by receipt id, from a publication-sweep receipt."""
    pulls: dict[str, Pull] = {}
    for action in actions:
        number = action.get("pr")
        receipt = action.get("receipt")
        head = action.get("head")
        if not isinstance(number, int) or not isinstance(head, str):
            continue
        pull = Pull(
            number=number,
            head=head,
            verdict=str(action.get("verdict") or ""),
            findings=int(action.get("findings") or 0),
            answered_rounds=int(action.get("answered_rounds") or 0),
        )
        if isinstance(receipt, str):
            pulls[receipt] = pull
    return pulls


def latest_sweep_pulls(state_root: Path) -> dict[str, Pull]:
    """PRs by receipt id from the newest finished publication-sweep job."""
    newest: tuple[str, Mapping[str, Any]] | None = None
    for job in _job_records(state_root / "jobs"):
        spec = job.get("spec") or {}
        state = job.get("state") or {}
        if spec.get("operation") != "publication_sweep" or not state.get("terminal"):
            continue
        created = str(job.get("created_at") or "")
        if newest is None or created > newest[0]:
            newest = (created, job)
    if newest is None:
        return {}
    artifacts = newest[1].get("artifacts") or {}
    result_path = artifacts.get("result") if isinstance(artifacts, Mapping) else None
    if not isinstance(result_path, str):
        return {}
    try:
        value = json.loads(Path(result_path).read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    actions = value.get("actions") if isinstance(value, Mapping) else None
    return pulls_from_sweep_actions(actions if isinstance(actions, list) else [])


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
            {"number": facts.pull.number, "at_head": facts.pull.head == facts.head, "verdict": facts.pull.verdict, "findings": facts.pull.findings}
            if facts.pull
            else None
        ),
        "next": action.to_dict(),
    }


__all__ = [
    "Action",
    "LaneFacts",
    "Pull",
    "Receipt",
    "advance",
    "collect",
    "derived_checkout_id",
    "lane_view",
    "latest_sweep_pulls",
    "pulls_from_sweep_actions",
]
