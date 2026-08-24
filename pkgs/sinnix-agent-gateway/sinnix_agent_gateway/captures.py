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
    """One runtime-declared capture lane and its exact native contract."""

    name: str
    path: Path
    native_contract: str
    root: Path | None = None
    native_lane: str | None = None


def queryable_capture_lanes(runtime_inventory: Path) -> dict[str, CaptureLane]:
    """Derive capture query contracts from every declared runtime lane.

    The inventory is the capture authority.  Every valid declared path is
    visible, including direct-file lanes that have no ``sinnix-capture``
    reader.  Sidecar capability is discovered only to choose the established
    reader, never to decide whether a runtime declaration exists.  Its native
    lane is the path basename, not the inventory's globally unique display
    name: a declaration such as ``peripherals-logitech`` owns the native
    ``peripherals/logitech`` sidecar.
    """
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
        if not lane_path.is_absolute():
            continue
        native_lane = lane_path.name
        index_path = lane_path / f"{native_lane}-index.jsonl"
        if index_path.is_file():
            lanes[name] = CaptureLane(
                name=name,
                path=lane_path,
                native_contract="sinnix-capture-v1-sidecar",
                root=lane_path.parent,
                native_lane=native_lane,
            )
        else:
            lanes[name] = CaptureLane(
                name=name,
                path=lane_path,
                native_contract="runtime-declared-path",
            )
    return lanes


class CaptureService:
    """Query declared native capture lanes without owning a lane registry."""

    def __init__(self, config: GatewayConfig, principal: Principal):
        self.config = config
        self.principal = principal
        self.execution = OwnerExecution()

    def _available_lanes(self) -> dict[str, CaptureLane]:
        return queryable_capture_lanes(self.config.runtime_inventory)

    def lanes_visible(self) -> dict[str, Any]:
        """List runtime-declared native lane contracts visible to this principal."""
        self.principal.require(Capability.CAPTURE_READ)
        lanes = self._available_lanes()
        available = sorted(lanes)
        visible = self.principal.filter_lanes(None, available)
        return {
            "lanes": [
                {
                    "name": name,
                    "ref": f"sinnix://captures/{name}",
                    "path": str(lanes[name].path),
                    "native_contract": lanes[name].native_contract,
                    **(
                        {
                            "capture_root": str(lanes[name].root),
                            "native_lane": lanes[name].native_lane,
                        }
                        if lanes[name].root is not None
                        else {}
                    ),
                }
                for name in visible
            ],
            "total_declared_lanes": len(available),
        }

    def lane(self, name: str) -> dict[str, Any]:
        """Return one canonical lane's inventory-derived native contract."""
        self.principal.require_lane(name)
        try:
            lane = self._available_lanes()[name]
        except KeyError as exc:
            raise ValueError("capture lane is not declared by runtime inventory") from exc
        return {
            "ref": f"sinnix://captures/{name}",
            "name": lane.name,
            "path": str(lane.path),
            "native_contract": lane.native_contract,
            **(
                {"capture_root": str(lane.root), "native_lane": lane.native_lane}
                if lane.root is not None
                else {}
            ),
        }

    def query(
        self, lanes: list[str] | None = None, since: float = 0.0, limit: int = 100
    ) -> dict[str, Any]:
        available = self._available_lanes()
        effective_lanes = self.principal.filter_lanes(lanes, sorted(available))
        if not effective_lanes:
            return {"records": [], "lanes_queried": [], "truncated": False}

        non_sidecar = [
            name for name in effective_lanes
            if available[name].native_contract != "sinnix-capture-v1-sidecar"
        ]
        if non_sidecar:
            return {
                "available": False,
                "failure_class": "native_contract_unavailable",
                "reason": "selected runtime capture paths have no admitted query reader",
                "lanes": non_sidecar,
            }

        lanes_by_root: dict[Path, list[CaptureLane]] = defaultdict(list)
        for lane in effective_lanes:
            contract = available[lane]
            assert contract.root is not None and contract.native_lane is not None
            lanes_by_root[contract.root].append(contract)

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
                assert lane.native_lane is not None
                command += ["--lane", lane.native_lane]

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
