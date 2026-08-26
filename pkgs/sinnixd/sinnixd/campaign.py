"""Pure scheduling helpers for one ready-Beads packet campaign wave."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from .packets import (
    PacketConfig,
    SubprocessBdReader,
    compile_launch_snapshot,
    derived_workspace,
    runtime_dimensions,
)

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
    """Keep one compiler result per carrier group, in deterministic order."""
    by_group: dict[str, CampaignLane] = {}
    for lane in lanes:
        prior = by_group.get(lane.group)
        if prior is None:
            by_group[lane.group] = lane
        elif prior.bead_ids != lane.bead_ids:
            raise ValueError(f"carrier group compiled inconsistently: {lane.group}")
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
                    "a bead in this carrier group already has an active job",
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

    def run(
        self,
        project_id: str,
        *,
        limit: int | None = None,
        dry_run: bool = False,
        credential_profile: str = "subscription",
        timeout_seconds: int = 3_600,
    ) -> dict[str, Any]:
        project = self.projects.get(project_id)
        config = PacketConfig.load(project.root)
        reader = SubprocessBdReader(project.root)
        ready = sorted(
            (
                row
                for row in reader.ready()
                if isinstance(row.get("id"), str) and row.get("id")
            ),
            key=lambda row: str(row["id"]),
        )
        if limit is not None:
            if isinstance(limit, bool) or limit < 1:
                raise ValueError("campaign limit must be positive")
            ready = ready[:limit]
        lanes = []
        for row in ready:
            bead_id = str(row["id"])
            snapshot = compile_launch_snapshot(
                bead_id,
                project_root=project.root,
                project_id=project_id,
                reader=reader,
                config=config,
            )
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
        active_workspaces = {
            record.name
            for record in self.workspaces.store.records()
            if record.project_id == project_id
        }
        active_beads: set[str] = set()
        active_conflict_keys: set[str] = set()
        for record in self.jobs.store.list():
            if record.spec.project_id != project_id or record.state.get("terminal"):
                continue
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
        schedule = build_schedule(
            lanes,
            active_workspace_names=active_workspaces,
            active_bead_ids=active_beads,
            active_conflict_keys=active_conflict_keys,
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
            self.workspaces.create(
                project_id=project_id,
                name=str(payload["workspace_name"]),
                branch=str(payload["branch"]),
                base=None,
            )
            lane_checkout = self.workspaces.resolve_checkout(
                project_id, str(payload["workspace_name"])
            )
            response = self._job_contracts.start_agent(
                principal=principal,
                project_id=project_id,
                checkout_id=lane_checkout.checkout_id,
                prompt=str(payload["prompt"]),
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
                allow_failed_dependencies=True,
                reject_conflicts=True,
            )
            job_id = str(response["job_id"])
            self.jobs.spool_event(
                {
                    "kind": "campaign",
                    "transition": "node launched",
                    "wave_id": wave_id,
                    "group": payload["group"],
                    "job_id": job_id,
                }
            )
            return job_id

        generation = (
            "ready-"
            + hashlib.sha256(
                "\0".join(lane.group for lane in schedule.lanes).encode()
            ).hexdigest()[:32]
        )
        plan = self.plans.submit_external(
            {
                "project_id": project_id,
                "input_generation": generation,
                "checkout_id": "default",
                "nodes": [
                    {
                        "id": lane.group,
                        "depends_on": [
                            before
                            for before, after in schedule.edges
                            if after == lane.group
                        ],
                        "payload": dict(lane.payload),
                    }
                    for lane in schedule.lanes
                ],
            },
            launcher=launch,
            correlation_id=wave_id,
            principal="agent-control",
            operation="packet-lane",
        )
        result["plan"] = plan
        return result

    @property
    def _job_contracts(self) -> Any:
        from .contracts import TypedJobContracts

        return TypedJobContracts(self.projects, self.jobs, self.native_runner)
