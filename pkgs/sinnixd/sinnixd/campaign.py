"""Scheduling and dispatch for one ready-Beads packet campaign, one shot at a time."""

from __future__ import annotations

import json
import re
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping, Sequence

from .limits import MAX_AGENT_TIMEOUT_SECONDS
from .packets import (
    PacketConfig,
    PacketError,
    SubprocessBdReader,
    compile_launch_snapshot,
    derived_workspace,
    runtime_dimensions,
)

RESUME_PREAMBLE = (
    "RESUME NOTICE: this worktree already carries partial work for this packet "
    "from a lane that did not finish. Before anything else run `git status` and "
    "`git log --oneline origin/master..HEAD`; keep what is correct, discard what "
    "is not, then complete the packet as specified below and commit.\n\n"
)


def frontier_order(row: Mapping[str, Any]) -> tuple[int, str]:
    """P0 before P4, then id: a wave limit must spend itself on the most urgent work."""
    priority = row.get("priority")
    rank = (
        priority if isinstance(priority, int) and not isinstance(priority, bool) else 9
    )
    return rank, str(row.get("id", ""))


CLAIM_ACTOR = "campaign"


def claim_beads(
    root: Path, bead_ids: Sequence[str], *, run: Callable[..., Any] = subprocess.run
) -> list[str]:
    """Mark a launched lane's beads in_progress so no later wave relaunches them.

    A claimed bead leaves the ready frontier until the sweep closes it at
    merge; an interrupted lane's claim is released by the operator. Returns
    the beads whose claim failed; a failed claim is reported, not fatal.
    """
    failed: list[str] = []
    for bead_id in bead_ids:
        try:
            result = run(
                [
                    "bd",
                    "update",
                    bead_id,
                    "-s",
                    "in_progress",
                    "-a",
                    CLAIM_ACTOR,
                    "--actor",
                    CLAIM_ACTOR,
                ],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            failed.append(bead_id)
            continue
        if result.returncode != 0:
            failed.append(bead_id)
    return failed


def held_workspace_names(
    existing: Mapping[str, Any], held_checkouts: set[str] | frozenset[str]
) -> set[str]:
    """Workspaces an agent is still editing; every other leftover one is resumable."""
    return {
        name
        for name, record in existing.items()
        if getattr(record, "workspace_id", None) in held_checkouts
    }


if TYPE_CHECKING:
    from .jobs import GenericJobs
    from .project_plans import ProjectPlanExecutor
    from .projects import ProjectCatalog
    from .workspaces import GitWorkspaces


@dataclass(frozen=True)
class CampaignLane:
    """The compiler output needed by the wave scheduler."""

    group: str
    bead_ids: tuple[str, ...]
    conflict_keys: tuple[str, ...]
    workspace_name: str
    branch: str
    payload: Mapping[str, Any]


class WaveDrainedError(RuntimeError):
    """Every lane in a wave was deferred; the message names the last reason."""

    code = "wave-drained"


@dataclass(frozen=True)
class CampaignSkip:
    group: str
    bead_ids: tuple[str, ...]
    code: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "group": self.group,
            "beads": list(self.bead_ids),
            "code": self.code,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CampaignSchedule:
    lanes: tuple[CampaignLane, ...]
    edges: tuple[tuple[str, str], ...]
    skipped: tuple[CampaignSkip, ...]

    def node_ids(self) -> tuple[str, ...]:
        return tuple(lane.group for lane in self.lanes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "groups": [
                {
                    "group": lane.group,
                    "beads": list(lane.bead_ids),
                    "conflict_keys": list(lane.conflict_keys),
                    "workspace": lane.workspace_name,
                }
                for lane in self.lanes
            ],
            "edges": [list(edge) for edge in self.edges],
            "skipped": [skip.to_dict() for skip in self.skipped],
        }


def dedupe_lanes(lanes: Sequence[CampaignLane]) -> tuple[CampaignLane, ...]:
    """Keep one compiler result per dispatch group, in deterministic order."""
    by_group: dict[str, CampaignLane] = {}
    for lane in lanes:
        prior = by_group.get(lane.group)
        if prior is None:
            by_group[lane.group] = lane
        elif prior.bead_ids != lane.bead_ids:
            raise ValueError(f"dispatch group compiled inconsistently: {lane.group}")
    return tuple(by_group[group] for group in sorted(by_group))


def build_schedule(
    lanes: Sequence[CampaignLane],
    *,
    active_workspace_names: set[str] | frozenset[str] = frozenset(),
    active_bead_ids: set[str] | frozenset[str] = frozenset(),
    active_conflict_keys: set[str] | frozenset[str] = frozenset(),
    limit: int | None = None,
) -> CampaignSchedule:
    """Filter active lanes and serialize each shared conflict key.

    The first lane for a key is the deterministic predecessor of the next
    lane for that key.  A lane can therefore have several predecessors, while
    disjoint lanes remain roots.  Admission still owns host pool capacity.
    """
    if limit is not None and (isinstance(limit, bool) or limit < 1):
        raise ValueError("campaign limit must be positive")
    unique = dedupe_lanes(lanes)
    selected: list[CampaignLane] = []
    skipped: list[CampaignSkip] = []
    for lane in unique:
        if lane.workspace_name in active_workspace_names:
            skipped.append(
                CampaignSkip(
                    lane.group,
                    lane.bead_ids,
                    "active-workspace",
                    f"workspace {lane.workspace_name} already exists",
                )
            )
        elif set(lane.bead_ids).intersection(active_bead_ids):
            skipped.append(
                CampaignSkip(
                    lane.group,
                    lane.bead_ids,
                    "active-bead",
                    "a bead in this dispatch group already has an active job",
                )
            )
        elif set(lane.conflict_keys).intersection(active_conflict_keys):
            overlap = sorted(set(lane.conflict_keys).intersection(active_conflict_keys))
            skipped.append(
                CampaignSkip(
                    lane.group,
                    lane.bead_ids,
                    "conflict-key-overlap",
                    "conflict keys overlap a running lane: " + ", ".join(overlap),
                )
            )
        else:
            selected.append(lane)
    if limit is not None:
        selected = selected[:limit]

    edges: set[tuple[str, str]] = set()
    prior_by_key: dict[str, str] = {}
    for lane in selected:
        for key in lane.conflict_keys:
            prior = prior_by_key.get(key)
            if prior is not None and prior != lane.group:
                edges.add((prior, lane.group))
            prior_by_key[key] = lane.group
    return CampaignSchedule(tuple(selected), tuple(sorted(edges)), tuple(skipped))


def runnable_groups(
    schedule: CampaignSchedule, states: Mapping[str, Mapping[str, Any]]
) -> tuple[str, ...]:
    """Return nodes whose predecessor keys are freed by terminal outcomes.

    A failed predecessor is intentionally terminal and therefore frees its
    conflict key.  Its failure remains visible in ``states`` for the wave
    result; it is not converted into success.
    """
    predecessors: dict[str, set[str]] = {lane.group: set() for lane in schedule.lanes}
    for before, after in schedule.edges:
        predecessors[after].add(before)
    result = []
    for group in sorted(predecessors):
        if (
            isinstance(states.get(group), Mapping)
            and states[group].get("terminal") is True
        ):
            continue
        if all(
            isinstance(states.get(before), Mapping)
            and states[before].get("terminal") is True
            for before in predecessors[group]
        ):
            result.append(group)
    return tuple(result)


@dataclass
class CampaignRunner:
    """Compose the packet compiler, plan manifest, workspaces, and jobs."""

    projects: "ProjectCatalog"
    jobs: "GenericJobs"
    workspaces: "GitWorkspaces"
    plans: "ProjectPlanExecutor"
    native_runner: Any
    integrator_backend: str = "codex"
    # Workers default to luna, so the integrator is a sibling rather than the
    # same model judging its own family's output.
    integrator_model: str = "gpt-5.6-terra"
    integrator_effort: str = "high"
    _provisioning: str | None = None

    def run(
        self,
        project_id: str,
        *,
        limit: int | None = None,
        bead_ids: Sequence[str] | None = None,
        dry_run: bool = False,
        credential_profile: str = "subscription",
        # Packed dispatch groups carry several beads per lane; the agent
        # ceiling is the honest default, not the old one-hour slice that
        # forced serial relaunch rounds.
        timeout_seconds: int = MAX_AGENT_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        project = self.projects.get(project_id)
        config = PacketConfig.load(project.root)
        reader = SubprocessBdReader(project.root)
        requested = set(bead_ids or ())
        if bead_ids is not None and not requested:
            raise ValueError("campaign bead_ids must not be empty")
        ready = sorted(
            (
                row
                for row in reader.ready()
                if isinstance(row.get("id"), str)
                and row.get("id")
                and (bead_ids is None or row["id"] in requested)
            ),
            key=frontier_order,
        )
        if limit is not None and (isinstance(limit, bool) or limit < 1):
            raise ValueError("campaign limit must be positive")
        lanes = []
        uncompilable: list[CampaignSkip] = []
        for row in ready:
            bead_id = str(row["id"])
            try:
                snapshot = compile_launch_snapshot(
                    bead_id,
                    project_root=project.root,
                    project_id=project_id,
                    reader=reader,
                    config=config,
                )
            except PacketError as error:
                # One bead that cannot compile is one bead out of the wave, not
                # a wave that refuses to launch.
                uncompilable.append(
                    CampaignSkip(bead_id, (bead_id,), "uncompilable", str(error))
                )
                continue
            workspace_name, branch = derived_workspace(snapshot, config)
            lanes.append(
                CampaignLane(
                    snapshot.group,
                    snapshot.bead_ids,
                    snapshot.dimensions.conflict_keys,
                    workspace_name,
                    branch,
                    {
                        "prompt": snapshot.prompt,
                        "backend": snapshot.dimensions.backend,
                        "model": snapshot.dimensions.model,
                        "effort": snapshot.dimensions.effort,
                        "template_version": config.template_version,
                        "dimensions": snapshot.dimensions.to_dict(),
                        "runtime_dimensions": runtime_dimensions(snapshot.dimensions),
                        "group": snapshot.group,
                        "bead_ids": list(snapshot.bead_ids),
                        "workspace_name": workspace_name,
                        "branch": branch,
                    },
                )
            )
        existing_workspaces = {
            record.name: record
            for record in self.workspaces.store.records()
            if record.project_id == project_id
        }
        active_beads: set[str] = set()
        active_conflict_keys: set[str] = set()
        held_checkouts: set[str] = set()
        for record in self.jobs.store.active_records():
            if record.spec.project_id != project_id or record.state.get("terminal"):
                continue
            if record.spec.kind == "attested-agent" and isinstance(
                record.spec.checkout, Mapping
            ):
                held = record.spec.checkout.get("checkout_id")
                if isinstance(held, str) and held:
                    held_checkouts.add(held)
            parameters = record.spec.contract.get("parameters")
            campaign = (
                parameters.get("campaign") if isinstance(parameters, Mapping) else None
            )
            bead_ids = (
                campaign.get("bead_ids") if isinstance(campaign, Mapping) else None
            )
            if isinstance(bead_ids, list):
                active_beads.update(item for item in bead_ids if isinstance(item, str))
            if record.spec.kind == "attested-agent" and record.state.get("phase") in {
                "submitted",
                "running",
                "cancelling",
                "stopping",
                "launch-unknown",
                "observation-unknown",
                "outcome-unknown",
            }:
                active_conflict_keys.update(record.spec.exclusive_keys)
        # A leftover worktree is a lane's state, not a lock. Only a worktree an
        # agent is still editing excludes its packet; an unheld one is resumed
        # by the next lane, so a killed lane's partial work stays in play
        # instead of parking the bead until someone disposes the worktree.
        active_workspaces = held_workspace_names(existing_workspaces, held_checkouts)
        schedule = build_schedule(
            lanes,
            active_workspace_names=active_workspaces,
            active_bead_ids=active_beads,
            active_conflict_keys=active_conflict_keys,
        )
        if uncompilable:
            schedule = CampaignSchedule(
                schedule.lanes, schedule.edges, schedule.skipped + tuple(uncompilable)
            )
        if limit is not None and len(schedule.lanes) > limit:
            # The limit bounds what this wave launches. Applying it to ready
            # candidates instead would spend the whole budget on beads the
            # skip filters were about to drop, and launch nothing.
            bounded = build_schedule(
                schedule.lanes[:limit],
                active_workspace_names=active_workspaces,
                active_bead_ids=active_beads,
                active_conflict_keys=active_conflict_keys,
            )
            deferred = tuple(
                CampaignSkip(lane.group, lane.bead_ids, "limit", "wave limit reached")
                for lane in schedule.lanes[limit:]
            )
            schedule = CampaignSchedule(
                bounded.lanes, bounded.edges, schedule.skipped + deferred
            )
        wave_id = str(uuid.uuid4())
        result: dict[str, Any] = {
            "wave_id": wave_id,
            "project_id": project_id,
            "dry_run": dry_run,
            "schedule": schedule.to_dict(),
        }
        if dry_run:
            return result
        self.jobs.spool_event(
            {
                "kind": "campaign",
                "transition": "wave started",
                "wave_id": wave_id,
                "project": project_id,
            }
        )
        if not schedule.lanes:
            self.jobs.spool_event(
                {
                    "kind": "campaign",
                    "transition": "wave drained",
                    "wave_id": wave_id,
                    "project": project_id,
                }
            )
            result["state"] = {"phase": "drained", "terminal": True}
            return result

        def launch(
            *,
            node: Mapping[str, Any],
            checkout: Any,
            dependency_job_ids: Sequence[str],
            correlation_id: str,
            principal: str,
        ) -> str:
            payload = node["payload"]
            workspace_name = str(payload["workspace_name"])
            prompt = str(payload["prompt"])
            self._provisioning = str(payload["group"])
            if workspace_name in existing_workspaces:
                prompt = RESUME_PREAMBLE + prompt
            else:
                self.workspaces.create(
                    project_id=project_id,
                    name=workspace_name,
                    branch=str(payload["branch"]),
                    base=None,
                )
            lane_checkout = self.workspaces.resolve_checkout(project_id, workspace_name)
            response = self._job_contracts.start_agent(
                principal=principal,
                project_id=project_id,
                checkout_id=lane_checkout.checkout_id,
                prompt=prompt,
                backend=str(payload["backend"]),
                model=str(payload["model"]),
                effort=str(payload["effort"]),
                credential_profile=credential_profile,
                timeout_seconds=timeout_seconds,
                result="last-message",
                parameters={
                    "campaign": {
                        "wave_id": wave_id,
                        "group": payload["group"],
                        "bead_ids": payload["bead_ids"],
                    },
                    "template_version": payload["template_version"],
                    "dimensions": payload["dimensions"],
                },
                dimensions=payload["runtime_dimensions"],
                dependency_job_ids=dependency_job_ids,
                exclusive_keys=tuple(payload["dimensions"]["conflict_keys"]),
            )
            job_id = str(response["job_id"])
            unclaimed = claim_beads(project.root, [str(b) for b in payload["bead_ids"]])
            self.jobs.spool_event(
                {
                    "kind": "campaign",
                    "transition": "node launched",
                    "wave_id": wave_id,
                    "group": payload["group"],
                    "job_id": job_id,
                    "unclaimed_beads": unclaimed,
                }
            )
            return job_id

        plan = self._submit_tolerating_provisioning_failures(
            schedule,
            project_id,
            launch,
            wave_id,
        )
        result["plan"] = plan
        result["schedule"] = schedule.to_dict()
        return result

    def advance(self, project_id: str, *, dry_run: bool = False) -> dict[str, Any]:
        """Dispatch each managed lane's next action once, from fresh facts.

        ``dry_run`` plans and returns without any side effect: no job record,
        no queued task, no agent launch, no workspace mutation. Its lanes are
        reported under ``planned`` rather than ``dispatched``, because a plan
        that reported job ids would read exactly like work that ran.

        Reads exactly what ``campaign.status`` reads (``lane_facts.collect``
        and ``advance``), so a dispatched action and the reason a lane shows
        there never disagree. A lane whose action is not dispatchable
        (wait/idle/done/park/await-sweep) or whose dispatch this call refused
        is reported in ``skipped`` and left for the next invocation to
        decide again — nothing is recorded between calls.
        """
        from .lane_facts import DISPATCHABLE_ACTIONS, closed_bead_ids, collect
        from .lane_facts import advance as next_action
        from .worktrunk import WorktrunkError, worktrunk_list

        project = self.projects.get(project_id)
        state_root = self.jobs.store.root
        try:
            worktrees = worktrunk_list(project.root, full=True)
        except WorktrunkError:
            # Without wt the planner still advances every lane whose action
            # needs no PR; a lane that needs one is reported as skipped.
            worktrees = ()
        lanes = collect(
            project_id,
            state_root=state_root,
            worktrees=worktrees,
            closed_beads=closed_bead_ids(project.root),
        )
        dispatched: list[dict[str, Any]] = []
        planned: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for facts in lanes:
            action = next_action(facts)
            entry = {
                "workspace": facts.name,
                "action": action.kind,
                "reason": action.reason,
            }
            if action.kind not in DISPATCHABLE_ACTIONS:
                skipped.append(entry)
                continue
            if dry_run:
                planned.append(entry)
                continue
            job_id: str | None = None
            reason = action.reason
            try:
                job_id = self._dispatch(project_id, project, facts, action)
            except (ValueError, KeyError, OSError) as error:
                reason = str(error)
            if job_id is None:
                skipped.append({**entry, "reason": reason})
            else:
                dispatched.append(
                    {"workspace": facts.name, "action": action.kind, "job_id": job_id}
                )
        return {
            "project_id": project_id,
            "dry_run": dry_run,
            "dispatched": dispatched,
            "planned": planned,
            "skipped": skipped,
        }

    def _dispatch(
        self, project_id: str, project: Any, facts: Any, action: Any
    ) -> str | None:
        if action.kind == "verify":
            return self._dispatch_declared(
                project_id, project, facts, "verify_affected", {}
            )
        if action.kind == "harvest":
            verify_job = facts.verify_job[0] if facts.verify_job else ""
            parameters = {"affected_job": verify_job} if verify_job else {}
            return self._dispatch_declared(
                project_id, project, facts, "harvest", parameters
            )
        if action.kind == "publish":
            return self._dispatch_publish(project_id, project, facts)
        if action.kind == "retry":
            return self._dispatch_retry(facts)
        if action.kind == "integrate":
            return self._dispatch_integrate(project_id, project, facts)
        if action.kind == "rebase":
            return self._dispatch_rebase(project_id, facts)
        return self._dispatch_review_fix(project_id, project, facts)

    def _dispatch_declared(
        self,
        project_id: str,
        project: Any,
        facts: Any,
        operation: str,
        parameters: Mapping[str, Any],
    ) -> str | None:
        response = self.jobs.start_declared(
            project=project,
            operation=project.operation(operation),
            correlation_id=str(uuid.uuid4()),
            principal="agent-control",
            parameters=parameters,
            checkout=self.workspaces.resolve_checkout(project_id, facts.name),
        )
        job_id = response.get("job_id")
        return str(job_id) if job_id else None

    def _dispatch_publish(
        self, project_id: str, project: Any, facts: Any
    ) -> str | None:
        """Publish a lane whose scan is clean, using the text the lane wrote."""
        receipt = facts.receipt.packet_id if facts.receipt else ""
        if not receipt:
            return None
        worktree = Path("/realm/worktrees") / facts.name
        title = worktree / ".lane/title"
        body = worktree / ".lane/body.md"
        if not title.is_file() or not body.is_file():
            # The worker contract requires the lane to write its own
            # publication text; a lane that skipped it is left for the
            # operator, not published under text nobody wrote.
            return None
        parameters: dict[str, Any] = {
            "authorize": True,
            "receipt_ref": receipt.rsplit("/", 1)[-1],
            "title_file": str(title),
            "body_file": str(body),
        }
        if facts.verify_job and facts.verify_job[1] == "succeeded":
            parameters["affected_job"] = facts.verify_job[0]
        return self._dispatch_declared(
            project_id, project, facts, "harvest", parameters
        )

    def _dispatch_retry(self, facts: Any) -> str | None:
        if not facts.lane_job:
            return None
        response = self._job_contracts.retry_agent(job_id=facts.lane_job)
        job_id = response.get("job_id") or facts.lane_job
        return str(job_id)

    def _launch_agent(
        self, project_id: str, facts: Any, prompt: str, *, label: str
    ) -> str | None:
        checkout = self.workspaces.resolve_checkout(project_id, facts.name)
        response = self._job_contracts.start_agent(
            principal="agent-control",
            project_id=project_id,
            checkout_id=checkout.checkout_id,
            prompt=prompt,
            backend=self.integrator_backend,
            model=self.integrator_model,
            effort=self.integrator_effort,
            credential_profile="subscription",
            timeout_seconds=MAX_AGENT_TIMEOUT_SECONDS,
            result="last-message",
            coordinator_label=label,
        )
        job_id = response.get("job_id")
        return str(job_id) if job_id else None

    def _dispatch_integrate(
        self, project_id: str, project: Any, facts: Any
    ) -> str | None:
        packet = (
            self._receipt_payload(facts.receipt.packet_id) if facts.receipt else None
        )
        verified = (
            facts.verify_job[0]
            if facts.verify_job and facts.verify_job[1] == "succeeded"
            else ""
        )
        event = {
            "project": project_id,
            "packet": packet,
            "receipt_ref": facts.receipt.packet_id if facts.receipt else "",
            "affected_job": verified,
        }
        return self._launch_agent(
            project_id,
            facts,
            self._integration_prompt(project.root, event, facts.name),
            label="integrator",
        )

    def _dispatch_rebase(self, project_id: str, facts: Any) -> str | None:
        refusal = (
            "rebasing onto origin/master conflicts"
            if facts.pull is not None
            else "its branch predates master's verification harness, so affected selection refuses"
        )
        prompt = (
            f"You are an integrator in /realm/worktrees/{facts.name}. Publication of this "
            f"lane was refused: {refusal}. Fetch origin, rebase "
            "the branch onto origin/master, resolve every conflict preserving the lane's "
            "intent and master's, run the project's quick gate (devtools verify --quick) "
            "and affected verification (devtools verify), fix what they surface, commit, and "
            "stop. Do not publish; the harvest runs again on your commit. Report the "
            "machine trailer (LANE-BRANCH/COMMIT/QUICK/CLASSIFICATION).\n"
        )
        return self._launch_agent(project_id, facts, prompt, label="rebase")

    def _dispatch_review_fix(
        self, project_id: str, project: Any, facts: Any
    ) -> str | None:
        repo = self._repo_slug(project.root)
        pull = facts.pull
        if not repo or pull is None:
            return None
        return self._launch_agent(
            project_id,
            facts,
            self._review_fix_prompt(repo, str(pull.number), facts.name),
            label="review-fix",
        )

    @staticmethod
    def _integration_prompt(
        root: Path, event: Mapping[str, Any], workspace: str
    ) -> str:
        contract = (
            root / "dots/_ai/skills/orchestrate/references/integrator-contract.md"
        )
        try:
            body = contract.read_text()
        except OSError:
            body = ""
        packet = event.get("packet")
        summary = (
            json.dumps(packet, indent=1, sort_keys=True)[:20_000]
            if isinstance(packet, Mapping)
            else ""
        )
        receipt = str(event.get("receipt_ref") or "")
        return (
            "# Integration packet\n\n"
            f"project: {event.get('project')}\n"
            f"workspace: {workspace}\n"
            f"worktree: /realm/worktrees/{workspace}\n"
            f"receipt_ref: {receipt.rsplit('/', 1)[-1]}\n"
            f"affected_job: {event.get('affected_job') or ''}\n\n"
            "## Review receipt\n\n"
            f"```json\n{summary}\n```\n\n"
            f"## Operating rules\n\n{body}\n"
        )

    @staticmethod
    def _review_fix_prompt(repo: str, pr: str, workspace: str) -> str:
        return (
            f"You are a review-fix lane in /realm/worktrees/{workspace} "
            f"(open PR #{pr} on {repo}). The hosted reviewer requested "
            "changes. Read the findings with: "
            f"gh api repos/{repo}/pulls/{pr}/comments (the open ones are the "
            "top-level comments by chatgpt-codex-connector[bot] from its latest "
            "review round, newer than its last +1 reaction; earlier rounds were "
            "superseded). For each: confirm against the code and fix with a focused "
            "test, or refute with concrete evidence. Post a threaded reply on every "
            f"open finding (gh api repos/{repo}/pulls/{pr}/comments/<comment_id>/replies "
            "-f body='...'), disposition style: \"Fixed in <sha> - one line.\" or "
            '"Refuted: <evidence>." with "[review-fix lane]" appended. Verify with '
            "the project's devtools (devtools test <selection>; devtools verify "
            "--quick); rebase onto origin/master; push the branch. Then request "
            f're-review by commenting exactly "@codex review" on the PR '
            f'(gh pr comment {pr} --repo {repo} --body "@codex review"). Update '
            ".lane/body.md's disposition table (uncommitted). Report per-finding "
            "dispositions with the machine trailer "
            "(LANE-BRANCH/COMMIT/QUICK/CLASSIFICATION).\n"
        )

    @staticmethod
    def _repo_slug(root: Path) -> str:
        try:
            url = subprocess.run(
                ["git", "-C", str(root), "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
        match = re.search(r"github\.com[:/]([^/]+/[^/.]+)", url)
        return match.group(1) if match else ""

    @staticmethod
    def _receipt_payload(receipt: str) -> Mapping[str, Any] | None:
        """The harvest receipt an integrate action names.

        The lane fact carries the packet id only; the receipt file holds what
        the integrator reads (scan flags, lane trailer, verification evidence).
        """
        packet_root = Path.home() / ".local/state/sinnixd/harvest-packets"
        name = receipt.rsplit("/", 1)[-1]
        if not re.fullmatch(r"harvest-[0-9a-f]{32}", name):
            return None
        try:
            payload = json.loads((packet_root / f"{name}.json").read_text())
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, Mapping) else None

    def _submit_tolerating_provisioning_failures(
        self,
        schedule: CampaignSchedule,
        project_id: str,
        launch: Any,
        wave_id: str,
    ) -> dict[str, Any]:
        """Drop a lane whose workspace fails to provision, then submit the rest.

        A workspace that will not provision costs one lane, not the wave.
        """
        self._wave_id = wave_id
        from .workspaces import WorkspaceError

        lanes = list(schedule.lanes)
        last_deferral: str | None = None
        while lanes:
            try:
                return self._submit_plan(lanes, schedule, project_id, launch)
            except WorkspaceError as error:
                # The lane being provisioned is the one that raised.
                failed = self._provisioning
                remaining = [lane for lane in lanes if lane.group != failed]
                if failed is None or len(remaining) == len(lanes):
                    raise
                self.jobs.spool_event(
                    {
                        "kind": "campaign",
                        "transition": "lane deferred",
                        "wave_id": wave_id,
                        "project": project_id,
                        "group": failed,
                        "reason": str(error)[:400],
                    }
                )
                last_deferral = f"{failed}: {error}"
                lanes = remaining
        # Every lane was deferred. Reporting that as a conflict names the wrong
        # cause when the real one was provisioning, so the last reason is what
        # gets raised.
        raise WaveDrainedError(last_deferral or "every lane in this wave was deferred")

    def _submit_plan(
        self,
        lanes: list[CampaignLane],
        schedule: CampaignSchedule,
        project_id: str,
        launch: Any,
    ) -> dict[str, Any]:
        return self.plans.submit_external(
            {
                "project_id": project_id,
                "checkout_id": "default",
                "nodes": [
                    {
                        "id": lane.group,
                        "depends_on": [
                            before
                            for before, after in schedule.edges
                            if after == lane.group
                            and any(other.group == before for other in lanes)
                        ],
                        "payload": dict(lane.payload),
                    }
                    for lane in lanes
                ],
            },
            launcher=launch,
            correlation_id=self._wave_id,
            principal="agent-control",
            operation="packet-lane",
        )

    @property
    def _job_contracts(self) -> Any:
        from .contracts import TypedJobContracts

        return TypedJobContracts(self.projects, self.jobs, self.native_runner)
