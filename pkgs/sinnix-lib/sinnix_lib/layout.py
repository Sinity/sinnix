"""Authoritative root and capture layout shared with declarative configuration."""

import json
from importlib.resources import files
from pathlib import Path

MANIFEST = json.loads(files(__package__).joinpath("filesystem-layout.json").read_text())
ROOTS = MANIFEST["roots"]
OPTIONAL = {root: set(nodes) for root, nodes in MANIFEST["optional"].items()}
ACTIVITY_LANES = MANIFEST["activity_lanes"]


def capture_lane_path(root: Path | str, lane: str) -> Path:
    """Lane identity stays stable while its physical home follows the layout."""
    if not lane or "/" in lane or lane in {".", ".."}:
        raise ValueError("lane must be a single nonempty path component")
    return Path(root) / ACTIVITY_LANES.get(lane, lane)


def inventory_structure(root: str) -> str:
    """Generated structure, not an inspection or preservation claim."""
    rows = ["<!-- BEGIN GENERATED ROOT LAYOUT -->", "| Home | Purpose |", "| --- | --- |"]
    rows.extend(f"| `{name}/` | {purpose} |" for name, purpose in ROOTS[root].items())
    rows.append("<!-- END GENERATED ROOT LAYOUT -->")
    return "\n".join(rows)
