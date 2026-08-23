from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .capabilities import Capability, Principal
from .config import GatewayConfig
from sinnix_mcp.execution import ExecutionProfile, OwnerExecution, OwnerRoute


@dataclass(frozen=True)
class CaptureLane:
    """One queryable sinnix-capture lane declared by the runtime inventory."""

    name: str
    root: Path


def queryable_capture_lanes(runtime_inventory: Path) -> dict[str, CaptureLane]:
    """Discover collector-compatible lanes from the runtime inventory."""
    try:
        inventory = json.loads(runtime_inventory.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    captures = inventory.get("captures")
    if not isinstance(captures, list):
        return {}
    lanes: dict[str, CaptureLane] = {}
    for row in captures:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        path = row.get("path")
        if not isinstance(name, str) or not name or not isinstance(path, str):
            continue
        lane_path = Path(path)
        index_path = lane_path / f"{name}-index.jsonl"
        if (
            not lane_path.is_absolute()
            or not lane_path.is_dir()
            or not index_path.is_file()
        ):
            continue
        lanes[name] = CaptureLane(name=name, root=lane_path.parent)
    return lanes


class CaptureService:
    """Query declared sinnix-capture sidecar indexes without owning a lane registry."""

    def __init__(self, config: GatewayConfig, principal: Principal):
        self.config = config
        self.principal = principal
        self.execution = OwnerExecution()

    def _available_lanes(self) -> dict[str, CaptureLane]:
        return queryable_capture_lanes(self.config.runtime_inventory)

    def lanes_visible(self) -> dict[str, Any]:
        """List runtime-declared envelope lanes visible to this principal."""
        self.principal.require(Capability.CAPTURE_READ)
        available = sorted(self._available_lanes())
        visible = self.principal.filter_lanes(None, available)
        return {"lanes": visible, "total_queryable_lanes": len(available)}

    def query(
        self, lanes: list[str] | None = None, since: float = 0.0, limit: int = 100
    ) -> dict[str, Any]:
        available = self._available_lanes()
        effective_lanes = self.principal.filter_lanes(lanes, sorted(available))
        if not effective_lanes:
            return {"records": [], "lanes_queried": [], "truncated": False}

        lanes_by_root: dict[Path, list[str]] = defaultdict(list)
        for lane in effective_lanes:
            lanes_by_root[available[lane].root].append(lane)

        bounded_limit = max(0, min(limit, 1_000))
        records: list[dict[str, Any]] = []
        truncated = False
        sorted_roots = sorted(lanes_by_root.items(), key=lambda item: str(item[0]))
        for root, root_lanes in sorted_roots:
            command = [
                self.config.capture_command,
                "query",
                "--capture-root",
                str(root),
                "--since",
                str(since),
            ]
            for lane in root_lanes:
                command += ["--lane", lane]

            result = self.execution.run(
                command,
                ExecutionProfile(
                    route=OwnerRoute("capture-query"),
                    timeout_seconds=20,
                    max_stdout_bytes=self.config.max_result_bytes,
                ),
            )
            if result.failure_class is not None:
                failure_class = {
                    "command_timeout": "collector_timeout",
                    "command_unavailable:FileNotFoundError": "collector_unavailable",
                }.get(result.failure_class, "collector_failed")
                return {
                    "available": False,
                    "failure_class": failure_class,
                    "reason": result.stderr_excerpt()
                    or (
                        "sinnix-capture query is unavailable"
                        if failure_class == "collector_unavailable"
                        else "sinnix-capture query failed"
                    ),
                    "command": list(result.command),
                }

            try:
                payload = result.decode_json()
            except json.JSONDecodeError:
                return {
                    "available": False,
                    "failure_class": "unparseable_output",
                    "reason": "sinnix-capture query did not return valid JSON",
                }

            root_records = (
                payload.get("records", payload) if isinstance(payload, dict) else payload
            )
            if not isinstance(root_records, list):
                return {
                    "available": False,
                    "failure_class": "unparseable_output",
                    "reason": "sinnix-capture query did not return a record list",
                }
            for record in root_records:
                if len(records) >= bounded_limit:
                    truncated = True
                    break
                if isinstance(record, dict):
                    records.append(record)
            if truncated:
                break

        return {
            "records": records,
            "lanes_queried": effective_lanes,
            "truncated": truncated,
        }
