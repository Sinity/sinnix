"""Pure scheduling helpers for one ready-Beads packet campaign wave."""

from __future__ import annotations

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
    merge or the reactor releases it when the lane is interrupted. Returns
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
                reject_conflicts=True,
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

        plan = self._submit_tolerating_conflicts(
            schedule,
            project_id,
            launch,
            wave_id,
        )
        result["plan"] = plan
        result["schedule"] = schedule.to_dict()
        return result

    def _submit_tolerating_conflicts(
        self,
        schedule: CampaignSchedule,
        project_id: str,
        launch: Any,
        wave_id: str,
    ) -> dict[str, Any]:
        self._wave_id = wave_id
        """Drop a lane an admission race refuses, then submit the rest.

        The reactor refills on its own schedule, so no pre-check can be exact:
        a key can go active between scheduling and launching. Refusing the
        whole wave for one raced lane would make concurrent scheduling useless.
        """
        from .jobs import AdmissionConflictError
        from .workspaces import WorkspaceError

        lanes = list(schedule.lanes)
        last_deferral: str | None = None
        while lanes:
            try:
                return self._submit_plan(lanes, schedule, project_id, launch)
            except WorkspaceError as error:
                # A workspace that will not provision costs one lane, not the
                # wave. The lane being provisioned is the one that raised.
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
                continue
            except AdmissionConflictError as error:
                blocked = set(error.conflicts)
                remaining = [
                    lane
                    for lane in lanes
                    if not blocked.intersection(lane.conflict_keys)
                ]
                if len(remaining) == len(lanes):
                    raise
                self.jobs.spool_event(
                    {
                        "kind": "campaign",
                        "transition": "lane deferred",
                        "wave_id": wave_id,
                        "project": project_id,
                        "reason": str(error),
                    }
                )
                last_deferral = str(error)
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
