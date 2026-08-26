"""Build a durable, model-free dispatch plan from the current Beads frontier."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from .campaign import CampaignLane, build_schedule
from .packets import (
    PacketConfig,
    SubprocessBdReader,
    compile_launch_snapshot,
    derived_workspace,
)

PLAN_SCHEMA_VERSION = 1


def _orbit(keys: tuple[str, ...]) -> str:
    """Return the stable subsystem orbit used to keep related work together."""
    return sorted(key.split(":", 1)[0] for key in keys if ":" in key)[0] if keys else "unclassified"


def _judgment_gates(snapshot: Any) -> list[str]:
    gates: list[str] = []
    if snapshot.atlas_refs:
        gates.append("atlas-context")
    if snapshot.dimensions.inferred_conflict_keys:
        gates.append("inferred-conflicts")
    if not snapshot.dimensions.verification_commands:
        gates.append("missing-verification")
    return gates


def build_dispatch_plan(
    projects: Mapping[str, Path], *, limit: int | None = None
) -> dict[str, Any]:
    """Compile ready beads without launching jobs or mutating task state."""
    if limit is not None and (isinstance(limit, bool) or limit < 1):
        raise ValueError("planner limit must be positive")
    lanes: list[CampaignLane] = []
    metadata: dict[str, tuple[Any, str]] = {}
    for project_id, root in sorted(projects.items()):
        config = PacketConfig.load(root)
        reader = SubprocessBdReader(root)
        ready = sorted(
            (row for row in reader.ready() if isinstance(row.get("id"), str) and row["id"]),
            key=lambda row: str(row["id"]),
        )
        for row in ready:
            bead_id = str(row["id"])
            snapshot = compile_launch_snapshot(
                bead_id, project_root=root, project_id=project_id, reader=reader, config=config
            )
            workspace, branch = derived_workspace(snapshot, config)
            lane = CampaignLane(
                snapshot.group,
                snapshot.bead_ids,
                snapshot.dimensions.conflict_keys,
                workspace,
                branch,
                {"project_id": project_id, "bead_ids": list(snapshot.bead_ids)},
            )
            lanes.append(lane)
            metadata[lane.group] = (snapshot, project_id)
    schedule = build_schedule(lanes, limit=limit)
    groups = []
    for lane in schedule.lanes:
        snapshot, project_id = metadata[lane.group]
        groups.append(
            {
                "order": len(groups),
                "project_id": project_id,
                "group": lane.group,
                "beads": list(lane.bead_ids),
                "workspace": lane.workspace_name,
                "branch": lane.branch,
                "orbit": _orbit(lane.conflict_keys),
                "conflict_keys": list(lane.conflict_keys),
                "judgment_gate": _judgment_gates(snapshot),
            }
        )
    generation = hashlib.sha256(
        json.dumps(groups, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:32]
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "generation": generation,
        "groups": groups,
        "skipped": [item.to_dict() for item in schedule.skipped],
        "edges": [list(edge) for edge in schedule.edges],
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="sinnixd-planner")
    result.add_argument("--project-root", action="append", required=True, metavar="PROJECT=/ABSOLUTE/PATH")
    result.add_argument("--output", type=Path, default=Path("/realm/tmp/work/dispatch-plan.json"))
    result.add_argument("--limit", type=int)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    projects: dict[str, Path] = {}
    for value in args.project_root:
        name, separator, path = value.partition("=")
        if not separator or not name or not Path(path).is_absolute():
            parser().error("project root must be PROJECT=/absolute/path")
        projects[name] = Path(path)
    plan = build_dispatch_plan(projects, limit=args.limit)
    args.output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = args.output.with_name(f".{args.output.name}.tmp")
    temporary.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    temporary.replace(args.output)
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
